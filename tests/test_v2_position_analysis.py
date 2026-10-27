import struct,sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from analyze_v2_position_capture import compare,skin_selected


class SelectedPoseOracle(unittest.TestCase):
    def scene(self,z=0):
        cpu=np.array([[0.,0,0],[1,0,0],[0,1,0]],np.float32)
        faces=np.array([[0,1,2]])
        world=np.array([[[.2,.2,z,1],[.3,.2,z,1]],[[.2,.3,z,1],[0,0,0,0]]],np.float32)
        return cpu,faces,world

    def test_actual_plane_offset_is_measured(self):
        a=compare(*self.scene())[0];b=compare(*self.scene(.01))[0]
        self.assertEqual(a['absolutePlaneErrorMeters']['maximum'],0)
        self.assertAlmostEqual(b['absolutePlaneErrorMeters']['p99'],.01,places=8)

    def test_missing_and_wrong_primitive_evidence_rejected(self):
        c,f,w=self.scene();w[:,:,3]=0
        with self.assertRaisesRegex(ValueError,'Missing/invalid'):compare(c,f,w)
        c,f,w=self.scene();w[w[:,:,3]>0,3]=2
        with self.assertRaisesRegex(ValueError,'primitive ID'):compare(c,f,w)

    def test_nonfinite_world_rejected(self):
        c,f,w=self.scene();w[0,0,0]=np.nan
        with self.assertRaisesRegex(ValueError,'Missing/invalid'):compare(c,f,w)

    def binding(self):
        return dict(totalVertices=1,resources=[dict(firstVertex=0,vertexCount=1,
            scale=[1,1,1],bias=[0,0,0],palette=[(0,np.eye(4,dtype=np.float32).reshape(-1))])])

    def test_decoded_pose_and_actor_translation(self):
        pose=np.tile(np.eye(4,dtype=np.float32),(95,1,1));pose[0,:3,3]=[10,20,30];pose[1,:3,3]=[.1,-.2,.3]
        row=struct.pack('<3f4B4B2I',1,2,3,0,0,0,0,255,0,0,0,0,0)
        world=skin_selected(self.binding(),row,pose.tobytes())
        np.testing.assert_allclose(world,[[11.1,21.8,33.3]],rtol=0,atol=2e-6)

    def test_zero_weights_and_short_pose_rejected(self):
        pose=np.tile(np.eye(4,dtype=np.float32),(95,1,1)).tobytes();row=bytes(28)
        with self.assertRaisesRegex(ValueError,'Zero skin'):skin_selected(self.binding(),row,pose)
        with self.assertRaisesRegex(ValueError,'dimensions'):skin_selected(self.binding(),row,pose[:-4])


if __name__=='__main__':unittest.main()
