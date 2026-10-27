"""Package a closed UV1/detail roundtrip; default is read-only verification."""
import argparse, json, shutil, struct, hashlib
from pathlib import Path
import mod
from mod import ROOT, read_json, write_json, digest
from build_v2_anatomy_material import complete_depot
from v2_anatomy_material_contract import generate
from v2_skin_material import inspect
from audit_v2_target_uv1 import audit
from v2_cloth_material import native_objects
from player_rig_redirect import header_crc
from packed_mesh_format import CookedMesh

LOWER='characters/models/geralt/body/model/l_01_mg__body.w2mesh'
GRAPH='characters/malemod/anatomy/skin.w2mg'
UPPER='characters/models/geralt/body/model/t_01_mg__body_hires.w2mesh'

def property_span(raw,reader,offset,length,label,kind):
    end=offset+length
    if raw[offset]!=0:raise ValueError('Unobserved serialized property object')
    at=offset+1;found=[]
    while at+2<=end:
        name,=struct.unpack_from('<H',raw,at)
        if not name:break
        if at+8>end:raise ValueError('Truncated serialized property')
        name,ty,size=struct.unpack_from('<HHI',raw,at)
        if size<4 or at+size+4>end:raise ValueError('Serialized property leaves object')
        if reader.names[name]==label:
            if reader.names[ty]!=kind:raise ValueError('Serialized property type differs')
            found.append((at+8,size-4))
        at+=size+4
    if len(found)!=1:raise ValueError('Missing or duplicate exact serialized property')
    return found[0]

def upper_min_w_layout(raw):
    # CookedMesh validates header/table/export CRCs and the observed torso
    # palette. The raw-byte gate below also covers every other child export.
    reader=CookedMesh(raw,allow_stock_torso_mapping=True,allow_multi_section=True)
    offset,count,_=struct.unpack_from('<III',raw,88)
    entries=list(struct.iter_unpack('<HHIIIII',raw[offset:offset+count*24]))
    ids=[i for i,e in enumerate(entries)if reader.names[e[0]]=='CMesh']
    if len(ids)!=1:raise ValueError('Expected one stock upper CMesh')
    index=ids[0];entry=entries[index];at,length=entry[4],entry[3]
    box,box_length=property_span(raw,reader,at,length,'boundingBox','Box')
    minimum,min_length=property_span(raw,reader,box,box_length,'Min','Vector')
    word,word_length=property_span(raw,reader,minimum,min_length,'W','Float')
    if word_length!=4:raise ValueError('Bounding-box Min.W is not one float word')
    return dict(word=word,headerCRC=32,exportTableCRC=96,meshExportCRC=offset+index*24+20)

def upper_bytes_equivalence(before,after):
    if len(before)!=len(after):raise ValueError('Stock upper file size changed')
    a,b=upper_min_w_layout(before),upper_min_w_layout(after)
    if a!=b:raise ValueError('Stock upper serialized layout changed')
    allowed={offset+i for offset in a.values()for i in range(4)}
    changed=[i for i,(x,y)in enumerate(zip(before,after))if x!=y]
    if any(i not in allowed for i in changed):
        raise ValueError('Stock upper changed outside exact Box.Min.W and derived CRC words')
    return dict(onlyAllowedSerializedField='CMesh.boundingBox:Box.Min:Vector.W:Float',
        minWOffset=a['word'],beforeMinWHex=before[a['word']:a['word']+4].hex(),afterMinWHex=after[a['word']:a['word']+4].hex(),
        changedByteOffsets=changed,derivedCRCOffsets={k:v for k,v in a.items()if k!='word'},
        allOtherFileBytesIdentical=True,allSpatialXYZAndMaxWIdentical=True,headerAndExportCRCsVerified=True,
        noFileBytesPatched=True,epsilonUsed=False,
        semanticEvidence='SDK core/math.ws Box uses Min/Max Vector; GetBoxRange and observed gameplay bounds consume XYZ. Private engine C++ implementation unavailable; no universal claim about W reads.')

def audit_upper(before,after):
    before,after=Path(before),Path(after)
    if digest(Path(str(before)+'.1.buffer'))!=digest(Path(str(after)+'.1.buffer')):
        raise ValueError('Stock upper GPU buffer changed')
    return dict(schema='malemod.stock-upper-min-w-equivalence/1',baselineSHA256=digest(before),candidateSHA256=digest(after),
        GPUBufferSHA256=digest(Path(str(after)+'.1.buffer')),GPUBufferByteIdentical=True,
        **upper_bytes_equivalence(before.read_bytes(),after.read_bytes()))

def owned_path(value,owned):
    path=Path(value).resolve()
    if not path.is_relative_to(owned):raise ValueError('Receipt path leaves owned material work')
    return path

def intake_path(intake,relative):
    path=Path(relative)
    if path.is_absolute()or path.drive or '..'in path.parts:
        raise ValueError('Expected a bounded depot-relative input')
    target=(intake/path).resolve()
    if not target.is_relative_to(intake.resolve()):raise ValueError('Intake resource leaves its directory')
    return target

def preflight(job,baseline_info,graph_receipt):
    job,baseline_info,graph_receipt=map(lambda p:Path(p).resolve(),(job,baseline_info,graph_receipt))
    owned=(ROOT/'v2/build/materials').resolve()
    if not all(p.is_relative_to(owned)for p in (job,baseline_info,graph_receipt)):
        raise ValueError('Expected owned material inputs')
    if (job/'package.json').exists():raise ValueError('Preserve existing package descriptor')
    roundtrip=read_json(job/'official-roundtrip.json');verified=read_json(job/'native-uv1-audit.json')
    candidate_path=job/'uv1-candidate.json';candidate=read_json(candidate_path)
    baseline=read_json(baseline_info);compiled=read_json(graph_receipt);intake=job/'build/intake'
    if (roundtrip.get('baselineInfoSHA256')!=digest(baseline_info)
            or roundtrip.get('graphReceiptSHA256')!=digest(graph_receipt)
            or not roundtrip.get('sourceMapsUnchanged')or roundtrip.get('globallyAdopted')
            or not verified.get('nativeRoundtripVerified')
            or roundtrip.get('candidateReceiptSHA256')!=digest(candidate_path)
            or verified.get('globallyAdopted')
            or not all(candidate.get(k)for k in ['allOtherFBXPropertiesByteIdentical','stockUV1Unchanged','sourceUV0Unchanged'])):
        raise ValueError('Closed UV1 roundtrip and exact source ancestry required')
    fbx=owned_path(candidate['outputFBX'],owned)
    if digest(fbx)!=candidate['outputFBXSHA256']or digest(fbx.with_suffix('.xml'))!=candidate['outputXMLSHA256']:
        raise ValueError('Audited FBX or material sidecar changed')
    command=compiled.get('command',{})
    if not compiled.get('nativeCompiled')or command.get('exitCode')!=0 or not isinstance(command.get('args'),list)or not command['args']:
        raise ValueError('Successful officially compiled graph receipt required')
    compiler=owned_path(command['args'][0],owned)
    if compiler.name.lower()!='wcc_lite.exe'or digest(compiler)!=compiled['command']['wccSHA256']:
        raise ValueError('Exact owned native compiler changed')
    cooked=owned_path(roundtrip['cooked'],owned);old_cooked=owned_path(baseline['cooked'],owned)
    if (not compiled.get('nativeCompiled')or compiled.get('command',{}).get('exitCode')!=0
            or not compiled.get('compiledPayloadChanged')or compiled['SHA256']!=digest(intake/GRAPH)
            or roundtrip['graphSHA256']!=compiled['SHA256']
            or roundtrip['importedMeshSHA256']!=digest(intake/LOWER)):
        raise ValueError('Imported UV1 mesh or officially compiled detail graph changed')
    if ([c.get('command')for c in roundtrip.get('commands',[])]!=['import','cook']
            or any(c.get('exitCode')!=0 for c in roundtrip['commands'])):
        raise ValueError('Successful official import and cook records required')
    if (verified['candidateReceiptSHA256']!=digest(candidate_path)
            or owned_path(verified['candidateReceipt'],owned)!=candidate_path
            or verified['candidateCookedSHA256']!=digest(cooked/LOWER)
            or verified['candidateBufferSHA256']!=digest(cooked/(LOWER+'.1.buffer'))
            or verified['baselineCookedSHA256']!=digest(old_cooked/LOWER)
            or verified['baselineBufferSHA256']!=digest(old_cooked/(LOWER+'.1.buffer'))):
        raise ValueError('Native UV1 attribute proof changed')
    if verified.get('schema')!='malemod.target-stock-detail-uv1-native-audit/1':raise ValueError('Unrecognized native attribute audit')
    sections=verified.get('sections',[])
    if len(sections)!=6 or {(r.get('lod'),r.get('nativeMaterial'))for r in sections}!={(0,0),(0,1),(0,2),(1,0),(1,3),(1,4)}:
        raise ValueError('Native attribute audit must close both LODs and all material states')
    for row in sections:
        if row['nativeMaterial']==0:
            if not row.get('stockNativeUV1Exact'):raise ValueError('Stock secondary UV was not preserved')
        else:
            if not row.get('targetUV1HalfExact')or row.get('actualNativeWeldHalfEqualitySamples',0)<=0:
                raise ValueError('Native seam half-UV equality was not verified')
            field=job/('lod%d-target-uv1.npz'%row['lod'])
            if digest(field)!=row['targetFieldSHA256']:raise ValueError('Audited secondary UV field changed')
    changed={GRAPH,LOWER};maps=set()
    observed={p.relative_to(intake).as_posix()for p in intake.rglob('*')if p.is_file()and p.suffix not in ('.db','.db-shm','.db-wal')}
    if observed!=set(roundtrip['sourceInventory'])or not changed<=observed:
        raise ValueError('Closed source inventory is incomplete or has extra inputs')
    for relative,sha in roundtrip['sourceInventory'].items():
        path=intake_path(intake,relative)
        if path.name.lower()=='shaderdx12_0.cache':raise ValueError('An old material shader cache entered the intake')
        if relative not in changed and digest(path)!=sha:
            raise ValueError('Frozen nonmesh/nongraph source changed: '+relative)
        if relative.startswith('characters/malemod/anatomy/lod')and relative.endswith('.xbm'):maps.add(relative)
    expected_maps={'characters/malemod/anatomy/lod%d-%s.xbm'%(lod,role)for lod in range(2)for role in ['ambient','normal','specular','natural-diffuse','erect-diffuse']}
    if maps!=expected_maps or not inspect(intake/GRAPH).get('stockSeamDetail'):
        raise ValueError('Exact ten source textures and strict UV1 detail graph required')
    carriers=roundtrip.get('carrierBuffersUnchanged',[])
    expected_carriers={'characters/malemod/garments/'+kind+'.w2mesh.1.buffer'for kind in ['ribbed','elastic','red','blue']}
    if len(carriers)!=4 or {r['path']for r in carriers}!=expected_carriers:
        raise ValueError('All four unchanged native carrier buffers are required')
    for row in carriers:
        if digest(cooked/row['path'])!=row['sha256']or digest(old_cooked/row['path'])!=row['sha256']:
            raise ValueError('Frozen native carrier changed')
    for row in baseline['retainedAssets']:
        if not intake_path(intake,row['path']).is_file():raise ValueError('A retained native package asset is missing')
    return job,baseline,roundtrip,verified

def build(job,baseline_info,graph_receipt):
    job,baseline,roundtrip,verified=preflight(job,baseline_info,graph_receipt)
    frozen_inputs={relative:digest(intake_path(job/'build/intake',relative))for relative in roundtrip['sourceInventory']}
    cfg=mod.settings();cfg['depot']=complete_depot(cfg)
    compiled=read_json(graph_receipt);cfg['wcc']=Path(compiled['command']['args'][0])
    if digest(cfg['wcc'])!=compiled['command']['wccSHA256']:raise ValueError('Official compiler changed')
    cfg['base']=ROOT.parent/'Work/dependencies/base-wolverine'
    lock=read_json(ROOT/'dependencies/base.lock.json');lock['commit']='47023a7f53d794cff84f2f423ba6a7d1fb98ec0f'
    write_json(job/'dependencies/base.lock.json',lock)
    if Path(graph_receipt).resolve()!=(job/'graph-compiled.json').resolve():
        shutil.copy2(graph_receipt,job/'graph-compiled.json')
    previous=mod.ROOT;mod.ROOT=job
    try:
        published=mod.build(cfg,dict(name='mod000000WitcherV2',version='2.0.0-stock-seam-detail',platform='pc',cacheBuilders=['textures'],reuseReadOnlyDepot=True,
            scope='Verified secondary UV and local stock skin detail; original geometry, primary UV, texture inputs and numerical physics unchanged'),job/'build/intake')
    finally:mod.ROOT=previous
    observed={p.relative_to(job/'build/intake').as_posix()for p in(job/'build/intake').rglob('*')if p.is_file()and p.suffix not in ('.db','.db-shm','.db-wal')}
    if observed!=set(frozen_inputs)or any(digest(intake_path(job/'build/intake',relative))!=sha for relative,sha in frozen_inputs.items()):
        raise ValueError('Native build changed the frozen source intake')
    return finalize_existing(job,baseline_info,graph_receipt,published,digest(published/'build-manifest.json'))

def verify_published(job,published,manifest_sha,compiled):
    published=Path(published).resolve()
    if not published.is_relative_to((job/'publish').resolve()):raise ValueError('Existing publish leaves this exact job')
    manifest_path=published/'build-manifest.json'
    if not manifest_sha or digest(manifest_path)!=manifest_sha:raise ValueError('Existing published manifest hash differs')
    manifest=read_json(manifest_path)
    if manifest.get('project')!='mod000000WitcherV2'or manifest.get('version')!='2.0.0-stock-seam-detail'or manifest.get('baseCommit')!='47023a7f53d794cff84f2f423ba6a7d1fb98ec0f'or manifest.get('shaderCompilation'):
        raise ValueError('Existing published project identity differs')
    files=manifest['files'];paths=[r['path']for r in files]
    actual={p.relative_to(published).as_posix()for p in published.rglob('*')if p.is_file()}
    if len(paths)!=len(set(paths))or actual!=set(paths)|{'build-manifest.json'}:raise ValueError('Existing published inventory differs')
    for row in files:
        path=intake_path(published,row['path'])
        if path.name.lower()=='shaderdx12_0.cache'or path.stat().st_size!=row['bytes']or digest(path)!=row['sha256']:
            raise ValueError('Existing published file changed or contains an old shader cache')
    commands=manifest['nativeCommands']
    if [r.get('command')for r in commands]!=['cook','buildcache','dependencies','pack','metadatastore']:
        raise ValueError('Expected exact five successful native package commands')
    compiler=Path(compiled['command']['args'][0]).resolve();depot=None
    for command in commands:
        args=command['args']
        if command.get('exitCode')!=0 or command.get('wccSHA256')!=digest(compiler)or Path(args[0]).resolve()!=compiler:
            raise ValueError('Existing native command/compiler differs')
        if Path(args[args.index('-workspaceDir')+1]).resolve()!=(job/'build/intake').resolve():
            raise ValueError('Existing native workspace differs')
        current=Path(args[args.index('-uncookDir')+1]).resolve()
        if not current.is_relative_to((job/'build').resolve())or depot is not None and current!=depot:
            raise ValueError('Existing native dependency view differs')
        depot=current;log=intake_path(job,command['logPath'])
        if digest(log)!=command['logSHA256']or mod.native_failure(log.read_text(errors='replace'),command['exitCode']):
            raise ValueError('Existing native command log failed or changed')
    cook=commands[0];native_input=Path(next(a.split('=',1)[1]for a in cook['args']if a.startswith('-mod='))).resolve()
    cooked=Path(next(a.split('=',1)[1]for a in cook['args']if a.startswith('-outdir='))).resolve()
    if not native_input.is_relative_to((job/'build').resolve())or cooked!=native_input.parent/'cooked':
        raise ValueError('Existing native input/cooked paths differ')
    source={p.relative_to(job/'build/intake').as_posix():digest(p)for p in(job/'build/intake').rglob('*')if p.is_file()and p.suffix not in ('.db','.db-shm','.db-wal')}
    native={p.relative_to(native_input).as_posix()for p in native_input.rglob('*')if p.is_file()}
    if native!=set(source):raise ValueError('Existing native input inventory differs')
    for relative,sha in source.items():
        if digest(intake_path(native_input,relative))!=sha or digest(intake_path(depot,relative))!=sha:
            raise ValueError('Existing native input/depot differs from frozen intake')
    for command in commands[1:3]:
        if next(a.split('=',1)[1]for a in command['args']if a.startswith('-db='))!=str(cooked/'cook.db'):
            # Recorded Windows separators/case may differ through the junction.
            db=Path(next(a.split('=',1)[1]for a in command['args']if a.startswith('-db='))).resolve()
            if db!=cooked/'cook.db':raise ValueError('Native cache/dependencies used another cook database')
    return published,manifest,cooked

def finalize_existing(job,baseline_info,graph_receipt,published,manifest_sha):
    job,baseline,roundtrip,verified=preflight(job,baseline_info,graph_receipt)
    compiled=read_json(graph_receipt)
    if digest(job/'graph-compiled.json')!=digest(graph_receipt):raise ValueError('Job compiler receipt differs')
    published,manifest,cooked=verify_published(job,published,manifest_sha,compiled)
    # The final cooker must reproduce the already independently audited buffer.
    if digest(cooked/(LOWER+'.1.buffer'))!=verified['candidateBufferSHA256']:
        raise ValueError('Final cook differs from the closed UV1 corner audit')
    final_audit=audit(job/'uv1-candidate.json',Path(read_json(baseline_info)['cooked'])/LOWER,cooked/LOWER,job/'final-native-uv1-audit.json')
    material=generate(cooked/LOWER,job/'build/intake'/LOWER,job/'material-contract.json',graph=job/'build/intake'/GRAPH)
    geometry=[]
    for row in roundtrip['carrierBuffersUnchanged']:
        if digest(cooked/row['path'])!=row['sha256']:raise ValueError('Final garment carrier changed')
        geometry.append(dict(path=row['path'],SHA256=row['sha256']))
    upper=audit_upper(Path(baseline['cooked'])/UPPER,cooked/UPPER)
    write_json(job/'stock-upper-equivalence.json',upper)
    result=dict(baseline,directory=str(published),cooked=str(cooked),skinGraph=GRAPH,skinGraphSHA256=digest(job/'build/intake'/GRAPH),
        graphSHA256=digest(job/'build/intake'/baseline['graph']),materialContractSHA256=digest(job/'material-contract.json'),
        cookedBodyBufferSHA256=material['cookedBufferSHA256'],nativeGeometry=geometry,nativeGameplayObserved=False,
        sourcePackageInfoPath=str(Path(baseline_info).resolve()),sourcePackageInfoSHA256=digest(baseline_info),
        stockSeamDetail=dict(roundtripSHA256=digest(job/'official-roundtrip.json'),nativeAuditSHA256=digest(job/'final-native-uv1-audit.json'),
            graphReceiptSHA256=digest(graph_receipt),uvIndex=1,sourceUV0Unchanged=True,sourceMapsUnchanged=True,
            stockUpperEquivalenceSHA256=digest(job/'stock-upper-equivalence.json')),
        finalizedExistingPublish=dict(manifestSHA256=manifest_sha,nativeCommandsRerun=False))
    result.pop('shaderCompilation',None)
    result['retainedAssets']=[dict(path=r['path'],sha256=digest(job/'build/intake'/r['path']))for r in baseline['retainedAssets']]
    write_json(job/'package.json',result)
    return dict(packageInfo=str(job/'package.json'),packageInfoSHA256=digest(job/'package.json'),nativeAttributeProof=final_audit['nativeRoundtripVerified'])

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('job','baseline-info','graph-receipt'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--execute',action='store_true');p.add_argument('--finalize-existing',type=Path);p.add_argument('--manifest-sha256');a=p.parse_args()
    if a.finalize_existing:
        if not a.manifest_sha256 or a.execute:p.error('Finalize requires --manifest-sha256 and must not use --execute')
        result=finalize_existing(a.job,a.baseline_info,a.graph_receipt,a.finalize_existing,a.manifest_sha256)
    elif a.execute:result=build(a.job,a.baseline_info,a.graph_receipt)
    else:
        preflight(a.job,a.baseline_info,a.graph_receipt);result=dict(verified=True,nativeCommandsExecuted=False)
    print(json.dumps(result,indent=2))
