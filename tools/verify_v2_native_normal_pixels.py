"""Roundtrip the two published native normals and test actual welded frames."""
import argparse,json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image
import mod
from mod import ROOT,digest,read_json,write_json
from build_v2_anatomy_material import complete_depot
from bake_v2_skin_textures import sample,unit

def verify(job,output,frames,bank,posed):
 job=Path(job).absolute();output=Path(output).absolute();frames=Path(frames).absolute();bank=Path(bank).absolute();posed=Path(posed).absolute()
 if output.exists()or not output.resolve().is_relative_to(job.resolve()):raise ValueError('Use fresh owned normal roundtrip output')
 package=read_json(job/'package.json');content=Path(package['directory'])/'Mods/mod000000WitcherV2/content';output.mkdir(parents=True);packed=output/'published-content';mod.copy_tree(content,packed)
 for p in content.rglob('*'):
  if p.is_file()and digest(p)!=digest(packed/p.relative_to(content)):raise ValueError('Published normal input changed')
 cfg=mod.settings();cfg['depot']=complete_depot(cfg);cfg['wcc']=ROOT/'v2/build/materials/anatomy-01/build/shaders-05/runtime/bin/x64_RedKit/wcc_lite.exe';prior=mod.ROOT;mod.ROOT=output
 try:
  def one(lod):
   scope=output/('lod%d'%lod);scope.mkdir();uncooked=scope/'uncooked';workspace=scope/'workspace';workspace.mkdir();rel='characters/malemod/anatomy/lod%d-normal.xbm'%lod
   uncook=mod.run_wcc(cfg,'uncook',['-indir='+str(packed),'-outdir='+str(uncooked),'-targetfile='+rel.replace('/','\\'),'-uncookext=xbm','-imgfmt=tga'],workspace,'normal%d-published-uncook'%lod)
   if not(uncooked/rel).is_file():raise ValueError('Published normal was not recovered')
   image=scope/('lod%d-normal.tga'%lod);export=mod.run_wcc(cfg,'export',['-depot=local','-file='+rel.replace('/','\\'),'-out='+str(image)],uncooked,'normal%d-published-export'%lod)
   with Image.open(image)as im:
    if im.size!=(4096,4096):raise ValueError('Published native normal resolution changed')
   return dict(lod=lod,path=str(image),SHA256=digest(image),uncook=uncook,export=export)
  with ThreadPoolExecutor(max_workers=2)as pool:images=list(pool.map(one,[0,1]))
 finally:mod.ROOT=prior
 stock=ROOT/'v2/build/native-fit-02/build/depot-bb7d8c28a8c3/characters/models/geralt/body/model/body_01_mg__geralt_n01.tga';stockPixels=np.asarray(Image.open(stock).convert('RGB'),float)/255;reports=[]
 for image in images:
  lod=image['lod'];f=np.load(frames/('lod%d-native-frames.npz'%lod));fit=np.load(ROOT/('v2/build/fitted-geralt/lod%d.npz'%lod));donor=np.load(ROOT/('v2/build/materials/source-anatomy-01/lod%d-material-donor.npz'%lod));bi=f['bodyNativeRows'][fit['seamBody']];mi=f['moduleNativeRows'][donor['seamModule']]
  targetTS=unit(sample(stockPixels,f['bodyUV'][fit['seamBody']])*2-1);actualTS=unit(sample(np.asarray(Image.open(image['path']).convert('RGB'),float)/255,f['moduleUV'][donor['seamModule']])*2-1);cases=[]
  for cp in sorted(bank.glob('v2-checkpoint-*.packet')):
   w=np.fromfile(posed/(cp.stem+'.world40'),'<f4').reshape(-1,10)
   if not np.array_equal(w[bi,3:],w[mi,3:]):raise ValueError('Posed shared native frames are not identical')
   N=unit(w[bi,3:6]);T=unit(w[bi,6:9]);B=unit(np.cross(N,T))*w[bi,9,None];matrix=np.stack([T,B,N],axis=-1);a=unit(np.einsum('nij,nj->ni',matrix,targetTS));b=unit(np.einsum('nij,nj->ni',matrix,actualTS));angle=np.degrees(np.arccos(np.clip((a*b).sum(1),-1,1)));cases.append(dict(stage=int(cp.stem.split('-')[-1]),degrees=np.percentile(angle,[0,50,95,100]).tolist()))
  reports.append(dict(lod=lod,actualPublishedPixels=True,image=image,cases=cases,maximumAngleDegrees=max(x['degrees'][-1]for x in cases),worstP95Degrees=max(x['degrees'][2]for x in cases)))
 proof=dict(schema='malemod.actual-published-native-normal-weld/1',packageInfoSHA256=digest(job/'package.json'),textureCacheSHA256=digest(packed/'texture.cache'),framesProofSHA256=digest(frames/'frames.json'),posedProofSHA256=digest(posed/'proof.json'),stockReference=dict(path=str(stock),SHA256=digest(stock),scope='Official SDKstock authoring normal, retailGPUlogicalview not recaptured'),reports=reports,maximumAngleDegrees=max(x['maximumAngleDegrees']for x in reports),worstP95Degrees=max(x['worstP95Degrees']for x in reports),nativeAppearanceVerified=False)
 write_json(output/'proof.json',proof);return proof

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--frames',type=Path,required=True);p.add_argument('--bank',type=Path,required=True);p.add_argument('--posed',type=Path,required=True);a=p.parse_args();print(json.dumps(verify(a.job,a.output,a.frames,a.bank,a.posed),indent=2))
