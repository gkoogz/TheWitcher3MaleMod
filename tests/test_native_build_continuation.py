from pathlib import Path
import json
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mod import digest, write_json
from native_build_continuation import files, validate_continuation


class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        parent = self.root / 'build/world'
        self.w = parent / 'workspace'
        self.j = parent / 'package-0123456789ab'
        self.view = parent / 'depot-0123456789ab'
        for d in (self.w, self.view, self.j / 'native-input', self.j / 'cooked'):
            d.mkdir(parents=True)
            (d / 'own.w2w').write_bytes(b'exact resource')
        (self.j / 'cooked/cook.db').write_bytes(b'exact database')
        self.tool = self.root / 'wcc.exe'
        self.tool.write_bytes(b'official fixture')
        self.log = self.root / 'cook.log'
        self.log.write_text('successful cook')
        self.command = self.root / 'cook.json'
        self.project = dict(name='modTest', cacheBuilders=['physics'])
        write_json(self.command, dict(command='cook', exitCode=0,
            logPath='cook.log', logSHA256=digest(self.log), wccSHA256=digest(self.tool),
            args=['cook', '-mod=' + str(self.j / 'native-input'),
                  '-outdir=' + str(self.j / 'cooked'), '-workspaceDir', str(self.w),
                  '-uncookDir', str(self.view)]))
        self.receipt = self.j / 'continuation.json'
        write_json(self.receipt, dict(schema='malemod.native-build-continuation/1',
            job=str(self.j), project=self.project, cookRecordPath='cook.json',
            cookRecordSHA256=digest(self.command), workspaceFiles=files(self.w),
            **{'native-input':files(self.j / 'native-input'), 'cooked':files(self.j / 'cooked')}))

    def check(self):
        return validate_continuation(self.root, {'wcc':self.tool}, self.w,
                                     self.project, self.receipt)

    def test_exact_owned_success(self):
        self.assertEqual(self.check()[0], self.j)

    def test_changed_cook_input_output_workspace_or_tool_rejected(self):
        for p in (self.j / 'native-input/own.w2w', self.j / 'cooked/cook.db',
                  self.w / 'own.w2w', self.tool, self.log, self.command):
            original = p.read_bytes()
            p.write_bytes(original + b'changed')
            with self.assertRaises(ValueError): self.check()
            p.write_bytes(original)

    def test_downstream_output_or_recipe_change_rejected(self):
        self.project['cacheBuilders'] = []
        with self.assertRaises(ValueError): self.check()
        self.project['cacheBuilders'] = ['physics']
        (self.j / 'bundle-input').mkdir()
        with self.assertRaises(ValueError): self.check()


if __name__ == '__main__':
    unittest.main()
