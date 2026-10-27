"""Bind material-only bake frames to actual B04 native rows and cooked UVs."""
import argparse,json,hashlib
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from mod import ROOT,digest,read_json,write_json
from packed_mesh_format import CookedMesh
from v2_source_precision import parse_b04

def unit(x):return x/np.maximum(np.linalg.norm(x,axis=-1,keepdims=True),1e-20)
def decode(words):return np.column_stack([(words>>(a*10))&1023 for a in range(3)])/511.5-1

def prepare(output,binding,manifest,donor):
 output=Path(output).absolute();binding=Path(binding).absolute();manifest=Path(manifest).absolute();donor=Path(donor).absolute()
 if output.exists()or not output.resolve().is_relative_to((ROOT/'v2/build/materials').resolve()):raise ValueError('Use fresh native material frame output')
 raw=binding.read_bytes();resources=parse_b04(raw);meta=read_json(manifest)
 if digest(binding)!=meta['bindingSHA256']:raise ValueError('Native source binding manifest changed')
 meshpath=Path(meta['resources'][0]['cookedPath']);mesh=CookedMesh(meshpath.read_bytes(),allow_multi_section=True);buffer=Path(str(meshpath)+'.1.buffer').read_bytes();sections=mesh.skin_sections(buffer)
 if digest(meshpath)!=meta['resources'][0]['cookedSHA256']or digest(Path(str(meshpath)+'.1.buffer'))!=meta['resources'][0]['bufferSHA256']:raise ValueError('Cooked material source changed')
 r=resources[0];words=np.ndarray((r['count'],13),'<u4',buffer=raw,offset=r['rowoffset'],strides=(52,4)).copy();positions=words[:,:3].copy().view('<f4')*r['scale']+r['bias'];uv=np.zeros((r['count'],2))
 for s in sections:uv[s['firstVertex']:s['firstVertex']+s['vertexCount']]=np.frombuffer(buffer,'<f2',s['vertexCount']*2,s['uvOffset']).reshape(-1,2)
 N=unit(decode(words[:,5]));T=unit(decode(words[:,6]));B=unit(np.cross(N,T))*((words[:,6]>>30)/1.5-1)[:,None];frames=np.stack([T,B,N],axis=-1)
 if np.any(abs(np.linalg.det(frames))<1e-6):raise ValueError('Native skin frame is singular')
 output.mkdir(parents=True);reports=[]
 for lod in [0,1]:
  fit=np.load(ROOT/('v2/build/fitted-geralt/lod%d.npz'%lod));d=np.load(donor/('lod%d-material-donor.npz'%lod));count=int(fit['bodyCount'])
  # Authored body UV is lineage of the verified original stock FBX; convert
  # its V convention once. Source moduleUV already uses runtime convention.
  from wcc_fbx import Document
  from prepare_v2_skin_donor import lineage
  stock=Document(ROOT/'v2/build/geralt-base/pelvis-legs.fbx').meshes[lod]
  stockuv=next(x for x in stock.children if x.name=='LayerElementUV').array('UV').reshape(-1,2)
  bodyuv=lineage(fit,'body')@stockuv;bodyuv[:,1]=1-bodyuv[:,1]
  mappings=[];errors=[]
  for material,points,reference_uv in [(0,fit['points'][:count],bodyuv),(1,fit['points'][count:],d['moduleUV'])]:
   contract=meta['resources'][0]['sections'];section=next(s for s in contract if s['lod']==lod and s['material']==material);first,n=section['firstVertex'],section['vertexCount']
   k=min(16,n);distance,candidates=cKDTree(positions[first:first+n]).query(points*.01,k=k)
   selected=[];unreferenced=[];used=set(np.unique(d['bodyFaces']if material==0 else d['moduleFaces']).tolist())
   for i in range(len(points)):
    valid=np.where(distance[i]<=.00005)[0]
    if not len(valid):
     if i not in used:
      selected.append(first+int(candidates[i,0]));unreferenced.append(i);continue
     raise ValueError('Authored vertex leaves measured native quantization bound: lod%d material%d row%d distance%.9g'%(lod,material,i,distance[i,0]))
    choices=candidates[i,valid]+first;error=np.max(abs(uv[choices]-reference_uv[i]),axis=1)
    best=np.lexsort((distance[i,valid],error))[0]
    if error[best]>.0011:raise ValueError('Native material vertex leaves authored UV chart')
    selected.append(choices[best])
   selected=np.asarray(selected);mappings.append(selected);active=np.array(sorted(used));errors.append(dict(material=material,maximumUsedPositionErrorMm=float(np.linalg.norm(positions[selected[active]]-points[active]*.01,axis=1).max()*1000),maximumUsedUVDifference=float(np.max(abs(uv[selected[active]]-reference_uv[active]))),unusedAuthoredRowsAbsentFromCook=unreferenced))
  body,module=mappings;edge=d['seamModule'];body_edge=body[fit['seamBody']];module_edge=module[edge]
  if not np.array_equal(words[body_edge],words[module_edge]):raise ValueError('Native shared material boundary is not exact whole-row weld')
  target=output/('lod%d-native-frames.npz'%lod);np.savez_compressed(target,bodyUV=uv[body],moduleUV=uv[module],bodyFrame=frames[body],moduleFrame=frames[module],bodyNativeRows=body,moduleNativeRows=module)
  reports.append(dict(lod=lod,path=str(target),SHA256=digest(target),matches=errors,sharedEdgeRows=len(edge),sharedWhole52ByteRowsIdentical=True,edgeNativeFrameTransferIdentity=True))
 proof=dict(schema='malemod.actual-native-skin-bake-frames/1',bindingPath=str(binding),bindingSHA256=digest(binding),manifestSHA256=digest(manifest),cookedMeshSHA256=digest(meshpath),cookedBufferSHA256=digest(Path(str(meshpath)+'.1.buffer')),sourceGeometryUVTBNChanged=False,UVSource='Actual cooked half2 values, no assumed float16 rounding',frameSource='Actual B04 baseline shader N/T words; normalized native T,B,N columns, correct handedness',lods=reports,nativeObserved=False)
 write_json(output/'frames.json',proof);return proof

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--binding',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--donor',type=Path,required=True);a=p.parse_args();print(json.dumps(prepare(a.output,a.binding,a.manifest,a.donor),indent=2))
