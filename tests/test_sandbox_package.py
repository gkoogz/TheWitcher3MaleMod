import importlib.util
from pathlib import Path
import sys
import unittest
import json
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from release_exclusions import assert_release_path
import sandbox


class SandboxPackagingTests(unittest.TestCase):
    def test_release_does_not_accept_studio_or_private_files(self):
        for path in ('Mods/modMaleModIteration/content/bundles/bundle',
            'Mods/modMaleModContinueTest/content/scripts/autocontinue.ws',
            'dev/sandbox/manifest.json','local/config.json','captures/frame.png',
            'payload/Mods/modMaleMod/content/scripts/iteration_platform.ws'):
            with self.subTest(path=path),self.assertRaises(ValueError):assert_release_path(path)

    def test_runtime_and_rig_paths_are_allowed(self):
        for path in ('bin/x64_dx12/malemod-native/malemod_witcher.dll',
            'Mods/modMaleMod/content/bundles/buffers0.bundle',
            'Mods/mod0000MaleModBodyBoundary/content/metadata.store','Manage.ps1'):
            self.assertEqual(assert_release_path(path),path)

    def test_ordinary_install_refuses_studio_without_overwriting_rig_receipt(self):
        import mod
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            with patch.object(mod,'verify_package',return_value=dict(project='modMaleModIteration')):
                with self.assertRaises(ValueError):mod.install_package(dict(game=root/'game'),root/'package')
            self.assertFalse((root/'game').exists())

    def test_portable_shortcut_has_no_machine_python_or_game_path(self):
        source=(ROOT/'tools/Create-IterationShortcut.ps1').read_text()
        self.assertNotIn('E:\\SteamLibrary',source)
        self.assertNotIn('C:\\Program Files\\Python310',source)

    def test_frozen_payload_excludes_source_candidates_and_sandbox(self):
        profile=json.loads((ROOT/'release/profiles/0.5.0-beta.2.json').read_text())
        self.assertEqual(len(profile['files']),40)
        self.assertEqual(profile['baseCommit'],'99ff741ea95f18ed84526c35a6c3f38a37d857b6')
        for row in profile['files']:assert_release_path(row['path'])

    def test_release_adoption_bootstraps_without_host_receipts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);game=root/'game';profile=json.loads((ROOT/'release/profiles/0.5.0-beta.2.json').read_text())
            exe=game/'bin/x64_dx12/witcher3.exe';exe.parent.mkdir(parents=True);exe.write_bytes(b'owned fixture exe')
            profile['gameExecutableSHA256']=sandbox.digest(exe)
            for row in profile['files']:
                target=game/row['path'];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(row['path'].encode())
                row['sha256']=sandbox.digest(target)
            declared=root/'release/profiles/0.5.0-beta.2.json';declared.parent.mkdir(parents=True)
            declared.write_text(json.dumps(profile))
            released=root/'manifest.json';released.write_text(json.dumps(dict(schema=1,version=profile['version'],files=profile['files'])))
            before={r['path']:sandbox.digest(game/r['path']) for r in profile['files']}
            with patch.object(sandbox,'ROOT',root),patch.object(sandbox,'settings',return_value=dict(game=game)):
                sandbox.adopt_release(released)
                sandbox.adopt_release(released)
                native=json.loads((root/'local/native-installation.json').read_text())
                fallback=json.loads((root/'local/installation.json').read_text())
                self.assertEqual((len(native['files']),len(fallback['files'])),(35,5))
                self.assertEqual(native['baseCommit'],profile['baseCommit'])
                self.assertEqual(before,{r['path']:sandbox.digest(game/r['path']) for r in profile['files']})
                changed=game/profile['files'][0]['path'];changed.write_bytes(b'foreign proxy')
                with self.assertRaises(ValueError):sandbox.adopt_release(released)
