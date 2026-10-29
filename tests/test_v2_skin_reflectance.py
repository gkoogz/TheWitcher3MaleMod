"""Native-F0 adaptation must preserve the weld and original spatial detail."""
import sys
from pathlib import Path
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import v2_physical_skin_material as physical
import v2_skin_reflectance as reflectance


class ResponseTests(unittest.TestCase):
    def test_weld_is_exact_stock_even_for_extreme_source_colors(self):
        colors = np.asarray([[0, 0, 0], [1, 1, 1], [0, .2, 1], [.8, 0, .1]])
        ambient = np.asarray([[.9, .6, .08], [.8, .7, .15], [1, .55, .3], [.7, .5, 0]])
        actual = reflectance.specular_reference(colors, ambient, np.ones(4))
        expected = np.power(np.asarray([239, 241, 255]) / 255, 2.2) * .25 * ambient[:, 2, None]
        np.testing.assert_array_equal(actual, expected)

    def test_legacy_blue_phong_chroma_cannot_reappear(self):
        ambient = np.broadcast_to([1, .6, .1], (3, 3))
        colors = np.asarray([[.05, .1, .8], [.7, .02, .01], [.1, .8, .1]])
        actual = reflectance.specular_reference(colors, ambient, np.asarray([0, .5, .9]))
        chroma = actual / actual[:, 2, None]
        stock = np.power(np.asarray([239, 241, 255]) / 255, 2.2)
        np.testing.assert_allclose(chroma, np.broadcast_to(stock/stock[2], (3, 3)), rtol=1e-14)

    def test_spatial_detail_survives_and_tapers_to_stock_at_weld(self):
        ambient = np.broadcast_to([1, .6, .1], (2, 3))
        colors = np.asarray([[.1, .1, .1], [.2, .2, .2]])
        source = reflectance.specular_reference(colors, ambient, np.zeros(2))
        middle = reflectance.specular_reference(colors, ambient, np.ones(2)*.5)
        stock = reflectance.specular_reference(colors, ambient, np.ones(2))
        self.assertTrue(np.all(source[1] > source[0]))
        np.testing.assert_allclose(middle, (source+stock)*.5, rtol=1e-14)
        np.testing.assert_array_equal(stock[0], stock[1])

    def test_actual_canonical_reference_is_reproducible(self):
        donor = ROOT/'v2/build/materials/source-anatomy-01/lod0-material-donor.npz'
        specular = ROOT.parent/'Work/wolverine/payload/SharedBody-specular.dds'
        if not donor.exists() or not specular.exists():
            self.skipTest('Canonical private inputs unavailable')
        proof = reflectance.calibration(donor, specular)
        self.assertEqual(proof['rows'], 15683)
        self.assertAlmostEqual(proof['referenceLuminance'], reflectance.REFERENCE_LUMINANCE, places=13)
        self.assertGreater(proof['spatialDetailRange'][1], 1.4)
        self.assertGreater(proof['spatialDetailRange'][0], .9)


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.source = ROOT/'v2/build/materials/waist-join-01/build/intake'/physical.GRAPH
        if not self.source.exists():
            self.skipTest('Current private material fixture unavailable')

    def upgrade(self, *, ambient=True):
        graph = physical.PhysicalGraph(self.source)
        codes = [('physicalSkinSpecular(', reflectance.SPECULAR_CODE)]
        if ambient:
            codes.append(('physicalSkinAmbient(', reflectance.AMBIENT_CODE))
        for signature, code in codes:
            node = next(i for i, row in enumerate(graph.objects) if signature.encode() in row[2].get('customCode', ('', b''))[1])
            graph.objects[node][2]['customCode'] = ('String', physical.encoded_string(code))
        return graph

    def test_historical_material_stays_valid_and_explicit(self):
        proof = physical.inspect(self.source)
        self.assertFalse(proof['bodyMatchedReflectance'])
        self.assertEqual(proof['specularStrength'], [1, 1.5, 2])

    def test_complete_variant_changes_only_two_function_sources(self):
        original = physical.PhysicalGraph(self.source)
        changed = self.upgrade()
        differences = [i for i, (a,b) in enumerate(zip(original.objects, changed.objects)) if a != b]
        self.assertEqual(len(differences), 2)
        for node in differences:
            self.assertEqual(set(original.objects[node][2]) ^ set(changed.objects[node][2]), set())
            for key in original.objects[node][2]:
                if key != 'customCode':
                    self.assertEqual(original.objects[node][2][key], changed.objects[node][2][key])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'skin.w2mg'
            path.write_bytes(changed.rebuild())
            proof = physical.inspect(path)
            self.assertTrue(proof['bodyMatchedReflectance'])
            self.assertTrue(proof['normalComplete'])
            self.assertIsNone(proof['specularStrength'])

    def test_half_applied_variant_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'skin.w2mg'
            path.write_bytes(self.upgrade(ambient=False).rebuild())
            with self.assertRaisesRegex(ValueError, 'physicalSkinAmbient'):
                physical.inspect(path)

    def test_actual_hlsl_compiler_accepts_matched_response(self):
        proof = physical.validate_custom_functions(body_matched=True)
        self.assertTrue(proof['passed'])
        self.assertFalse(proof['deviceCreated'])


if __name__ == '__main__':
    unittest.main()
