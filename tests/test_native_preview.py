"""Preview identity failures must stop before native launch or file cleanup."""
import json
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


if __name__ == '__main__':
    unittest.main()
