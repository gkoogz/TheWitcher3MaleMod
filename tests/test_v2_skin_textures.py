import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from bake_v2_skin_textures import source_normal,encode_normal,unit,frames,raster,pad_cut_edge,sample,srgb_to_linear,linear_to_srgb,enforce_boundary

class SourceSkinTextures(unittest.TestCase):
 def test_source_normal_z_is_unsigned_positive(self):
  raw=np.array([[128,128,128],[192,64,64],[0,255,255]],np.uint8)
  expected=raw.astype(float)/255*2;expected[:,:2]-=1;expected=unit(expected)
  np.testing.assert_allclose(source_normal(raw),expected,atol=1e-7)
  np.testing.assert_allclose(source_normal(np.array([[128,128,128]],np.uint8))[0,2],.9999846,atol=1e-6)
 def test_native_quantization_preserves_source_direction(self):
  raw=np.random.default_rng(41).integers(0,256,(20000,3),dtype=np.uint8);n=source_normal(raw)
  decoded=unit(encode_normal(n).astype(float)/255*2-1)
  angle=np.degrees(np.arccos(np.clip(np.sum(n*decoded,axis=1),-1,1)))
  self.assertLess(float(angle.max()),.4)
 def test_frames_account_for_v_orientation(self):
  p=np.array([[0.,0,0],[1,0,0],[0,1,0]]);f=np.array([[0,1,2]]);n=np.tile([0.,0,1],(3,1));uv=p[:,:2]
  a=frames(p,f,n,uv);b=frames(p,f,n,uv*np.array([1,-1]))
  np.testing.assert_allclose(a[0],np.eye(3));np.testing.assert_allclose(b[0],np.diag([1,-1,1]))
 def test_gutter_does_not_replace_valid_neighbor_chart(self):
  uv=np.array([[.3,.3],[.6,.3],[.3,.6],[.62,.3],[.85,.3],[.62,.6]])
  faces=np.array([[0,1,2],[3,4,5]]);attrs=np.c_[np.array([1.,1,1,0,0,0]),np.zeros((6,2))]
  low,pixels,_=raster(uv,faces,attrs,size=128);old=int((pixels[:,:,0]>0).sum());low,pixels,added=pad_cut_edge(uv,faces,low,pixels,size=128)
  self.assertGreater(added,0);self.assertEqual(int((pixels[:,:,0]>0).sum()),old+added)
  # Interior of the adjacent valid, unmodified source triangle stays empty.
  x,y=(np.array([.65,.36])*128-.5).astype(int);self.assertEqual(pixels[y-low[1],x-low[0],0],0)
 def test_sampling_is_native_top_down_at_texel_centers(self):
  image=np.array([[[1.,0,0],[0,1,0]],[[0,0,1],[1,1,1]]])
  np.testing.assert_allclose(sample(image,np.array([[.25,.25],[.25,.75]])),[[1,0,0],[0,0,1]])
 def test_source_srgb_decode_known_points_and_byte_roundtrip(self):
  np.testing.assert_allclose(srgb_to_linear(np.array([0.,.04045,.5,1.])),[0.,.00313080495356,.214041140482,1.],atol=1e-11)
  values=np.arange(256)/255
  np.testing.assert_array_equal(np.uint8(linear_to_srgb(srgb_to_linear(values))*255+.5),np.arange(256,dtype=np.uint8))
 def test_encoded_specular_seam_preserves_stock_linear_f0(self):
  strength=np.array([1.,1.5,2.]);stock=np.array([.2167838843802262,.22079493441818632,.25])*.125
  encoded=np.round(linear_to_srgb(stock/strength)*255)/255
  np.testing.assert_allclose(srgb_to_linear(encoded)*strength,stock,atol=.0009)
  # Encoding the linear seam value as a raw byte would darken the edge again.
  self.assertGreater(float(np.max(np.abs(srgb_to_linear(stock/strength)*strength-stock))),.02)
 def test_shared_edge_footprint_matches_stock_beside_valid_chart(self):
  uv=np.array([[.3,.3],[.6,.3],[.3,.6],[.602,.3],[.85,.3],[.602,.6]],dtype=np.float16).astype(float)
  faces=np.array([[0,1,2],[3,4,5]]);attrs=np.tile([0.,.125,.25],(6,1));attrs[:3,0]=1
  low,pixels,_=raster(uv,faces,attrs,size=128);low,pixels,_=pad_cut_edge(uv,faces,low,pixels,size=128)
  pixels,proof=enforce_boundary(uv,faces,np.array([0,1,2]),attrs,low,pixels,size=128)
  image=np.zeros((128,128,3));image[low[1]:low[1]+pixels.shape[0],low[0]:low[0]+pixels.shape[1]]=pixels
  np.testing.assert_allclose(sample(image,uv[:3]),np.tile([1.,.125,.25],(3,1)),atol=1e-12)
  # The neighboring valid source chart remains unchanged away from the edge.
  np.testing.assert_array_equal(sample(image,np.array([[.75,.35]])),[[0,0,0]])
  self.assertEqual(proof['sharedEdgeSegments'],3);self.assertTrue(proof['nativeHalfUV'])
 def test_eight_pixel_boundary_collar_preserves_near_mips(self):
  uv=np.array([[.3,.3],[.6,.3],[.3,.6]],dtype=np.float16).astype(float);faces=np.array([[0,1,2]])
  attrs=np.tile([1.,.125,.25],(3,1));low,pixels,_=raster(uv,faces,attrs,size=128)
  low,pixels,_=pad_cut_edge(uv,faces,low,pixels,pixels=16,size=128)
  pixels,proof=enforce_boundary(uv,faces,np.arange(3),attrs,low,pixels,size=128,tolerance=8)
  image=np.zeros((128,128,3));image[low[1]:low[1]+pixels.shape[0],low[0]:low[0]+pixels.shape[1]]=pixels
  for _ in range(3):
   np.testing.assert_allclose(sample(image,uv)[:,0],1,atol=1e-12)
   h,w=image.shape[:2];image=image.reshape(h//2,2,w//2,2,3).mean(axis=(1,3))
  self.assertEqual(proof['tolerancePixels'],8)
if __name__=='__main__':unittest.main()
