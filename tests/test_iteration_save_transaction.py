import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from iteration_save_transaction import begin, restore


class SaveTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'gamesaves'
        self.root.mkdir()
        (self.root/'CheckPoint_old.sav').write_bytes(b'original')
        self.receipt = begin(self.root, Path(self.temp.name)/'backup')
        time.sleep(.01)

    def private_checkpoint(self, mod='modmalemodcontinuetest'):
        (self.root/'CheckPoint_new.json').write_text(json.dumps({'modName': mod}))
        (self.root/'CheckPoint_new.sav').write_bytes(b'private')

    def test_rotated_original_and_own_checkpoint_restored(self):
        (self.root/'CheckPoint_old.sav').unlink()
        self.private_checkpoint()
        result = restore(self.receipt, closed_private_session=True)
        self.assertEqual((self.root/'CheckPoint_old.sav').read_bytes(), b'original')
        self.assertEqual(set(p.name for p in self.root.iterdir()), {'CheckPoint_old.sav'})
        self.assertEqual(len(result['archivedPrivateCreated']), 2)

    def test_changed_original_preserved(self):
        (self.root/'CheckPoint_old.sav').write_bytes(b'user-change')
        with self.assertRaisesRegex(ValueError, 'changed original'):
            restore(self.receipt, closed_private_session=True)
        self.assertEqual((self.root/'CheckPoint_old.sav').read_bytes(), b'user-change')

    def test_foreign_save_does_not_allow_partial_mutation(self):
        (self.root/'CheckPoint_old.sav').unlink()
        self.private_checkpoint('other-mod')
        with self.assertRaisesRegex(ValueError, 'provenance'):
            restore(self.receipt, closed_private_session=True)
        self.assertFalse((self.root/'CheckPoint_old.sav').exists())
        self.assertTrue((self.root/'CheckPoint_new.sav').exists())

    def test_closed_child_and_backup_identity_required(self):
        with self.assertRaisesRegex(ValueError, 'closed'):
            restore(self.receipt, closed_private_session=False)
        (self.receipt.parent/'CheckPoint_old.sav').write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError, 'backup changed'):
            restore(self.receipt, closed_private_session=True)


if __name__ == '__main__':
    unittest.main()
