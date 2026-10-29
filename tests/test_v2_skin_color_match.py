"""Measured color adaptation must retain detail, state differences and weld."""
import sys
from pathlib import Path
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import v2_physical_skin_material as physical
import v2_skin_color_match as color


class ColorResponseTests(unittest.TestCase):
    def test_natural_reference_matches_actual_stock_target(self):
        source = np.asarray(color.SOURCE_LINEAR_REFERENCE) ** (1/2.2)
        target = np.asarray(color.TARGET_LINEAR_REFERENCE) ** (1/2.2)
        np.testing.assert_allclose(color.diffuse_reference(source, target, 0), target, rtol=1e-14)

    def test_weld_is_original_stock_for_extreme_source_colors(self):
        source = np.asarray([[0, 0, 0], [1, 1, 1], [1, 0, .3]])
        target = np.asarray([[.2, .3, .4], [.4, .5, .6], [.8, .1, 0]])
        np.testing.assert_allclose(color.diffuse_reference(source, target, np.ones(3)), target, atol=1e-15)

    def test_relative_source_detail_and_state_differences_survive(self):
        natural = np.asarray([[.5, .35, .25], [.6, .4, .3]])
        erect = natural * np.asarray([.98, 1.01, 1.04])
        target = np.asarray([[.55, .45, .45], [.55, .45, .45]])
        a = color.diffuse_reference(natural, target, np.zeros(2)) ** 2.2
        b = color.diffuse_reference(erect, target, np.zeros(2)) ** 2.2
        np.testing.assert_allclose(a[1]/a[0], (natural[1]/natural[0])**2.2, rtol=1e-14)
        np.testing.assert_allclose(b/a, (erect/natural)**2.2, rtol=1e-14)

    def test_actual_hash_pinned_calibration_and_both_map_bounds(self):
        donor = ROOT/'v2/build/materials/source-anatomy-01/lod0-material-donor.npz'
        target = ROOT/'v2/build/materials/physical-skin-field-01/lod0-target-uv1.npz'
        stock = ROOT/'v2/build/native-fit-02/build/depot-bb7d8c28a8c3/characters/models/geralt/body/model/body_01_mg__geralt_d01.tga'
        maps = ROOT/'v2/build/materials/original-source-maps-01/textures.json'
        if not all(p.exists() for p in [donor, target, stock, maps]):
            self.skipTest('Private calibration inputs unavailable')
        proof = color.calibration(donor, target, stock, maps)
        self.assertEqual(proof['rows'], 15683)
        self.assertEqual(proof['conservativeFootprintTexels'], 1605696)
        self.assertEqual(len(proof['states']), 2)
        for state in proof['states']:
            self.assertEqual(state['channelsBelowZero'], 0)
            self.assertEqual(state['channelsAboveOne'], 0)
        self.assertNotEqual(proof['states'][0]['nativeSampleMedian'], proof['states'][1]['nativeSampleMedian'])


class ColorGraphTests(unittest.TestCase):
    def setUp(self):
        self.source = ROOT/'v2/build/materials/body-reflectance-02/build/intake'/physical.GRAPH
        if not self.source.exists():
            self.skipTest('Compiled body-reflectance fixture unavailable')

    def upgraded(self, *, diffuse=True, sss=True):
        graph = physical.PhysicalGraph(self.source)
        codes = []
        if diffuse:
            codes.append(('physicalSkinDiffuse(', color.DIFFUSE_CODE))
        if sss:
            codes.append(('sourceSubsurface(', color.SSS_CODE))
        for signature, code in codes:
            node = next(i for i,row in enumerate(graph.objects) if signature.encode() in row[2].get('customCode', ('', b''))[1])
            graph.objects[node][2]['customCode'] = ('String', physical.encoded_string(code))
        return graph

    def inspect_graph(self, graph):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'skin.w2mg'
            path.write_bytes(graph.rebuild())
            return physical.inspect(path)

    def test_historical_reflectance_only_graph_stays_explicit(self):
        proof = physical.inspect(self.source)
        self.assertTrue(proof['bodyMatchedReflectance'])
        self.assertFalse(proof['bodyMatchedColor'])

    def test_complete_color_variant_changes_only_two_functions(self):
        old = physical.PhysicalGraph(self.source)
        new = self.upgraded()
        self.assertEqual(sum(a != b for a,b in zip(old.objects, new.objects)), 2)
        proof = self.inspect_graph(new)
        self.assertTrue(proof['bodyMatchedColor'])
        self.assertEqual(proof['diffuseLinearGains'], list(color.LINEAR_GAINS))
        self.assertFalse(proof['sourceSubsurfaceSRGBDecoded'])
        self.assertEqual(proof['subsurfaceInputDecode'], 'native stock Color times Color')

    def test_diffuse_without_sss_upgrade_is_rejected(self):
        with self.assertRaises(ValueError):
            self.inspect_graph(self.upgraded(sss=False))

    def test_sss_without_diffuse_upgrade_is_rejected(self):
        with self.assertRaises(ValueError):
            self.inspect_graph(self.upgraded(diffuse=False))

    def test_sss_cannot_replace_native_stock_color_with_source_diffuse(self):
        graph = self.upgraded()
        node = next(i for i,row in enumerate(graph.objects) if b'sourceSubsurface(' in row[2].get('customCode', ('', b''))[1])
        graph.rewire(graph.socket(node, 'blendColor'), graph.socket(graph.sampler(graph.parameter('Diffuse')), 'Color'))
        with self.assertRaisesRegex(ValueError, 'SSS'):
            self.inspect_graph(graph)

    def test_real_hlsl_compiler_accepts_complete_color_variant(self):
        proof = physical.validate_custom_functions(body_matched=True, body_color_matched=True)
        self.assertTrue(proof['passed'])
        self.assertFalse(proof['deviceCreated'])


if __name__ == '__main__':
    unittest.main()
