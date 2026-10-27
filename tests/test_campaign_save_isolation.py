"""Save isolation recovery uses disposable files and never launches a game."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import campaign_save_isolation as isolation


class IsolationTests(unittest.TestCase):
    def setup_tree(self,root):
        saves=root/'saves';saves.mkdir();(saves/'ordinary.sav').write_bytes(b'original')
        (saves/'ordinary.json').write_bytes(b'original metadata')
        return saves,root/'holding'

    def test_restore_is_repeatable_and_preserves_unrelated_addition(self):
        with tempfile.TemporaryDirectory()as d,patch.object(isolation,'quiet'):
            saves,holding=self.setup_tree(Path(d));receipt=isolation.isolate(saves,holding)
            self.assertEqual(list(saves.iterdir()),[])
            (saves/'unrelated.txt').write_bytes(b'user addition')
            self.assertEqual(isolation.restore_originals(receipt),2)
            self.assertEqual(isolation.restore_originals(receipt),2)
            self.assertEqual((saves/'ordinary.sav').read_bytes(),b'original')
            self.assertEqual((saves/'unrelated.txt').read_bytes(),b'user addition')
            self.assertFalse((holding/'ordinary.sav').exists())

    def test_changed_original_or_backup_is_not_overwritten(self):
        with tempfile.TemporaryDirectory()as d,patch.object(isolation,'quiet'):
            saves,holding=self.setup_tree(Path(d));receipt=isolation.isolate(saves,holding)
            (saves/'ordinary.sav').write_bytes(b'external edit')
            with self.assertRaises(ValueError):isolation.restore_originals(receipt)
            self.assertEqual((saves/'ordinary.sav').read_bytes(),b'external edit')
            self.assertTrue((holding/'ordinary.sav').exists())
            (saves/'ordinary.sav').unlink();(holding/'ordinary.sav').write_bytes(b'changed backup')
            with self.assertRaises(ValueError):isolation.restore_originals(receipt)
            self.assertFalse((saves/'ordinary.json').exists())

    def test_failed_cross_volume_copy_keeps_every_original(self):
        with tempfile.TemporaryDirectory()as d,patch.object(isolation,'quiet'):
            saves,holding=self.setup_tree(Path(d));copy=isolation.shutil.copy2
            def fail(source,dest):
                if source.name=='ordinary.sav':raise OSError('simulated full destination')
                return copy(source,dest)
            with patch.object(isolation.shutil,'copy2',fail):
                with self.assertRaises(OSError):isolation.isolate(saves,holding)
            self.assertEqual((saves/'ordinary.sav').read_bytes(),b'original')
            self.assertTrue(isolation.read_json(holding/'isolation.json')['restored'])

    def test_running_game_cannot_trigger_isolation(self):
        with tempfile.TemporaryDirectory()as d:
            saves,holding=self.setup_tree(Path(d))
            with patch.object(isolation,'quiet',side_effect=RuntimeError('game active')):
                with self.assertRaises(RuntimeError):isolation.isolate(saves,holding)
            self.assertFalse(holding.exists())

    def test_recovery_retries_pending_photos_after_world_was_already_removed(self):
        with tempfile.TemporaryDirectory()as d,patch.object(isolation,'quiet'):
            saves,holding=self.setup_tree(Path(d));receipt=isolation.isolate(saves,holding)
            session=holding/'session.json';isolation.write_json(session,dict(closed=True,iterationWorldFilesRemoved=True,
                iterationScreenshotTransaction=str(holding/'photos.json'),iterationScreenshotFilesRestored=False))
            data=isolation.read_json(receipt);data['session']=str(session);isolation.write_json(receipt,data)
            with patch('close_sealed_session.close'),patch('run_iteration_world.finish')as finish,patch.object(isolation,'recovery_probe',return_value=Path('probe')):
                self.assertEqual(isolation.cleanup(receipt),2)
                finish.assert_called_once_with(str(session),recovery_audio_probe=Path('probe'))
            self.assertEqual((saves/'ordinary.sav').read_bytes(),b'original')

    def test_failed_photo_recovery_keeps_verified_original_backups(self):
        with tempfile.TemporaryDirectory()as d,patch.object(isolation,'quiet'):
            saves,holding=self.setup_tree(Path(d));receipt=isolation.isolate(saves,holding)
            session=holding/'session.json';isolation.write_json(session,dict(closed=True,iterationWorldFilesRemoved=True,
                iterationScreenshotTransaction=str(holding/'photos.json'),iterationScreenshotFilesRestored=False))
            data=isolation.read_json(receipt);data['session']=str(session);isolation.write_json(receipt,data)
            with patch('close_sealed_session.close'),patch('run_iteration_world.finish',side_effect=ValueError('unknown photo edit')),patch.object(isolation,'recovery_probe',return_value=Path('probe')):
                with self.assertRaisesRegex(ValueError,'unknown photo edit'):isolation.cleanup(receipt)
            self.assertEqual((holding/'ordinary.sav').read_bytes(),b'original')
            self.assertFalse(isolation.read_json(receipt)['restored'])


if __name__=='__main__':unittest.main()
