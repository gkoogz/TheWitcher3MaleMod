"""Cook an isolated animated-parent/deformation/dangle attachment candidate.

Does not install. Reuses and re-verifies the immutable native cage geometry;
the report records its original Base revision separately from today's pin.
"""
import copy
import json
import shutil
import subprocess
import uuid
from pathlib import Path
from mod import ROOT, settings, base_checkout, digest, write_json, run_wcc, required_file
from motion_entity import make_entity
from deformation_graph import deformation_graph, add_deformation_component
from verify_motion import verify
from prepare_motion import rig_world
import numpy as np


def main(transform_controls=False, identity_root=False, model_pose=False, attached_pose=False, cage_path=None):
    if model_pose and attached_pose:raise ValueError('Choose one pose input')
    parent_space='attached' if attached_pose else 'model' if model_pose else 'local'
    cfg = settings()
    pin = base_checkout(cfg)
    cage = Path(cage_path).resolve() if cage_path else ROOT / 'build/motion/cage-dec402309e13'
    if not cage.is_relative_to(ROOT/'build/motion'):raise ValueError('Cage must be an owned build job')
    verified = verify(cage)
    source_record = json.loads((cage / 'motion.json').read_text(encoding='utf-8'))
    job = ROOT / 'build/motion' / ('deformation-' + uuid.uuid4().hex[:12])
    job.mkdir(parents=True)
    converter = ROOT / 'build/research/wkit-current/MaleModCR2W.exe'
    stock_graph = cfg['redkit'] / 'r4data/gameplay/behaviors/pc/behaviorgraph/pc_scabbards.w2beh'
    template_path = job / 'stock-graph.json'
    subprocess.run([str(converter), 'export', str(stock_graph), str(template_path)],
                   check=True, capture_output=True)
    dyng = json.loads((cage / 'motion-dyng.json').read_text(encoding='utf-8'))
    skeleton = dyng['_chunks']['CSkeleton #1']
    names = [b['_vars']['name']['_value'] for b in skeleton['_vars']['bones']['_elements']]
    controlled = source_record['newBones']
    stock = names[:-len(controlled)]
    if names[-len(controlled):] != controlled:
        raise ValueError('Native cage joint names differ')
    root_name=None
    if identity_root:
        observed_names,parents,worlds=rig_world(skeleton['_vars'])
        if observed_names != names or parents[0] != -1 or not np.allclose(worlds[0],np.eye(4),atol=1e-7):
            raise ValueError('Identity-root policy requires an observed identity bone zero')
        root_name=names[0]
    graph_path = 'characters/malemod/behavior/deformation.w2beh'
    rig_path = 'characters/malemod/physics/deformation.w2rig'
    entity_path = 'items/bodyparts/geralt_items/legs/bare/l_01_mg__body_underwear.w2ent'
    recipe = deformation_graph(json.loads(template_path.read_text(encoding='utf-8')), stock, controlled,
                               transform_controls=transform_controls,identity_root=root_name,
                               parent_space=parent_space)
    write_json(job / 'deformation-graph.json', recipe)
    rig = {k: copy.deepcopy(v) for k, v in dyng.items() if k != '_chunks'}
    rig['_chunks'] = {'CSkeleton #0': copy.deepcopy(skeleton)}
    rig['_chunks']['CSkeleton #0'].update(_key='CSkeleton #0', _parentKey='')
    write_json(job / 'deformation-rig.json', rig)
    make_entity(job)
    entity = add_deformation_component(json.loads((job / 'motion-entity.json').read_text(encoding='utf-8')),
                                      rig_path.replace('/', '\\'), graph_path.replace('/', '\\'))
    write_json(job / 'deformation-entity.json', entity)
    for source, destination in [('deformation-graph.json', graph_path),
                                ('deformation-rig.json', rig_path),
                                ('deformation-entity.json', entity_path)]:
        resource = job / 'intake' / destination
        resource.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([str(converter), 'import', str(job/source), str(resource)],
                       check=True, capture_output=True)
    for source in ['characters/malemod/body/geralt_motion.w2mesh',
                   'characters/malemod/physics/geralt_motion.w3dyng']:
        resource = job / 'intake' / source
        resource.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cage / source, resource)
    resources = list((job/'intake').rglob('*'))
    for resource in resources:
        if resource.is_file():
            target = job / resource.relative_to(job/'intake')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(resource, target)
    evidence = dict(baseCommit=pin['commit'], cageBaseCommit=source_record['baseCommit'],
                    sourceCage=cage.relative_to(ROOT).as_posix(),
                    cageVerification=verified, stockGraphSHA256=digest(stock_graph),
                    stockNames=stock, controlledNames=controlled,
                    fullTransformChannels=transform_controls,
                    identityRoot=root_name,
                    parentPoseSpace=parent_space,
                    poseInheritanceObserved=False, liveScaleObserved=False,
                    dangleCompatibilityObserved=False, installed=False)
    try:
        evidence['nativeCook'] = run_wcc(cfg, 'cook', [
            '-platform=pc', '-mod='+str(job/'intake'), '-outdir='+str(job/'cooked')+'\\'],
            job, 'deformation-bridge')
        evidence['resources'] = [dict(path=p.relative_to(job/'intake').as_posix(),
                                      sourceSHA256=digest(p),
                                      cookedSHA256=digest(required_file(job/'cooked'/p.relative_to(job/'intake'))))
                                 for p in resources if p.is_file()]
        log = (ROOT/evidence['nativeCook']['logPath']).read_text(encoding='utf-8', errors='replace')
        for kind in ['CAnimatedComponent', 'CAnimatedAttachment', 'CAnimDangleComponent',
                     *(['CBehaviorGraphInputNode','CBehaviorGraphConstraintReset'] if attached_pose else
                       ['CBehaviorGraphTPoseNode','CBehaviorGraphConstraintNodeParentAlign']),
                     'CBehaviorGraphScaleBoneNode', 'CSkeleton']:
            if ': '+kind+' (' not in log:
                raise RuntimeError('Cook omitted ' + kind)
        if transform_controls:
            for kind in ['CBehaviorGraphVariableNode','CBehaviorGraphTranslateBoneNode',
                         'CBehaviorGraphRotateBoneNode','CBehaviorVariable']:
                if ': '+kind+' (' not in log:raise RuntimeError('Cook omitted '+kind)
        from inspect_native import inspect
        from verify_deformation_graph import verify_graph
        native_dump=inspect(job/'cooked'/graph_path)
        evidence['poseGraph']=verify_graph(native_dump['output'],stock_names=stock,
            identity_root=root_name,transform_controls=transform_controls,
            parent_space=parent_space)
    finally:
        write_json(job/'deformation-probe.json', evidence)
    print(job)
    return evidence


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--transforms',action='store_true')
    parser.add_argument('--identity-root',action='store_true')
    parser.add_argument('--model-pose',action='store_true')
    parser.add_argument('--attached-pose',action='store_true')
    parser.add_argument('--cage',type=Path)
    args=parser.parse_args()
    main(args.transforms,args.identity_root,args.model_pose,args.attached_pose,args.cage)
