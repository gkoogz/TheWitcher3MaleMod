from pathlib import Path
import sys,json
from mod import ROOT
A=ROOT
from mod import settings,run_wcc,write_json,digest,build,verify_package
from build_body_boundary import material_policy,verify_texture_metadata
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--bake',type=Path,required=True);parser.add_argument('--job',type=Path,required=True)
parser.add_argument('--authoring-base',type=Path,help='Clean checkout of the existing character-binding pin for native package provenance')
args=parser.parse_args();R=args.bake.resolve();job=args.job.absolute()
if not job.is_relative_to(A/'build') or job.parent.resolve()!=(A/'build/body-boundary').resolve():raise ValueError('Use an owned body-boundary build directory')
workspace=job/'intake';workspace.mkdir(exist_ok=True);cfg=settings();records=[]
if args.authoring_base:cfg['base']=args.authoring_base.resolve()
for name in ['diffuse','normal']:
 source=job/f'atlas-{name}.tga';output=workspace/'characters/malemod/materials'/f'body_{name}.xbm';output.parent.mkdir(parents=True,exist_ok=True);group,compression=material_policy(name)
 record=run_wcc(cfg,'import',['-depot=local','-file='+str(source),'-out='+str(output),'-texturegroup='+group],workspace,'import-'+name)
 dump=run_wcc(cfg,'dumpfile',['-file='+str(output),'-out=\\\\?\\'],workspace,'verify-'+name)
 xml=Path(str(output)+'.xml');meta=verify_texture_metadata(xml,group,compression);xml.unlink()
 records.append(dict(channel=name,atlasSHA256=digest(source),nativeSHA256=digest(output),metadata=meta,importCommand=record,dumpCommand=dump))
write_json(job/'material-imports.json',dict(materials=records,bakeManifestSHA256=digest(R/'bake-manifest.json')))
package=build(cfg,dict(name='mod00000MaleModNeckMaterial',version='0.4.32-neck-material',platform='pc',cacheBuilders=['textures'],scope='Dedicated generated neck chart; retained body and source maps preserved'),workspace)
verify_package(package);(R/'package.txt').write_text(str(package))
