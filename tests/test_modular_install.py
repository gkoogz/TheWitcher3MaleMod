import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import install_modular_native as installer


class ModularInstallTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.game, self.preview = self.root/'game', self.root/'preview'
        self.native = self.game/installer.PREFIX
        self.candidate = self.preview/installer.PREFIX
        self.native.mkdir(parents=True)
        self.candidate.mkdir(parents=True)
        (self.root/'local').mkdir()
        names = ['malemod_witcher.dll', 'surface_worker.exe', 'geralt.render',
                 'geralt.bindings', 'malemod-runtime.profile']
        for name in names:
            (self.native/name).write_bytes(name.encode())
            shutil.copy2(self.native/name, self.candidate/name)
        self.old = dict(game=str(self.game), files=[
            dict(path=installer.PREFIX+n, sha256=installer.digest(self.native/n)) for n in names])
        self.receipt = self.root/'local/native-installation.json'
        self.receipt.write_text(json.dumps(self.old))
        (self.candidate/'malemod_witcher.dll').write_bytes(b'new tested DLL')
        artifact = lambda n, data: (self.candidate/n).write_bytes(installer.ARTIFACTS[n]+data)
        artifact('geralt.modular', b'coupled geometry')
        geometry = installer.digest(self.candidate/'geralt.modular')
        artifact('geralt.modular-native', (geometry+installer.digest(self.candidate/'geralt.render')).encode())
        artifact('geralt.modular-dynamic', geometry.encode())
        artifact('geralt.modular-transfer', geometry.encode())
        artifact('geralt.modular-materials', (geometry+
            installer.digest(self.candidate/'geralt.modular-dynamic')+
            installer.digest(self.candidate/'geralt.modular-native')).encode())
        for name in installer.ARTIFACTS:
            (self.candidate/(name+'.sha256')).write_text(installer.digest(self.candidate/name)+'\n')
        self.manifest = dict(files=[dict(path=installer.PREFIX+p.name, sha256=installer.digest(p))
                                   for p in self.candidate.iterdir()])
        self.proof = dict(nativeDLLSHA256=installer.digest(self.candidate/'malemod_witcher.dll'),
                          sharedSourceRevision='0'*40)
        self.proof_file = self.root/'proof.json'
        self.proof_file.write_text('{}')
        self.manifest_file = self.root/'preview.json'
        self.manifest_file.write_text('{}')
        self.patches = [patch.object(installer, 'ROOT', self.root),
            patch.object(installer, 'load_preview', return_value=(self.preview, self.manifest)),
            patch.object(installer, 'validate_gate', return_value=self.proof),
            patch.object(installer, 'verify_native_compatibility'),
            patch.object(installer.subprocess, 'run', return_value=SimpleNamespace(stdout='')),
            patch.object(Path, 'home', return_value=self.root)]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def install(self, **kwargs):
        return installer.install_modular_native(dict(game=self.game), self.manifest_file,
                                                 self.proof_file, **kwargs)

    def test_validation_does_not_write_and_install_has_exact_rollback(self):
        before = self.receipt.read_bytes()
        self.assertTrue(self.install(validate_only=True)['validated'])
        self.assertEqual(before, self.receipt.read_bytes())
        result = self.install()
        for row in self.old['files']:
            self.assertEqual(installer.digest(Path(result['backup'])/row['path']), row['sha256'])
        updated = json.loads(self.receipt.read_text())
        for row in updated['files']:
            self.assertEqual(installer.digest(self.game/row['path']), row['sha256'])

    def test_unmanaged_artifact_is_preserved(self):
        path = self.native/'geralt.modular'
        path.write_bytes(b'user file')
        with self.assertRaisesRegex(ValueError, 'unmanaged'):
            self.install()
        self.assertEqual(path.read_bytes(), b'user file')

    def prepare_worker_change(self):
        before = b'MMRUN001'+b'a'*40+installer.digest(self.native/'surface_worker.exe').encode()+b'b'*64+b'calibration'
        (self.native/'malemod-runtime.profile').write_bytes(before)
        (self.candidate/'surface_worker.exe').write_bytes(b'ordered worker')
        after = before[:48]+installer.digest(self.candidate/'surface_worker.exe').encode()+before[112:]
        (self.candidate/'malemod-runtime.profile').write_bytes(after)
        for row in self.old['files']:
            row['sha256'] = installer.digest(self.game/row['path'])
        self.receipt.write_text(json.dumps(self.old))
        self.refresh_manifest()
        self.proof['workerAdoption'] = dict(path=str(self.root/'worker-proof.json'), sha256='bound')

    def refresh_manifest(self):
        self.manifest['files'] = [dict(path=installer.PREFIX+p.name,sha256=installer.digest(p))
                                  for p in self.candidate.iterdir()]

    def test_worker_adoption_replaces_only_profile_worker_digest(self):
        self.prepare_worker_change()
        with patch('ordered_worker_adoption.validate') as validate:
            result = self.install(validate_only=True)
        self.assertIn(installer.PREFIX+'surface_worker.exe',result['replacements'])
        self.assertIn(installer.PREFIX+'malemod-runtime.profile',result['replacements'])
        self.assertEqual(validate.call_args.args[2],(self.native/'surface_worker.exe').resolve())

    def test_worker_adoption_cannot_change_calibration(self):
        self.prepare_worker_change()
        path = self.candidate/'malemod-runtime.profile'
        path.write_bytes(path.read_bytes()+b'changed calibration')
        self.refresh_manifest()
        with patch('ordered_worker_adoption.validate'):
            with self.assertRaisesRegex(ValueError,'calibration'):
                self.install(validate_only=True)

    def test_worker_change_requires_explicit_adoption(self):
        self.prepare_worker_change()
        del self.proof['workerAdoption']
        with self.assertRaisesRegex(ValueError,'Unreviewed numerical'):
            self.install(validate_only=True)

    def test_copy_failure_restores_old_dll_and_receipt(self):
        copy = shutil.copy2
        before = self.receipt.read_bytes()
        def fail(source, destination, *a, **kw):
            if Path(source) == self.candidate/'geralt.modular':
                raise OSError('simulated disk failure')
            return copy(source, destination, *a, **kw)
        with patch.object(installer.shutil, 'copy2', side_effect=fail):
            with self.assertRaisesRegex(OSError, 'disk failure'):
                self.install()
        self.assertEqual(before, self.receipt.read_bytes())
        self.assertFalse((self.native/'geralt.modular').exists())
        for row in self.old['files']:
            self.assertEqual(installer.digest(self.game/row['path']), row['sha256'])


class ModularAcceptanceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        names = ['malemod_witcher.dll', 'surface_worker.exe', 'geralt.render',
                 'geralt.bindings', 'malemod-runtime.profile'] + list(installer.ARTIFACTS)
        names += [name+'.sha256' for name in installer.ARTIFACTS]
        self.bundle = {installer.PREFIX+name: name for name in names}
        self.preview = self.root/'preview.json'
        self.write(self.preview, {'files': [dict(path=p, sha256=h) for p, h in self.bundle.items()]})
        self.source = self.root/'source.json'
        self.write(self.source, dict(schema='malemod.modular-build-source/1',
                   sharedSourceRevision='a'*40, coupledArtifacts=self.bundle))
        self.evidence = []
        sessions = []
        self.traces = []
        self.transactions = []
        for index, scene in enumerate(['grey', 'campaign']):
            directory = self.root/scene
            directory.mkdir()
            trace = directory/('verification-'+str(index)+'.jsonl')
            self.write(trace, dict(stage=600, modular=True, bodyResourceMask=3,
                                  renderFlags=0, modularCompletedLODMask=15))
            receipt = directory/'receipt.json'
            transaction=directory/'saves.json'
            self.write(transaction,dict(schema='malemod.private-save-transaction/1',
                files=[dict(name='save.sav',sha256='saved')],originalsVerified=1,finishedUnixSeconds=123))
            self.transactions.append(transaction)
            prefix='iteration' if scene=='grey' else 'campaign'
            self.write(receipt, dict(closed=True, audioRestored=True,
                moduleSHA256='malemod_witcher.dll', modulePath=str(directory/'malemod_witcher.dll'),
                observations=dict(physicalInputUsed=False, processID=index),
                nativePreview=str(self.preview),
                nativePreviewSHA256=installer.digest(self.preview),
                **{prefix+'SaveOriginalsVerified':1,prefix+'SaveTransaction':str(transaction)}))
            self.evidence.extend([receipt, trace])
            self.traces.append(trace)
            sessions.append(dict(receipt=str(receipt), scene=scene, stages=[600]))
        self.evidence.extend(self.transactions)
        self.proof = dict(schema='malemod.modular-native-acceptance/1',
            previewSHA256=installer.digest(self.preview), nativeDLLSHA256='malemod_witcher.dll',
            sharedSourceRevision='a'*40, sourceManifest=str(self.source),
            sourceManifestSHA256=installer.digest(self.source), sessions=sessions,
            gate=dict.fromkeys(['originalPelvis', 'collarTopology', 'nativeAppearance',
                'independentMotion', 'shapeControls', 'supportedLODs', 'campaign'], True))
        self.proof_path = self.root/'proof.json'
        self.loader = patch.object(installer, 'load_preview', side_effect=
            lambda path, *args, **kwargs: (self.root, installer.read_json(Path(path))))
        self.loader.start()

    def write(self, path, value):
        path.write_text(json.dumps(value)+'\n')

    def validate(self):
        self.proof['evidence'] = [dict(path=str(p), sha256=installer.digest(p)) for p in self.evidence]
        self.write(self.proof_path, self.proof)
        return installer.validate_gate(self.proof_path, self.preview)

    def tearDown(self):
        self.loader.stop()
        self.temp.cleanup()

    def test_complete_bound_candidate(self):
        self.assertEqual(self.validate()['sharedSourceRevision'], 'a'*40)

    def test_lod_assertion_does_not_replace_actual_gpu_evidence(self):
        for path in self.traces:
            data=installer.read_json(path);data['modularCompletedLODMask']=5;self.write(path,data)
        with self.assertRaisesRegex(ValueError, 'both native LODs'):
            self.validate()

    def test_campaign_save_restoration_must_match_transaction(self):
        path=self.transactions[1];data=installer.read_json(path)
        data['originalsVerified']=0;self.write(path,data)
        with self.assertRaisesRegex(ValueError, 'save restoration is unverified'):
            self.validate()

    def test_same_dll_with_different_materials_is_rejected(self):
        other = self.root/'other-preview.json'
        manifest=installer.read_json(self.preview)
        for row in manifest['files']:
            if row['path'].endswith('geralt.modular-materials'):row['sha256']='different materials'
        self.write(other,manifest)
        path=self.evidence[2];receipt=installer.read_json(path)
        receipt.update(nativePreview=str(other), nativePreviewSHA256=installer.digest(other))
        self.write(path,receipt)
        with self.assertRaisesRegex(ValueError, 'different coupled artifacts'):
            self.validate()

    def test_empty_stage_claim_is_rejected(self):
        self.proof['sessions'][0]['stages']=[]
        with self.assertRaisesRegex(ValueError, 'nonempty and unique'):
            self.validate()

    def test_source_provenance_cannot_name_a_different_bundle(self):
        source=installer.read_json(self.source);source['coupledArtifacts']={}
        self.write(self.source,source);self.proof['sourceManifestSHA256']=installer.digest(self.source)
        with self.assertRaisesRegex(ValueError, 'different runtime artifacts'):
            self.validate()


if __name__ == '__main__':
    unittest.main()
