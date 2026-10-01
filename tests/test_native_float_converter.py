"""Catch the native converter's silent loss of integer-valued float properties."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from deformation_graph import deformation_graph

CONVERTER = ROOT / 'build/research/wkit-current/MaleModCR2W.exe'


@unittest.skipUnless(CONVERTER.is_file(), 'Pinned local converter is unavailable')
class NativeFloatTests(unittest.TestCase):
    def test_reference_mask_weights_survive_binary_round_trip(self):
        names = ['fixture_' + str(i) for i in range(94)]
        controlled = ['mm_shaft_' + str(i).zfill(2) for i in range(8)] + ['mm_scrotum_l', 'mm_scrotum_r']
        template = dict(_type='CR2W', _extension='', _imports=[], _properties=[],
                        _buffers=[], _embedded=[], _chunks={'CBehaviorGraph #0': {'_vars': {}}})
        graph = deformation_graph(template, names, controlled, identity_root=names[0],
                                  parent_space='attached', rest_joints=True)
        with tempfile.TemporaryDirectory() as temp:
            source, binary, output = [Path(temp) / name for name in ('graph.json', 'graph.w2beh', 'roundtrip.json')]
            source.write_text(json.dumps(graph))
            for args in [('import', source, binary), ('export', binary, output)]:
                subprocess.run([str(CONVERTER), *map(str, args)], check=True, capture_output=True)
            chunks = json.loads(output.read_text())['_chunks'].values()
            constant = next(c for c in chunks if c['_type'] == 'CBehaviorGraphFloatValueNode')
            self.assertEqual(constant['_vars']['value']['_value'], 1.0)
            mask = next(c for c in chunks if c['_type'] == 'CBehaviorGraphBlendOverrideNode')
            bones = mask['_vars']['Bones with weights']['_elements']
            self.assertEqual([b['_vars']['m_weight']['_value'] for b in bones], [1.0] * 10)
