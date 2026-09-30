import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('adapter', Path(__file__).resolve().parents[1] / 'tools/mod.py')
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


class BuildTests(unittest.TestCase):
    def test_attachment_build_requires_matching_pin_and_unchanged_evidence(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(adapter,'ROOT',Path(temp)), patch.object(adapter,'base_checkout',return_value={'commit':'current'}):
            root=Path(temp);asset=root/'generated/mesh.w2mesh';asset.parent.mkdir();asset.write_bytes(b'verified native mesh')
            profile=root/'characters/geralt-attachment.json';profile.parent.mkdir();profile.write_text('{}')
            adapter.write_json(root/'generated/fit.json',{'baseCommit':'current','profileSHA256':adapter.digest(profile)})
            record={'baseCommit':'current','nativeVerified':True,'fitReport':'generated/fit.json','files':[{'path':'generated/mesh.w2mesh','sha256':adapter.digest(asset)}]}
            adapter.write_json(root/'generated/attachment.json',record)
            adapter.validate_attachment({},'generated/attachment.json')
            asset.write_bytes(b'changed')
            with self.assertRaises(RuntimeError):adapter.validate_attachment({},'generated/attachment.json')
            record['baseCommit']='old';adapter.write_json(root/'generated/attachment.json',record)
            with self.assertRaises(RuntimeError):adapter.validate_attachment({},'generated/attachment.json')

    def test_override_recipe_rejects_changed_stock_and_existing_edits(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(adapter, 'ROOT', Path(temp)):
            root = Path(temp)
            source = root / 'redkit/r4data/items/bare.w2ent'
            source.parent.mkdir(parents=True)
            data = b'CR2W fixture characters\\bare.w2mesh'
            source.write_bytes(data)
            recipe = {'feature': 'appearance.bare-body', 'overrides': [{'sourceLayer': 'redkit',
                      'source': 'items/bare.w2ent', 'sourceSHA256': hashlib.sha256(data).hexdigest(),
                      'destination': 'items/underwear.w2ent', 'expectedMesh': 'characters/bare.w2mesh',
                      'excludedMesh': 'characters/boxers.w2mesh'}]}
            cfg = {'redkit': root / 'redkit', 'depot': root / 'depot'}
            adapter.prepare_overrides(cfg, recipe)
            output = root / 'generated/workspace/items/underwear.w2ent'
            self.assertEqual(output.read_bytes(), data)
            source.write_bytes(b'changed SDK source')
            with self.assertRaises(RuntimeError):
                adapter.prepare_overrides(cfg, recipe)
            self.assertEqual(output.read_bytes(), data)
            source.write_bytes(data); output.write_bytes(b'local sculpt')
            with self.assertRaises(RuntimeError):
                adapter.prepare_overrides(cfg, recipe)
            self.assertEqual(output.read_bytes(), b'local sculpt')

    def test_install_refuses_overwrite_and_uninstall_preserves_owned_files(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(adapter, 'ROOT', Path(temp)):
            root = Path(temp).resolve()
            game = root / 'game'; game.mkdir()
            package = root / 'publish/fixture'
            resource = package / 'Mods/modMaleMod/content/bundles/body.bundle'
            resource.parent.mkdir(parents=True); resource.write_bytes(b'bundle fixture')
            manifest = {'project': 'modMaleMod', 'version': 'test', 'baseCommit': 'pinned',
                        'gameplayTested': False, 'files': [{'path': resource.relative_to(package).as_posix(),
                        'sha256': adapter.digest(resource), 'bytes': resource.stat().st_size}]}
            adapter.write_json(package / 'build-manifest.json', manifest)
            cfg = {'game': game}
            adapter.install_package(cfg, package)
            installed = game / 'Mods/modMaleMod'
            with self.assertRaises(RuntimeError):
                adapter.install_package(cfg, package)
            extra = installed / 'user-added.txt'; extra.write_text('preserve this')
            with self.assertRaises(RuntimeError):
                adapter.uninstall_package(cfg)
            self.assertTrue(extra.exists())
            extra.unlink()
            adapter.uninstall_package(cfg)
            self.assertFalse(installed.exists())
            receipt = adapter.read_json(root / 'local/installation.json')
            backup = Path(receipt['uninstalledTo']) / 'content/bundles/body.bundle'
            self.assertEqual(backup.read_bytes(), b'bundle fixture')

    def test_empty_cache_requires_native_evidence_for_every_input(self):
        self.assertTrue(adapter.empty_cache_expected('textures', 'Found 0 files to process'))
        self.assertFalse(adapter.empty_cache_expected('textures', 'Found 1 files to process'))
        log = "Found 1 files to process\nMesh 'body.w2mesh' does not contain collision"
        self.assertTrue(adapter.empty_cache_expected('physics', log))
        self.assertFalse(adapter.empty_cache_expected('physics', log.replace('Found 1', 'Found 2')))
        self.assertFalse(adapter.empty_cache_expected('physics', ''))

    @unittest.skipUnless(os.name == 'nt', 'Native junctions require Windows')
    def test_readthrough_view_overrides_without_changing_stock(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(adapter, 'ROOT', Path(temp)):
            root = Path(temp)
            stock, workspace = root / 'stock', root / 'workspace'
            (stock / 'characters').mkdir(parents=True)
            (stock / 'textures').mkdir()
            (workspace / 'characters').mkdir(parents=True)
            (stock / 'characters/body.w2mesh').write_bytes(b'stock')
            (stock / 'characters/sibling.w2mesh').write_bytes(b'sibling')
            (stock / 'textures/skin.xbm').write_bytes(b'texture')
            (workspace / 'characters/body.w2mesh').write_bytes(b'custom')
            (workspace / 'characters/new.w2mesh').write_bytes(b'new')
            (workspace / 'localization.db').write_bytes(b'do not cook')
            view = adapter.readthrough_depot(stock, workspace)
            self.assertEqual((view / 'characters/body.w2mesh').read_bytes(), b'custom')
            self.assertEqual((view / 'characters/sibling.w2mesh').read_bytes(), b'sibling')
            self.assertEqual((view / 'characters/new.w2mesh').read_bytes(), b'new')
            self.assertTrue(os.path.samefile(view / 'textures', stock / 'textures'))
            self.assertFalse((view / 'localization.db').exists())
            self.assertEqual((stock / 'characters/body.w2mesh').read_bytes(), b'stock')
            # Remove the link itself before TemporaryDirectory's cleanup.
            os.rmdir(view / 'textures')

    def test_resource_paths_reject_windows_escapes(self):
        for value in ['../body.w2mesh', 'characters/../body.w2mesh', 'C:/body.w2mesh',
                      '//server/share/body.w2mesh', '/absolute.w2mesh', 'body.w2mesh:stream', 'a//b']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                adapter.relative_resource(value)
        self.assertEqual(adapter.relative_resource('characters\\male\\body.w2mesh').as_posix(),
                         'characters/male/body.w2mesh')

    def test_native_startup_arguments_are_separate_tokens(self):
        cfg = {'wcc': Path('wcc_lite.exe')}
        args = adapter.native_args(cfg, 'export', ['-depot=local'], Path('C:/workspace'), Path('C:/depot'))
        self.assertEqual(args[1:3], ['export', '-depot=local'])
        self.assertIn('-uncookDir', args)
        self.assertNotIn('-uncookDir=C:/depot', args)
        self.assertEqual(args[args.index('-workspaceDir') + 1], str(Path('C:/workspace')) + os.sep)

    def test_import_output_is_an_absolute_owned_path(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(adapter, 'ROOT', Path(temp)):
            root = Path(temp)
            source = root / 'sample.fbx'
            source.write_bytes(b'fbx fixture')

            def native(cfg, command, options, workspace, label):
                destination = Path(next(x[5:] for x in options if x.startswith('-out=')))
                self.assertTrue(destination.is_absolute())
                self.assertTrue(destination.is_relative_to(root.resolve() / 'generated/workspace'))
                destination.write_bytes(b'CR2W fixture')
                return {'exitCode': 0}

            with patch.object(adapter, 'run_wcc', side_effect=native):
                adapter.import_mesh({}, source, 'characters/malemod/body.w2mesh')
            self.assertEqual((root / 'generated/workspace/characters/malemod/body.w2mesh').read_bytes(), b'CR2W fixture')

    def test_native_success_without_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(adapter, 'ROOT', Path(temp)):
            source = Path(temp) / 'source.fbx'
            source.write_bytes(b'fixture')
            with patch.object(adapter, 'run_wcc', return_value={'exitCode': 0}), self.assertRaises(RuntimeError):
                adapter.import_mesh({}, source, 'characters/malemod/absent.w2mesh')

    def test_import_cannot_replace_an_existing_resource(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(adapter, 'ROOT', Path(temp)):
            root = Path(temp)
            source = root / 'source.fbx'
            source.write_bytes(b'fixture')
            output = root / 'generated/workspace/characters/existing.w2mesh'
            output.parent.mkdir(parents=True)
            output.write_bytes(b'original')
            with patch.object(adapter, 'run_wcc') as native, self.assertRaises(ValueError):
                adapter.import_mesh({}, source, 'characters/existing.w2mesh')
            native.assert_not_called()
            self.assertEqual(output.read_bytes(), b'original')

    def test_package_rejects_corruption_and_extra_files(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(adapter, 'ROOT', Path(temp)):
            directory = Path(temp) / 'publish/test'
            resource = directory / 'Mods/modMaleMod/content/scripts/local/test.ws'
            resource.parent.mkdir(parents=True)
            original = b'exec function Fixture() {}'
            resource.write_bytes(original)
            manifest = {'files': [{'path': resource.relative_to(directory).as_posix(),
                        'sha256': hashlib.sha256(original).hexdigest(), 'bytes': len(original)}], 'gameplayTested': False}
            (directory / 'build-manifest.json').write_text(json.dumps(manifest))
            adapter.verify_package(directory)
            resource.write_bytes(b'corrupted')
            with self.assertRaises(RuntimeError):
                adapter.verify_package(directory)
            resource.write_bytes(original)
            (directory / 'unrecorded.txt').write_text('extra')
            with self.assertRaises(RuntimeError):
                adapter.verify_package(directory)

    def test_build_blocks_a_different_base_revision(self):
        with patch.object(adapter, 'read_json', return_value={'commit': 'pinned', 'referenceAsset': 'reference.glb'}):
            result = type('Result', (), {'stdout': 'different\n'})()
            with patch.object(adapter.subprocess, 'run', return_value=result), self.assertRaises(RuntimeError):
                adapter.base_checkout({'base': Path('base')})


if __name__ == '__main__':
    unittest.main()
