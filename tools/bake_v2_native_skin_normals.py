"""Correct only the narrow seam's normal transfer using actual native frames.

Geometry, UVs, runtime N/T, source physics and all eight nonnormal maps remain
unchanged. The previous seam mask defines the complete editable atlas region.
"""
import argparse,json,shutil
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree
from scipy.ndimage import distance_transform_edt
from mod import ROOT,digest,read_json,write_json
from bake_v2_skin_textures import unit,source_normal,encode_normal,sample,raster,pad_cut_edge,enforce_boundary
from prepare_v2_skin_donor import EXPECTED
from malemod_base.graft import extend_seam_field

def native_transfer(module_frame,body_frame):
 """Preserve the shader's world direction even when T and N aren't square."""
 return np.linalg.solve(module_frame,body_frame)

def bake(output,previous,frames,donor):
 output=Path(output).absolute();previous=Path(previous).absolute();frames=Path(frames).absolute();donor=Path(donor).absolute()
 if output.exists()or not output.resolve().is_relative_to((ROOT/'v2/build/materials').resolve()):raise ValueError('Use fresh normal-only bake output')
 old=read_json(previous);proof=read_json(frames/'frames.json');inventory=read_json(donor/'donor.json');source=next(Path(x['path'])for x in inventory['maps']if x['name']=='SharedBody-normal.dds')
 if digest(source)!=EXPECTED[source.name]:raise ValueError('Original source normal changed')
 stock=ROOT/'v2/build/native-fit-02/build/depot-bb7d8c28a8c3/characters/models/geralt/body/model/body_01_mg__geralt_n01.tga'
 stock_pixels=np.asarray(Image.open(stock).convert('RGB'),float)/255;source_pixels=np.asarray(Image.open(source).convert('RGB'));output.mkdir(parents=True);new=dict(old);reports=[]
 for record in old['lods']:
  lod=record['lod'];native=next(x for x in proof['lods']if x['lod']==lod);fpath=Path(native['path'])
  if digest(fpath)!=native['SHA256']:raise ValueError('Native frame donor changed')
  a=np.load(fpath);d=np.load(donor/('lod%d-material-donor.npz'%lod));fit=np.load(ROOT/('v2/build/fitted-geralt/lod%d.npz'%lod));n=int(fit['bodyCount']);points=fit['points'];uv=a['moduleUV'];bodyUV=a['bodyUV'];seam=d['seamModule'];unique,selected=np.unique(seam,return_index=True)
  boundary=bodyUV[fit['seamBody'][selected]];targetUV=extend_seam_field(points[n:],d['moduleFaces'],unique,boundary,boundary.mean(0),3)
  nearest=cKDTree(points[fit['seamModule']]).query(points[n:])[1];bodyIDs=fit['seamBody'][nearest]
  # Native T/B/N columns are not guaranteed orthogonal. Solve the actual
  # shader frame; transposition of a geometric derivative proxy is wrong.
  rotation=native_transfer(a['moduleFrame'],a['bodyFrame'][bodyIDs])
  attrs=np.c_[d['seamBlend'],targetUV,rotation.reshape(-1,9)];low,fields,diagnostic=raster(uv,d['moduleFaces'],attrs)
  low,fields,gutter=pad_cut_edge(uv,d['moduleFaces'],low,fields,pixels=16);fields,edge=enforce_boundary(uv,d['moduleFaces'],unique,attrs,low,fields,tolerance=8)
  valid=fields[:,:,0]>0;_,nearestField=distance_transform_edt(~valid,return_indices=True)
  rows={r['role']:r for r in record['files']};oldNormal=Path(rows['Normal']['path']);ambient=Path(rows['Ambient']['path'])
  if digest(oldNormal)!=rows['Normal']['sha256']or digest(ambient)!=rows['Ambient']['sha256']:raise ValueError('Previous seam inputs changed')
  image=np.asarray(Image.open(oldNormal).convert('RGB')).copy();weight=np.asarray(Image.open(ambient).convert('RGB'))[:,:,2].astype(float)/255
  gy,gx=np.where(weight>0);w=weight[gy,gx,None];yy=np.clip(gy-low[1],0,fields.shape[0]-1);xx=np.clip(gx-low[0],0,fields.shape[1]-1)
  v=fields[nearestField[0,yy,xx],nearestField[1,yy,xx]];normalTarget=sample(stock_pixels,v[:,1:3])*2-1;normalTarget=unit(np.einsum('nij,nj->ni',v[:,3:].reshape(-1,3,3),normalTarget));base=source_normal(source_pixels[gy,gx]);image[gy,gx]=encode_normal(base*(1-w)+normalTarget*w)
  # Preserve every texel outside the pre-existing seam mask byte-for-byte.
  original=np.asarray(Image.open(oldNormal).convert('RGB'));assert np.array_equal(image[weight==0],original[weight==0])
  files=[]
  for row in record['files']:
   sourceFile=Path(row['path']);target=output/sourceFile.name;entry=dict(row,path=str(target))
   if row['role']=='Normal':Image.fromarray(image,'RGB').save(target);entry.update(sha256=digest(target),nativeFrameNormalTransfer=True)
   else:
    if digest(sourceFile)!=row['sha256']:raise ValueError('Nonnormal source map changed')
    shutil.copy2(sourceFile,target);assert digest(target)==row['sha256']
   files.append(entry)
  reports.append(dict(record,files=files,nativeNormalTransfer=dict(frameDonorSHA256=digest(fpath),actualCookedUV=True,matrix='inverse(nativeModuleTBN)*nativeStockTBN',editableTexels=int((weight>0).sum()),outsideExistingSeamMaskByteIdentical=True,otherMapsByteIdentical=True,boundary=edge)))
 new.update(lods=reports,nativeFrameDonor=dict(path=str((frames/'frames.json').resolve()),SHA256=digest(frames/'frames.json')),previousTextures=dict(path=str(previous),SHA256=digest(previous)),normalTransfer='Actual native B04 baseline TBN and actual cooked UV; no geometry-derived tangent frame',cooked=False,nativeObserved=False)
 write_json(output/'textures.json',new);return new

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--previous',type=Path,required=True);p.add_argument('--frames',type=Path,required=True);p.add_argument('--donor',type=Path,required=True);a=p.parse_args();print(json.dumps(bake(a.output,a.previous,a.frames,a.donor),indent=2))
