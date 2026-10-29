import ctypes,os,subprocess,sys,tempfile,unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import screenshot_transaction as photos


@unittest.skipUnless(os.name=='nt','Windows file-sharing contract')
class OriginalFileLeaseTests(unittest.TestCase):
    @contextmanager
    def directory(self):
        with tempfile.TemporaryDirectory()as name:
            root=Path(name)
            try:yield root
            finally:
                for key in list(photos._ORIGINAL_LEASES):
                    if Path(key).is_relative_to(root.resolve()):photos._release_originals(key)

    def child(self,code,*args):
        return subprocess.run([sys.executable,'-c',code,*map(str,args)],capture_output=True,text=True)

    def test_external_write_blocked_read_allowed_and_release_allows_write(self):
        with self.directory()as root:
            gallery=root/'gallery';gallery.mkdir();photo=gallery/'photo.png';photo.write_bytes(b'original')
            receipt=root/'receipt.json';photos._hold_originals(receipt,gallery)
            read=self.child('from pathlib import Path;import sys;assert Path(sys.argv[1]).read_bytes()==b"original"',photo)
            self.assertEqual(read.returncode,0,read.stderr)
            write=self.child('from pathlib import Path;import sys;Path(sys.argv[1]).write_bytes(b"changed")',photo)
            self.assertNotEqual(write.returncode,0);self.assertIn('PermissionError',write.stderr)
            self.assertEqual(photo.read_bytes(),b'original')
            photos._release_originals(receipt)
            write=self.child('from pathlib import Path;import sys;Path(sys.argv[1]).write_bytes(b"changed")',photo)
            self.assertEqual(write.returncode,0,write.stderr);self.assertEqual(photo.read_bytes(),b'changed')

    def test_owned_directory_move_releases_and_reacquires_windows_lease(self):
        with self.directory()as root:
            gallery=root/'gallery';gallery.mkdir();(gallery/'photo.png').write_bytes(b'original')
            holding=root/'holding';receipt=root/'receipt.json';photos._hold_originals(receipt,gallery)
            direct=self.child('import os,sys;os.rename(sys.argv[1],sys.argv[2])',gallery,holding)
            self.assertNotEqual(direct.returncode,0)
            self.assertTrue(gallery.is_dir());self.assertFalse(holding.exists())
            photos._rename_originals(receipt,gallery,holding)
            self.assertFalse(gallery.exists());self.assertEqual((holding/'photo.png').read_bytes(),b'original')
            write=self.child('from pathlib import Path;import sys;Path(sys.argv[1]).write_bytes(b"changed")',holding/'photo.png')
            self.assertNotEqual(write.returncode,0)
            photos._rename_originals(receipt,holding,gallery)
            self.assertEqual((gallery/'photo.png').read_bytes(),b'original')

    def test_existing_writer_fails_before_rename_and_closes_partial_lease(self):
        with self.directory()as root,patch.object(photos,'quiet'):
            gallery=root/'gallery';gallery.mkdir();first=gallery/'a.png';last=gallery/'b.png'
            first.write_bytes(b'a');last.write_bytes(b'b')
            probe=photos._OriginalFileLease(gallery);kernel=probe.kernel;probe.close()
            writer=kernel.CreateFileW(str(last),0x40000000,0x1|0x2|0x4,None,3,0x80,None)
            self.assertNotEqual(writer,ctypes.c_void_p(-1).value)
            try:
                with patch.object(photos,'ACTIVE',root/'active.json'),patch.object(photos.os,'rename')as rename:
                    with self.assertRaises(OSError)as error:photos.begin(gallery,root/'transaction')
                    self.assertEqual(error.exception.winerror,32);rename.assert_not_called()
                    self.assertFalse((root/'transaction').exists());self.assertFalse((root/'active.json').exists())
                # a.png was opened before b.png failed. It must not remain locked.
                child=self.child('from pathlib import Path;import sys;Path(sys.argv[1]).write_bytes(b"released")',first)
                self.assertEqual(child.returncode,0,child.stderr)
                self.assertEqual(last.read_bytes(),b'b')
            finally:kernel.CloseHandle(writer)

    def test_inventory_failure_releases_preflight_handles(self):
        with self.directory()as root,patch.object(photos,'quiet'):
            gallery=root/'gallery';gallery.mkdir();photo=gallery/'photo.png';photo.write_bytes(b'original')
            with patch.object(photos,'ACTIVE',root/'active.json'),patch.object(photos,'inventory',side_effect=ValueError('inventory interruption')):
                with self.assertRaisesRegex(ValueError,'inventory interruption'):photos.begin(gallery,root/'transaction')
            write=self.child('from pathlib import Path;import sys;Path(sys.argv[1]).write_bytes(b"released")',photo)
            self.assertEqual(write.returncode,0,write.stderr);self.assertFalse((root/'transaction').exists())

    def test_begin_restore_keeps_lease_until_full_verified_commit(self):
        with self.directory()as root,patch.object(photos,'quiet'):
            gallery=root/'gallery';gallery.mkdir();photo=gallery/'photo.png';photo.write_bytes(b'original')
            with patch.object(photos,'ACTIVE',root/'active.json'):
                receipt=photos.begin(gallery,root/'transaction');holding=Path(photos.read_json(receipt)['holding'])
                self.assertIn(photos._lease_key(receipt),photos._ORIGINAL_LEASES)
                write=self.child('from pathlib import Path;import sys;Path(sys.argv[1]).write_bytes(b"changed")',holding/'photo.png')
                self.assertNotEqual(write.returncode,0)
                result=photos.restore(receipt)
                self.assertTrue(result['restored']);self.assertEqual(photo.read_bytes(),b'original')
                self.assertNotIn(photos._lease_key(receipt),photos._ORIGINAL_LEASES)
                write=self.child('from pathlib import Path;import sys;Path(sys.argv[1]).write_bytes(b"released")',photo)
                self.assertEqual(write.returncode,0,write.stderr)


if __name__=='__main__':unittest.main()
