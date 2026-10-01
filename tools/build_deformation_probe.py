"""Build a reversible native output test before publishing source sliders.

The existing controller and menu stay authoritative. This adds one clearly
labelled bridge test; accepting a graph variable is not proof of visible motion.
"""
import argparse
import json
import shutil
import uuid
from pathlib import Path
from mod import ROOT, settings, build, write_json, digest, verify_package
from deformation_graph import add_deformation_component
import subprocess
import copy
from prepare_motion import scalar


def probe_script(source, direct=False, late=False):
    def replace_once(old, new):
        nonlocal source
        if source.count(old) != 1:
            raise ValueError('Controller insertion marker changed: ' + old)
        source = source.replace(old, new)

    replace_once('    private var panelOpen : bool;', '''    private var deformationRoot : CAnimatedComponent;
    private var bridgeScale : float;
    private var bridgeAccepted : bool;
    private var panelOpen : bool;''')
    replace_once('        LoadTuning();', '''        deformationRoot = (CAnimatedComponent)GetEntity().GetComponent("MaleModDeformation");
        if (!deformationRoot) { deformationRoot = (CAnimatedComponent)thePlayer.GetComponent("MaleModDeformation"); }
        bridgeScale = 1.0;
        LoadTuning();''')
    if direct or late:
        replace_once('        bridgeScale = 1.0;', '''        if (deformationRoot) { deformationRoot.UpdateByOtherAnimatedComponent(thePlayer.GetRootAnimatedComponent()); }
        bridgeScale = 1.0;''')
    replace_once("        if (control == 'MaleModGravity') { return gravityValue; }", '''        if (control == 'MaleModBridgeScale') { return bridgeScale; }
        if (control == 'MaleModGravity') { return gravityValue; }''')
    replace_once("        if (control == 'MaleModGravity') { gravityValue = ClampF(value,0.0,2.0); }", '''        if (control == 'MaleModBridgeScale') { bridgeScale = ClampF(value,0.8,1.2); }
        else if (control == 'MaleModGravity') { gravityValue = ClampF(value,0.0,2.0); }''')
    replace_once('    private function ApplyTuning()\n    {', '''    private function ApplyTuning()
    {
        var scale : Vector;
        if (deformationRoot)
        {
            scale = Vector(bridgeScale, bridgeScale, bridgeScale);
            bridgeAccepted = deformationRoot.SetBehaviorVectorVariable('mm_shaft_00_scale', scale);
        }''')
    replace_once('            + " | gravity "', '            + " | graph: " + (bool)deformationRoot + " | variable accepted: " + bridgeAccepted + " | bridge scale: " + bridgeScale\n            + " | gravity "')
    replace_once('    group = m_flashValueStorage.CreateTempFlashObject();', '''    controls.PushBackFlashObject(MaleModSlider(m_flashValueStorage, 'MaleModBridgeScale',
        "Scale bridge (test)", controller.GetTuning('MaleModBridgeScale'),0.8,1.2,40));
    group = m_flashValueStorage.CreateTempFlashObject();''')
    if direct:
        start=source.index('    controls.PushBackFlashObject(MaleModSlider(m_flashValueStorage, \'MaleModGravity\',')
        end=source.index('    controls.PushBackFlashObject(MaleModSlider(m_flashValueStorage, \'MaleModBridgeScale\',',start)
        source=source[:start]+source[end:]
        replace_once('    public function Status() : string',
                     '    public function BridgeAccepted() : bool { return bridgeAccepted; }\n\n    public function Status() : string')
        source=source.replace('"Scale bridge (test)"','"Direct scale test | accepted: " + controller.BridgeAccepted()')
        source=source.replace('MaleMod - motion controls','MaleMod - isolated pose test')
    if late:
        if not direct:
            replace_once('    public function Status() : string',
                '    public function BridgeAccepted() : bool { return bridgeAccepted; }\n\n    public function Status() : string')
        replace_once('    private var bridgeAccepted : bool;', '''    private var bridgeAccepted : bool;
    private var bridgeBooted : bool;
    private var bridgeChanges : int;''')
        replace_once('        listening = true;', '''        listening = true;
        GotoState('MaleModGraphStartup');''')
        replace_once("if (control == 'MaleModBridgeScale') { bridgeScale = ClampF(value,0.8,1.2); }",
                     "if (control == 'MaleModBridgeScale') { bridgeScale = ClampF(value,0.8,1.2); bridgeChanges += 1; }")
        replace_once('    public function BridgeAccepted() : bool { return bridgeAccepted; }', '''    public function BridgeAccepted() : bool { return bridgeAccepted; }

    public latent function BootDeformationGraph()
    {
        var graphs : array<name>;
        Sleep(0.25);
        if (!listening || !deformationRoot) { return; }
        graphs.PushBack('MaleModDeformationLate');
        bridgeBooted = deformationRoot.ActivateBehaviors(graphs);
        deformationRoot.UnfreezePose();
        ApplyTuning();
    }

    public function BridgeDetail() : string
    {
        var actual : Vector;
        if (deformationRoot) { actual = deformationRoot.GetBehaviorVectorVariable('mm_shaft_00_scale'); }
        return "late graph: " + bridgeBooted + " | changes: " + bridgeChanges
            + " | requested: " + bridgeScale + " | readback: " + actual.X;
    }''')
        replace_once('return "Native controller attached: "', 'return BridgeDetail() + " | Native controller attached: "')
        replace_once('    group = m_flashValueStorage.CreateTempFlashObject();', '''    controls.PushBackFlashObject(MaleModDiagnosticRow(m_flashValueStorage,'MaleModGraphActive',
        "Graph active: " + controller.BridgeBooted() + " | accepted: " + controller.BridgeAccepted()));
    controls.PushBackFlashObject(MaleModDiagnosticRow(m_flashValueStorage,'MaleModCallbackState',
        "Slider changes: " + controller.BridgeChanges() + " | requested: " + controller.GetTuning('MaleModBridgeScale')));
    controls.PushBackFlashObject(MaleModDiagnosticRow(m_flashValueStorage,'MaleModGraphReadback',
        "Graph readback: " + controller.BridgeReadback() + " | frozen: " + controller.BridgeFrozen()));
    group = m_flashValueStorage.CreateTempFlashObject();''')
        source+='''
function MaleModDiagnosticRow(storage : CScriptedFlashValueStorage, control : name, label : string) : CScriptedFlashObject
{
    var row : CScriptedFlashObject;
    row = MaleModSlider(storage,control,label,0.0,0.0,1.0,1);
    row.SetMemberFlashBool("disabled",true);
    return row;
}
state MaleModGraphStartup in MaleModMotionComponent
{
    event OnEnterState(previous : name) { StartGraph(); }
    entry function StartGraph() { parent.BootDeformationGraph(); }
}
exec function MaleModScale(value : float)
{
    var controller : MaleModMotionComponent;
    controller = MaleModFindController();
    if (controller) { controller.SetTuning('MaleModBridgeScale',value); }
    MaleModShowStatus();
}
'''
        source=source.replace('    public function BridgeDetail() : string', '''    public function BridgeBooted() : bool { return bridgeBooted; }
    public function BridgeChanges() : int { return bridgeChanges; }
    public function BridgeFrozen() : bool { return deformationRoot && deformationRoot.HasFrozenPose(); }
    public function BridgeReadback() : float
    {
        var actual : Vector;
        if (deformationRoot) { actual = deformationRoot.GetBehaviorVectorVariable('mm_shaft_00_scale'); }
        return actual.X;
    }
    public function BridgeDetail() : string''')
    return source


def main(job,direct=False,late=False):
    job = Path(job).resolve()
    if not job.is_relative_to(ROOT/'build/motion'):
        raise ValueError('Expected an owned deformation probe')
    evidence = json.loads((job/'deformation-probe.json').read_text(encoding='utf-8'))
    if evidence.get('parentPoseSpace')=='attached':
        raise ValueError('Ordinary helper stack resets its input pose; attached input candidate is held. Use the player-stack builder.')
    if not evidence.get('nativeCook'):
        raise ValueError('Candidate lacks native cook evidence')
    cfg = settings()
    workspace = ROOT/'build/jobs'/('deformation-release-'+uuid.uuid4().hex[:12])
    workspace.mkdir(parents=True)
    entity = 'items/bodyparts/geralt_items/legs/bare/l_01_mg__body_underwear.w2ent'
    custom = add_deformation_component(json.loads((job/'scripted-motion-entity.json').read_text(encoding='utf-8')),
        'characters\\malemod\\physics\\deformation.w2rig', 'characters\\malemod\\behavior\\deformation.w2beh',
        output='direct' if direct else 'dangle')
    if late:
        def late_slot(resource):
            for c in resource['_chunks'].values():
                if c['_type']=='CAnimatedComponent':
                    slots=c['_vars']['behaviorInstanceSlots']['_elements']
                    slots[0]['_vars']['alwaysOnTopOfStack']=scalar('Bool',False)
                    # Current native RTTI retains instanceName/graph/alwaysOnTop,
                    # but not the legacy converter's alwaysLoaded field. Native
                    # stack Init activates the first slot only; the delayed
                    # explicit ActivateBehaviors call creates the second instance.
                    slot=copy.deepcopy(slots[0]);slot['_vars'].update(
                        instanceName=scalar('CName','MaleModDeformationLate'))
                    slots.append(slot)
                for value in c['_vars'].values():
                    if value.get('_type')=='CR2W':late_slot(value)
        late_slot(custom)
    recipe = workspace/'entity.json'
    write_json(recipe, custom)
    output = workspace/entity
    output.parent.mkdir(parents=True)
    converter = ROOT/'build/research/wkit-current/MaleModCR2W.exe'
    subprocess.run([str(converter), 'import', str(recipe), str(output)], check=True, capture_output=True)
    for record in evidence['resources']:
        if record['path'] == entity:
            continue
        source = job/'intake'/record['path']
        if digest(source) != record['sourceSHA256']:
            raise ValueError('Verified candidate resource changed')
        target = workspace/record['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    script = workspace/'scripts/local/maleModPhysics.ws'
    script.parent.mkdir(parents=True)
    script.write_text(probe_script((ROOT/'probes/runtime/maleModPhysics.ws').read_text(encoding='utf-8'),direct,late),
                      encoding='utf-8')
    version=('0.4.13-attached-pose-test' if direct and evidence.get('parentPoseSpace')=='attached' else
             '0.4.12-model-pose-test' if direct and evidence.get('parentPoseSpace')=='model' else
             '0.4.11-connected-motion-test' if late and not direct and evidence.get('identityRoot') else
             '0.4.10-root-pose-test' if evidence.get('identityRoot') else
             '0.4.9-connected-graph-test' if late else
             '0.4.7-ordered-pose-test' if direct else '0.4.5-deformation-bridge-test')
    project = dict(name='modMaleMod', version=version, platform='pc',
        cacheBuilders=['textures', 'physics'], scriptedCook=True, motionEntity=entity,
        motionOutput='direct' if direct else 'dangle',
        deformationBridge=dict(sourceProbe=job.relative_to(ROOT).as_posix(),
            lateActivation=late,
            identityRoot=evidence.get('identityRoot'),
            fullTransformChannels=evidence.get('fullTransformChannels',False),
            parentPoseSpace=evidence.get('parentPoseSpace','local'),
            sourceProbeSHA256=digest(job/'deformation-probe.json'),
            cageBaseCommit=evidence['cageBaseCommit'], currentBaseAdoption='Control/output probe only; cage geometry unchanged'),
        scope=('Connected native graph-to-dangle test; three native engine controls plus scale probe. Full source sliders and dynamic pelvis incomplete.'
            if not direct else 'Isolated native pose/scale test; secondary motion is not the visible output in direct mode. Source sliders and dynamic pelvis are incomplete.'))
    package = build(cfg, project, workspace)
    verify_package(package)
    write_json(workspace/'candidate-provenance.json', dict(sourceProbe=str(job.relative_to(ROOT)),
        sourceProbeSHA256=digest(job/'deformation-probe.json'), cageBaseCommit=evidence['cageBaseCommit'],
        installed=False, observedGameplay=False, package=str(package.relative_to(ROOT))))
    print(package)
    return package


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('job', type=Path)
    parser.add_argument('--direct',action='store_true')
    parser.add_argument('--late',action='store_true')
    args=parser.parse_args()
    main(args.job,args.direct,args.late)
