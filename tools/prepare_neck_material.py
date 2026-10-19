"""Bake measured neck skin into an unused atlas chart without altering geometry."""
from pathlib import Path
import sys,json,struct,hashlib
import numpy as np
from PIL import Image,ImageDraw
from scipy.ndimage import distance_transform_edt
from scipy.spatial import cKDTree
import argparse
from mod import ROOT,settings
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base',type=Path,required=True,help='Shared modular dependency checkout')
parser.add_argument('--source',type=Path,required=True,help='Source modular asset job with assembly/runtime/material bindings')
parser.add_argument('--output',type=Path,required=True,help='Fresh private output directory')
parser.add_argument('--job',type=Path,required=True,help='Fresh owned build directory for native texture intake')
args=parser.parse_args();A=ROOT;B=args.base.resolve();N=args.source.resolve();R=args.output.resolve()
if R.exists() or args.job.exists():raise ValueError('Use fresh output and native job directories')
job=args.job.absolute()
if not job.is_relative_to(A/'build') or job.parent.resolve()!=(A/'build/body-boundary').resolve():raise ValueError('Use a job beneath the owned body-boundary build root')
R.mkdir(parents=True)
job.mkdir(parents=True)
sys.path.insert(0,str(B))
from malemod_base.loft_material import chart,sample,bake_patch,surface_density
from malemod_base.material_atlas import compose_tiles,bake_repeat
from malemod_base.skin_match import linear,encoded
from malemod_base.modular_shading import corner_frames
from malemod_base.modular_anatomy import Mesh
from scipy import sparse
dtype=np.dtype([('uv','<f4',(2,)),('normal','<f4',(3,)),('tangent','<f4',(3,)),('sign','<f4'),('bones','<u4',(4,)),('weights','<f4',(4,)),('color','<f4',(4,)),('reflection','<f4',(2,))])
raw=(N/'materials-01.bin').read_bytes();nv,nf,nm=struct.unpack_from('<3I',raw,200);offset=216+nv*25+nf+nf*3*92
mat=np.frombuffer(raw,dtype,count=nm*3,offset=offset).copy().reshape(nm,3)
m=np.load(N/'assembly-01/body-union.npz');p=m['points'];f=m['faces'];owner=np.load(N/'runtime-01/ownership.npz');rings=owner['neck_rings']
uv=np.zeros((len(p),2));uv[f]=mat['uv'];uv[:,0]=uv[:,0]*2-1
rect=[.525,.395,.975,.485]
selected,newuv,s,t,length,circumference=chart(p,rings,f,rect)
# Prove the reserved rectangle and its filter gutter do not overlap retained
# anatomy. Body coordinates are in the separate left atlas tile.
oldcorners=mat['uv'].copy();oldcorners[:,:,0]=oldcorners[:,:,0]*2-1
ramp=np.zeros(len(p),bool);ramp[owner['ramp_rings']]=True
retained=(~selected)&(~ramp[f].all(1))
lo=oldcorners[retained].min(1);hi=oldcorners[retained].max(1)
overlap=((hi[:,0]>.52)&(lo[:,0]<.98)&(hi[:,1]>.39)&(lo[:,1]<.49))
assert not overlap.any(),'Reserved chart intersects retained material'
mask=Image.new('L',(1024,1024));draw=ImageDraw.Draw(mask)
lobe=np.any((owner['frames']>=13)&(owner['weights']>0),axis=1)
retained_lobe=lobe&(~np.isin(np.arange(len(p)),rings.ravel()))
distance_to_neck=cKDTree(p[rings[0]]).query(p)[0]
distal=retained_lobe&(distance_to_neck>np.quantile(distance_to_neck[retained_lobe],.4))
for tri in oldcorners[distal[f].all(1)]:
 if np.ptp(tri[:,0])<.1:draw.polygon([tuple(x*1023) for x in tri],fill=255)
distance=distance_transform_edt(np.asarray(mask)>0);cy,cx=np.unravel_index(distance.argmax(),distance.shape)
tile_center=np.array([cx,cy])/1023;radius=min(12.,distance[cy,cx]*.6)/1023
print('Measured skin tile',tile_center,radius,flush=True)
def unit(v):return v/np.maximum(np.linalg.norm(v,axis=-1,keepdims=True),1e-12)
normal=np.zeros((len(p),3));tangent=np.zeros_like(normal);sign=np.ones(len(p))
normal[f]=mat['normal'];tangent[f]=mat['tangent'];sign[f]=mat['sign']
def boundary_normal(image,ids,row):
 n=unit(normal[ids]);old_t=unit(tangent[ids]-np.sum(tangent[ids]*n,axis=1)[:,None]*n);old_b=np.cross(n,old_t)*sign[ids,None]
 q=p[rings[row]];new_t=np.roll(q,-1,axis=0)-np.roll(q,1,axis=0);new_t=unit(new_t-n*np.sum(new_t*n,axis=1)[:,None]);new_b=np.cross(n,new_t)
 direction=p[rings[1]]-p[rings[0]] if row==0 else p[rings[-1]]-p[rings[-2]]
 new_b*=np.where(np.sum(new_b*direction,axis=1)<0,-1,1)[:,None]
 sampled=unit(sample(image,uv[ids])[:,:3]/127.5-1)
 world=old_t*sampled[:,0,None]+old_b*sampled[:,1,None]+n*sampled[:,2,None]
 return unit(np.stack([np.sum(world*new_t,axis=1),np.sum(world*new_b,axis=1),np.sum(world*n,axis=1)],axis=1))
results=[]
for channel,stock,source in [
 ('diffuse',A/'build/probe/geralt_lower.fbm/body_01_mg__geralt_d01.tga',B/'assets/materials/wolverine/R14-skin-natural.dds'),
 ('normal',A/'build/probe/geralt_lower.fbm/body_01_mg__geralt_n01.tga',B/'assets/materials/wolverine/SharedBody-normal.dds')]:
 left=Image.open(stock).convert('RGBA');right=Image.open(source).convert('RGBA')
 if channel=='normal':right=bake_repeat(right,16)
 else:
  gain=json.loads((A/'build/body-boundary/radial-skin-packed-4/skin-match.json').read_text())['linearRGBGain'];q=np.asarray(right).copy()
  for start in range(0,len(q),32):q[start:start+32,:,:3]=encoded(linear(q[start:start+32,:,:3])*gain)
  right=Image.fromarray(q,'RGBA')
 assert left.size==right.size
 full=compose_tiles([left,right]);original=np.asarray(full).copy();data=np.asarray(right)
 W,H=right.size;x0,y0,x1,y1=np.rint(np.array(rect)*[W,H,W,H]).astype(int)
 # Endpoints use texel centers. Write their exact rectangle into the binding.
 actual=np.array([x0/(W-1),y0/(H-1),x1/(W-1),y1/(H-1)])
 if results:assert np.allclose(actual,results[0]['rect'],atol=.001)
 sx,sy=(tile_center*[W-1,H-1]).astype(int);rad=max(4,int(radius*min(W,H)))
 tile=data[sy-rad:sy+rad,sx-rad:sx+rad,:3]
 if channel=='normal':
  low=boundary_normal(data,rings[0],0);high=boundary_normal(data,rings[-1],-1);tile=unit(tile/127.5-1)
 else:low=linear(sample(data,uv[rings[0]])[:,:3]);high=linear(sample(data,uv[rings[-1]])[:,:3]);tile=linear(tile)
 # Density from actual retained UV support. Keep the same source microdetail
 # scale around the strip and along its measured median meridian length.
 # Boundary UVs zigzag across source aliases; their summed length grossly
 # overstates texture density. Measure the actual retained lobe area instead.
 faces=f[distal[f].all(1)];coords=oldcorners[distal[f].all(1)]
 island=np.ptp(coords[:,:,0],axis=1)<.1
 density=surface_density(p,faces[island],coords[island])
 repeats=[circumference*density/(radius*4),np.median(length)*density/(radius*4)]
 patch=bake_patch(low,high,s,tile,x1-x0+1,y1-y0+1,repeats,channel=='normal')
 pixel=np.clip(np.rint((patch+1)*127.5),0,255).astype('u1') if channel=='normal' else encoded(patch)
 out=original.copy();out[y0:y1+1,W+x0:W+x1+1,:3]=pixel
 # Eight-texel edge gutters preserve filtering without touching source charts.
 for pad in range(1,9):
  out[y0-pad,W+x0:W+x1+1,:3]=pixel[0];out[y1+pad,W+x0:W+x1+1,:3]=pixel[-1]
  out[y0-8:y1+9,W+x0-pad]=out[y0-8:y1+9,W+x0]
  out[y0-8:y1+9,W+x1+pad]=out[y0-8:y1+9,W+x1]
 unchanged=out.copy();unchanged[y0-8:y1+9,W+x0-8:W+x1+9]=original[y0-8:y1+9,W+x0-8:W+x1+9];assert np.array_equal(unchanged,original)
 dest=job/f'atlas-{channel}.tga';Image.fromarray(out,'RGBA').save(dest)
 results.append(dict(channel=channel,path=str(dest),sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),rect=actual.tolist(),retainedPixelsExact=True,repeats=repeats,measuredRetainedDensity=density))
 print(channel,dest,flush=True)
# Both source textures are 4096 square in this observed pipeline.
assert np.array_equal(results[0]['rect'],results[1]['rect'])
selected,newuv,*_=chart(p,rings,f,results[0]['rect']);newuv[:,:,0]=(newuv[:,:,0]+1)*.5
mat['uv'][selected]=newuv
mesh=Mesh(p,f,mat['uv'].astype(float),sparse.load_npz(N/'assembly-01/body-union-donors.npz'),m['source_faces'],m['generated'],m['normal_field'])
frames=corner_frames(mesh);mat['tangent']=frames['tangent'];mat['sign']=frames['sign']
dest=R/'materials.bin';dest.write_bytes(raw[:offset]+mat.tobytes());dest.with_suffix('.bin.sha256').write_text(hashlib.sha256(dest.read_bytes()).hexdigest()+'\n')
(R/'bake-manifest.json').write_text(json.dumps(dict(textures=results,material=str(dest),materialSHA256=hashlib.sha256(dest.read_bytes()).hexdigest(),sourceMaterialSHA256=hashlib.sha256(raw).hexdigest(),sourceGeometrySHA256=hashlib.sha256((N/'assembly-01/body-union.npz').read_bytes()).hexdigest(),bodyGeometryChanged=False,retainedUVExact=True,rectangle=results[0]['rect'],tileCenter=tile_center.tolist(),tileRadius=radius),indent=2))
