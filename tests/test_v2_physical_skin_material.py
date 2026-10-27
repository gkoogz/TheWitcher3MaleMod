"""Physical-channel topology checks; an incomplete normal graph cannot adopt."""
import sys
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import v2_physical_skin_material as physical


class PhysicalSkinTests(unittest.TestCase):
    def setUp(self):
        self.path=ROOT/'v2/build/materials/physical-skin-01/draft-channels'/physical.GRAPH
        if not self.path.exists():self.skipTest('Owned physical-channel draft fixture unavailable')

    def altered(self,edit):
        g=physical.PhysicalGraph(self.path)
        edit(g)
        with patch.object(physical,'PhysicalGraph',return_value=g):
            with self.assertRaises(ValueError):physical.inspect(self.path,require_complete=False)

    def test_draft_channels_are_explicitly_not_adoptable(self):
        proof=physical.inspect(self.path,require_complete=False)
        self.assertTrue(proof['physicalVariant'])
        self.assertFalse(proof['normalComplete'])
        self.assertFalse(proof['bakedAmbientActive'])
        with self.assertRaisesRegex(ValueError,'normal transport remains incomplete'):
            physical.inspect(self.path)

    def test_old_baked_mask_cannot_reach_native_output(self):
        def edit(g):
            output=next(i for i,o in enumerate(g.objects)if o[0]=='CMaterialBlockOutputColorSkin')
            g.rewire(g.socket(output,'Specularity'),g.socket(g.sampler(g.parameter('Ambient')),'Color'))
        self.altered(edit)

    def test_source_uv0_must_remain_original(self):
        def edit(g):
            source=g.sampler(g.parameter('Diffuse'))
            target=g.sampler(g.parameter(physical.MARKER))
            g.rewire(g.socket(source,'UV'),g.upstream(g.socket(target,'UV')))
        self.altered(edit)

    def test_stock_target_cannot_use_source_uv(self):
        def edit(g):
            target=g.sampler(g.parameter(physical.MARKER))
            uv0=next(i for i,o in enumerate(g.objects)if o[0]=='CMaterialBlockTexCoords'and o[2].get('coordinatesIndex',('Int32',bytes(4)))==('Int32',bytes(4)))
            g.rewire(g.socket(target,'UV'),g.socket(uv0,'UV'))
        self.altered(edit)

    def test_r8_variant_preserves_original_native_collapse_capability(self):
        self.altered(lambda g:g.objects[0][2].update(canUseOnCollapsableObjects=('Bool',b'\0')))

    def test_specular_cannot_drop_source_srgb_conversion(self):
        def edit(g):
            node=next(i for i,o in enumerate(g.objects)if b'physicalSkinSpecular('in o[2].get('customCode',('',b''))[1])
            g.objects[node][2]['customCode']=('String',physical.encoded_string(physical.SPECULAR_CODE.replace('1.5','1.0')))
        self.altered(edit)

    def test_source_sss_must_decode_original_not_mixed_diffuse(self):
        def edit(g):
            sss=next(i for i,o in enumerate(g.objects)if b'sourceSubsurface('in o[2].get('customCode',('',b''))[1])
            diffuse=next(i for i,o in enumerate(g.objects)if b'physicalSkinDiffuse('in o[2].get('customCode',('',b''))[1])
            g.rewire(g.socket(sss,'albedo'),g.socket(diffuse,'Out'))
        self.altered(edit)

    def test_native_detail_strength_cannot_be_silently_disabled(self):
        self.altered(lambda g:g.objects[g.parameter('DetailPower')][2].update(scalar=('Float',struct.pack('<f',0))))

    def test_actual_native_basis_and_world_position_nodes_roundtrip(self):
        donor=ROOT/'v2/build/materials/carriers-09/build/intake/characters/malemod/garments/fabric.w2mg'
        if not donor.exists():self.skipTest('Closed native WorldPosition donor unavailable')
        source=ROOT/'v2/build/materials/target-uv1-03/build/intake'/physical.GRAPH
        observed={}
        def weight(g,color):
            _,out=g.custom('float physicalSkinDecodeWeight(float offset,float4 albedo,float4 blendColor){return saturate(albedo.r);}',
                           dict(offset=g.socket(g.parameter('VarianceOffset'),'Value'),albedo=color,blendColor=color))
            return out,dict(encoding='R8')
        def normal(g,ctx):
            observed.update(g.raw_native_basis(ctx['weight']))
            position,proof=g.world_position(donor)
            observed['position']=position
            self.assertEqual(proof['export'],215)
            return dict(complete=False,reason='Test built-in provenance only')
        g,proof=physical.build(source,weight,normal)
        with tempfile.TemporaryDirectory(dir=self.path.parents[6])as folder:
            target=Path(folder)/'builtins.w2mg'
            target.write_bytes(g.rebuild())
            parsed=physical.PhysicalGraph(target)
            for key in ['nativeT','nativeB','nativeN']:
                node=parsed.ptr(observed[key],'block')
                self.assertEqual(parsed.objects[node][0],'CMaterialBlockTangentToWorld')
            node=parsed.ptr(observed['position'],'block')
            self.assertEqual(parsed.objects[node][0],'CMaterialBlockWorldPosition')
            self.assertFalse(proof['normalComplete'])


class CompletePhysicalSkinTests(unittest.TestCase):
    def setUp(self):
        self.path=ROOT/'v2/build/materials/physical-skin-01/build/intake'/physical.GRAPH
        if not self.path.exists():self.skipTest('Complete owned physical graph unavailable')

    def altered(self,edit):
        g=physical.PhysicalGraph(self.path);edit(g)
        with patch.object(physical,'PhysicalGraph',return_value=g):
            with self.assertRaises(ValueError):physical.inspect(self.path)

    def normal(self,g):
        return next(i for i,o in enumerate(g.objects)if b'physicalSkinNormalTransport('in o[2].get('customCode',('',b''))[1])

    def test_complete_shared_validator_and_physical_instance_contract(self):
        import v2_skin_material as skin
        import v2_anatomy_material_contract as contract
        proof=skin.inspect(self.path)
        self.assertTrue(proof['normalComplete'])
        self.assertEqual(proof['detailMode'],'physical-stock-uv1')
        params=dict(DetailPower=.5,DetailAlbedoPower=0,VarianceOffset=1,RSpecScale=0,RSpecBase=1,
                    RSpecScale2=struct.unpack('<f',struct.pack('<f',.2))[0],RSpecBase2=0)
        self.assertEqual(contract.validate_source_scalars(params,proof),'physical-stock-uv1')
        with self.assertRaises(ValueError):contract.validate_source_scalars(dict(params,Ambient='old-baked.xbm'),proof)
        with self.assertRaises(ValueError):contract.validate_source_scalars(params,dict(proof,normalComplete=False))

    def test_stock_normal_cannot_use_source_atlas(self):
        def edit(g):
            g.rewire(g.socket(self.normal(g),'stockEncoded'),g.socket(g.sampler(g.parameter('Normal')),'Color'))
        self.altered(edit)

    def test_normal_cannot_use_postmapped_normal_as_geometric_basis(self):
        def edit(g):
            node=self.normal(g)
            g.rewire(g.socket(node,'nativeN'),g.upstream(g.socket(node,'nativeT')))
        self.altered(edit)

    def test_native_rnm_arithmetic_is_immutable(self):
        def edit(g):
            node=next(i for i,o in enumerate(g.objects)if b'float4 normBlend('in o[2].get('customCode',('',b''))[1])
            g.objects[node][2]['customCode']=('String',physical.encoded_string('float4 normBlend(){return 0;}'))
        self.altered(edit)

    def test_normal_transport_cannot_silently_normalize_endpoint(self):
        def edit(g):
            node=self.normal(g)
            from v2_physical_skin_normal import NORMAL_CODE
            g.objects[node][2]['customCode']=('String',physical.encoded_string(NORMAL_CODE.replace('return sourceEncoded;','return normalize(sourceEncoded);')))
        self.altered(edit)


if __name__=='__main__':unittest.main()
