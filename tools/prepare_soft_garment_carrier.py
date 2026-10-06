"""Adopt an officially compiled soft cloth graph into verified rigid sentinels.

Reuses byte-identical, previously imported procedural textures and entity.
Reimports all four material owners with the new supported forward graph.
Cooking remains a separate strict clean-Base operation.
"""
import argparse,json,shutil
from pathlib import Path
from mod import ROOT,settings,run_wcc,digest,write_json
from prepare_garment_carrier import KINDS,verify_normal_encoding,verify_material
from soft_cloth_material import GRAPH,inspect

def prepare(job,source):
    job,source=Path(job).absolute(),Path(source).absolute()
    if not job.is_relative_to(ROOT/'build') or not source.is_relative_to(ROOT/'build'):raise ValueError('Use owned build sources and output')
    graph=job/'intake'/GRAPH;optical=inspect(graph)
    compiled=json.loads((job/'graph-resave-final.json').read_text())
    if not compiled['nativeCompiled'] or not compiled.get('compiledPayloadChanged') or compiled['SHA256']!=digest(graph) or not optical['compiledNormal'] or not optical['compiledDiffuse']:raise ValueError('Soft graph needs its matching actual official compiler receipt with refreshed shader payload')
    prior=json.loads((source/'authoring.json').read_text());assets=job/'intake/characters/malemod/garments';assets.mkdir(parents=True,exist_ok=True);resources=[];reused=[]
    cfg=settings();cfg['depot']=cfg['redkit']/'r4data'
    for kind in KINDS:
        for channel,suffix in [('diffuse','.xbm'),('normal-roughness','-normal.xbm')]:
            origin=source/'intake/characters/malemod/garments'/(kind+suffix)
            receipt=next(v for v in prior['textures']if v['kind']==kind and v['channel']==channel)
            if digest(origin)!=receipt['nativeSHA256']:raise ValueError('Reused texture differs from native import receipt')
            if channel=='normal-roughness':verify_normal_encoding(origin,cooked=False)
            destination=assets/origin.name;shutil.copy2(origin,destination);reused.append(dict(kind=kind,channel=channel,sourceJob=str(source),sourceAuthoringSHA256=digest(source/'authoring.json'),nativeSHA256=digest(destination),byteIdentical=True,originalImportReceipt=receipt))
        fbx=job/(kind+'.fbx');shutil.copy2(source/(kind+'.fbx'),fbx)
        xml=(source/(kind+'.xml')).read_text();old='characters\\malemod\\garments\\cloth_dry.w2mg'
        if xml.count(old)!=1:raise ValueError('Expected one verified dry carrier material owner')
        fbx.with_suffix('.xml').write_text(xml.replace(old,GRAPH.replace('/','\\')))
        mesh=assets/(kind+'.w2mesh')
        if mesh.exists():raise ValueError('Use a fresh soft carrier import; existing mesh must be explicitly reviewed')
        command=run_wcc(cfg,'import',['-depot=local','-file='+str(fbx),'-out='+str(mesh)],job/'intake','import-soft-garment-'+kind)
        material=verify_material(mesh,kind,GRAPH);resources.append(dict(kind=kind,command=command,material=material,sourceSentinelFBXSHA256=digest(fbx)))
    entity=source/'intake/characters/malemod/garments/carrier.w2ent'
    if digest(entity)!=prior['entitySHA256']:raise ValueError('Source carrier entity differs from its native authoring receipt')
    shutil.copy2(entity,assets/entity.name)
    proof=dict(recipeSHA256=digest(Path(__file__)),sourceCarrierSHA256=prior['sourceCarrierSHA256'],resources=resources,textures=reused,materialPresentation=dict(graph=GRAPH,opacity=.95,roughness=.88,specularity=.015,automaticWetness=False,opticalContract=optical,officialResave=compiled),entitySHA256=digest(assets/entity.name),nativeCooked=False,observedGameplay=False)
    write_json(job/'authoring.json',proof)
    return proof

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('job',type=Path);p.add_argument('--source',required=True,type=Path);a=p.parse_args();prepare(a.job,a.source)
