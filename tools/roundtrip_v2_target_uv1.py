"""Private official import/cook of UV1-only mesh plus separately compiled graph."""
import argparse,json,os,shutil
from pathlib import Path
import mod
from mod import ROOT,digest,read_json,write_json
from build_v2_anatomy_material import complete_depot
from audit_v2_target_uv1 import audit

LOWER='characters/models/geralt/body/model/l_01_mg__body.w2mesh'
GRAPH='characters/malemod/anatomy/skin.w2mg'


def run(job,graph,graph_receipt,baseline_info):
    job,graph,graph_receipt,baseline_info=map(lambda p:Path(p).resolve(),(job,graph,graph_receipt,baseline_info))
    owned=(ROOT/'v2/build/materials').resolve()
    if not all(p.is_relative_to(owned)for p in(job,graph,graph_receipt,baseline_info)):raise ValueError('Use only owned private material inputs')
    candidate=read_json(job/'uv1-candidate.json');fbx=Path(candidate['outputFBX']);xml=fbx.with_suffix('.xml')
    if digest(fbx)!=candidate['outputFBXSHA256']or digest(xml)!=candidate['outputXMLSHA256']:raise ValueError('Attribute candidate changed')
    compiled=read_json(graph_receipt)
    if not compiled.get('nativeCompiled')or digest(graph)!=compiled['SHA256']:raise ValueError('Exact official compiled graph receipt required')
    shutil.copy2(graph_receipt,job/'graph-compiled.json')
    authored=graph_receipt.parent/'graph-authored.json'
    if authored.exists():shutil.copy2(authored,job/'graph-authored.json')
    baseline=read_json(baseline_info);source_job=baseline_info.parent;source=source_job/'build/intake';workspace=job/'build/intake'
    if workspace.exists():raise ValueError('Preserve existing roundtrip workspace; choose a fresh UV1 candidate job')
    source_inventory={p.relative_to(source).as_posix():digest(p)for p in source.rglob('*')if p.is_file()and p.suffix not in('.db','.db-shm','.db-wal')}
    mod.copy_tree(source,workspace)
    for relative,sha in source_inventory.items():
        if digest(workspace/relative)!=sha:raise ValueError('Private intake copy differs: '+relative)
    graph_target=workspace/GRAPH;shutil.copy2(graph,graph_target)
    maps={p:sha for p,sha in source_inventory.items()if p.startswith('characters/malemod/anatomy/lod')and p.endswith('.xbm')}
    if len(maps)!=10:raise ValueError('Expected exact ten frozen source maps')
    cfg=mod.settings();cfg['depot']=complete_depot(cfg)
    if compiled.get('command',{}).get('args'):cfg['wcc']=Path(compiled['command']['args'][0])
    cfg['base']=ROOT.parent/'Work/dependencies/base-wolverine'
    cooked=job/'build/uv1-cooked';native=job/'build/uv1-native-input';cooked.mkdir();native.mkdir()
    original_root=mod.ROOT;mod.ROOT=job;commands=[]
    try:
        commands.append(mod.run_wcc(cfg,'import',['-depot=local','-file='+str(fbx),'-out='+str(workspace/LOWER)],workspace,'uv1-official-mesh-import'))
        for p in workspace.rglob('*'):
            if p.is_file()and(p.suffix.startswith(('.w2','.w3'))or p.suffix in('.xbm','.env','.xml','.csv')):
                relative=p.relative_to(workspace);target=native/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
        commands.append(mod.run_wcc(cfg,'cook',['-platform=pc','-mod='+str(native),'-outdir='+str(cooked)+os.sep],workspace,'uv1-official-mesh-cook'))
    finally:mod.ROOT=original_root
    for relative,sha in source_inventory.items():
        if digest(source/relative)!=sha:raise ValueError('Frozen baseline intake was modified: '+relative)
        if relative not in(GRAPH,LOWER)and digest(workspace/relative)!=sha:raise ValueError('Nongraph/nonmesh private asset changed: '+relative)
    if digest(graph_target)!=compiled['SHA256']:raise ValueError('Compiled graph changed during roundtrip')
    for relative,sha in maps.items():
        if digest(workspace/relative)!=sha:raise ValueError('Frozen source map changed: '+relative)
    baseline_cooked=Path(baseline['cooked']);carriers=[]
    for kind in('ribbed','elastic','red','blue'):
        relative='characters/malemod/garments/'+kind+'.w2mesh.1.buffer'
        if digest(cooked/relative)!=digest(baseline_cooked/relative):raise ValueError('Frozen garment buffer changed: '+relative)
        carriers.append(dict(path=relative,sha256=digest(cooked/relative)))
    proof=dict(schema='malemod.target-uv1-official-roundtrip/1',candidateReceiptSHA256=digest(job/'uv1-candidate.json'),
        graph=str(graph),graphSHA256=digest(graph),graphReceiptSHA256=digest(graph_receipt),baselineInfo=str(baseline_info),baselineInfoSHA256=digest(baseline_info),
        sourceInventory=source_inventory,commands=commands,cooked=str(cooked),sourceMapsUnchanged=True,carrierBuffersUnchanged=carriers,
        importedMeshSHA256=digest(workspace/LOWER),globallyAdopted=False,shaderCacheBuilt=False)
    write_json(job/'official-roundtrip.json',proof)
    native_audit=audit(job/'uv1-candidate.json',baseline_cooked/LOWER,cooked/LOWER,job/'native-uv1-audit.json')
    from v2_anatomy_material_contract import generate
    material=generate(cooked/LOWER,workspace/LOWER,job/'material-contract.json',graph=graph_target)
    return dict(roundtrip=proof,audit=native_audit,materialContract=material)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in('job','graph','graph-receipt','baseline-info'):parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args();print(json.dumps(run(a.job,a.graph,a.graph_receipt,a.baseline_info),indent=2))
