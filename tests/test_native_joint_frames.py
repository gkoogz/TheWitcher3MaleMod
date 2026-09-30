import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from native_joint_frames import orient_chain,verify_rest_axes


class NativeFrameTests(unittest.TestCase):
    def test_identity_cage_is_rejected_and_oriented_bind_stays_at_rest(self):
        w=np.tile(np.eye(4),(10,1,1));w[:8,1,3]=np.linspace(0,35,8);w[:8,2,3]=np.linspace(90,115,8)
        with self.assertRaises(ValueError):verify_rest_axes(w)
        fixed=orient_chain(w);verify_rest_axes(fixed)
        np.testing.assert_array_equal(fixed[:,:3,3],w[:,:3,3])
        # With solver output equal to the aligned rest frame, skinning must be
        # identity. Changing only the skeleton while keeping old skin binds fails.
        for old,new in zip(w[:7],fixed[:7]):
            np.testing.assert_allclose(new@np.linalg.inv(new),np.eye(4),atol=1e-12)
            self.assertGreater(np.linalg.norm(new@np.linalg.inv(old)-np.eye(4)),.1)
        np.testing.assert_array_equal(fixed[8:],w[8:])
