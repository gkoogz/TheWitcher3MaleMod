"""Official published-cache roundtrip of stock and seam boundary inputs."""
import argparse,json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image
import mod
from mod import ROOT,read_json,write_json,digest
from build_v2_anatomy_material import complete_depot
from bake_v2_skin_textures import sample

def verify(job,output,edge_proof):
 job=Path(job).absolute();output=Path(output).absolute()
 if output.exists()or not output.resolve().is_relative_to(job.resolve()):raise ValueError('Use fresh roundtrip output inside owned material job')
 package=read_json(job/'package.json');manifest=read_json(Path(package['directory'])/'build-manifest.json')
 content=Path(package['directory'])/'Mods/mod000000WitcherV2/content'
 if not content.is_dir():raise ValueError('Exact official published package is unavailable')
 output.mkdir(parents=True);packed=output/'published-content';mod.copy_tree(content,packed)
 for path in content.rglob('*'):
  if path.is_file()and digest(path)!=digest(packed/path.relative_to(content)):raise ValueError('Published roundtrip input changed')
 cfg=mod.settings();cfg['depot']=complete_depot(cfg);cfg['wcc']=ROOT/'v2/build/materials/anatomy-01/build/shaders-05/runtime/bin/x64_RedKit/wcc_lite.exe'
 tasks=[('stock','characters/models/geralt/body/model/body_01_mg__geralt_d01.xbm'),('seam','characters/malemod/anatomy/lod0-natural-diffuse.xbm'),('mask','characters/malemod/anatomy/lod0-ambient.xbm')]
 prior=mod.ROOT;mod.ROOT=output
 try:
  def one(item):
   role,path=item;scope=output/role;scope.mkdir();uncooked=scope/'uncooked';workspace=scope/'workspace';workspace.mkdir()
   uncook=mod.run_wcc(cfg,'uncook',['-indir='+str(packed),'-outdir='+str(uncooked),'-targetfile='+path.replace('/','\\'),'-uncookext=xbm','-imgfmt=tga'],workspace,'seam-cache-'+role+'-uncook')
   if not(uncooked/path).is_file():raise ValueError('Native roundtrip did not recover exact published resource')
   image=scope/(role+'.tga');export=mod.run_wcc(cfg,'export',['-depot=local','-file='+path.replace('/','\\'),'-out='+str(image)],uncooked,'seam-cache-'+role+'-export')
   with Image.open(image)as im:
    if im.size!=(4096,4096):raise ValueError('Published source boundary lost its native resolution')
   return dict(role=role,path=path,image=str(image),imageSHA256=digest(image),uncook=uncook,export=export)
  with ThreadPoolExecutor(max_workers=2)as pool:rows=list(pool.map(one,tasks))
 finally:mod.ROOT=prior
 images={r['role']:np.asarray(Image.open(r['image']).convert('RGB'),float)/255 for r in rows}
 edge=np.load(edge_proof);error=np.max(abs(sample(images['seam'],edge['UV'])-sample(images['stock'],edge['stockUV'])),axis=1)*255
 weight=sample(images['mask'],edge['UV'])[:,2]
 proof=dict(schema='malemod.published-seam-pixel-roundtrip/1',packageInfoSHA256=digest(job/'package.json'),textureCacheSHA256=digest(packed/'texture.cache'),allInputsFromActualPublishedCache=True,files=rows,LOD0StockDiffuseError255Percentiles=np.percentile(error,[0,50,95,100]).tolist(),LOD0BoundaryWeightPercentiles=np.percentile(weight,[0,1,50,99,100]).tolist(),nativeAppearanceVerified=False)
 write_json(output/'proof.json',proof);return proof

def collect_reference(job,output,edge_proof,stock_tga):
 """Close an owned-resource roundtrip when stock is an external dependency."""
 job=Path(job).absolute();output=Path(output).absolute();stock_tga=Path(stock_tga).absolute()
 if not output.resolve().is_relative_to(job.resolve()):raise ValueError('Roundtrip collection leaves owned job')
 edge=np.load(edge_proof);files=[];images={}
 for role in ['seam','mask']:
  p=output/role/(role+'.tga')
  with Image.open(p)as im:
   if im.size!=(4096,4096):raise ValueError('Published seam image resolution differs')
   images[role]=np.asarray(im.convert('RGB'),float)/255
  commands=[]
  for command in ['uncook','export']:
   matches=[p for p in (output/'build/logs').glob('*.json')if role+'-'+command in p.name]
   if len(matches)!=1:raise ValueError('Missing or ambiguous official roundtrip command')
   record=read_json(matches[0])
   if record['exitCode']!=0:raise ValueError('Official roundtrip command failed')
   commands.append(dict(path=str(matches[0]),SHA256=digest(matches[0]),record=record))
  files.append(dict(role=role,path=str(p),SHA256=digest(p),commands=commands))
 stock=np.asarray(Image.open(stock_tga).convert('RGB'),float)/255
 error=np.max(abs(sample(images['seam'],edge['UV'])-sample(stock,edge['stockUV'])),axis=1)*255;w=sample(images['mask'],edge['UV'])[:,2]
 proof=dict(schema='malemod.published-seam-pixel-reference/1',packageInfoSHA256=digest(job/'package.json'),textureCacheSHA256=digest(output/'published-content/texture.cache'),actualPublishedSeamImages=True,stockReference=dict(path=str(stock_tga),SHA256=digest(stock_tga),kind='Verified original official-export 4096 stock authoring image; external retail compression NOT recaptured'),files=files,LOD0StockDiffuseError255Percentiles=np.percentile(error,[0,50,95,100]).tolist(),LOD0BoundaryWeightPercentiles=np.percentile(w,[0,1,50,99,100]).tolist(),nativeAppearanceVerified=False)
 write_json(output/'reference-proof.json',proof);return proof

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--edge-proof',type=Path,required=True);p.add_argument('--collect-reference',type=Path);a=p.parse_args();print(json.dumps(collect_reference(a.job,a.output,a.edge_proof,a.collect_reference)if a.collect_reference else verify(a.job,a.output,a.edge_proof),indent=2))
