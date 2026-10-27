"""Prepare/resave/import/cook the isolated source-fabric carrier job.

No current binding or installed/staged resource is replaced. The original
carrier FBX geometry and resulting native buffers must remain byte-identical.
"""
import argparse
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

import mod
from mod import ROOT,digest,read_json,write_json
from v2_fabric_material import GRAPH,ROLE_PARAMETER,author,validate_hlsl
from v2_skin_material import state

JOB=ROOT/'v2/build/materials/carriers-08'
PRIOR=ROOT/'v2/build/materials/carriers-07'
KINDS=('ribbed','elastic','red','blue')


def prepare(job=JOB):
    job=Path(job);cfg=mod.settings();sdk=cfg['redkit']/'r4data'
    intake=job/'build/intake';assets=intake/'characters/malemod/garments';assets.mkdir(parents=True,exist_ok=True)
    graph=intake/GRAPH
    proof=author(sdk/'engine/materials/graphs/pbr_std.w2mg',graph,sdk)
    proof['nativeHLSL']=validate_hlsl();write_json(job/'graph-authored.json',proof)
    rows=[]
    prior_info=read_json(PRIOR/'package.json');prior_cook=Path(prior_info['cooked'])
    for role,kind in enumerate(KINDS):
        source=PRIOR/(kind+'.fbx');fbx=job/source.name;shutil.copy2(source,fbx)
        tree=ET.parse(PRIOR/(kind+'.xml'))
        material=tree.find('./materials/material')
        material.attrib['base']=GRAPH.replace('/','\\')
        params={p.attrib['name']:p for p in material.findall('param')}
        params[ROLE_PARAMETER].attrib['value']=str(role)
        params['RSpecBase'].attrib['value']='0.0'
        # These measured texture inputs remain available for compatibility;
        # the source analytic graph does not substitute their bump/albedo.
        for suffix in ('.xbm','-normal.xbm'):
            origin=PRIOR/'build/intake/characters/malemod/garments'/(kind+suffix)
            shutil.copy2(origin,assets/origin.name)
        tree.write(fbx.with_suffix('.xml'),encoding='utf-8',xml_declaration=True)
        old_buffer=prior_cook/'characters/malemod/garments'/(kind+'.w2mesh.1.buffer')
        rows.append(dict(kind=kind,role=role,fbxSHA256=digest(fbx),priorFbxSHA256=digest(source),priorNativeBufferSHA256=digest(old_buffer)))
    report=dict(schema='malemod.witcher-v2-source-fabric-preparation/1',graph=proof,carriers=rows,
                geometryEdited=False,currentBindingsModified=False,nativeObserved=False)
    write_json(job/'prepared.json',report)
    return report


def build(job=JOB):
    job=Path(job);cfg=mod.settings();cfg['depot']=cfg['redkit']/'r4data';cfg['base']=ROOT.parent/'Work/dependencies/base-wolverine'
    if not(job/'prepared.json').exists():prepare(job)
    intake=job/'build/intake';graph=intake/GRAPH;before=state(graph)[2][0][3]
    prior_root=mod.ROOT;mod.ROOT=job
    try:
        temp=job/'build/graph-resave-temp';temp.mkdir(parents=True,exist_ok=True)
        command=mod.run_wcc(cfg,'resave',['-tmpdir='+str(temp),'-path='+str(Path(GRAPH).parent),'-ext=w2mg','-nosourcecontrol','-ignorefileversion'],intake,'source-fabric-graph-resave')
        args=command['args'];depot=Path(args[args.index('-uncookDir')+1]);compiled=depot/GRAPH
        after=state(compiled)[2][0][3]
        shutil.copy2(compiled,graph)
        write_json(job/'graph-compiled.json',dict(command=command,graphSHA256=digest(graph),compiledPayloadChanged=before!=after,
                                                originalCompiledPayloadSHA256=__import__('hashlib').sha256(before).hexdigest(),compiledPayloadSHA256=__import__('hashlib').sha256(after).hexdigest(),
                                                nativeObserved=False))
        imports=[]
        for kind in KINDS:
            fbx=job/(kind+'.fbx');target=intake/'characters/malemod/garments'/(kind+'.w2mesh')
            command=mod.run_wcc(cfg,'import',['-depot=local','-file='+str(fbx),'-out='+str(target)],intake,'source-fabric-'+kind)
            imports.append(dict(kind=kind,sourceFbxSHA256=digest(fbx),nativeSHA256=digest(target),command=command))
        lock=read_json(ROOT/'dependencies/base.lock.json');lock['commit']='47023a7f53d794cff84f2f423ba6a7d1fb98ec0f';write_json(job/'dependencies/base.lock.json',lock)
        project=dict(name='mod000000V2Fabric',version='2.0.0-source-fabric-preview',platform='pc',cacheBuilders=['textures'],reuseReadOnlyDepot=True,
                     scope='Canonical procedural raster fabric material, unchanged observed native carrier geometry')
        package=mod.build(cfg,project,intake);manifest=read_json(package/'build-manifest.json')
        cook=next(c for c in manifest['nativeCommands']if c['command']=='cook')
        cooked=Path(next(a.split('=',1)[1]for a in cook['args']if a.startswith('-outdir=')))
        prepared=read_json(job/'prepared.json');geometry=[]
        for row in prepared['carriers']:
            path=cooked/'characters/malemod/garments'/(row['kind']+'.w2mesh.1.buffer')
            current=digest(path)
            if current!=row['priorNativeBufferSHA256']:raise ValueError('Source fabric cook changed native carrier buffer: '+row['kind'])
            geometry.append(dict(kind=row['kind'],bufferSHA256=current,byteIdenticalToCarriers07=True))
        report=dict(directory=str(package),cooked=str(cooked),graph=GRAPH,graphSHA256=digest(graph),roleParameter=ROLE_PARAMETER,
                    roleValues={k:i for i,k in enumerate(KINDS)},RSpecBase=0,roughness=224/255,imports=imports,nativeGeometry=geometry,
                    shaderCacheRequired=True,nativeObserved=False,currentBindingsModified=False)
        write_json(job/'package.json',report);print(json.dumps(report,indent=2));return report
    finally:mod.ROOT=prior_root


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--job',type=Path,default=JOB);parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args()
    if args.prepare_only:print(json.dumps(prepare(args.job),indent=2))
    else:build(args.job)
