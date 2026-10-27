"""Private physical-R body import/package; no adoption, staging or shader cache."""
import argparse,json,shutil,os
from pathlib import Path
import mod
from mod import ROOT,digest,read_json,write_json
from build_v2_anatomy_material import complete_depot,texture_properties
from build_v2_detail_package import audit_upper,intake_path,owned_path,LOWER,UPPER,GRAPH
from audit_v2_physical_skin_field import audit


def inventory(directory):
    return {p.relative_to(directory).as_posix():digest(p)for p in directory.rglob('*')if p.is_file()and p.suffix not in('.db','.db-shm','.db-wal')}


def validate_source_delta(original,frozen,replacements,removed,graph_sha):
    expected={'characters/malemod/anatomy/lod%d-%s.xbm'%(lod,kind)for lod in(0,1)for kind in('natural-diffuse','erect-diffuse','normal','specular')}
    if set(replacements)!=expected or removed!={'characters/malemod/anatomy/lod%d-ambient.xbm'%lod for lod in(0,1)}:
        raise ValueError('Only exact eight original maps and two disconnected Ambient removals permitted')
    if set(frozen)!=set(original)-removed:raise ValueError('Fresh physical intake has unexpected/missing files')
    changed={GRAPH,LOWER}|set(replacements)
    for relative,sha in original.items():
        if relative not in removed|changed and frozen[relative]!=sha:raise ValueError('Unrelated intake asset changed: '+relative)
    if frozen[GRAPH]!=graph_sha:raise ValueError('Current physical graph was overwritten')
    for relative,sha in replacements.items():
        if frozen[relative]!=sha:raise ValueError('Original map replacement differs')


def preflight(job,baseline_info,field_receipt,maps_receipt,graph_receipt,graph):
    owned=(ROOT/'v2/build/materials').resolve()
    job,baseline_info,field_receipt,maps_receipt,graph_receipt,graph=[owned_path(p,owned)for p in(job,baseline_info,field_receipt,maps_receipt,graph_receipt,graph)]
    if job.exists():raise ValueError('Use a fresh physical cook job; never overwrite an existing job')
    baseline,field,maps,compiled=[read_json(p)for p in(baseline_info,field_receipt,maps_receipt,graph_receipt)]
    source=baseline_info.parent/'build/intake';original=inventory(source)
    if (not field.get('onlySourceColorRChanged')or not field.get('sourceGBAUnchanged')or not field.get('stockRGBAUnchanged')
            or not field.get('geometryUV0UV1BonesNormalsTangentsUnchanged')or field.get('globallyAdopted')):raise ValueError('Exact R-only source field required')
    fbx=Path(field['outputFBX']);fbx=fbx if fbx.is_absolute()else ROOT/fbx
    if digest(fbx)!=field['outputFBXSHA256']or digest(fbx.with_suffix('.xml'))!=field['outputXMLSHA256']:raise ValueError('Physical FBX or sidecar changed')
    command=compiled.get('command',{})
    if (not compiled.get('nativeCompiled')or not compiled.get('compiledPayloadChanged')or command.get('exitCode')!=0
            or digest(graph)!=compiled.get('SHA256')or digest(command['args'][0])!=command.get('wccSHA256')):raise ValueError('Exact successfully resaved graph required')
    if maps.get('schema')!='malemod.original-source-native-imports/1'or not maps.get('nativeImported')or len(maps['files'])!=8:raise ValueError('Eight closed original source map imports required')
    replacements={}
    for row in maps['files']:
        path=owned_path(row['target'],owned);relative='characters/malemod/anatomy/'+path.name
        if relative in replacements or relative not in original:raise ValueError('Unexpected or duplicate source map')
        if digest(path)!=row['SHA256']or row['command']['exitCode']!=0:raise ValueError('Imported original map changed/failed')
        props=texture_properties(path)
        if props['compression']!='TCM_QualityColor'or props['textureGroup']!=row['textureGroup']:raise ValueError('Original RGB packing changed')
        if digest(row['sourceTGA'])!=row['sourceTGASHA256']or digest(row['sourceDDS'])!=row['sourceDDSSHA256']:raise ValueError('Canonical map input changed')
        replacements[relative]=path
    expected={'characters/malemod/anatomy/lod%d-%s.xbm'%(lod,kind)for lod in(0,1)for kind in('natural-diffuse','erect-diffuse','normal','specular')}
    removed={'characters/malemod/anatomy/lod%d-ambient.xbm'%lod for lod in(0,1)}
    if set(replacements)!=expected or not removed<=original.keys():raise ValueError('Exact physical texture inventory required')
    if any(Path(p).name.lower()=='shaderdx12_0.cache'for p in original):raise ValueError('Never carry old shader caches into the fresh cook')
    return dict(job=job,baseline_info=baseline_info,field_receipt=field_receipt,maps_receipt=maps_receipt,graph_receipt=graph_receipt,graph=graph,
        baseline=baseline,field=field,maps=maps,compiled=compiled,source=source,original=original,fbx=fbx,replacements=replacements,removed=removed)


def execute(**args):
    p=preflight(**args);job=p['job'];job.mkdir();workspace=job/'build/intake'
    for relative,sha in p['original'].items():
        if relative in p['removed']:continue
        target=intake_path(workspace,relative);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p['source']/relative,target)
        if digest(target)!=sha:raise ValueError('Frozen reference copy differs')
    # Overrides go LAST; the historical03 graph must never overwrite the new graph.
    for relative,path in p['replacements'].items():shutil.copy2(path,intake_path(workspace,relative))
    shutil.copy2(p['graph'],workspace/GRAPH)
    shutil.copy2(p['graph_receipt'],job/'graph-compiled.json')
    authored=p['graph_receipt'].parent/'graph-authored.json'
    if authored.exists():shutil.copy2(authored,job/'graph-authored.json')
    fbx=job/'geralt-physical-skin.fbx';shutil.copy2(p['fbx'],fbx);shutil.copy2(p['fbx'].with_suffix('.xml'),fbx.with_suffix('.xml'))
    cfg=mod.settings();cfg['depot']=complete_depot(cfg);cfg['wcc']=Path(p['compiled']['command']['args'][0]);cfg['base']=ROOT.parent/'Work/dependencies/base-wolverine'
    lock=read_json(ROOT/'dependencies/base.lock.json');lock['commit']='47023a7f53d794cff84f2f423ba6a7d1fb98ec0f';write_json(job/'dependencies/base.lock.json',lock)
    previous=mod.ROOT;mod.ROOT=job
    try:
        imported=mod.run_wcc(cfg,'import',['-depot=local','-file='+str(fbx),'-out='+str(workspace/LOWER)],workspace,'physical-source-r-body-import')
        frozen=inventory(workspace)
        validate_source_delta(p['original'],frozen,{rel:digest(path)for rel,path in p['replacements'].items()},p['removed'],p['compiled']['SHA256'])
        write_json(job/'imports.json',dict(schema='malemod.physical-source-skin-import/1',graphSHA256=frozen[GRAPH],sourceInventory=frozen,
            fieldReceipt=str(p['field_receipt']),fieldReceiptSHA256=digest(p['field_receipt']),mapsReceipt=str(p['maps_receipt']),mapsReceiptSHA256=digest(p['maps_receipt']),
            graphReceiptSHA256=digest(p['graph_receipt']),baselineInfo=str(p['baseline_info']),baselineInfoSHA256=digest(p['baseline_info']),mesh=dict(path=str(workspace/LOWER),SHA256=frozen[LOWER],command=imported)))
        initial_input=job/'build/physical-native-input';initial_cooked=job/'build/physical-cooked';initial_input.mkdir();initial_cooked.mkdir()
        for relative in frozen:
            path=workspace/relative
            if path.suffix.startswith(('.w2','.w3'))or path.suffix in('.xbm','.env','.xml','.csv'):
                target=intake_path(initial_input,relative);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
        initial_command=mod.run_wcc(cfg,'cook',['-platform=pc','-mod='+str(initial_input),'-outdir='+str(initial_cooked)+os.sep],workspace,'physical-source-r-audit-cook')
        first_audit=audit(p['field_receipt'],Path(p['baseline']['cooked'])/LOWER,initial_cooked/LOWER,job/'native-r-audit.json')
        audit_upper(Path(p['baseline']['cooked'])/UPPER,initial_cooked/UPPER)
        for kind in('ribbed','elastic','red','blue'):
            relative='characters/malemod/garments/'+kind+'.w2mesh.1.buffer'
            if digest(initial_cooked/relative)!=digest(Path(p['baseline']['cooked'])/relative):raise ValueError('Initial carrier buffer changed')
        write_json(job/'official-roundtrip.json',dict(schema='malemod.physical-source-r-official-roundtrip/1',
            fieldReceiptSHA256=digest(p['field_receipt']),mapsReceiptSHA256=digest(p['maps_receipt']),graphReceiptSHA256=digest(p['graph_receipt']),
            baselineInfoSHA256=digest(p['baseline_info']),commands=[imported,initial_command],cooked=str(initial_cooked),nativeAuditSHA256=digest(job/'native-r-audit.json'),nativeRRoundtripVerified=True,globallyAdopted=False))
        print('INITIAL NATIVE R ROUNDTRIP PASSED; beginning package build',flush=True)
        published=mod.build(cfg,dict(name='mod000000WitcherV2',version='2.0.0-physical-source-skin',platform='pc',cacheBuilders=['textures'],reuseReadOnlyDepot=True,
            scope='Original canonical source maps at UV0, stock chart at UV1 and physical vertex-R blend; geometry and numerical physics unchanged'),workspace)
    finally:mod.ROOT=previous
    if inventory(workspace)!=frozen or inventory(p['source'])!=p['original']:raise ValueError('Frozen source intake changed during native build')
    manifest=read_json(published/'build-manifest.json');cook=next(c for c in manifest['nativeCommands']if c['command']=='cook')
    cooked=Path(next(a.split('=',1)[1]for a in cook['args']if a.startswith('-outdir=')))
    if digest(str(cooked/LOWER)+'.1.buffer')!=first_audit['candidateBufferSHA256']:raise ValueError('Final package cook changed the audited geometry buffer')
    native=audit(p['field_receipt'],Path(p['baseline']['cooked'])/LOWER,cooked/LOWER,job/'final-native-r-audit.json')
    upper=audit_upper(Path(p['baseline']['cooked'])/UPPER,cooked/UPPER);write_json(job/'stock-upper-equivalence.json',upper)
    carriers=[]
    for kind in('ribbed','elastic','red','blue'):
        relative='characters/malemod/garments/'+kind+'.w2mesh.1.buffer';sha=digest(cooked/relative)
        if sha!=digest(Path(p['baseline']['cooked'])/relative):raise ValueError('Garment carrier buffer changed')
        carriers.append(dict(path=relative,SHA256=sha))
    from v2_anatomy_material_contract import generate
    material=generate(cooked/LOWER,workspace/LOWER,job/'material-contract.json',graph=workspace/GRAPH)
    result=dict(p['baseline'],directory=str(published),cooked=str(cooked),skinGraph=GRAPH,skinGraphSHA256=digest(workspace/GRAPH),graphSHA256=digest(workspace/p['baseline']['graph']),
        importsSHA256=digest(job/'imports.json'),materialContractSHA256=digest(job/'material-contract.json'),cookedBodyBufferSHA256=digest(str(cooked/LOWER)+'.1.buffer'),nativeGeometry=carriers,
        sourcePackageInfoPath=str(p['baseline_info']),sourcePackageInfoSHA256=digest(p['baseline_info']),nativeGameplayObserved=False,
        physicalSourceSkin=dict(fieldReceiptSHA256=digest(p['field_receipt']),mapsReceiptSHA256=digest(p['maps_receipt']),nativeAuditSHA256=digest(job/'final-native-r-audit.json'),
            graphReceiptSHA256=digest(p['graph_receipt']),stockUpperEquivalenceSHA256=digest(job/'stock-upper-equivalence.json'),onlySourceRGeometryAttributeChanged=True,sourceUV0Unchanged=True,UV1Exact03=True,originalMapsOnly=True),
        retainedAssets=[dict(path=r['path'],sha256=digest(workspace/r['path']))for r in p['baseline']['retainedAssets']])
    for old in('shaderCompilation','stockSeamDetail','seamMaterials','seamTextureImports','finalizedExistingPublish','combinedIntakeSHA256'):result.pop(old,None)
    write_json(job/'package.json',result)
    return dict(packageInfo=str(job/'package.json'),packageInfoSHA256=digest(job/'package.json'),nativeRRoundtripVerified=native['nativeRRoundtripVerified'],shaderCacheBuilt=False,globallyAdopted=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in('job','baseline-info','field-receipt','maps-receipt','graph-receipt','graph'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--execute',action='store_true');a=vars(p.parse_args());run=a.pop('execute');a={key.replace('-','_'):value for key,value in a.items()}
    print(json.dumps(execute(**a)if run else dict(verified=bool(preflight(**a)),nativeCommandsExecuted=False),indent=2))
