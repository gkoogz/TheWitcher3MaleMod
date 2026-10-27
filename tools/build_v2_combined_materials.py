"""Fresh body/fabric package with RGB normal packing, preserving canonical data.

Copies verified owned intakes. Reimports only the two unchanged normal TGAs
with RGB-preserving compression to match the observed native RGB decoder.
"""
import argparse
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET
import mod
from mod import ROOT,digest,read_json,write_json
from build_v2_anatomy_material import JOB as SKIN_JOB,complete_depot,texture_properties
from v2_skin_material import GRAPH,inspect
from v2_anatomy_material_contract import generate


def prepare(job):
    job=Path(job).absolute()
    if job.exists()or not job.resolve().is_relative_to((ROOT/'v2/build/materials').resolve()):raise ValueError('Use a fresh owned material job')
    skin_info=SKIN_JOB/'package-with-shaders.json';skin=read_json(skin_info)
    fabric_job=ROOT/'v2/build/materials/carriers-08';fabric_info=fabric_job/'package.json';fabric=read_json(fabric_info)
    intake=job/'build/intake';intake.mkdir(parents=True)
    inventory=[]
    for p in sorted((SKIN_JOB/'build/intake').rglob('*')):
        if not p.is_file()or p.suffix in ['.db','.db-shm','.db-wal']:continue
        rel=p.relative_to(SKIN_JOB/'build/intake');q=intake/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
        inventory.append(dict(path=rel.as_posix(),SHA256=digest(q)))
    overrides=[]
    for rel in [fabric['graph']]+['characters/malemod/garments/'+k+'.w2mesh'for k in ['ribbed','elastic','red','blue']]:
        p=fabric_job/'build/intake'/rel;q=intake/rel
        previous=digest(q)if q.exists()else None;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
        overrides.append(dict(path=rel,previousSHA256=previous,SHA256=digest(q)))
    if digest(intake/fabric['graph'])!=fabric['graphSHA256']:raise ValueError('Fabric source graph changed')
    for p in ['graph-compiled.json','graph-authored.json']:
        shutil.copy2(SKIN_JOB/p,job/p)
    bake_path=SKIN_JOB/'source-textures-03/textures.json';bake=read_json(bake_path)
    cfg=mod.settings();cfg['depot']=complete_depot(cfg)
    groups=ET.fromstring((cfg['depot']/'engine/textures/texturegroups.xml').read_bytes())
    name='V2AnatomyNormalRGB'
    if any(g.attrib.get('name')==name for g in groups):raise ValueError('Owned normal group collision')
    group=ET.SubElement(groups,'group',name=name)
    for key,value in [('compression','TCM_QualityColor'),('maxsize','4096'),('resizable','0'),('category','Characters')]:ET.SubElement(group,key,value=value)
    group_data=ET.tostring(groups,encoding='utf-8',xml_declaration=True)
    prior=mod.ROOT;mod.ROOT=job;normal_imports=[]
    try:
        for lod in bake['lods']:
            row=next(r for r in lod['files']if r['role']=='Normal');source=Path(row['path'])
            if digest(source)!=row['sha256']:raise ValueError('Source normal TGA changed')
            scratch=job/'build/normal-import'/source.stem;config=scratch/'engine/textures/texturegroups.xml';config.parent.mkdir(parents=True,exist_ok=True);config.write_bytes(group_data)
            target=intake/'characters/malemod/anatomy'/source.with_suffix('.xbm').name
            command=mod.run_wcc(cfg,'import',['-depot=local','-file='+str(source),'-out='+str(target),'-texturegroup='+name],scratch,'source-rgb-normal-'+source.stem)
            properties=texture_properties(target)
            if properties['textureGroup']!=name or properties['compression']!='TCM_QualityColor':raise ValueError('Native RGB normal import changed packing contract')
            normal_imports.append(dict(source=str(source),sourceSHA256=digest(source),path=str(target),SHA256=digest(target),properties=properties,command=command))
    finally:mod.ROOT=prior
    lower='characters/models/geralt/body/model/l_01_mg__body.w2mesh'
    if digest(intake/lower)!=digest(SKIN_JOB/'build/intake'/lower):raise ValueError('Normal transport changed body geometry')
    proof=dict(schema='malemod.witcher-v2-combined-material-intake/1',skinPackageInfoPath=str(skin_info),skinPackageInfoSHA256=digest(skin_info),
               fabricPackageInfoPath=str(fabric_info),fabricPackageInfoSHA256=digest(fabric_info),sourceInventory=inventory,overrides=overrides,
               normalImports=normal_imports,normalPacking='RGB through TCM_QualityColor; native shader 2*RGB-1; no gamma stage',
               sourceTGABytesUnchanged=True,bodyGeometryUnchanged=True,canonicalMathUnchanged=True)
    write_json(job/'intake.json',proof);return proof


def cook(job):
    job=Path(job).absolute();proof=read_json(job/'intake.json');skin=read_json(proof['skinPackageInfoPath']);fabric=read_json(proof['fabricPackageInfoPath'])
    cfg=mod.settings();cfg['depot']=complete_depot(cfg);cfg['base']=ROOT.parent/'Work/dependencies/base-wolverine'
    isolated=SKIN_JOB/'build/shaders-05/runtime/bin/x64_RedKit/wcc_lite.exe'
    if digest(isolated)!=digest(cfg['wcc']):raise ValueError('Owned native compiler differs')
    cfg['wcc']=isolated
    lock=read_json(ROOT/'dependencies/base.lock.json');lock['commit']='47023a7f53d794cff84f2f423ba6a7d1fb98ec0f';write_json(job/'dependencies/base.lock.json',lock)
    expected={r['path']:r['SHA256']for r in proof['sourceInventory']}
    expected.update({r['path']:r['SHA256']for r in proof['overrides']})
    expected.update({Path(r['path']).relative_to(job/'build/intake').as_posix():r['SHA256']for r in proof['normalImports']})
    for rel,sha in expected.items():
        if digest(job/'build/intake'/rel)!=sha:raise ValueError('Combined native input changed: '+rel)
    prior=mod.ROOT;mod.ROOT=job
    try:published=mod.build(cfg,dict(name='mod000000WitcherV2',version='2.0.0-source-materials',platform='pc',cacheBuilders=['textures'],reuseReadOnlyDepot=True,scope='Source skin RGB normal packing and canonical analytic fabric; geometry and numerical worker unchanged'),job/'build/intake')
    finally:mod.ROOT=prior
    manifest=read_json(published/'build-manifest.json');command=next(c for c in manifest['nativeCommands']if c['command']=='cook');cooked=Path(next(a.split('=',1)[1]for a in command['args']if a.startswith('-outdir=')))
    lower='characters/models/geralt/body/model/l_01_mg__body.w2mesh'
    material=generate(cooked/lower,job/'build/intake'/lower,job/'material-contract.json')
    old_lower=Path(skin['cooked'])/(lower+'.1.buffer')
    if digest(cooked/(lower+'.1.buffer'))!=digest(old_lower):raise ValueError('RGB material transport changed body buffer')
    geometry=[]
    for kind in ['ribbed','elastic','red','blue']:
        rel='characters/malemod/garments/'+kind+'.w2mesh.1.buffer'
        if digest(cooked/rel)!=digest(Path(fabric['cooked'])/rel):raise ValueError('Combined material changed native carrier buffer')
        geometry.append(dict(path=rel,SHA256=digest(cooked/rel)))
    result=dict(skin,directory=str(published),cooked=str(cooked),combinedIntakeSHA256=digest(job/'intake.json'),
                graph=fabric['graph'],graphSHA256=digest(job/'build/intake'/fabric['graph']),skinGraph=GRAPH,
                skinGraphSHA256=inspect(job/'build/intake'/GRAPH)['SHA256'],materialContractSHA256=digest(job/'material-contract.json'),
                cookedBodyBufferSHA256=material['cookedBufferSHA256'],nativeGeometry=geometry,nativeGameplayObserved=False)
    result['retainedAssets']=[dict(path=r['path'],sha256=digest(job/'build/intake'/r['path']))for r in skin['retainedAssets']]
    if 'derivedSeam' in proof:
        result['seamMaterials']=proof['derivedSeam']
        result['seamTextureImports']=[dict(path=r['path'],SHA256=r['SHA256'],sourceSHA256=r['sourceSHA256'],role=r['role'])for r in proof['seamImports']]
    result.pop('shaderCompilation',None)
    write_json(job/'package.json',result);return result


def derive_fabric(job,source_job,graph):
    """Carry already imported RGB maps forward; change one resaved graph only."""
    job=Path(job).absolute();source_job=Path(source_job).absolute();graph=Path(graph).absolute()
    if job.exists()or not job.resolve().is_relative_to((ROOT/'v2/build/materials').resolve()):raise ValueError('Use a fresh owned derived material job')
    if not source_job.resolve().is_relative_to((ROOT/'v2/build/materials').resolve())or not graph.resolve().is_relative_to((ROOT/'v2/build/materials').resolve()):raise ValueError('Derived inputs leave owned material work')
    proof=read_json(source_job/'intake.json');fabric=read_json(proof['fabricPackageInfoPath'])
    # Bounded native reader checks the resaved source's tables/export CRCs.
    from v2_cloth_material import native_objects
    if native_objects(graph)[2][0][0]!='CMaterialGraph':raise ValueError('Derived fabric graph is not a native material')
    mod.copy_tree(source_job/'build/intake',job/'build/intake')
    for name in ['graph-compiled.json','graph-authored.json']:shutil.copy2(source_job/name,job/name)
    target=job/'build/intake'/fabric['graph'];before=digest(target);shutil.copy2(graph,target)
    for row in proof['overrides']:
        if row['path']==fabric['graph']:row['SHA256']=digest(target)
    for row in proof['normalImports']:
        old=Path(row['path']);rel=old.relative_to(source_job/'build/intake');row['copiedFrom']=str(old);row['path']=str(job/'build/intake'/rel)
        if digest(Path(row['path']))!=row['SHA256']:raise ValueError('Derived job changed an RGB normal input')
    proof['derivedFrom']=dict(job=str(source_job),intakeSHA256=digest(source_job/'intake.json'),fabricGraphPath=str(graph),fabricGraphSHA256=digest(graph),previousFabricGraphSHA256=before)
    write_json(job/'intake.json',proof);return proof


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['prepare','cook','derive-fabric']);parser.add_argument('--job',type=Path,required=True)
    parser.add_argument('--source-job',type=Path);parser.add_argument('--fabric-graph',type=Path)
    args=parser.parse_args();print(json.dumps(prepare(args.job)if args.action=='prepare'else derive_fabric(args.job,args.source_job,args.fabric_graph)if args.action=='derive-fabric'else cook(args.job),indent=2))
