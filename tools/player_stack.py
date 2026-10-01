"""Owned player-stack pose test; preserve stock animation and appearance binding.

No stock depot writes. The v164 player entity is patched only at two observed
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
from mod import ROOT, settings, base_checkout, digest, write_json, build, verify_package
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
        '    editable var deformationGraph : CBehaviorGraph;\n    private var ownsPoseLayer : bool;\n    editable var dynamicConstraint',1)
    start=result.index('        deformationRoot = (CAnimatedComponent)GetEntity().GetComponent(')
    end=result.index('        bridgeScale = 1.0;',start)
    result=result[:start]+'        deformationRoot = thePlayer.GetRootAnimatedComponent();\n'+result[end:]
    start=result.index('    public latent function BootDeformationGraph()')
    end=result.index('    public function BridgeBooted()',start)
    checks='\n'.join("        if (deformationRoot.skeleton.bones[%d].nameAsCName != '%s') { return; }" % (i,n)
        for i,n in enumerate(names))
    result=result[:start]+'''    public latent function BootDeformationGraph()
    {
        var slot : SBehaviorGraphInstanceSlot;
        var i : int;
        Sleep(0.25);
        if (!listening || !deformationRoot || !deformationGraph || !deformationRoot.skeleton) { return; }
        if (deformationRoot.skeleton.bones.Size() != 104) { return; }
'''+checks+'''
        for (i = 0; i < deformationRoot.runtimeBehaviorInstanceSlots.Size(); i += 1)
        {
            if (deformationRoot.runtimeBehaviorInstanceSlots[i].instanceName == 'MaleModAnatomyLayer') { return; }
        }
        slot.instanceName = 'MaleModAnatomyLayer';
        slot.graph = deformationGraph;
        slot.alwaysOnTopOfStack = true;
        deformationRoot.runtimeBehaviorInstanceSlots.PushBack(slot);
        ownsPoseLayer = true;
        bridgeBooted = deformationRoot.AttachBehavior('MaleModAnatomyLayer');
        ApplyTuning();
    }

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
    return result


def main(probe_dir, player_inspection=None, rest_joints=False, measure_pose=False, full_joint_lod=False):
    if measure_pose and not rest_joints:raise ValueError('Pose measurement requires the current authored-rest candidate')
    cfg=settings();pin=base_checkout(cfg);probe_dir=Path(probe_dir).resolve()
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
    script.write_text(player_script((ROOT/'probes/runtime/maleModPhysics.ws').read_text(),names,pose_rest),encoding='utf-8')
    evidence=dict(probe,baseCommit=pin['commit'],executionPhase='player-stack',authoredRestMask=rest_joints,
        fullJointLod=full_joint_lod,poseMeasurement=measure_pose,
        playerRigRecipe=(job/'player-rig.json').relative_to(ROOT).as_posix(),
        playerRigRecipeSHA256=digest(job/'player-rig.json'),
        sourcePlayerNativeDump=source_dump.relative_to(ROOT).as_posix(),
        sourcePlayerNativeDumpSHA256=digest(source_dump),
        sourcePlayerSHA256=PLAYER_SHA,sourceRigSHA256=RIG_SHA,
        playerImportPatch=patch,playerParentImportPatch=parent_patch,parentRigPatch=parent_rig_patch,
        sourceParentSHA256=digest(parent_source),installed=False,observedGameplay=False)
    evidence['sourceInputProbe']=probe_dir.relative_to(ROOT).as_posix()
    evidence['sourceInputProbeSHA256']=digest(probe_dir/'deformation-probe.json')
    evidence['inputProbeNativeCook']=evidence.pop('nativeCook')
    evidence['inputProbeResources']=evidence.pop('resources')
    evidence['resources']=[dict(path=p.relative_to(workspace).as_posix(),sourceSHA256=digest(p))
        for p in workspace.rglob('*') if p.is_file() and p.suffix!='.ws']
    write_json(job/'deformation-probe.json',evidence)
    project=dict(name='modMaleMod',version='0.4.17-full-joint-lod' if full_joint_lod else '0.4.16-pose-measurement' if measure_pose else '0.4.15-authored-rest-test' if rest_joints else '0.4.14-player-stack-test',platform='pc',cacheBuilders=['textures','physics'],
        scriptedCook=True,motionEntity=BODY,motionOutput='player',additionalNativeDumps=[RIG,PLAYER,PARENT],
        deformationBridge=dict(sourceProbe=job.relative_to(ROOT).as_posix(),sourceProbeSHA256=digest(job/'deformation-probe.json'),
            lateActivation=False,identityRoot=probe['identityRoot'],fullTransformChannels=False,parentPoseSpace='attached',
            executionPhase='player-stack',authoredRestMask=rest_joints,fullJointLod=full_joint_lod,
            poseMeasurement=measure_pose,cageBaseCommit=probe['cageBaseCommit']),
        scope='Player stack pose/scale probe. Full source controls, dynamic pelvis and secondary motion remain incomplete.')
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
    args=parser.parse_args();main(args.probe,args.player_inspection,args.rest_joints,args.measure_pose,args.full_joint_lod)
