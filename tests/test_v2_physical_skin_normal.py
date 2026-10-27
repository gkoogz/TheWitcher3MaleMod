from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from v2_physical_skin_normal import reference, NORMAL_CODE


class PhysicalNormalTests(unittest.TestCase):
    def value(self,source=(.6,.4,.96,1),stock=(.4,.6,.96,1),w=.5,frame=None,uvx=(1,0),uvy=(0,1),rt=False):
        return reference(source,stock,w,[1,0,0],[0,1,0],uvx,uvy,np.eye(3)if frame is None else frame,rt)

    def test_encoded_endpoints_pass_through_exactly(self):
        a=np.asarray([.5555,.1234,.9876,.75],np.float32);b=np.asarray([.77,.31,.89,1],np.float32)
        for rt in [False,True]:
            np.testing.assert_array_equal(self.value(a,b,0,rt=rt),a)
            np.testing.assert_array_equal(self.value(a,b,1,rt=rt),b)

    def test_flat_maps_preserve_geometric_normal_with_skew(self):
        frame=np.array([[1,.1,.25],[.2,1,0],[.65,.2,1.]])
        for w in np.linspace(0,1,21):
            out=self.value((.5,.5,1,1),(.5,.5,1,1),w,frame)
            world=frame@(out[:3]*2-1)
            np.testing.assert_allclose(world/np.linalg.norm(world),frame[:,2]/np.linalg.norm(frame[:,2]),atol=1e-13)

    def test_180_degree_native_tangent_twist_stays_finite(self):
        frame=np.diag([-1.,-1.,1.])
        for w in np.linspace(0,1,101):self.assertTrue(np.isfinite(self.value(w=w,frame=frame)).all())

    def test_mirrored_uv_has_expected_horizontal_orientation(self):
        source=(.5,.5,1,1);stock=(.7,.5,.96,1)
        a=self.value(source,stock,.5);b=self.value(source,stock,.5,uvx=(-1,0))
        self.assertLess(b[0],a[0]);self.assertTrue(np.isfinite(b).all())

    def test_degenerate_uv_and_native_basis_use_explicit_ts_fallback(self):
        expected=np.asarray([.5,.5,.96,1])
        np.testing.assert_allclose(self.value(uvx=(0,0),uvy=(0,0)),expected)
        np.testing.assert_allclose(self.value(frame=np.zeros((3,3))),expected)

    def test_rt_is_explicit_encoded_ts_blend(self):
        np.testing.assert_allclose(self.value(rt=True),[.5,.5,.96,1])

    def test_derivatives_precede_raster_endpoint_branches(self):
        raster=NORMAL_CODE.split('#else',1)[1]
        self.assertLess(raster.index('ddx(position.xyz)'),raster.index('if(w<=0)'))
        self.assertIn('defined(RT_MULTI_MATERIAL_GENERATION_TYPE) || ST_RAYTRACING',NORMAL_CODE)


if __name__=='__main__':unittest.main()
