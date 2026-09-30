"""Isolated native deformation graph probe. Does not install or edit stock data.

Cooking establishes resource acceptance only, not pose inheritance, live shape
control, or compatibility with the dangle simulator. Keep those separate gates.
"""
import copy
import json
import subprocess
import shutil
import uuid
from mod import ROOT, settings, digest, write_json, run_wcc, required_file
from prepare_motion import scalar, array, reference, handle, vector


def graph_recipe(template):
    result = {k: copy.deepcopy(v) for k, v in template.items() if k != '_chunks'}
    chunks = {}

    def node(kind, parent, values):
        key = kind + ' #' + str(len(chunks))
        chunks[key] = dict(_type=kind, _key=key, _parentKey=parent, _flags=0, _vars=values)
        return key

    root = node('CBehaviorGraph', '', {})
    top = node('CBehaviorGraphTopLevelNode', root, {'id': scalar('Uint32', 1)})
    pose = node('CBehaviorGraphParentInputNode', top, {
        'id': scalar('Uint32', 2), 'parentSocket': scalar('CName', 'Input')})
    control = node('CBehaviorGraphVectorVariableNode', top, {
        'id': scalar('Uint32', 3), 'variableName': scalar('CName', 'mm_probe_scale')})
    scale = node('CBehaviorGraphScaleBoneNode', top, {
        'id': scalar('Uint32', 4), 'boneName': scalar('String', 'mm_shaft_00'),
        'scale': vector('Vector', [1, 1, 1, 0]),
        'cachedInputNode': reference('ptr:CBehaviorGraphNode', pose),
        'cachedControlVariableNode': reference('ptr:CBehaviorGraphVectorValueNode', control)})
    out = node('CBehaviorGraphOutputNode', top, {
        'id': scalar('Uint32', 5), 'cachedInputNode': reference('ptr:CBehaviorGraphNode', scale)})
    variable = node('CBehaviorVectorVariable', root, {
        'name': scalar('CName', 'mm_probe_scale'), 'varIndex': scalar('Uint32', 0),
        'value': vector('Vector', [1, 1, 1, 0]), 'defaultValue': vector('Vector', [1, 1, 1, 0])})
    # Retain the inspected graph's buffered schema, replacing every graph/node
    # reference. Authoring sockets are unnecessary for this cached-node probe.
    original = template['_chunks']['CBehaviorGraph #0']['_vars']
    values = copy.deepcopy(original)
    values['stateMachines'] = array('array:2,0,ptr:CBehaviorGraphStateMachineNode', [])
    values['Toplevelnode'] = handle('CBehaviorVariable', top)
    values['Unk2'] = scalar('Uint32', 0)
    values['Variables1'] = array('array:0,0,IdHandle', [])
    values['Unk4'] = scalar('Uint32', 1)
    values['Vectorvariables1'] = array('array:0,0,IdHandle', [
        {'_type': 'IdHandle', '_vars': {'handlename': scalar('CName', 'mm_probe_scale'),
                                      'handle': handle('CBehaviorVariable', variable)}}])
    chunks[root]['_vars'] = values
    chunks[top]['_vars'].update({
        'Inputnodes': array('CBufferVLQInt32:CHandle:CBehaviorVariable',
                            [handle('CBehaviorVariable', x) for x in [pose, control, scale, out]]),
        'Unk1': array('CBufferVLQInt32:CName', []), 'Unk2': array('CBufferVLQInt32:CName', []),
        'Outputnode': handle('CBehaviorVariable', out)})
    result['_chunks'] = chunks
    return result


def main():
    cfg = settings()
    job = ROOT / 'build/control-graph' / uuid.uuid4().hex[:12]
    job.mkdir(parents=True)
    source = cfg['redkit']/'r4data/gameplay/behaviors/pc/behaviorgraph/pc_scabbards.w2beh'
    converter = ROOT / 'build/research/wkit-current/MaleModCR2W.exe'
    template = job/'stock-scabbards.json'
    subprocess.run([str(converter), 'export', str(source), str(template)], check=True, capture_output=True)
    recipe = job / 'probe.json'
    write_json(recipe, graph_recipe(json.loads(template.read_text(encoding='utf-8'))))
    resource = job / 'intake/characters/malemod/probes/control.w2beh'
    resource.parent.mkdir(parents=True)
    subprocess.run([str(converter), 'import', str(recipe), str(resource)], check=True, capture_output=True)
    workspace_resource = job / resource.relative_to(job/'intake')
    workspace_resource.parent.mkdir(parents=True)
    shutil.copy2(resource, workspace_resource)
    evidence = {'stockResource':str(source), 'stockSHA256':digest(source),
                'templateSHA256': digest(template), 'recipeSHA256': digest(recipe),
                'resourceSHA256': digest(resource), 'nativeCook': None,
                'cookedResourceSHA256':None,
                'observedGameplay': False, 'poseInheritanceVerified': False,
                'dynamicConstraintCompatibilityVerified': False, 'installed': False}
    try:
        evidence['nativeCook'] = run_wcc(cfg, 'cook', ['-platform=pc', '-mod='+str(job/'intake'),
            '-outdir='+str(job/'cooked')+'\\'], job, 'control-graph')
        evidence['cookedResourceSHA256']=digest(required_file(job/'cooked'/resource.relative_to(job/'intake')))
        log=(ROOT/evidence['nativeCook']['logPath']).read_text(encoding='utf-8',errors='replace')
        for kind in ['CBehaviorGraph','CBehaviorGraphScaleBoneNode','CBehaviorGraphParentInputNode',
                     'CBehaviorGraphVectorVariableNode','CBehaviorVectorVariable','CBehaviorGraphOutputNode']:
            if ': '+kind+' (' not in log:raise RuntimeError('Cook omitted required graph node '+kind)
    finally:
        write_json(job/'probe.json.report.json', evidence)
    print(job)
    return evidence


if __name__ == '__main__':
    main()
