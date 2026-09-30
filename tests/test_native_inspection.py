from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1]/'tools'
sys.path.insert(0, str(TOOLS))
import inspect_native


class InspectionTest(unittest.TestCase):
    def test_rejects_non_native_input_before_launching_tool(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)/'not-native.txt'
            source.write_text('plain text')
            with patch.object(inspect_native, 'run_wcc') as native:
                with self.assertRaises(ValueError):
                    inspect_native.inspect(source)
                native.assert_not_called()

    def test_native_dump_uses_owned_copy_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            source = root/'sdk/native.w2ent'
            source.parent.mkdir()
            source.write_bytes(b'CR2W native fixture')
            def native(cfg, command, options, workspace, label):
                self.assertEqual(command, 'dumpfile')
                owned = Path(options[0].removeprefix('-file='))
                self.assertTrue(owned.is_relative_to(root/'build'))
                self.assertNotEqual(owned, source)
                self.assertEqual(owned.read_bytes(), source.read_bytes())
                self.assertEqual(options[1], '-out=\\\\?\\')
                Path(str(owned)+'.xml').write_text('<dump><objects/></dump>')
                return {'exitCode': 0}
            with patch.object(inspect_native, 'ROOT', root), patch.object(inspect_native, 'settings', return_value={}), patch.object(inspect_native, 'run_wcc', side_effect=native):
                report = inspect_native.inspect(source)
            self.assertEqual(source.read_bytes(), b'CR2W native fixture')
            self.assertTrue(Path(report['output']).is_file())

