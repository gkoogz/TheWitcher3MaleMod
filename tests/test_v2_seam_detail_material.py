import sys
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import v2_seam_detail_material as detail
import v2_skin_material as skin
import v2_anatomy_material_contract as contract


class SeamStockDetailTests(unittest.TestCase):
    def setUp(self):
        self.graph = ROOT/'v2/build/materials/stock-detail-01/build/intake'/detail.GRAPH
        if not self.graph.exists():
            self.skipTest('Fresh stock-detail graph fixture unavailable')

    def altered(self, edit):
        graph = detail.Graph(self.graph)
        edit(graph)
        with patch.object(detail, 'Graph', return_value=graph):
            with self.assertRaises(ValueError):
                detail.inspect(self.graph)

    def test_actual_native_graph_contract(self):
        proof = detail.inspect(self.graph)
        self.assertEqual(proof['uvIndex'], 1)
        self.assertEqual(proof['detailMaskInputs'], 3)
        self.assertEqual(proof['detailPower'], .5)
        self.assertEqual(proof['detailTile'], [25, 25])

    def test_shared_validator_recognizes_only_complete_stock_detail(self):
        proof = skin.inspect(self.graph)
        self.assertFalse(proof['flatDetailNormal'])
        self.assertEqual(proof['detailMode'], 'stock-seam-uv1')
        self.assertEqual(proof['stockSeamDetail']['uvIndex'], 1)
        self.assertTrue(proof['sourceSpecularSRGBDecoded'])
        self.assertTrue(proof['sourceSubsurfaceSRGBDecoded'])

    def test_stock_detail_without_explicit_marker_cannot_bypass_legacy_guard(self):
        g = detail.Graph(self.graph)
        root = next(i for i, o in enumerate(g.objects) if o[0] == 'CMaterialGraph')
        marker = g.parameter(detail.PARAMETER)
        g.array(root, 'pixelParameterBlocks', [i for i in g.ids(root,'pixelParameterBlocks') if i != marker])
        with patch.object(skin, 'state', return_value=(g.reader,g.imports,g.objects,g.name,g.ids,g.ptr)):
            with self.assertRaises(ValueError):
                skin.inspect(self.graph)

    def test_scalar_contract_requires_verified_graph_and_keeps_legacy_strict(self):
        params = dict(DetailPower=0,DetailAlbedoPower=0,VarianceOffset=1,RSpecScale=0,RSpecBase=1,
                      RSpecScale2=struct.unpack('<f',struct.pack('<f',.2))[0],RSpecBase2=0)
        self.assertEqual(contract.validate_source_scalars(params,None),'flat-source')
        enabled = dict(params,DetailPower=.5)
        with self.assertRaises(ValueError):
            contract.validate_source_scalars(enabled,None)
        proof = skin.inspect(self.graph)
        self.assertEqual(contract.validate_source_scalars(enabled,proof),'stock-seam-uv1')
        with self.assertRaises(ValueError):
            contract.validate_source_scalars(params,proof)
        with self.assertRaises(ValueError):
            contract.validate_source_scalars(dict(enabled,StockSeamAmbient='wrong.xbm'),proof)
        with self.assertRaises(ValueError):
            contract.validate_source_scalars(dict(enabled,DetailNormal='wrong.xbm'),proof)
        with self.assertRaises(ValueError):
            contract.validate_source_scalars(dict(enabled,DetailTile=1),proof)

    def test_source_and_original_native_function_code_unchanged(self):
        before = detail.Graph(ROOT/'v2/build/materials/seam-native-07/build/intake'/detail.GRAPH)
        after = detail.Graph(self.graph)
        old = sorted(o[2]['customCode'] for o in before.objects if 'customCode' in o[2])
        new = sorted(o[2]['customCode'] for o in after.objects if 'customCode' in o[2])
        self.assertEqual(old, new)
        authored_path = self.graph.parents[5]/'authored-skin.w2mg'
        authored = detail.Graph(authored_path) if authored_path.exists() else after
        root = next(i for i, o in enumerate(before.objects) if o[0] == 'CMaterialGraph')
        authored_root = next(i for i, o in enumerate(authored.objects) if o[0] == 'CMaterialGraph')
        self.assertEqual(before.objects[root][3], authored.objects[authored_root][3])
        # Native/source second-lobe route keeps the original Ambient.R output.
        for graph in [before,after]:
            red = graph.socket(graph.sampler(graph.parameter('Ambient')), 'Red')
            second = [graph.ptr(e,'destination') for e in graph.ids(red,'connections') if graph.name(graph.ptr(e,'destination')) == 'In']
            self.assertEqual(len(second), 1)
            self.assertEqual(graph.objects[graph.ptr(second[0],'block')][0], 'CMaterialBlockMathPower')
            self.assertEqual(graph.upstream(second[0]), red)

    def test_wrong_uv_channel_rejected(self):
        def edit(g):
            sampler = g.sampler(g.parameter(detail.PARAMETER))
            node = g.ptr(g.upstream(g.socket(sampler,'UV')), 'block')
            g.objects[node][2]['coordinatesIndex'] = ('Int32', struct.pack('<i',0))
        self.altered(edit)

    def test_mask_cannot_use_tiled_detail_coordinates(self):
        def edit(g):
            sampler = g.sampler(g.parameter(detail.PARAMETER))
            detail_sampler = g.sampler(g.parameter('DetailNormal'))
            g.rewire(g.socket(sampler,'UV'), g.upstream(g.socket(detail_sampler,'UV')))
        self.altered(edit)

    def test_wrong_stock_mask_channel_rejected(self):
        def edit(g):
            sampler = g.sampler(g.parameter(detail.PARAMETER))
            red = g.socket(sampler,'Red')
            mask_input = g.ptr(g.ids(red,'connections')[0],'destination')
            g.rewire(mask_input, g.socket(sampler,'Green'))
        self.altered(edit)

    def test_existing_ambient_red_is_not_seam_weight(self):
        def edit(g):
            sampler = g.sampler(g.parameter(detail.PARAMETER))
            mask = g.ptr(g.ptr(g.ids(g.socket(sampler,'Red'),'connections')[0],'destination'),'block')
            ambient = g.sampler(g.parameter('Ambient'))
            g.rewire(g.socket(mask,'B'), g.socket(ambient,'Red'))
        self.altered(edit)

    def test_flat_detail_dependency_rejected(self):
        self.altered(lambda g:g.texture(g.parameter('DetailNormal'), 'engine\\textures\\editor\\normal.xbm'))

    def test_zero_detail_power_rejected(self):
        self.altered(lambda g:g.objects[g.parameter('DetailPower')][2].update(scalar=('Float',struct.pack('<f',0))))

    def test_wrong_name_hash_convention_rejected(self):
        graph = detail.Graph(self.graph)
        with patch.object(detail, 'native_name_hash', return_value=123):
            with self.assertRaises(ValueError):
                graph.rebuild()


if __name__ == '__main__':
    unittest.main()
