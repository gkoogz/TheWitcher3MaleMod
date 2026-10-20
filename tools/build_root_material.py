"""Build an isolated root material candidate; never install it.

Own the skin graph/instances and redirect only the existing thirteen mod body
meshes. Preserve source mesh payloads with bounded import/CRC replacements.
"""
from pathlib import Path
import argparse, shutil, struct
from mod import ROOT, settings, run_wcc, write_json, digest, build, read_json
from player_rig_redirect import redirect

STOCK_SKIN='characters/models/common/materials/skin_body/skin_body__mg_01.w2mi'
STOCK_BASE='characters/models/common/materials/base_materials/base_skin.w2mi'
STOCK_GRAPH='engine/materials/graphs/pbr_skin.w2mg'

def owned_path(original,label):
    prefix='characters/malemod/';suffix=Path(original).suffix
    return prefix+label+'_'*(len(original)-len(prefix+label+suffix))+suffix

def main(job,graph,textures):
    job=Path(job).absolute();graph=Path(graph).resolve();textures=Path(textures).resolve()
    if not job.is_relative_to(ROOT/'build') or job.exists():raise ValueError('Use a fresh owned build job')
    cfg=settings();workspace=job/'intake';workspace.mkdir(parents=True)
    paths={p:owned_path(p,l) for p,l in [(STOCK_SKIN,'root_skin_instance'),(STOCK_BASE,'root_skin_base'),(STOCK_GRAPH,'root_skin')]}
    sdk=Path('E:/SteamLibrary/steamapps/common/The Witcher 3 REDkit/r4data')
    for old in [STOCK_SKIN,STOCK_BASE]:
        target=workspace/paths[old];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(sdk/old,target)
    target=workspace/paths[STOCK_GRAPH];shutil.copy2(graph,target)
    tmp=job/'resave-tmp';tmp.mkdir()
    command=run_wcc(cfg,'resave',['-tmpdir='+str(tmp),'-path='+str(Path('characters/malemod')),'-ext=w2mi','-nosourcecontrol','-ignorefileversion'],workspace,'resave-owned-root-instances')
    depot=Path(command['args'][command['args'].index('-uncookDir')+1])
    proofs=[]
    for old,dependency in [(STOCK_BASE,STOCK_GRAPH),(STOCK_SKIN,STOCK_BASE)]:
        path=workspace/paths[old];data=(depot/paths[old]).read_bytes()
        output,proof=redirect(data,dependency.replace('/','\\'),paths[dependency].replace('/','\\'),1,expected_headers=1)
        path.write_bytes(output);proofs.append(dict(resource=paths[old],**proof))
    selection=read_json(ROOT/'build/full-runtime/current-install.json');source=ROOT/selection['bodyJob']/'intake'
    meshes=sorted((source/'characters/malemod/body').rglob('*.w2mesh'))+[source/'characters/models/geralt/body/model/t_01_mg__body_hires.w2mesh']
    if len(meshes)!=13:raise ValueError('Expected exact thirteen-resource body family')
    for path in meshes:
        data=path.read_bytes();output,proof=redirect(data,STOCK_SKIN.replace('/','\\'),paths[STOCK_SKIN].replace('/','\\'),1,expected_headers=1)
        target=workspace/path.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(output)
        proofs.append(dict(resource=path.relative_to(source).as_posix(),sourceSHA256=digest(path),**proof))
    for name in ['body_diffuse.xbm','body_normal.xbm']:
        target=workspace/'characters/malemod/materials'/name;target.parent.mkdir(exist_ok=True);shutil.copy2(textures/name,target)
    # The packed surface map is identical to the currently installed base body.
    shutil.copy2(source/'characters/malemod/materials/body_ambient.xbm',workspace/'characters/malemod/materials/body_ambient.xbm')
    write_json(job/'source-proof.json',dict(graphSHA256=digest(graph),instanceResave=command,resources=proofs,installed=False))
    package=build(cfg,dict(name='mod00000MaleModNeckMaterial',version='0.4.32-root-material',platform='pc',cacheBuilders=['textures'],scope='Owned root skin graph and body material references; geometry and skin binding payloads preserved'),workspace)
    (job/'package.txt').write_text(str(package));print(package)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--job',type=Path,required=True);p.add_argument('--graph',type=Path,required=True);p.add_argument('--textures',type=Path,required=True);a=p.parse_args();main(a.job,a.graph,a.textures)
