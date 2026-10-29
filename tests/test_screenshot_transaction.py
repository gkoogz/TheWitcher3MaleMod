import tempfile,time,unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import screenshot_transaction as photos


class ScreenshotTransactionTests(unittest.TestCase):
    @contextmanager
    def directory(self):
        with tempfile.TemporaryDirectory()as d:
            try:yield d
            finally:
                # Tests which deliberately leave a pending transaction emulate
                # its parent-process exit before deleting their own fixtures.
                for key in list(photos._ORIGINAL_LEASES):
                    if Path(key).is_relative_to(Path(d).resolve()):photos._release_originals(key)

    def setup(self,root):
        screens=root/'screenshots';screens.mkdir();(screens/'screenshot_123.png').write_bytes(b'original photo')
        return screens

    def session(self,root,receipt):
        session=root/'session.json';photos.atomic_json(session,dict(observations=dict(processID=1,processCreationTime='owned'),
            launchedUnixSeconds=time.time()-1,closed=True,audioRestored=True,iterationWorldFilesRemoved=True))
        photos.bind(receipt,session)

    def test_filename_collision_preserves_original_and_archives_new_image(self):
        with self.directory()as d,patch.object(photos,'quiet'):
            root=Path(d);screens=self.setup(root)
            with patch.object(photos,'ACTIVE',root/'active.json'):
                receipt=photos.begin(screens,root/'transaction');self.session(root,receipt)
                (screens/'screenshot_123.png').write_bytes(b'\x89PNG\r\n\x1a\nnew native image')
                result=photos.restore(receipt)
                self.assertEqual((screens/'screenshot_123.png').read_bytes(),b'original photo')
                self.assertEqual(Path(result['archive'][0]['path']).read_bytes(),b'\x89PNG\r\n\x1a\nnew native image')
                self.assertEqual(photos.restore(receipt)['originalsVerified'],1)

    def test_unexpected_concurrent_file_is_not_deleted_or_overwritten(self):
        with self.directory()as d,patch.object(photos,'quiet'):
            root=Path(d);screens=self.setup(root)
            with patch.object(photos,'ACTIVE',root/'active.json'):
                receipt=photos.begin(screens,root/'transaction');self.session(root,receipt)
                (screens/'user-note.txt').write_bytes(b'user data')
                with self.assertRaisesRegex(ValueError,'concurrent'):photos.restore(receipt)
                self.assertEqual((screens/'user-note.txt').read_bytes(),b'user data')
                holding=Path(photos.read_json(receipt)['holding']);self.assertEqual((holding/'screenshot_123.png').read_bytes(),b'original photo')

    def test_interrupted_begin_before_directory_move_is_recoverable(self):
        with self.directory()as d,patch.object(photos,'quiet'):
            root=Path(d);screens=self.setup(root)
            with patch.object(photos,'ACTIVE',root/'active.json'):
                with patch.object(photos.os,'rename',side_effect=OSError('interrupted')):
                    with self.assertRaises(OSError):photos.begin(screens,root/'transaction')
                receipt=Path(photos.read_json(root/'active.json')['receipt'])
                with self.assertRaisesRegex(ValueError,'pending'):photos.pending()
                self.assertTrue(photos.restore(receipt)['restored'])

    def test_interrupted_restore_after_new_photos_archive_resumes(self):
        with self.directory()as d,patch.object(photos,'quiet'):
            root=Path(d);screens=self.setup(root)
            with patch.object(photos,'ACTIVE',root/'active.json'):
                receipt=photos.begin(screens,root/'transaction');self.session(root,receipt)
                (screens/'screenshot_9.png').write_bytes(b'\x89PNG\r\n\x1a\nnew')
                with patch.object(photos.os,'rename',side_effect=OSError('interrupted')):
                    with self.assertRaises(OSError):photos.restore(receipt)
                self.assertTrue(photos.restore(receipt)['restored'])
                self.assertEqual((screens/'screenshot_123.png').read_bytes(),b'original photo')

    def test_original_quarantine_edit_is_blocked(self):
        with self.directory()as d,patch.object(photos,'quiet'):
            root=Path(d);screens=self.setup(root)
            with patch.object(photos,'ACTIVE',root/'active.json'):
                receipt=photos.begin(screens,root/'transaction');self.session(root,receipt)
                holding=Path(photos.read_json(receipt)['holding']);photo=holding/'screenshot_123.png'
                with self.assertRaises(PermissionError):photo.write_bytes(b'external edit')
                self.assertEqual(photo.read_bytes(),b'original photo')
                self.assertTrue(photos.restore(receipt)['restored'])

    def test_edit_after_parent_exit_is_preserved_and_restoration_refused(self):
        with self.directory()as d,patch.object(photos,'quiet'):
            root=Path(d);screens=self.setup(root)
            with patch.object(photos,'ACTIVE',root/'active.json'):
                receipt=photos.begin(screens,root/'transaction');self.session(root,receipt)
                photos._release_originals(receipt) # Emulate the owning process exiting.
                holding=Path(photos.read_json(receipt)['holding']);photo=holding/'screenshot_123.png';photo.write_bytes(b'external edit')
                with self.assertRaisesRegex(ValueError,'originals changed'):photos.restore(receipt)
                self.assertEqual(photo.read_bytes(),b'external edit')

    def test_interrupted_final_receipt_commit_retains_archive_provenance(self):
        with self.directory()as d,patch.object(photos,'quiet'):
            root=Path(d);screens=self.setup(root)
            with patch.object(photos,'ACTIVE',root/'active.json'):
                receipt=photos.begin(screens,root/'transaction');self.session(root,receipt)
                (screens/'screenshot_9.png').write_bytes(b'\x89PNG\r\n\x1a\nnew');write=photos.atomic_json
                def interrupted(path,data):
                    if data.get('restored'):raise OSError('final journal interruption')
                    return write(path,data)
                with patch.object(photos,'atomic_json',side_effect=interrupted):
                    with self.assertRaises(OSError):photos.restore(receipt)
                result=photos.restore(receipt);self.assertEqual(len(result['archive']),1)
                self.assertEqual((screens/'screenshot_123.png').read_bytes(),b'original photo')


if __name__=='__main__':unittest.main()
