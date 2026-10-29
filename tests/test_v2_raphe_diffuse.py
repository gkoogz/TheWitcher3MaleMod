"""Bounded diffuse repair: endpoints, same-state taps, channel isolation."""
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import v2_raphe_diffuse as raphe
import v2_physical_skin_material as physical


class ResponseTests(unittest.TestCase):
    def uv(self,x,y):
        return (np.asarray([x,y],dtype=float)+.5)/4096

    def test_outside_mask_is_exact_for_rgb_and_alpha(self):
        uv=np.asarray([self.uv(3000,650),self.uv(2550,580),self.uv(2600,720),self.uv(3400,650)])
        original=np.asarray([[.2,.3,.4,.1],[1,0,.5,.25],[.35,.6,.9,.75],[.123,.456,.789,.456]])
        result=raphe.diffuse_reference(uv,original,np.zeros_like(original),np.ones_like(original))
        self.assertTrue(np.array_equal(result,original))

    def test_gap_center_interpolates_linear_rgb_and_keeps_original_alpha(self):
        uv=self.uv((2509+2681)/2,650)
        original=np.asarray([.68,.47,.32,.123456789])
        left=np.asarray([.2,.4,.6,0]);right=np.asarray([.8,.6,.4,1])
        result=raphe.diffuse_reference(uv,original,left,right)
        expected=((left[:3]**2.2+right[:3]**2.2)*.5)**(1/2.2)
        np.testing.assert_allclose(result[:3],expected,atol=2e-15)
        self.assertEqual(result[3],original[3])

    def test_mask_uses_expanded_plateau_and_bounded_smooth_feather(self):
        uv=np.asarray([self.uv(2509-6,650),self.uv(2509-4,650),
                       self.uv(2509-2,650),self.uv(2509,650)])
        _,_,mask,_=raphe.sampling_reference(uv)
        np.testing.assert_allclose(mask,[0,.5,1,1],atol=1e-14)
        eps=1e-5
        samples=np.asarray([self.uv(2509-6+eps,650),self.uv(2509-2-eps,650)])
        _,_,near,_=raphe.sampling_reference(samples)
        self.assertLess(near[0],1e-8)
        self.assertGreater(near[1],1-1e-8)

    def test_donor_taps_use_exact_texel_center_convention_and_inset(self):
        left,right,mask,_=raphe.sampling_reference(self.uv(2595,650))
        np.testing.assert_array_equal(left,self.uv(2509-12,650))
        np.testing.assert_array_equal(right,self.uv(2681+12,650))
        self.assertEqual(mask,1)

    def test_state_specific_donor_changes_remain_visible(self):
        uv=self.uv(2595,650);original=np.asarray([.68,.47,.32,1])
        a=np.asarray([.4,.3,.2,.1]);b=np.asarray([.6,.5,.4,.9])
        natural=raphe.diffuse_reference(uv,original,a,b)
        erect=raphe.diffuse_reference(uv,original,a*.9,b*.9)
        np.testing.assert_allclose(erect[:3],natural[:3]*.9,atol=1e-14)
        self.assertEqual(erect[3],1)

    def test_zero_width_apex_and_vertical_caps_do_not_modify_source(self):
        uv=np.asarray([self.uv(2630,592),self.uv(3517,590),
                       self.uv(2600,685),self.uv(3550,708)])
        _,_,mask,_=raphe.sampling_reference(uv)
        np.testing.assert_array_equal(mask,np.zeros(4))

    def test_actual_inserted_seam_vertices_and_faces_cannot_reach_support(self):
        source=Path(physical.__file__).resolve().parents[1]
        donor=source/'v2/build/materials/source-anatomy-01/lod0-material-donor.npz'
        if not donor.exists():
            self.skipTest('Private canonical donor unavailable')
        data=np.load(donor)
        _,_,mask,_=raphe.sampling_reference(data['moduleUV'])
        self.assertEqual(int((mask[:17528]>0).sum()),174)
        self.assertTrue(np.all(mask[17528:]==0))
        self.assertTrue(np.all(data['seamBlend'][mask>0]==0))
        inserted=np.any(data['moduleFaces']>=17528,axis=1)
        self.assertLess(float(data['moduleUV'][data['moduleFaces'][inserted],1].max()),588/4096)

    def test_actual_canonical_band_colors_are_replaced_by_adjacent_state_tissue(self):
        from PIL import Image
        from bake_v2_skin_textures import sample
        source=Path(physical.__file__).resolve().parents[1]
        path=source/'v2/build/materials/original-source-maps-01/lod0-natural-diffuse.tga'
        if not path.exists():
            self.skipTest('Private canonical diffuse unavailable')
        uv=np.asarray([[.883226191988373,.16702678145591587],
                       [.6377481955200269,.16538125143957177]])
        image=np.asarray(Image.open(path).convert('RGBA'))
        original=sample(image,uv)/255
        left_uv,right_uv,mask,_=raphe.sampling_reference(uv)
        result=raphe.diffuse_reference(uv,original,sample(image,left_uv)/255,sample(image,right_uv)/255)
        self.assertTrue(np.all(mask==1))
        self.assertTrue(np.all(result[:,:2]<original[:,:2]))
        np.testing.assert_array_equal(result[:,3],original[:,3])
        # Exact stored filler texels coexist with DXT's neighboring green119
        # blocks; bilinear interpolation must retain that observed variation.
        np.testing.assert_array_equal(image[684,3617],[173,121,82,255])
        np.testing.assert_array_equal(image[677,2612],[173,121,82,255])
        np.testing.assert_allclose(original[:,:3]*255,[[173,121,82],[173,121,82]],rtol=0,atol=2)

    @unittest.skipUnless(sys.platform=='win32','Windows native shader compiler required')
    def test_native_vector4_wrapper_rejects_the_failed_float2_body(self):
        from unittest.mock import patch
        bad=raphe.LEFT_UV_CODE.replace('float4 rapheDiffuseLeftUV(', 'float2 rapheDiffuseLeftUV(')
        bad=bad.replace('return float4(', 'return (').replace(',0.0,0.0);', ');')
        self.assertNotEqual(bad,raphe.LEFT_UV_CODE)
        with patch.dict(raphe.CODES,{'rapheDiffuseLeftUV':bad}):
            with self.assertRaisesRegex(ValueError,'native vector4=True'):
                raphe.validate_custom_functions()

    @unittest.skipUnless(sys.platform=='win32','Windows native shader compiler required')
    def test_actual_shader_compiler_accepts_both_donor_sampling_paths(self):
        proof=raphe.validate_custom_functions()
        self.assertTrue(proof['passed'])
        self.assertFalse(proof['deviceCreated'])


class GraphTests(unittest.TestCase):
    def setUp(self):
        source=Path(physical.__file__).resolve().parents[1]
        self.path=source/'v2/build/materials/body-visual-03/build/intake'/physical.GRAPH
        if not self.path.exists():
            self.skipTest('Private compiled body-color03 fixture unavailable')

    def graph(self):
        return raphe.build(self.path)[0]

    def test_historical_graph_stays_explicit_and_original_functions_unchanged(self):
        old=physical.PhysicalGraph(self.path)
        self.assertEqual(raphe.inspect_graph(old),dict(rapheDiffuseRepair=False))
        new=self.graph()
        old_codes=[o[2]['customCode']for o in old.objects if 'customCode'in o[2]]
        new_codes=[o[2]['customCode']for o in new.objects if 'customCode'in o[2]]
        self.assertEqual(new_codes[:len(old_codes)],old_codes)
        self.assertEqual(new.imports,old.imports)
        self.assertEqual(len(new_codes)-len(old_codes),3)
        self.assertEqual(len(new.ids(raphe.original_diffuse_sampler(new))),len(old.ids(raphe.original_diffuse_sampler(old))))

    def test_serialized_repair_keeps_three_samplers_on_same_state_parameter(self):
        graph=self.graph()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'skin.w2mg';path.write_bytes(graph.rebuild())
            result=raphe.inspect_graph(physical.PhysicalGraph(path))
        self.assertTrue(result['rapheDiffuseRepair'])
        self.assertEqual(len(result['tapSamplers']),2)
        self.assertTrue(result['originalAlphaPreserved'])

    def test_complete_physical_inspector_accepts_only_verified_diffuse_route(self):
        graph=self.graph()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'skin.w2mg';path.write_bytes(graph.rebuild())
            proof=physical.inspect(path)
        self.assertTrue(proof['rapheDiffuseRepair'])
        self.assertTrue(proof['bodyMatchedColor'])
        self.assertTrue(proof['bodyMatchedReflectance'])
        self.assertTrue(proof['normalComplete'])
        self.assertFalse(proof['rapheDiffuseScope']['otherMaterialChannelsChanged'])
        self.assertFalse(physical.inspect(self.path)['rapheDiffuseRepair'])

    def test_combined_native_hlsl_helpers_compile_with_raphe_variant(self):
        proof=physical.validate_custom_functions(body_matched=True,body_color_matched=True,raphe_diffuse=True)
        self.assertTrue(proof['passed'])
        with self.assertRaises(ValueError):
            physical.validate_custom_functions(raphe_diffuse=True)

    def test_partial_or_altered_function_is_rejected(self):
        graph=self.graph();proof=raphe.inspect_graph(graph)
        node=proof['nodes']['rapheDiffuseRepair']
        graph.objects[node][2]['customCode']=('String',physical.encoded_string(raphe.REPAIR_CODE.replace('-6.0','-7.0')))
        with self.assertRaisesRegex(ValueError,'altered'):
            raphe.inspect_graph(graph)

    def test_donor_rebound_to_another_parameter_is_rejected(self):
        graph=self.graph();proof=raphe.inspect_graph(graph)
        tap=proof['tapSamplers']['left']
        graph.rewire(graph.socket(tap,'Texture'),graph.socket(graph.parameter('Normal'),'Texture'))
        with self.assertRaisesRegex(ValueError,'same-state'):
            raphe.inspect_graph(graph)

    def test_donor_wrong_uv_or_bypass_is_rejected(self):
        graph=self.graph();proof=raphe.inspect_graph(graph)
        tap=proof['tapSamplers']['left']
        graph.rewire(graph.socket(tap,'UV'),proof['uvOutput'])
        with self.assertRaises(ValueError):
            raphe.inspect_graph(graph)

    def test_repair_leaking_to_sss_is_rejected(self):
        graph=self.graph();proof=raphe.inspect_graph(graph)
        node=next(i for i,o in enumerate(graph.objects)if b'sourceSubsurface('in o[2].get('customCode',('',b''))[1])
        graph.rewire(graph.socket(node,'albedo'),proof['repairOutput'])
        with self.assertRaisesRegex(ValueError,'leaks'):
            raphe.inspect_graph(graph)

    def test_partial_repair_without_actual_output_route_is_rejected(self):
        graph=self.graph();proof=raphe.inspect_graph(graph)
        node=next(i for i,o in enumerate(graph.objects)if b'physicalSkinDiffuse('in o[2].get('customCode',('',b''))[1])
        graph.rewire(graph.socket(node,'albedo'),proof['rawOutput'])
        with self.assertRaises(ValueError):
            raphe.inspect_graph(graph)


if __name__=='__main__':
    unittest.main()
