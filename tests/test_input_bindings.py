import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from input_bindings import edit_bindings,CONTEXTS

class InputBindingsTests(unittest.TestCase):
    def source(self):
        return ''.join('['+c+']\r\nIK_W=(Action=Forward)\r\n\r\n' for c in CONTEXTS).encode()
    def test_roundtrip_preserves_other_actions(self):
        before=self.source();after,added=edit_bindings(before)
        self.assertEqual(len(added),24)
        self.assertEqual(edit_bindings(after)[0],after)
        self.assertEqual(edit_bindings(after,True)[0],before)
    def test_existing_binding_is_never_overwritten(self):
        with self.assertRaises(ValueError):edit_bindings(self.source().replace(b'[Combat]',b'[Combat]\r\nIK_F6=(Action=OtherMod)'))
    def test_utf16_is_preserved(self):
        before=self.source().decode().encode('utf-16')
        self.assertEqual(edit_bindings(edit_bindings(before)[0],True)[0],before)
