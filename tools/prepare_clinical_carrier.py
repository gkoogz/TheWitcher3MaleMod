"""Author owned rigid fluid carriers for REDengine's lit scene passes.

The engine retains camera, depth, materials and entity placement. Native draws
replace only these fingerprinted carriers with Base's numerical liquid mesh.
"""
import argparse,copy,json,shutil,subprocess
from pathlib import Path
import numpy as np
from PIL import Image
from mod import ROOT,settings,run_wcc,write_json,digest,build,verify_package
from wcc_fbx import Document
from prepare_motion import scalar,reference,array,vector
from build_body_boundary import verify_texture_metadata


def prepare_textures(job,cfg,workspace):
    records=[]
    for name,rgba,group,compression in [
        ('white',(246,245,242,255),'CharacterDiffuse','TCM_DXTNoAlpha'),
        ('flat',(128,128,255,255),'CharacterNormal','TCM_Normals')]:
        image=job/(name+'.tga');Image.new('RGBA',(256,256),rgba).save(image)
        target=workspace/'characters/malemod/clinical'/(name+'.xbm')
        command=run_wcc(cfg,'import',['-depot=local','-file='+str(image),'-out='+str(target),'-texturegroup='+group],workspace,'import-fluid-'+name)
        dump_command=run_wcc(cfg,'dumpfile',['-file='+str(target),'-out=\\\\?\\'],workspace,'verify-fluid-'+name)
        dump=Path(str(target)+'.xml');metadata=verify_texture_metadata(dump,group,compression)
        records.append(dict(name=name,sourceSHA256=digest(image),nativeSHA256=digest(target),nativeMetadataDumpSHA256=digest(dump),command=command,nativeMetadataCommand=dump_command,**metadata))
        dump.unlink()
    return records

def author(job):
    job=Path(job).absolute()
    if not job.is_relative_to(ROOT/'build') or job.exists():raise ValueError('Use a fresh owned build directory')
    job.mkdir(parents=True);workspace=job/'intake';workspace.mkdir()
    cfg=settings();cfg['depot']=cfg['redkit']/'r4data'
    converter=ROOT/'build/research/wkit-current/MaleModCR2W.exe'
    source=cfg['depot']/'items/bodyparts/geralt_items/legs/bare/l_01_mg__body.w2ent'
    raw=job/'stock-carrier-schema.json'
    subprocess.run([str(converter),'export',str(source),str(raw)],capture_output=True,check=True)
    entity=json.loads(raw.read_text())
    resources=[]
    for kind,graph in [('opaque','pbr_std'),('clear','transparent_lit_vert')]:
        document=Document(ROOT/'build/probe/geralt_lower.fbx')
        objects=document.root('Objects');keep={m.values[0] for m in document.meshes}
        for node in objects.children:
            if node.name=='Model' and node.values[-1]=='Mesh':keep.add(node.values[0])
            if node.name=='Material':keep.add(node.values[0])
        objects.children=[n for n in objects.children if n.values[0] in keep]
        connections=document.root('Connections');connections.children=[n for n in connections.children if n.values[1] in keep and (n.values[2] in keep or n.values[2]==0)]
        rng=np.random.default_rng(8917 if kind=='opaque' else 3109)
        for mesh in document.meshes:
            points=rng.uniform(-12800,12800,(192,3))
            points[:2]=[[-12800,-12800,-12800],[12800,12800,12800]]
            faces=np.arange(192).reshape(-1,3);faces[:,2]=-faces[:,2]-1
            mesh.set_array('Vertices',points);mesh.set_array('PolygonVertexIndex',faces)
            for layer in mesh.children:
                if not layer.name.startswith('LayerElement'):continue
                if layer.name=='LayerElementMaterial':layer.set_array('Materials',np.zeros(64,dtype=np.int32));continue
                channel,width={'LayerElementNormal':('Normals',3),'LayerElementColor':('Colors',4),'LayerElementUV':('UV',2),'LayerElementReflectionUV':('UV',2)}[layer.name]
                values=np.tile([0,0,1],(192,1)) if channel=='Normals' else np.ones((192,width)) if channel=='Colors' else np.full((192,width),.5)
                layer.set_array(channel,values)
        for model in [n for n in objects.children if n.name=='Model']:
            for prop in model.child('Properties70').children:
                if prop.values[0] in ['Lcl Translation','Lcl Rotation','Lcl Scaling']:
                    for p in prop.props[-3:]:p.value=1. if prop.values[0]=='Lcl Scaling' else 0.;p.raw=None
        fbx=job/(kind+'.fbx');document.save(fbx)
        opacity='1.0' if kind=='opaque' else '.82'
        fbx.with_suffix('.xml').write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<mesh><mesh_data autohideDistance="500.00" isTwoSided="true" useExtraStreams="true" mergeInGlobalShadowMesh="false" entityProxy="false"><LODs><LOD_info distance="0.00"/><LOD_info distance="250.00"/></LODs></mesh_data><materials><material name="Material0" local="true" base="engine\\materials\\graphs\\{graph}.w2mg"><param name="Diffuse" type="handle:ITexture" value="characters\\malemod\\clinical\\white.xbm"/><param name="Normal" type="handle:ITexture" value="characters\\malemod\\clinical\\flat.xbm"/><param name="Opacity" type="Float" value="{opacity}"/><param name="RSpecScale" type="Float" value="1.0"/><param name="RSpecBase" type="Float" value=".65"/><param name="Refraction" type="Float" value=".015"/></material></materials></mesh>''')
        target=workspace/'characters/malemod/clinical'/(kind+'.w2mesh');target.parent.mkdir(parents=True,exist_ok=True)
        resources.append(dict(kind=kind,path=target.relative_to(workspace).as_posix(),command=run_wcc(cfg,'import',['-depot=local','-file='+str(fbx),'-out='+str(target)],workspace,'import-fluid-'+kind)))
    # Dedicated solid/clear materials retain REDengine lighting and depth.
    # Tiny constant images are deterministic material inputs, not generated art.
    textures=prepare_textures(job,cfg,workspace)
    def edit(resource):
        chunks=resource['_chunks'];prefix=resource['_extension']
        item_key=next(k for k,c in chunks.items() if c['_type']=='CItemEntity');old=chunks.pop(item_key);new_key=item_key.replace('CItemEntity','CEntity')
        old['_type']='CEntity';old['_key']=new_key;old['_vars']['name']=scalar('String','MaleModClinicalCarrier');chunks[new_key]=old
        mesh_key=next(k for k,c in chunks.items() if c['_type']=='CMeshComponent');mesh=chunks[mesh_key];mesh['_parentKey']=new_key
        for kind,key in [('opaque',mesh_key),('clear',prefix+'CMeshComponent #'+str(len(chunks)+1))]:
            c=copy.deepcopy(mesh);c['_key']=key;v=c['_vars'];v['name']=scalar('String','MaleModClinical'+kind)
            v['drawableFlags']=scalar('EDrawableFlags','DF_IsVisible|DF_NoDissolves')
            v['mesh']['_vars']['_depotPath']['_value']='characters\\malemod\\clinical\\'+kind+'.w2mesh'
            v['boundingBox']['_vars']={a:vector('Vector',[*([n]*3),1]) for a,n in [('Min',-128),('Max',128)]}
            chunks[key]=c
        old['_vars']['Components']=array('array:0,0,ptr:CComponent',[reference('ptr:CComponent',k) for k,c in chunks.items() if c['_type']=='CMeshComponent'])
        for chunk in list(chunks.values()):
            for name,value in list(chunk['_vars'].items()):
                if name=='entityClass':value['_value']='CEntity'
                if name=='entityObject':value['_vars']['_reference']['_value']=new_key
                if value.get('_type')=='CR2W':edit(value)
        # The converter's reference fields encode chunk ordinals. Keep the
        # entity before its components and make every ordinal contiguous.
        ordered=sorted(chunks.items(),key=lambda kv:int(kv[0].rsplit('#',1)[1]))
        remap={k:prefix+c['_type']+' #'+str(i) for i,(k,c) in enumerate(ordered)}
        remap[item_key]=remap[new_key]
        def references(value):
            if isinstance(value,dict):
                for k,v in value.items():
                    if isinstance(v,str) and v in remap:value[k]=remap[v]
                    else:references(v)
            elif isinstance(value,list):
                for v in value:references(v)
        references(resource)
        resource['_chunks']={remap[k]:c for k,c in ordered}
    edit(entity)
    recipe=job/'entity.json';write_json(recipe,entity);output=workspace/'characters/malemod/clinical/carrier.w2ent'
    subprocess.run([str(converter),'import',str(recipe),str(output)],capture_output=True,check=True)
    write_json(job/'authoring.json',dict(recipeSHA256=digest(Path(__file__)),schemaSourceSHA256=digest(source),resources=resources,textures=textures,entitySHA256=digest(output),nativeCooked=False,observedGameplay=False))
    return job


def refresh_materials(job,source):
    """Reuse verified owned carriers while reimporting their two small maps."""
    job,source=[Path(p).absolute() for p in [job,source]]
    if not job.is_relative_to(ROOT/'build') or job.exists() or not source.is_relative_to(ROOT/'build'):
        raise ValueError('Use a fresh owned build output and an owned carrier source')
    receipt=json.loads((source/'authoring.json').read_text());intake=source/'intake'
    expected=[intake/'characters/malemod/clinical'/(n+ext) for n,ext in [('opaque','.w2mesh'),('clear','.w2mesh'),('carrier','.w2ent')]]
    if any(not p.is_file() for p in expected):raise ValueError('Owned carrier source is incomplete')
    job.mkdir(parents=True);workspace=job/'intake';shutil.copytree(intake,workspace)
    preserved=[dict(path=p.relative_to(intake).as_posix(),sourceSHA256=digest(p)) for p in expected]
    cfg=settings();cfg['depot']=cfg['redkit']/'r4data'
    textures=prepare_textures(job,cfg,workspace)
    for p in preserved:
        if digest(workspace/p['path'])!=p['sourceSHA256']:raise ValueError('Material refresh changed a native carrier')
    write_json(job/'authoring.json',dict(recipeSHA256=digest(Path(__file__)),sourceAuthoringSHA256=digest(source/'authoring.json'),sourceJob=source.relative_to(ROOT).as_posix(),schemaSourceSHA256=receipt['schemaSourceSHA256'],resources=receipt['resources'],preservedCarriers=preserved,textures=textures,entitySHA256=digest(workspace/'characters/malemod/clinical/carrier.w2ent'),nativeCooked=False,observedGameplay=False))
    return job

def cook(job):
    job=Path(job).absolute();cfg=settings();cfg['depot']=cfg['redkit']/'r4data'
    package=build(cfg,dict(name='modMaleModClinical',version='0.4.33',platform='pc',cacheBuilders=['textures'],scope='Owned fluid carriers; native Base liquid mesh and scene queries'),job/'intake')
    m=verify_package(package);cooked=next(a.removeprefix('-outdir=') for r in m['nativeCommands'] if r['command']=='cook' for a in r['args'] if a.startswith('-outdir='))
    write_json(job/'package.json',dict(directory=package.relative_to(ROOT).as_posix(),cooked=cooked))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('job',type=Path);p.add_argument('--cook',action='store_true');p.add_argument('--materials-from',type=Path);a=p.parse_args();cook(a.job) if a.cook else refresh_materials(a.job,a.materials_from) if a.materials_from else author(a.job)
