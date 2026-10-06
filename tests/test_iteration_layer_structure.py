"""Authored input ownership tests; native cook/gameplay are separate gates."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from prepare_iteration_world import author, WORLD, LAYER


class NativeLayerStructureTests(unittest.TestCase):
    def test_native_source_has_no_manually_owned_embedded_group(self):
        result = author({'floor': {'extentMeters': 32, 'thicknessMeters': .5},
                         'spawnMeters': [0, 0, .03]}, True)
        chunks = result[WORLD]['_chunks']
        fields = chunks['CGameWorld #0']['_vars']
        self.assertTrue(fields['newLayerGroupFormat']['_value'])
        self.assertFalse(fields['hasEmbeddedLayerInfos']['_value'])
        self.assertNotIn('Firstlayer', fields)
        self.assertFalse(any(c['_type'] in ('CLayerGroup', 'CLayerInfo') for c in chunks.values()))
        self.assertEqual(fields['terrainClipMap']['_vars']['_reference']['_value'], 'CClipMap #4')
        self.assertIn(LAYER, result)

    def test_control_only_differs_in_native_layer_ownership(self):
        contract = {'floor': {'extentMeters': 32, 'thicknessMeters': .5},
                    'spawnMeters': [0, 0, .03]}
        control = author(contract)
        native = author(contract, True)
        self.assertEqual({p: r for p, r in control.items() if p != WORLD},
                         {p: r for p, r in native.items() if p != WORLD})
        for key in ('CPathLibWorld #3', 'CClipMap #4'):
            self.assertEqual(control[WORLD]['_chunks'][key], native[WORLD]['_chunks'][key])


if __name__ == '__main__':
    unittest.main()
