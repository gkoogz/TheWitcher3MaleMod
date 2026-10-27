"""Bake source skin inputs with a measured, local Geralt material transition.

Only fresh ignored outputs are written. Source geometry, maps, fit and runtime
remain read-only. Runtime D3D UV uses image y=v; WCC FBX authoring flips V.
"""
import argparse, json, sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from scipy.ndimage import distance_transform_edt,binary_dilation
from PIL import Image,ImageDraw
from prepare_v2_skin_donor import ROOT,digest,lineage,EXPECTED
from wcc_fbx import Document
sys.path.insert(0,str(ROOT.parent/'MaleMod'))
from malemod_base.graft import extend_seam_field

def unit(x):return x/np.maximum(np.linalg.norm(x,axis=-1,keepdims=True),1e-20)
def source_normal(rgb):
 n=np.asarray(rgb,dtype=np.float32)/255.;n=n*2;n[...,:2]-=1
 return unit(n)
def encode_normal(n):return np.uint8(np.clip((unit(n)*.5+.5)*255+.5,0,255))
def srgb_to_linear(x):return np.where(x<=.04045,x/12.92,((x+.055)/1.055)**2.4)
def linear_to_srgb(x):return np.where(x<=.0031308,x*12.92,1.055*np.maximum(x,0)**(1/2.4)-.055)
def sample(image,uv):
 # Match wrap sampling at pixel centers, retaining all original source texels.
 h,w=image.shape[:2];xy=uv*np.array([w,h])-.5;lo=np.floor(xy).astype(int);f=xy-lo
 a=image[lo[:,1]%h,lo[:,0]%w];b=image[lo[:,1]%h,(lo[:,0]+1)%w]
 c=image[(lo[:,1]+1)%h,lo[:,0]%w];d=image[(lo[:,1]+1)%h,(lo[:,0]+1)%w]
 return (a*(1-f[:,0,None])+b*f[:,0,None])*(1-f[:,1,None])+(c*(1-f[:,0,None])+d*f[:,0,None])*f[:,1,None]
def frames(points,faces,normals,uv):
 tri=points[faces];tuv=uv[faces];e1=tri[:,1]-tri[:,0];e2=tri[:,2]-tri[:,0]
 d1=tuv[:,1]-tuv[:,0];d2=tuv[:,2]-tuv[:,0];det=d1[:,0]*d2[:,1]-d1[:,1]*d2[:,0];valid=abs(det)>1e-14
 tangent=np.zeros_like(points);bitangent=np.zeros_like(points)
 t=(e1[valid]*d2[valid,1,None]-e2[valid]*d1[valid,1,None])/det[valid,None]
 b=(-e1[valid]*d2[valid,0,None]+e2[valid]*d1[valid,0,None])/det[valid,None]
 for k in range(3):np.add.at(tangent,faces[valid,k],t);np.add.at(bitangent,faces[valid,k],b)
 n=unit(normals);t=unit(tangent-n*(tangent*n).sum(1)[:,None]);fallback=np.linalg.norm(t,axis=1)<.5
 axis=np.tile([1.,0,0],(len(n),1));axis[abs(n[:,0])>.9]=[0,1,0];t[fallback]=unit(np.cross(axis,n))[fallback]
 b=unit(np.cross(n,t));b*=np.where((b*bitangent).sum(1)<0,-1,1)[:,None]
 return np.stack([t,b,n],axis=-1)
def raster(uv,faces,attributes,size=4096):
 active=faces[np.max(attributes[faces,0],axis=1)>0];q=uv[active]*size-.5
 low=np.maximum(np.floor(q.min((0,1))).astype(int),0);high=np.minimum(np.ceil(q.max((0,1))).astype(int),size-1)
 result=np.zeros((high[1]-low[1]+1,high[0]-low[0]+1,attributes.shape[1]),np.float32)
 overlaps=0;max_conflict=0.
 for ids,tri in zip(active,q):
  a,b,c=tri;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
  if abs(den)<1e-12:continue
  lo=np.maximum(np.ceil(tri.min(0)).astype(int),low);hi=np.minimum(np.floor(tri.max(0)).astype(int),high)
  if np.any(hi<lo):continue
  y,x=np.mgrid[lo[1]:hi[1]+1,lo[0]:hi[0]+1];wa=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/den
  wb=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/den;wc=1-wa-wb;inside=(wa>=-1e-7)&(wb>=-1e-7)&(wc>=-1e-7)
  if not inside.any():continue
  yy=y[inside]-low[1];xx=x[inside]-low[0];values=wa[inside,None]*attributes[ids[0]]+wb[inside,None]*attributes[ids[1]]+wc[inside,None]*attributes[ids[2]]
  old=result[yy,xx];overlap=(old[:,0]>0)&(values[:,0]>0)
  if overlap.any():
   overlaps+=int(overlap.sum());max_conflict=max(max_conflict,float(abs(old[overlap,1:3]-values[overlap,1:3]).max()))
  replace=values[:,0]>old[:,0];result[yy[replace],xx[replace]]=values[replace]
 return low,result,dict(repeatedTransitionPixels=overlaps,maximumRepeatedTargetUVDifference=max_conflict)
def pad_cut_edge(uv,faces,low,fields,pixels=8,size=4096):
 # Cover the complete module chart first. Padding may occupy unused atlas
 # texels only; no neighboring valid source surface receives a seam edit.
 coverage=Image.new('1',(size,size));draw=ImageDraw.Draw(coverage)
 for face in faces:
  tri=uv[face]*size-.5;draw.polygon([tuple(p)for p in tri],fill=1)
 low=low-pixels;fields=np.pad(fields,((pixels,pixels),(pixels,pixels),(0,0)))
 # A gutter may meet the atlas border; retain only actual in-bounds texels.
 # No wrapped distant source chart is painted by this bounded operation.
 start=np.maximum(-low,0);stop=np.minimum(np.array(fields.shape[1::-1]),size-low)
 fields=fields[start[1]:stop[1],start[0]:stop[0]];low=low+start
 valid=np.asarray(coverage)[low[1]:low[1]+fields.shape[0],low[0]:low[0]+fields.shape[1]]
 mask=fields[:,:,0]>0;distance,nearest=distance_transform_edt(~mask,return_indices=True)
 gutter=(distance>0)&(distance<=pixels)&~valid
 fields[gutter]=fields[nearest[0][gutter],nearest[1][gutter]]
 return low,fields,int(gutter.sum())
def enforce_boundary(uv,faces,edge,attributes,low,fields,size=4096,tolerance=1):
 # A geometric cut can border another VALID part of the original atlas. The
 # unused-chart gutter above deliberately excludes it, leaving shared-edge
 # bilinear samples partially in source skin. Enforce the complete sampler
 # footprint at the actual native HALF UV cut, with one pixel tolerance.
 edges=np.sort(np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1)
 edges,count=np.unique(edges,axis=0,return_counts=True)
 edges=edges[(count==1)&np.isin(edges,edge).all(1)]
 if not len(edges):raise ValueError('Missing shared material boundary')
 mask=np.zeros(fields.shape[:2],bool)
 for a,b in edges:
  p,q=uv[a]*size-.5,uv[b]*size-.5
  steps=int(np.ceil(abs(q-p).max()*2))+1
  points=p[None,:]+(q-p)[None,:]*np.linspace(0,1,steps)[:,None]
  base=np.floor(points).astype(int)-low
  for x in [0,1]:
   for y in [0,1]:
    xx,yy=base[:,0]+x,base[:,1]+y
    if np.any(xx<0)or np.any(xx>=mask.shape[1])or np.any(yy<0)or np.any(yy>=mask.shape[0]):raise ValueError('Boundary sampler footprint leaves baked field')
    mask[yy,xx]=True
 if not 1<=tolerance<=8:raise ValueError('Boundary tolerance must remain a bounded mip gutter')
 mask=binary_dilation(mask,iterations=tolerance)
 yy,xx=np.where(mask);points=np.c_[xx+low[0],yy+low[1]];distance=np.full(len(points),np.inf);values=np.zeros((len(points),attributes.shape[1]))
 for a,b in edges:
  p,q=uv[a]*size-.5,uv[b]*size-.5;v=q-p;den=np.dot(v,v)
  if den<1e-20:continue
  fraction=np.clip((points-p)@v/den,0,1);delta=points-(p+fraction[:,None]*v)
  d=(delta*delta).sum(1);take=d<distance
  values[take]=attributes[a]*(1-fraction[take,None])+attributes[b]*fraction[take,None];distance[take]=d[take]
 if not np.isfinite(distance).all():raise ValueError('Boundary constraints have no finite source')
 values[:,0]=1;fields[yy,xx]=values
 return fields,dict(sharedEdgeSegments=len(edges),samplerFootprintTexels=len(points),tolerancePixels=tolerance,nativeHalfUV=True)
def bake(donor,output,ambient,stock_spec,source_strength,boundary_exact=False):
 if output.exists():raise ValueError('Use a fresh texture output directory')
 meta=json.loads((donor/'donor.json').read_text());source={x['name']:Path(x['path'])for x in meta['maps']}
 for name,p in source.items():
  if digest(p)!=EXPECTED[name]:raise ValueError('Canonical source map changed')
 stock=ROOT/'v2/build/native-fit-02/build/depot-bb7d8c28a8c3/characters/models/geralt/body/model'
 target_d=np.asarray(Image.open(stock/'body_01_mg__geralt_d01.tga').convert('RGBA'),np.float32)/255
 target_n=np.asarray(Image.open(stock/'body_01_mg__geralt_n01.tga').convert('RGB'),np.float32)/255
 target_a=np.asarray(Image.open(ambient).convert('RGB'),np.float32)/255
 fitdoc=Document(ROOT/'v2/build/fitted-geralt/geralt-wolverine.fbx');output.mkdir(parents=True);reports=[]
 roughness=float((2/17)**.25)
 for row,mesh in zip(meta['lods'],fitdoc.meshes):
  lod=row['lod'];d=np.load(donor/('lod%d-material-donor.npz'%lod));fit=np.load(ROOT/('v2/build/fitted-geralt/lod%d.npz'%lod));n=int(fit['bodyCount']);points=fit['points'];uv=d['moduleUV'];seam=d['seamModule']
  originalUV=next(x for x in mesh.children if x.name=='LayerElementUV').array('UV').reshape(-1,2)[:n]
  # Fitted body FBX UV already includes exact stock lineage; convert to the
  # observed native sampler orientation only at this authoring boundary.
  bodyUV=originalUV.copy();bodyUV[:,1]=1-bodyUV[:,1]
  if boundary_exact:
   uv=uv.astype(np.float16).astype(np.float64);bodyUV=bodyUV.astype(np.float16).astype(np.float64)
  unique,selected=np.unique(seam,return_index=True);boundary=bodyUV[fit['seamBody'][selected]]
  targetUV=extend_seam_field(points[n:],d['moduleFaces'],unique,boundary,boundary.mean(0),3)
  normals=next(x for x in mesh.children if x.name=='LayerElementNormal').array('Normals').reshape(-1,3)
  moduleFrame=frames(points[n:],d['moduleFaces'],normals[n:],uv)
  bodyFrame=frames(points[:n],d['bodyFaces'],normals[:n],bodyUV)
  nearest=cKDTree(points[fit['seamModule']]).query(points[n:])[1];bodyIDs=fit['seamBody'][nearest]
  rotation=np.einsum('nji,njk->nik',moduleFrame,bodyFrame[bodyIDs])
  attrs=np.c_[d['seamBlend'],targetUV,rotation.reshape(-1,9)]
  low,fields,diagnostic=raster(uv,d['moduleFaces'],attrs);padding=16 if boundary_exact else 8;low,fields,gutter=pad_cut_edge(uv,d['moduleFaces'],low,fields,pixels=padding);diagnostic['cutEdgeGutterPixels']=gutter;diagnostic['maximumGutterDistancePixels']=padding
  if boundary_exact:
   fields,boundary_proof=enforce_boundary(uv,d['moduleFaces'],unique,attrs,low,fields,tolerance=8);diagnostic['boundarySamplerConstraint']=boundary_proof
  yy,xx=np.where(fields[:,:,0]>0);values=fields[yy,xx];w=values[:,0,None];targetUV=values[:,1:3];rot=values[:,3:].reshape(-1,3,3)
  gx=xx+low[0];gy=yy+low[1];rgbTarget=srgb_to_linear(sample(target_d,targetUV)[:,:3]);normalTarget=sample(target_n,targetUV)*2-1;normalTarget=unit(np.einsum('nij,nj->ni',rot,normalTarget));ambientTarget=sample(target_a,targetUV)
  files=[]
  for state,name in [('natural','R14-skin-natural.dds'),('erect','R14-skin-erect.dds')]:
   image=np.array(Image.open(source[name]).convert('RGBA'));saved=image.copy();pixels=srgb_to_linear(image[gy,gx,:3]/255.);pixels=pixels*(1-w)+rgbTarget*w
   image[gy,gx,:3]=np.uint8(np.clip(linear_to_srgb(pixels)*255+.5,0,255));path=output/('lod%d-%s-diffuse.tga'%(lod,state));Image.fromarray(image,'RGBA').save(path)
   mask=np.zeros(image.shape[:2],bool);mask[gy,gx]=True
   if not np.array_equal(image[~mask],saved[~mask]):raise ValueError('Source color changed outside local transition')
   files.append(dict(role=state+'Diffuse',path=str(path.resolve()),sha256=digest(path),outsideTransitionExact=True))
  normal=np.array(Image.open(source['SharedBody-normal.dds']).convert('RGB'));selected=source_normal(normal[gy,gx]);maximumError=0.
  for start in range(0,4096,128):normal[start:start+128]=encode_normal(source_normal(normal[start:start+128]))
  normal[gy,gx]=encode_normal(selected*(1-w)+normalTarget*w);path=output/('lod%d-normal.tga'%lod);Image.fromarray(normal,'RGB').save(path);files.append(dict(role='Normal',path=str(path.resolve()),sha256=digest(path)))
  spec=np.array(Image.open(source['SharedBody-specular.dds']).convert('RGB'));originalSpec=spec.copy();base=srgb_to_linear(spec[gy,gx]/255)
  seamSpec=ambientTarget[:,2,None]*np.asarray(stock_spec)[None,:]/np.asarray(source_strength)[None,:]
  spec[gy,gx]=np.uint8(np.clip(linear_to_srgb(base*(1-w)+seamSpec*w)*255+.5,0,255))
  if not np.array_equal(spec[~mask],originalSpec[~mask]):raise ValueError('Source specular changed outside local transition')
  path=output/('lod%d-specular.tga'%lod);Image.fromarray(spec,'RGB').save(path);files.append(dict(role='SourceSpec',path=str(path.resolve()),sha256=digest(path),outsideTransitionExact=True,seamInterpolation='IEC sRGB decode, linear blend, IEC encode; native graph decodes before amplitude'))
  # R is the stock second-specular-lobe receiver mask, G is native roughness,
  # B is the SSS seam blend. Primary SourceSpec has its own preserved RGB map.
  a=np.zeros((4096,4096,3),np.uint8);a[:,:,1]=round(roughness*255)
  channels=np.c_[ambientTarget[:,2]*w[:,0],roughness*(1-w[:,0])+ambientTarget[:,1]*w[:,0],w[:,0]]
  a[gy,gx]=np.uint8(np.clip(channels,0,1)*255+.5);path=output/('lod%d-ambient.tga'%lod);Image.fromarray(a,'RGB').save(path);files.append(dict(role='Ambient',path=str(path.resolve()),sha256=digest(path)))
  reports.append(dict(lod=lod,transitionTexels=len(yy),transitionBoundingBox=[*low.tolist(),fields.shape[1],fields.shape[0]],overlap=diagnostic,files=files))
 report=dict(schema='malemod.witcher-v2-source-skin-textures/1',sourceDonorSHA256=digest(donor/'donor.json'),
  stockAmbient=dict(path=str(ambient.resolve()),sha256=digest(ambient)),sourceStrength=source_strength,
  stockSpecular=stock_spec,healthySourceExponent=15,nativeRoughness=roughness,sourceSpecularSRGB=True,
  specularSeamEncoding='IEC sRGB; blend in linear domain toward stockF0/sourceStrength',
  ambientChannels=dict(R='seamWeight*stockAmbient.B: stock secondlobe scale=.2*R',G='lerp(sourceRoughness,stockAmbient.G,seamWeight)',B='seamWeight: native SSS mixes toward stockSSS'),
  sourceNormalConversion='normalize((2R-1,2G-1,2B)), encode .5*N+.5',
  sourceStateMap=meta['stateMap'],FBXModuleUV='(sourceU,1-sourceV); actual native runtime keeps source UV',
  seamSupportNativeUnits=3,boundarySamplerConstraint=boundary_exact,lods=reports,cooked=False,nativeObserved=False,
  caveats=['Native BRDF roughness is an explicit Phong-to-PBR adaptation',
   'Source strength uses licensed Alkali authored material, not a newly captured live c13 constant',
   'TBN seam transfer is derived from exact authored fit; official recook/native seam review is mandatory'])
 (output/'textures.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--donor',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--ambient',type=Path,required=True)
 ap.add_argument('--stock-spec',type=float,nargs=3,required=True);ap.add_argument('--source-strength',type=float,nargs=3,default=[1,1.5,2])
 ap.add_argument('--boundary-exact',action='store_true',help='Constrain the complete native shared-edge bilinear footprint to actual stock skin')
 args=ap.parse_args();bake(args.donor.resolve(),args.output.resolve(),args.ambient.resolve(),args.stock_spec,args.source_strength,args.boundary_exact)
