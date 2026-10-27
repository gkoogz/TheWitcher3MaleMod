"""Prepare read-only source skin/UV donors; does not alter fit, cook or runtime.

The donor retains source UV exactly away from a narrow seam. Material-specific
conversion/cooking is deliberately separate from the verified source inventory.
"""
import argparse, hashlib, json, sys
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix
from scipy.spatial import cKDTree
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from wcc_fbx import Document

EXPECTED={
 'R14-skin-natural.dds':'70ab81655d2e264c30f955b1a3772ca005841cbcc5fb00ea4040c2bbce71449f',
 'R14-skin-erect.dds':'df565b3b277ae873703ab06955c653d8e6b36c287c75eaaa132012bc6d25b452',
 'SharedBody-normal.dds':'a466fcc95100522ba5059fd1e44bef8e257b269edce8c44d9660ffc13df4f665',
 'SharedBody-specular.dds':'51f2625a6bc680433d1fbd21a66b29476fbf7209636df0618c53e1eaaf25780c',
}
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def lineage(a,label):return csr_matrix((a[label+'_data'],a[label+'_indices'],a[label+'_indptr']),shape=a[label+'_shape'])
def prepare(output,source,seam_width):
 if output.exists():raise ValueError('Use a fresh offline donor directory')
 if not(0<seam_width<=3):raise ValueError('Only a narrow measured seam transition is allowed')
 inventory=[]
 for name,expected in EXPECTED.items():
  p=source/name;actual=digest(p)
  if actual!=expected:raise ValueError('Canonical map differs: '+name)
  with Image.open(p)as im:size=im.size;mode=im.mode
  if size!=(4096,4096)or mode!='RGBA':raise ValueError('Unobserved source map layout')
  inventory.append(dict(name=name,path=str(p),sha256=actual,size=size,mode=mode))
 fit=ROOT/'v2/build/fitted-geralt';base=ROOT/'v2/build/geralt-base/pelvis-legs.fbx'
 doc=Document(base);donors=[];output.mkdir(parents=True)
 for lod,mesh in enumerate(doc.meshes):
  p=fit/('lod%d.npz'%lod);a=np.load(p);count=int(a['bodyCount']);module=a['points'][count:]
  source_uv=lineage(a,'module')@a['moduleOriginalUV'];seam=a['seamModule']-count
  distance=cKDTree(module[seam]).query(module)[0]
  # Smooth endpoints: exact Geralt at the shared edge, exact source outside
  # the local support. No surface positions, topology or simulation change.
  t=np.clip(distance/seam_width,0,1);blend=1-t*t*(3-2*t)
  body_uv=lineage(a,'body')@next(x for x in mesh.children if x.name=='LayerElementUV').array('UV').reshape(-1,2)
  seam_body_uv=body_uv[a['seamBody']]
  faces=a['faces'];is_module=np.all(faces>=count,axis=1)
  if np.any(np.any(faces>=count,axis=1)!=is_module):raise ValueError('Face crosses independent material groups')
  # Existing stock UVs remain untouched. The future own anatomy material uses
  # its original UV with a seam-only sampled target skin transition.
  np.testing.assert_array_equal(source_uv[:len(a['moduleOriginalUV'])],a['moduleOriginalUV'])
  target=output/('lod%d-material-donor.npz'%lod)
  np.savez_compressed(target,moduleUV=source_uv,seamTargetUV=seam_body_uv,seamModule=seam,
   seamBlend=blend,seamDistanceNative=distance,materialGroup=is_module.astype(np.uint8),
   moduleFaces=faces[is_module]-count,bodyUV=body_uv,bodyFaces=faces[~is_module])
  donors.append(dict(lod=lod,fitSHA256=digest(p),path=str(target),sha256=digest(target),
   stockMaterialFaces=int((~is_module).sum()),sourceMaterialFaces=int(is_module.sum()),
   sourceOriginalUVPreserved=True,sourceVerticesOutsideTransition=int((blend==0).sum()),
   transitionVertices=int(((blend>0)&(blend<1)).sum()),seamSamples=len(seam),
   maximumTransitionDistanceNative=seam_width))
 report=dict(schema='malemod.witcher-v2-source-skin-donor/1',maps=inventory,lods=donors,
  geometryModified=False,cooked=False,nativeObserved=False,
  stateMap={'0':'R14-skin-erect.dds','1':'R14-skin-natural.dds','2':'R14-skin-natural.dds'},
  stateTransition='Discrete canonical mechanical state selection; no continuous interpolation',
  normalDecode='normalize(float3(R*2-1,G*2-1,B*2)); source s4 at original UV',
  specularDecode='source s3 RGB at original UV, multiplied by live shader c13',
  detailTiling='source c14.xy=(16,16) applies separate s7 detail texture only',
  limitations=['Target shader parameter binding, source detail donor and native material switching remain to implement',
   'Target engine lighting is an engine adaptation; this inventory does not establish native appearance parity'])
 (output/'donor.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))
if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True)
 ap.add_argument('--source',type=Path,default=ROOT.parent/'Work/wolverine/payload');ap.add_argument('--seam-width',type=float,default=3)
 args=ap.parse_args();prepare(args.output,args.source,args.seam_width)
