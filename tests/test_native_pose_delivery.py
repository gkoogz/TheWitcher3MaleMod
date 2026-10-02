"""Nonidentity bind rotations expose errors hidden by rest-only pose checks."""
import sys,unittest
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from native_pose_delivery import bone_angles,script_angles
from mod import ROOT

class PoseDeliveryTests(unittest.TestCase):
    def test_controller_matches_bone_local_intrinsic_composition(self):
        rng=np.random.default_rng(7641);script=(ROOT/'probes/runtime/fixedPhysics.ws').read_text()
        for i in range(200):
            bind=Rotation.random(random_state=rng).as_matrix();parent=Rotation.random(random_state=rng)
            q=parent.as_quat();q[:3]=bind.T@q[:3];angles=script_angles(q,script)
            actual=bind@Rotation.from_euler('XYZ',angles,degrees=True).as_matrix()
            np.testing.assert_allclose(actual,parent.as_matrix()@bind,atol=1e-12)
            np.testing.assert_allclose(Rotation.from_euler('XYZ',bone_angles(bind,parent.as_matrix()),degrees=True).as_matrix(),bind.T@parent.as_matrix()@bind,atol=1e-12)

    def test_rest_only_cannot_validate_rotation_delivery(self):
        bind=Rotation.from_euler('xyz',[.3,-.6,.8]).as_matrix();parent=Rotation.from_euler('xyz',[-.5,.7,.4])
        old=bind@Rotation.from_euler('XYZ',parent.as_euler('xyz')).as_matrix()
        self.assertGreater(np.linalg.norm(old-parent.as_matrix()@bind),.5)
