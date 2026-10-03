"""Managed upgrade rollback must preserve preferences and survive partial copy."""
import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import install_native_runtime as native
from mod import digest,write_json

class NativeRestore(unittest.TestCase):
    def fixture(self,root):
        game=root/'game';backup=root/'local/snapshot';backup.mkdir(parents=True)
        rel='bin/x64_dx12/malemod-native/module.dll';extra='bin/x64_dx12/malemod-native/new-owned.bin'
        target=game/rel;target.parent.mkdir(parents=True);target.write_bytes(b'new')
        (game/extra).write_bytes(b'extra');prefs=target.parent/'malemod-controls.bin';prefs.write_bytes(b'user data')
        saved=backup/rel;saved.parent.mkdir(parents=True);saved.write_bytes(b'old')
        current=dict(game=str(game),files=[dict(path=rel,sha256=digest(target)),dict(path=extra,sha256=digest(game/extra))])
        previous=dict(game=str(game),files=[dict(path=rel,sha256=digest(saved))])
        write_json(root/'local/native-installation.json',current);write_json(backup/'receipt.json',previous)
        return game,backup,rel,extra,prefs,current
    def test_exact_restore_preserves_preferences(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();game,backup,rel,extra,prefs,_=self.fixture(root)
            with patch.object(native,'ROOT',root),patch.object(native.subprocess,'run') as query:
                query.return_value.stdout='';native.restore_native_runtime(dict(game=game),backup)
            self.assertEqual((game/rel).read_bytes(),b'old');self.assertFalse((game/extra).exists());self.assertEqual(prefs.read_bytes(),b'user data')
    def test_failed_partial_copy_recovers_previous_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();game,backup,rel,extra,prefs,current=self.fixture(root);copy=native.shutil.copy2
            def failing(source,target):
                if Path(source)==backup/rel and Path(target)==game/rel:
                    Path(target).write_bytes(b'partial');raise OSError('fixture partial-copy failure')
                return copy(source,target)
            with patch.object(native,'ROOT',root),patch.object(native.subprocess,'run') as query,patch.object(native.shutil,'copy2',failing):
                query.return_value.stdout=''
                with self.assertRaises(OSError):native.restore_native_runtime(dict(game=game),backup)
            self.assertEqual((game/rel).read_bytes(),b'new');self.assertEqual((game/extra).read_bytes(),b'extra');self.assertEqual(prefs.read_bytes(),b'user data')
            self.assertEqual(json.loads((root/'local/native-installation.json').read_text()),current)
    def test_unmanaged_changed_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();game,backup,rel,_,_,_=self.fixture(root);(game/rel).write_bytes(b'changed by user')
            with patch.object(native,'ROOT',root),patch.object(native.subprocess,'run') as query:
                query.return_value.stdout=''
                with self.assertRaises(ValueError):native.restore_native_runtime(dict(game=game),backup)
            self.assertEqual((game/rel).read_bytes(),b'changed by user')

if __name__=='__main__':unittest.main()
