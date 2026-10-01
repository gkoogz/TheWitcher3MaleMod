"""Owned player-stack pose test; preserve stock animation and appearance binding.

No stock depot writes. Observed player entities are patched only at two observed
equal-length rig imports and their CRCs; never rewritten through the converter.
"""
import argparse
import copy
import json
import shutil
import struct
import subprocess
import uuid
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path
import numpy as np
from mod import ROOT, settings, base_checkout, digest, write_json, build, verify_package, native_assert_key, native_failure
from prepare_motion import scalar, rig_world
from build_deformation_probe import probe_script
from player_rig_redirect import redirect, NEW_RIG

PLAYER='characters/base_entities/man_base/player_base_m/player_base_m.w2ent'
OLD_PARENT='characters/base_entities/man_base/man_base.w2ent'
PARENT='characters/base_entities/man_base/malebase.w2ent'
RIG=NEW_RIG.replace('\\','/')
GRAPH='characters/malemod/behavior/deformation.w2beh'
BODY='items/bodyparts/geralt_items/legs/bare/l_01_mg__body_underwear.w2ent'
PLAYER_SHA='430f88397bede2acd001f8699ca36144a895713f5d1e23c328b6afc37ebcb362'
RIG_SHA='a127b0b3ae7beb84d14bc940a2198a93b31d333397f5c4f59cf452cd5d29be1d'
PARENT_SHA='2fa3b1f381c85059b2f583925ee1c4ed59ccfce98ba5be20ea05531c6c4443b0'
EFFECTIVE_PLAYER='gameplay/templates/characters/player/player.w2ent'
GERALT_PLAYER='characters/player_entities/geralt/geralt_player.w2ent'
EFFECTIVE_TEMPLATES=(
    (EFFECTIVE_PLAYER,'c567566adbb9526ca8aba85555759f5d3f938c5ebcb590dfcd62189fec0ab415',163,
     'build/inspection/native-4559847a44f0/inspection.json'),
    (GERALT_PLAYER,'85d3b48eeb1639378346d36c12a88ab472a64cf191249d5990088bc26c9035e8',164,
     'build/inspection/native-2be16d6e54c1/inspection.json'))
STOCK_BASELINE='build/probe/stock-player-cook-16bcafa78ab2/source-baseline.json'


def verify_stock_template_baseline(cfg, receipt):
    """Permit only diagnostics demonstrated by the same untouched inputs/SDK."""
    receipt=(ROOT/receipt).resolve()
    if not receipt.is_relative_to(ROOT/'build/probe'):raise ValueError('Expected owned native stock baseline')
    baseline=json.loads(receipt.read_text())
    expected={p:h for p,h,v,i in EFFECTIVE_TEMPLATES}
    if baseline['sourceHashes']!=expected:raise ValueError('Stock baseline resource hashes changed')
    native=baseline['native'];log=ROOT/native['logPath']
    if digest(cfg['wcc'])!=native['wccSHA256'] or digest(log)!=native['logSHA256'] or native['exitCode']!=0:
        raise ValueError('Native stock baseline SDK/log changed or failed to execute')
    intake=Path(next(a.split('=',1)[1] for a in native['args'] if a.startswith('-mod='))).resolve()
    if not intake.is_relative_to(receipt.parent):raise ValueError('Stock baseline input leaves its job')
    for path,sha in expected.items():
        if digest(intake/path)!=sha:raise ValueError('Stock baseline input was modified')
    lines=log.read_text(errors='replace').splitlines()
    keys={native_assert_key(line) for line in lines if native_assert_key(line)}
    if keys!={'stock-player-name-collision-2873949622','stock-player-transform-parent-assert'}:
        raise ValueError('Stock baseline diagnostics differ from calibrated inputs')
    remaining=[]
    for line in lines:
        if native_assert_key(line) in keys:continue
        if '[Error][Assert]' in line and 'soundFileLoader.cpp:101] ( soundBank != nullptr )' not in line:
            raise ValueError('Stock baseline has another native assertion')
        remaining.append(line)
    if native_failure('\n'.join(remaining),native['exitCode']):raise ValueError('Stock baseline has another native failure')
    return sorted(keys)


def preserve_compiled_templates(cfg,workspace,cooked,probe):
    """Historical SDK source-cache packaging is deliberately unavailable."""
    raise ValueError('SDK source entity cache preservation is blocked after observed loading CTD; use shipped cooked templates')


def stage_shipped_templates(cfg,workspace,cooked,probe):
    """Preserve shipped cooked caches, never uncooked SDK entity caches."""
    workspace=Path(workspace).resolve();cooked=Path(cooked).resolve()
    if not workspace.is_relative_to(ROOT/'build') or not cooked.is_relative_to(ROOT/'build'):
        raise ValueError('Shipped template staging leaves owned build')
    receipt_path=ROOT/probe['shippedPlayerReceipt']
    if digest(receipt_path)!=probe['shippedPlayerReceiptSHA256']:raise ValueError('Shipped source receipt changed')
    receipt=json.loads(receipt_path.read_text())
    if digest(cfg['game']/'content/content0/bundles/startup.bundle')!=receipt['sourceBundleSHA256']:
        raise ValueError('Shipped source bundle changed')
    sources={r['path']:r for r in receipt['resources']}
    records=probe['effectiveTemplateResources']
    if set(sources)!={EFFECTIVE_PLAYER,GERALT_PLAYER} or {r['path'] for r in records}!=set(sources):
        raise ValueError('Expected exact gameplay/UI shipped template pair')
    output=[]
    for record in records:
        src=sources[record['path']];original=ROOT/src['source']
        if digest(original)!=src['sourceSHA256']:raise ValueError('Shipped cooked source changed')
        exact,patch=redirect(original.read_bytes(),expected_headers=src['embeddedHeaderCount'],require_cooked=True)
        source=workspace/record['path'];dest=cooked/record['path']
        if source.read_bytes()!=exact or digest(source)!=record['patchedSHA256']:
            raise ValueError('Shipped template staging exceeds import/CRC patch')
        rejected=cooked.parent/'recompiled-shipped-entities'/record['path']
        rejected.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dest,rejected)
        before=digest(dest);shutil.copy2(source,dest)
        output.append(dict(path=record['path'],sourceSHA256=src['sourceSHA256'],outputSHA256=digest(dest),
            recompiledSHA256=before,shippedCookedCachePreserved=True,patch=patch))
    return dict(command='stage-shipped-cooked-player-entities',files=output,observedGameplay=False)


def merge_rig(original, extension, full_joint_lod=False):
    result=copy.deepcopy(original)
    stock=result['_chunks']['CSkeleton #0']['_vars']
    extended=extension['_chunks']['CSkeleton #0']['_vars']
    for field in ('bones','parentIndices','rigdata'):
        if len(stock[field]['_elements'])!=94 or len(extended[field]['_elements'])!=104:
            raise ValueError('Unexpected observed rig count')
        if stock[field]['_elements']!=extended[field]['_elements'][:94]:
            raise ValueError('Stock '+field+' changed in extension')
        stock[field]=copy.deepcopy(extended[field])
    if full_joint_lod:
        if stock.get('lodBoneNum_1') != scalar('Int32',40):
            raise ValueError('Observed stock reduced-detail bone limit changed')
        # CalcTransforms limits model-space updates to GetLodBoneNum(). The
        # stock prefix of 40 excludes every appended joint (indices 94..103).
        # Keep all required joints in this private player's update range.
        stock['lodBoneNum_1']=scalar('Int32',len(stock['bones']['_elements']))
    return result


def player_entity(source):
    result=copy.deepcopy(source)
    def edit(resource):
        chunks=resource['_chunks']
        controller=next(k for k,c in chunks.items() if c['_type']=='MaleModMotionComponent')
        removed={k for k,c in chunks.items() if c['_type'] in ('CAnimDangleComponent','CMeshSkinningAttachment')}
        for k in removed:del chunks[k]
        for c in chunks.values():
            v=c['_vars']
            if c['_type']=='CItemEntity':
                v['Components']['_elements']=[e for e in v['Components']['_elements']
                    if e['_vars']['_reference']['_value'] not in removed]
            if c['_type']=='CMeshComponent':
                v.pop('transformParent',None)
                v['AttachmentsReference']['_elements']=[]
            if c['_type']=='CAnimDangleConstraint_Dyng':c['_parentKey']=controller
            if c['_type']=='MaleModMotionComponent':
                v['deformationGraph']={'_type':'handle:CBehaviorGraph','_vars':{
                    '_chunkHandle':scalar('bool',False),
                    '_className':scalar('string','CBehaviorGraph'),
                    '_depotPath':scalar('string',GRAPH.replace('/','\\')),
                    '_flags':scalar('uint16',0)}}
            for value in v.values():
                if value.get('_type')=='CR2W':edit(value)
        ordered={}
        def add(key):
            if key in ordered:return
            parent=chunks[key].get('_parentKey')
            if parent:add(parent)
            ordered[key]=chunks[key]
        for k in chunks:add(k)
        resource['_chunks']=ordered
    edit(result)
    return result


def player_script(source, names, pose_rest=None):
    result=probe_script(source,direct=True,late=True)
    result=result.replace('    editable var dynamicConstraint',
        '    editable var deformationGraph : CBehaviorGraph;\n    private var ownsPoseLayer : bool;\n    private var bridgeBootReason : string;\n    private var bridgeBootAttempts : int;\n    editable var dynamicConstraint',1)
    start=result.index('        deformationRoot = (CAnimatedComponent)GetEntity().GetComponent(')
    end=result.index('        bridgeScale = 1.0;',start)
    result=result[:start]+'        deformationRoot = thePlayer.GetRootAnimatedComponent();\n'+result[end:]
    start=result.index('    public latent function BootDeformationGraph()')
    end=result.index('    public function BridgeBooted()',start)
    checks='\n'.join("            if (deformationRoot.skeleton.bones[%d].nameAsCName != '%s') { bridgeBootReason = \"rig name mismatch at %d\"; return; }" % (i,n,i)
        for i,n in enumerate(names))
    result=result[:start]+'''    public latent function BootDeformationGraph()
    {
        var slot : SBehaviorGraphInstanceSlot;
        var i : int;
        var attempt : int;
        bridgeBootReason = "waiting for player root";
        for (attempt = 0; attempt < 10; attempt += 1)
        {
            Sleep(0.5);
            if (!listening || !thePlayer) { bridgeBootReason = "controller stopped"; return; }
            bridgeBootAttempts = attempt + 1;
            deformationRoot = thePlayer.GetRootAnimatedComponent();
            if (!deformationRoot) { bridgeBootReason = "player root unavailable"; continue; }
            if (!deformationGraph) { bridgeBootReason = "controller graph handle missing"; return; }
            if (!deformationRoot.skeleton) { bridgeBootReason = "player skeleton unavailable"; continue; }
            if (deformationRoot.skeleton.bones.Size() != 104)
            { bridgeBootReason = "player root has " + deformationRoot.skeleton.bones.Size() + " bones; expected 104"; continue; }
'''+checks+'''
            for (i = 0; i < deformationRoot.runtimeBehaviorInstanceSlots.Size(); i += 1)
            {
                if (deformationRoot.runtimeBehaviorInstanceSlots[i].instanceName == 'MaleModAnatomyLayer')
                { bridgeBootReason = "pose slot already present"; return; }
            }
            slot.instanceName = 'MaleModAnatomyLayer';
            slot.graph = deformationGraph;
            slot.alwaysOnTopOfStack = true;
            deformationRoot.runtimeBehaviorInstanceSlots.PushBack(slot);
            ownsPoseLayer = true;
            bridgeBooted = deformationRoot.AttachBehavior('MaleModAnatomyLayer');
            if (bridgeBooted)
            {
                bridgeBootReason = "attached";
                ApplyTuning();
                return;
            }
            bridgeBootReason = "AttachBehavior rejected slot";
            RemovePoseLayer();
        }
    }

    public function BridgeBootDetail() : string
    { return "Boot: " + bridgeBootReason + " | attempts: " + bridgeBootAttempts; }

    private function RemovePoseLayer()
    {
        var i : int;
        if (!ownsPoseLayer || !deformationRoot) { return; }
        deformationRoot.DetachBehavior('MaleModAnatomyLayer');
        for (i = deformationRoot.runtimeBehaviorInstanceSlots.Size() - 1; i >= 0; i -= 1)
        {
            if (deformationRoot.runtimeBehaviorInstanceSlots[i].instanceName == 'MaleModAnatomyLayer')
            { deformationRoot.runtimeBehaviorInstanceSlots.Erase(i); }
        }
        ownsPoseLayer = false;
        bridgeBooted = false;
    }

'''+result[end:]
    result=result.replace('    private function StopPanel()\n    {','    private function StopPanel()\n    {\n        RemovePoseLayer();',1)
    result=result.replace('MaleMod - isolated pose test','MaleMod - player pose test')
    result=result.replace('late graph: ','player layer: ')
    result=result.replace('    group = m_flashValueStorage.CreateTempFlashObject();',
        '''    controls.PushBackFlashObject(MaleModDiagnosticRow(m_flashValueStorage,'MaleModBootReason',controller.BridgeBootDetail()));
    group = m_flashValueStorage.CreateTempFlashObject();''',1)
    # No replacement of the player's stock graphs, freeze state or sampling.
    for forbidden in ('ActivateBehaviors(', 'UpdateByOtherAnimatedComponent(', 'UnfreezePose('):
        if forbidden in result:raise ValueError('Player script mutates stock animation scheduling: '+forbidden)
    if pose_rest is not None:
        from pose_diagnostics import add_pose_measurement
        result=add_pose_measurement(result,pose_rest)
    return result


def native_rig_frames(path, dump, expected):
    """Read observed native skeleton tail only, not a general v164 converter.

    Official dump supplies bone/parent arrays and export bounds. CSkeleton's
    buffered rig records are 12 float32 values (position/quaternion/scale).
    Verify the entire native export CRC and each record against authored data.
    """
    root=ET.parse(dump).getroot()
    skels=[o for o in root.findall('.//object') if o.get('class')=='CSkeleton' and o.get('id') is not None]
    if len(skels)!=1:raise ValueError('Expected one native player skeleton')
    skel=skels[0]
    names=[e.findtext('./object/properties/prop[@name="name"]') for e in skel.findall('./properties/prop[@name="bones"]/array/element')]
    parents=[int(e.text) for e in skel.findall('./properties/prop[@name="parentIndices"]/array/element')]
    enames,eparents,_=rig_world(expected)
    if names!=enames or parents!=eparents or len(names)!=104:raise ValueError('Native player rig joint mapping changed')
    export=root.find('.//exports/export[@index="0"]')
    if export is None:raise ValueError('Missing native skeleton export bounds')
    size=int(export.get('dataSize'));offset=int(export.get('dataOffset').split()[0]);data=Path(path).read_bytes()
    chunk=data[offset:offset+size]
    if len(chunk)!=size or zlib.crc32(chunk)!=int(export.get('crc'),16):raise ValueError('Native skeleton export CRC mismatch')
    length=104*48
    if size<=length:raise ValueError('Missing native skeleton reference buffer')
    actual=np.frombuffer(chunk[-length:],dtype='<f4').reshape(104,12)
    records=np.asarray([[r['_vars'][field]['_vars'][axis]['_value']
        for field in ('Position','Rotation','Scale') for axis in 'XYZW']
        for r in expected['rigdata']['_elements']],dtype=np.float64)
    error=float(np.max(np.abs(actual-records)))
    if not np.isfinite(error) or error>1e-6:raise ValueError('Native player rig reference records changed')
    if skel.findtext('./properties/prop[@name="lodBoneNum_1"]')!=str(expected['lodBoneNum_1']['_value']):
        raise ValueError('Native rig LOD policy differs from the verified recipe')
    for prop in ('controlRigDefinition','controlRigDefaultPropertySet','controlRigSettings','teleportDetectorData'):
        if skel.find('./properties/prop[@name="'+prop+'"]/reference') is None:raise ValueError('Lost stock rig metadata '+prop)
    return error


def verify_template_root(native_dump, source_dump):
    """Check the flattened moving-agent root, not merely its base include."""
    root=ET.parse(native_dump).getroot()
    original=ET.parse(source_dump).getroot()
    def moving(tree):
        nodes=[o for o in tree.findall('.//object') if o.get('id') is not None
            and o.get('class')=='CMovingPhysicalAgentComponent'
            and o.findtext('./properties/prop[@name="name"]')=='man_base']
        if len(nodes)!=1:raise ValueError('Expected one flattened Geralt moving-agent root')
        return nodes[0]
    node,old=moving(root),moving(original)
    resource=node.find('./properties/prop[@name="skeleton"]/resource')
    if resource is None or resource.get('path')!=NEW_RIG:
        raise ValueError('Effective player root still imports the stock rig')
    def resources(obj,name):return [(r.get('class'),r.get('path'))
        for r in obj.findall('./properties/prop[@name="'+name+'"]//resource')]
    for name in ('animationSets','behaviorInstanceSlots','runtimeBehaviorInstanceSlots','ragdoll','steeringBehavior'):
        if old.find('./properties/prop[@name="'+name+'"]') is None or resources(old,name)!=resources(node,name):
            raise ValueError('Effective player lost stock '+name)
    # Slot names, flags and graph order must survive, not just the graph paths.
    def slots(obj,name):return [(p.get('name'),p.get('type'),p.text)
        for p in obj.findall('./properties/prop[@name="'+name+'"]//object/properties/prop')
        if len(p)==0]
    for name in ('behaviorInstanceSlots','runtimeBehaviorInstanceSlots'):
        if slots(node,name)!=slots(old,name):raise ValueError('Effective player changed stock slot scheduling')
    return dict(privateRigImportVerified=True,stockRootBindingsPreserved=True,
        stockSlotSchedulingPreserved=True,rootClass=node.get('class'))


def verify_native_player(cooked, probe):
    cooked=Path(cooked)
    if probe.get('executionPhase')!='player-stack':raise ValueError('Input node must follow existing player graphs')
    root=ET.parse(Path(str(cooked/PLAYER)+'.xml')).getroot()
    animated=[o for o in root.findall('.//object') if o.get('id') is not None
        and o.findtext('./properties/prop[@name="name"]')=='man_base']
    if len(animated)!=1:raise ValueError('Expected observed man_base player root')
    resource=animated[0].find('./properties/prop[@name="skeleton"]/resource')
    if resource is None or resource.get('path')!=NEW_RIG:raise ValueError('Player root did not retain private rig')
    # Preserve stock graph/animation/ragdoll bindings in native loaded entity.
    source_dump=ROOT/probe['sourcePlayerNativeDump']
    if digest(source_dump)!=probe['sourcePlayerNativeDumpSHA256']:raise ValueError('Stock player native evidence changed')
    original=ET.parse(source_dump).getroot()
    old=next(o for o in original.findall('.//object') if o.get('id') is not None
        and o.findtext('./properties/prop[@name="name"]')=='man_base')
    def paths(node,prop):return [r.get('path') for r in node.findall('./properties/prop[@name="'+prop+'"]//resource')]
    if animated[0].get('class')!=old.get('class'):raise ValueError('Native player root class changed')
    for prop in ('animationSets','behaviorInstanceSlots','runtimeBehaviorInstanceSlots','ragdoll','steeringBehavior'):
        if old.find('./properties/prop[@name="'+prop+'"]') is None or paths(old,prop)!=paths(animated[0],prop):
            raise ValueError('Native player lost stock '+prop)
    recipe=ROOT/probe['playerRigRecipe']
    if digest(recipe)!=probe['playerRigRecipeSHA256']:raise ValueError('Private rig recipe changed')
    authored=json.loads(recipe.read_text())
    expected=authored['_chunks']['CSkeleton #0']['_vars']
    if probe.get('fullJointLod') and expected['lodBoneNum_1']['_value']!=len(expected['bones']['_elements']):
        raise ValueError('Private player LOD excludes required authored joints')
    error=native_rig_frames(cooked/RIG,Path(str(cooked/RIG)+'.xml'),expected)
    result=dict(nativePlayerRigVerified=True,playerRigPath=NEW_RIG,stockJointCount=94,
        authoredJointCount=10,stockRootBindingsPreserved=True,maximumRestFrameError=error,
        rigSHA256=digest(cooked/RIG),playerEntitySHA256=digest(cooked/PLAYER),
        parentEntitySHA256=digest(cooked/PARENT),observedGameplay=False)
    if probe.get('fullJointLod'):result.update(fullJointLodVerified=True,reducedDetailBoneCount=104)
    if probe.get('effectiveTemplates'):
        records=probe.get('effectiveTemplateResources',[])
        if {r['path'] for r in records}!={EFFECTIVE_PLAYER,GERALT_PLAYER}:
            raise ValueError('Missing effective gameplay/UI Geralt templates')
        verified=[]
        for record in records:
            source=ROOT/record['sourceNativeDump']
            if digest(source)!=record['sourceNativeDumpSHA256']:raise ValueError('Effective template source evidence changed')
            path=cooked/record['path']
            checked=verify_template_root(Path(str(path)+'.xml'),source)
            verified.append(dict(path=record['path'],sha256=digest(path),**checked))
        result.update(nativeEffectivePlayerTemplatesVerified=True,effectiveTemplates=verified)
    return result


def main(probe_dir, player_inspection=None, rest_joints=False, measure_pose=False, full_joint_lod=False,
         effective_templates=False, shipped_player=None, size_controls=False):
    if measure_pose and not rest_joints:raise ValueError('Pose measurement requires the current authored-rest candidate')
    if effective_templates and not (rest_joints and full_joint_lod):
        raise ValueError('Effective template repair requires authored rest and full joint LOD')
    cfg=settings();pin=base_checkout(cfg);probe_dir=Path(probe_dir).resolve()
    if effective_templates and shipped_player is None:
        raise ValueError('Effective player templates require an extracted shipped cooked source receipt')
    shipped_receipt=Path(shipped_player).resolve() if shipped_player else None
    if shipped_receipt and not shipped_receipt.is_relative_to(ROOT/'build/probe'):
        raise ValueError('Expected owned shipped player receipt')
    shipped_sources={r['path']:r for r in json.loads(shipped_receipt.read_text())['resources']} if shipped_receipt else {}
    if not probe_dir.is_relative_to(ROOT/'build/motion'):raise ValueError('Expected owned probe')
    probe=json.loads((probe_dir/'deformation-probe.json').read_text())
    if probe.get('parentPoseSpace')!='attached' or not probe.get('nativeCook'):raise ValueError('Expected verified input-node probe')
    source_player=cfg['redkit']/'r4data'/PLAYER
    source_rig=cfg['redkit']/'r4data/characters/base_entities/man_base/man_base.w2rig'
    if digest(source_player)!=PLAYER_SHA or digest(source_rig)!=RIG_SHA:raise ValueError('Observed stock sources changed')
    source_inspection=Path(player_inspection).resolve() if player_inspection else ROOT/'build/inspection/native-e797f49ca266/inspection.json'
    if not source_inspection.is_relative_to(ROOT/'build/inspection'):raise ValueError('Expected owned native inspection record')
    inspection=json.loads(source_inspection.read_text())
    source_dump=Path(inspection['output'])
    if inspection['sourceSHA256']!=PLAYER_SHA or digest(source_dump)!=inspection['outputSHA256']:
        raise ValueError('Reinspect the observed player entity with the native dumper')
    job=ROOT/'build/motion'/('player-stack-'+uuid.uuid4().hex[:12]);job.mkdir(parents=True)
    workspace=job/'intake';workspace.mkdir()
    converter=ROOT/'build/research/wkit-current/MaleModCR2W.exe'
    original_rig=job/'stock-rig.json'
    subprocess.run([str(converter),'export',str(source_rig),str(original_rig)],check=True,capture_output=True)
    rig=merge_rig(json.loads(original_rig.read_text()),json.loads((probe_dir/'deformation-rig.json').read_text()),full_joint_lod)
    write_json(job/'player-rig.json',rig)
    body=player_entity(json.loads((probe_dir/'scripted-motion-entity.json').read_text()))
    write_json(job/'player-body.json',body)
    for recipe,path in [('player-rig.json',RIG),('player-body.json',BODY)]:
        dest=workspace/path;dest.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run([str(converter),'import',str(job/recipe),str(dest)],check=True,capture_output=True)
    data,patch=redirect(source_player.read_bytes())
    data,parent_patch=redirect(data,OLD_PARENT.replace('/','\\'),PARENT.replace('/','\\'),1)
    dest=workspace/PLAYER;dest.parent.mkdir(parents=True);dest.write_bytes(data)
    write_json(job/'player-import-patch.json',dict(sourceSHA256=PLAYER_SHA,outputSHA256=digest(dest),rigPatch=patch,parentPatch=parent_patch))
    parent_source=cfg['redkit']/'r4data'/OLD_PARENT
    if digest(parent_source)!=PARENT_SHA:raise ValueError('Observed parent template changed')
    parent_data,parent_rig_patch=redirect(parent_source.read_bytes())
    parent_dest=workspace/PARENT;parent_dest.write_bytes(parent_data)
    write_json(job/'parent-import-patch.json',dict(sourceSHA256=digest(parent_source),outputSHA256=digest(parent_dest),**parent_rig_patch))
    effective=[]
    if effective_templates:
        for path,source_hash,version,inspection_path in EFFECTIVE_TEMPLATES:
            shipped=shipped_sources[path]
            source=ROOT/shipped['source'];source_hash=shipped['sourceSHA256'];version=164
            if digest(source)!=source_hash:raise ValueError('Observed effective player template changed')
            dump=ROOT/shipped['sourceNativeDump']
            if digest(dump)!=shipped['sourceNativeDumpSHA256']:
                raise ValueError('Reinspect effective player source')
            patched,record=redirect(source.read_bytes(),expected_version=version,
                expected_headers=shipped['embeddedHeaderCount'],require_cooked=True)
            dest=workspace/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(patched)
            effective.append(dict(path=path,sourceSHA256=source_hash,patchedSHA256=digest(dest),
                sourceNativeDump=dump.relative_to(ROOT).as_posix(),sourceNativeDumpSHA256=digest(dump),patch=record))
    for record in probe['resources']:
        if record['path'] not in (GRAPH,'characters/malemod/body/geralt_motion.w2mesh','characters/malemod/physics/geralt_motion.w3dyng'):continue
        source=probe_dir/'intake'/record['path']
        if digest(source)!=record['sourceSHA256']:raise ValueError('Verified cage/graph changed')
        dest=workspace/record['path'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
    if rest_joints:
        from deformation_graph import deformation_graph
        graph=deformation_graph(json.loads((probe_dir/'stock-graph.json').read_text()),probe['stockNames'],probe['controlledNames'],
            identity_root=probe['identityRoot'],parent_space='attached',rest_joints=True)
        write_json(job/'deformation-graph.json',graph)
        # Replace only this freshly copied, owned input; preserve immutable probe.
        (workspace/GRAPH).unlink()
        subprocess.run([str(converter),'import',str(job/'deformation-graph.json'),str(workspace/GRAPH)],check=True,capture_output=True)
    names,_parents,_worlds=rig_world(rig['_chunks']['CSkeleton #0']['_vars'])
    script=workspace/'scripts/local/maleModPhysics.ws';script.parent.mkdir(parents=True)
    pose_rest=None
    if measure_pose:
        root_frame=rig['_chunks']['CSkeleton #0']['_vars']['rigdata']['_elements'][94]['_vars']['Position']['_vars']
        pose_rest=[root_frame[c]['_value'] for c in 'XYZ']
    runtime=player_script((ROOT/'probes/runtime/maleModPhysics.ws').read_text(),names,pose_rest)
    size_contract=None
    if size_controls:
        if not effective_templates:raise ValueError('Size controls require the observed shipped player path')
        from size_controls import add_size_controls
        runtime,size_contract=add_size_controls(runtime,cfg['base'],probe['controlledNames'])
    script.write_text(runtime,encoding='utf-8')
    evidence=dict(probe,baseCommit=pin['commit'],executionPhase='player-stack',authoredRestMask=rest_joints,
        fullJointLod=full_joint_lod,poseMeasurement=measure_pose,
        effectiveTemplates=effective_templates,effectiveTemplateResources=effective,
        playerRigRecipe=(job/'player-rig.json').relative_to(ROOT).as_posix(),
        playerRigRecipeSHA256=digest(job/'player-rig.json'),
        sourcePlayerNativeDump=source_dump.relative_to(ROOT).as_posix(),
        sourcePlayerNativeDumpSHA256=digest(source_dump),
        sourcePlayerSHA256=PLAYER_SHA,sourceRigSHA256=RIG_SHA,
        playerImportPatch=patch,playerParentImportPatch=parent_patch,parentRigPatch=parent_rig_patch,
        sourceParentSHA256=digest(parent_source),installed=False,observedGameplay=False)
    if shipped_receipt:
        evidence.update(shippedPlayerReceipt=shipped_receipt.relative_to(ROOT).as_posix(),
            shippedPlayerReceiptSHA256=digest(shipped_receipt))
    evidence['sourceInputProbe']=probe_dir.relative_to(ROOT).as_posix()
    evidence['sourceInputProbeSHA256']=digest(probe_dir/'deformation-probe.json')
    evidence['inputProbeNativeCook']=evidence.pop('nativeCook')
    evidence['inputProbeResources']=evidence.pop('resources')
    evidence['resources']=[dict(path=p.relative_to(workspace).as_posix(),sourceSHA256=digest(p))
        for p in workspace.rglob('*') if p.is_file() and p.suffix!='.ws']
    write_json(job/'deformation-probe.json',evidence)
    project=dict(name='modMaleMod',version='0.4.21-size-controls-test' if size_controls else '0.4.20-shipped-player-load-test' if effective_templates else '0.4.18-boot-recovery-test' if full_joint_lod else '0.4.16-pose-measurement' if measure_pose else '0.4.15-authored-rest-test' if rest_joints else '0.4.14-player-stack-test',platform='pc',cacheBuilders=['textures','physics'],
        scriptedCook=True,motionEntity=BODY,motionOutput='player',additionalNativeDumps=[RIG,PLAYER,PARENT]+[r['path'] for r in effective],
        isolatedNativeDumps=[r['path'] for r in effective],
        isolatedNativeResources=[r['path'] for r in effective],
        stageShippedPlayerTemplates=effective_templates,
        nativeSourceBaseline=STOCK_BASELINE if effective_templates else None,
        deformationBridge=dict(sourceProbe=job.relative_to(ROOT).as_posix(),sourceProbeSHA256=digest(job/'deformation-probe.json'),
            lateActivation=False,identityRoot=probe['identityRoot'],fullTransformChannels=False,parentPoseSpace='attached',
            executionPhase='player-stack',authoredRestMask=rest_joints,fullJointLod=full_joint_lod,
            effectiveTemplates=effective_templates,
            poseMeasurement=measure_pose,cageBaseCommit=probe['cageBaseCommit']),
        sizeControls=size_contract,
        scope='Five live size cage controls; authored surface parity, remaining controls, dynamic pelvis and secondary motion incomplete.' if size_controls else 'Player stack pose/scale probe. Full source controls, dynamic pelvis and secondary motion remain incomplete.')
    package=build(cfg,project,workspace);verify_package(package)
    write_json(job/'candidate-provenance.json',dict(package=package.relative_to(ROOT).as_posix(),installed=False,observedGameplay=False))
    print(package)
    return package


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('probe',type=Path)
    parser.add_argument('--player-inspection',type=Path)
    parser.add_argument('--rest-joints',action='store_true')
    parser.add_argument('--measure-pose',action='store_true')
    parser.add_argument('--full-joint-lod',action='store_true')
    parser.add_argument('--effective-templates',action='store_true')
    parser.add_argument('--shipped-player',type=Path)
    parser.add_argument('--size-controls',action='store_true')
    args=parser.parse_args();main(args.probe,args.player_inspection,args.rest_joints,args.measure_pose,args.full_joint_lod,args.effective_templates,args.shipped_player,args.size_controls)
