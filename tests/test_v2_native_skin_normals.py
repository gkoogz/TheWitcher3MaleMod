import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from bake_v2_native_skin_normals import native_transfer,unit

class ActualNativeFrameTransfer(unittest.TestCase):
 def test_coincident_nonorthogonal_native_frames_keep_ts_direction(self):
  # Native packed shader axes need not form an orthonormal matrix. The exact
  # whole-row weld must still preserve the stock TS vector, unlike M.T @ M.
  native=np.array([[.05,0,0],[0,-1,0],[np.sqrt(1-.05**2),0,1.]])
  transfer=native_transfer(native,native)
  np.testing.assert_allclose(transfer,np.eye(3),atol=1e-12)
  self.assertGreater(float(np.max(abs(native.T@native-np.eye(3)))),.9)
 def test_distinct_native_frames_preserve_world_normal_not_uv_proxy(self):
  body=np.array([[.8,0,.2],[.1,-1,0],[.58,0,.98]])
  module=np.array([[.2,-.98,0],[.95,.1,.2],[.3,.15,.98]])
  values=unit(np.random.default_rng(78).normal(size=(2000,3)))
  transferred=unit(values@native_transfer(module,body).T)
  actual=unit(transferred@module.T);desired=unit(values@body.T)
  np.testing.assert_allclose(actual,desired,atol=1e-12)
  old=unit(unit(values@(module.T@body).T)@module.T)
  self.assertGreater(float(np.max(np.linalg.norm(old-desired,axis=1))),.05)

if __name__=='__main__':unittest.main()
