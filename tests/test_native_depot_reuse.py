"""A reused view must be an unchanged sibling intake, never a writable depot."""
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mod import validate_readonly_depot


class NativeDepotReuseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.workspace = root / 'workspace'
        self.view = root / 'depot-0123456789ab'
        for directory in (self.workspace, self.view):
            (directory / 'levels').mkdir(parents=True)
            (directory / 'levels/own.w2w').write_bytes(b'owned exact resource')

    def test_only_separate_output_readonly_commands(self):
        for name in ('dumpfile', 'buildcache', 'dependencies', 'pack', 'metadatastore'):
            validate_readonly_depot(name, self.workspace, self.view)
        for name in ('cook', 'resave', 'import', 'unknown'):
            with self.assertRaises(ValueError):
                validate_readonly_depot(name, self.workspace, self.view)

    def test_changed_or_missing_resource_refuses_reuse(self):
        target = self.view / 'levels/own.w2w'
        target.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            validate_readonly_depot('pack', self.workspace, self.view)
        target.unlink()
        with self.assertRaises(ValueError):
            validate_readonly_depot('dumpfile', self.workspace, self.view)

    def test_unrelated_or_unowned_view_refuses_reuse(self):
        for path in (self.view / 'depot-0123456789ab', self.view.parent / 'stock'):
            with self.assertRaises(ValueError):
                validate_readonly_depot('dumpfile', self.workspace, path)


if __name__ == '__main__':
    unittest.main()
