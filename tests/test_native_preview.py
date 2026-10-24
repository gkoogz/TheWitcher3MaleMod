"""Preview identity failures must stop before native launch or file cleanup."""
import json
from contextlib import ExitStack
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import native_preview as preview


class PreviewIdentity(unittest.TestCase):
    def fixture(self, root):
        game = root/'build/native-preview/example/game'
        game.mkdir(parents=True)
        # Test identity parsing without a junction by choosing this licensed
        # fixture root. Production additionally checks the executable hash.
        stock = game
        (game/'content').mkdir()
        manifest = game.parent/'preview.json'
        data = dict(schema='malemod.native-preview/1', game=str(game), sourceGame=str(stock), files=[])
        manifest.write_text(json.dumps(data))
        return manifest, game, data

    def test_close_resolves_bound_preview_without_requiring_mutable_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); manifest, game, _ = self.fixture(root)
            with patch.object(preview, 'ROOT', root), patch.object(preview, 'settings', return_value={'game':game}):
                r = dict(nativePreview=str(manifest), nativePreviewSHA256=preview.digest(manifest))
                self.assertEqual(preview.session_game(r), game)

    def test_external_storage_requires_matching_repository_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();external=root/'external';external.mkdir()
            config=root/'local/preview-storage.json';config.parent.mkdir()
            config.write_text(json.dumps(dict(repository=str(root),root=str(external))))
            with patch.object(preview,'ROOT',root):
                self.assertEqual(preview.preview_owners()[-1],external)
                config.write_text(json.dumps(dict(repository=str(root/'other'),root=str(external))))
                with self.assertRaisesRegex(ValueError,'repository-owned'):
                    preview.preview_owners()

    def test_changed_manifest_cannot_redirect_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); manifest, game, data = self.fixture(root)
            original = preview.digest(manifest); data['game'] = str(root/'outside')
            manifest.write_text(json.dumps(data))
            with patch.object(preview, 'ROOT', root), patch.object(preview, 'settings', return_value={'game':game}):
                with self.assertRaisesRegex(ValueError, 'manifest changed'):
                    preview.session_game(dict(nativePreview=str(manifest), nativePreviewSHA256=original))

    def test_external_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); manifest = root/'preview.json'
            manifest.write_text('{}')
            with patch.object(preview, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'repository-owned'):
                    preview.load_preview(manifest)

    def test_game_redirect_is_rejected_even_with_new_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); manifest, game, data = self.fixture(root)
            data['game'] = str(root/'outside'); manifest.write_text(json.dumps(data))
            with patch.object(preview, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'game identity'):
                    preview.load_preview(manifest, verify_files=False)

    def test_non_preview_sessions_retain_managed_game(self):
        game = Path('managed-game')
        with patch.object(preview, 'settings', return_value={'game':game}):
            self.assertEqual(preview.session_game({}), game)

    def test_changed_candidate_is_rejected_before_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); manifest, game, data = self.fixture(root)
            installed = root/'local/native-installation.json'
            installed.parent.mkdir(); installed.write_text(json.dumps({'files':[]}))
            candidate = game/'candidate.dll'; candidate.write_bytes(b'candidate')
            data.update(installationReceiptSHA256=preview.digest(installed),
                        files=[{'path':'candidate.dll','sha256':preview.digest(candidate)}])
            manifest.write_text(json.dumps(data)); candidate.write_bytes(b'changed')
            with patch.object(preview, 'ROOT', root), patch.object(preview, 'settings', return_value={'game':game}):
                with self.assertRaisesRegex(ValueError, 'Preview file changed'):
                    preview.load_preview(manifest)


class InstalledPreviewRebase(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory())).resolve()
        self.game = self.root/'previews/working/game'
        self.stock = self.root/'installed'
        self.manifest = self.game.parent/'preview.json'
        self.receipt = self.root/'closed-session.json'
        self.installation = self.root/'local/native-installation.json'
        rows = []
        # Include both a managed runtime and a copied, non-managed executable.
        for relative in ['runtime.dll', 'bin/x64_dx12/witcher3.exe', 'config.ini',
                         'bin/x64_dx12/malemod-native/malemod_witcher.dll']:
            for owner in [self.game, self.stock]:
                target = owner/relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(relative.encode())
            rows.append(dict(path=relative, sha256=preview.digest(self.game/relative)))
        self.data = dict(schema='malemod.native-preview/1', game=str(self.game),
                         sourceGame=str(self.stock), files=rows,
                         installationReceiptSHA256='historical', candidateAccepted=True)
        preview.write_json(self.manifest, self.data)
        self.session = dict(closed=True, audioRestored=True, iterationWorldFilesRemoved=True,
                            nativePreview=str(self.manifest),
                            nativePreviewSHA256=preview.digest(self.manifest))
        preview.write_json(self.receipt, self.session)
        self.installed = dict(game=str(self.stock), files=[rows[0]])
        preview.write_json(self.installation, self.installed)
        self.stack.enter_context(patch.object(preview, 'ROOT', self.root))
        self.stack.enter_context(patch.object(preview, 'settings', return_value={'game': self.stock}))
        self.running = self.stack.enter_context(patch.object(preview.subprocess, 'check_output', return_value=''))
        # load_preview's real ownership/content-junction checks are independently
        # covered above. This fixture needs no administrator-created junction.
        self.loader = self.stack.enter_context(patch.object(preview, 'load_preview',
            side_effect=lambda path, *args, **kwargs: (self.game, preview.read_json(path))))

    def rebase(self):
        return preview.rebase_installed_preview(self.manifest, self.receipt)

    def assert_no_new_manifest(self):
        self.assertEqual(list(self.manifest.parent.glob('preview-*.json')), [])

    def test_new_baseline_preserves_history_and_all_game_bytes(self):
        original = self.manifest.read_bytes()
        before = {p: p.read_bytes() for root in [self.game, self.stock]
                  for p in root.rglob('*') if p.is_file()}
        result = self.rebase()
        data = preview.read_json(result)
        self.assertNotEqual(result, self.manifest)
        self.assertEqual(result.parent, self.manifest.parent)
        self.assertEqual(self.manifest.read_bytes(), original)
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        self.assertEqual(data['installationReceiptSHA256'], preview.digest(self.installation))
        self.assertEqual(data['previousManifestSHA256'], preview.digest(self.manifest))
        self.assertEqual(data['previousManifest'], str(self.manifest))
        self.assertFalse(data['candidateAccepted'])
        self.loader.assert_any_call(self.manifest, preview.digest(self.manifest), verify_files=False)
        self.loader.assert_any_call(result)

    def test_receipt_must_bind_exact_manifest_hash(self):
        self.session['nativePreviewSHA256'] = 'stale'
        preview.write_json(self.receipt, self.session)
        with self.assertRaisesRegex(ValueError, 'exact verified closed'):
            self.rebase()
        self.assert_no_new_manifest()

    def test_incomplete_session_or_live_process_rejected(self):
        for flag in ['closed', 'audioRestored', 'iterationWorldFilesRemoved']:
            with self.subTest(flag=flag):
                preview.write_json(self.receipt, dict(self.session, **{flag: False}))
                with self.assertRaisesRegex(ValueError, 'exact verified closed'):
                    self.rebase()
        preview.write_json(self.receipt, self.session)
        self.running.return_value = '"witcher3.exe","123"'
        with self.assertRaisesRegex(ValueError, 'Close the game'):
            self.rebase()
        self.assert_no_new_manifest()

    def test_managed_receipt_must_match_preview_declaration(self):
        self.installed['files'][0]['sha256'] = 'different'
        preview.write_json(self.installation, self.installed)
        with self.assertRaisesRegex(ValueError, 'Installed runtime differs'):
            self.rebase()
        self.assert_no_new_manifest()

    def test_installed_disk_must_match_receipt(self):
        (self.stock/'runtime.dll').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Managed runtime changed'):
            self.rebase()
        self.assert_no_new_manifest()

    def test_unmanaged_preview_file_must_still_match(self):
        (self.game/'config.ini').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Preview file changed'):
            self.rebase()
        self.assert_no_new_manifest()

    def test_shared_hardlinked_preview_file_is_rejected(self):
        target = self.game/'runtime.dll'
        target.unlink()
        os.link(self.stock/'runtime.dll', target)
        with self.assertRaisesRegex(ValueError, 'owned regular copy'):
            self.rebase()
        self.assert_no_new_manifest()

    def test_installation_must_name_the_current_source_game(self):
        self.installed['game'] = str(self.root/'other-game')
        preview.write_json(self.installation, self.installed)
        with self.assertRaisesRegex(ValueError, 'Managed game path differs'):
            self.rebase()
        self.assert_no_new_manifest()

    def test_executable_must_match_licensed_game(self):
        (self.stock/'bin/x64_dx12/witcher3.exe').write_bytes(b'updated')
        with self.assertRaisesRegex(ValueError, 'executable differs'):
            self.rebase()
        self.assert_no_new_manifest()

    def test_existing_destination_is_never_overwritten(self):
        existing = self.manifest.parent/'preview-123.json'
        existing.write_bytes(b'historical proof')
        with patch.object(preview.time, 'time_ns', return_value=123):
            with self.assertRaises(FileExistsError):
                self.rebase()
        self.assertEqual(existing.read_bytes(), b'historical proof')

    def test_original_closed_receipt_authorizes_first_rebased_refresh_only(self):
        result = self.rebase()
        original = self.manifest.read_bytes()
        dll = self.root/'new.dll'
        dll.write_bytes(b'new candidate')
        preview.refresh_closed(result, self.receipt, dll)
        self.assertEqual((self.game/'bin/x64_dx12/malemod-native/malemod_witcher.dll').read_bytes(),
                         b'new candidate')
        self.assertEqual(self.manifest.read_bytes(), original)
        with self.assertRaisesRegex(ValueError, 'verified closed room receipt'):
            preview.refresh_closed(result, self.receipt, dll)

    def test_modified_rebase_manifest_cannot_inherit_closed_receipt(self):
        result = self.rebase()
        data = preview.read_json(result)
        data['unreviewedChange'] = True
        preview.write_json(result, data)
        with self.assertRaisesRegex(ValueError, 'verified closed room receipt'):
            preview.refresh_closed(result, self.receipt, self.root/'unused.dll')

    def test_rebase_receipt_path_and_bytes_are_bound(self):
        result = self.rebase()
        other = self.root/'copied-receipt.json'
        other.write_bytes(self.receipt.read_bytes())
        with self.assertRaisesRegex(ValueError, 'verified closed room receipt'):
            preview.refresh_closed(result, other, self.root/'unused.dll')
        self.session['extra'] = 'changed after rebase'
        preview.write_json(self.receipt, self.session)
        with self.assertRaisesRegex(ValueError, 'verified closed room receipt'):
            preview.refresh_closed(result, self.receipt, self.root/'unused.dll')

    def test_rebase_source_manifest_must_remain_exact(self):
        result = self.rebase()
        self.data['extra'] = 'changed history'
        preview.write_json(self.manifest, self.data)
        # The fixture loader intentionally mocks load_preview, so check its
        # expected-hash contract explicitly here as the real implementation does.
        def checked_loader(path, expected_hash=None, **kwargs):
            if expected_hash and preview.digest(path) != expected_hash:
                raise ValueError('Preview manifest changed')
            return self.game, preview.read_json(path)
        self.loader.side_effect = checked_loader
        with self.assertRaisesRegex(ValueError, 'Preview manifest changed'):
            preview.refresh_closed(result, self.receipt, self.root/'unused.dll')


if __name__ == '__main__':
    unittest.main()
