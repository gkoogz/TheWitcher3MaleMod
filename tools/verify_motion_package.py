"""Require native unpacked bytes to match the cooked motion resources."""
import argparse,uuid
from mod import *
from verify_cooked_motion import verify_binding
from verify_deformation_graph import verify_graph

def verify(directory):
    cfg=settings();package=Path(directory).resolve();manifest=verify_package(package)
    record=next(x for x in manifest['nativeCommands'] if x['command']=='scripted-cook')
    options=record['commands'][0]['args']
    cooked=Path(next(a.split('=',1)[1] for a in options if a.startswith('-outdir='))).resolve()
    if not cooked.is_relative_to(ROOT/'build'):raise ValueError('Cooked source leaves owned build area')
    job=ROOT/'build/jobs'/('unbundle-motion-'+uuid.uuid4().hex[:12]);out=job/'unpacked'
    native=run_wcc(cfg,'unbundle',['-dir='+str(package/'Mods/modMaleMod/content/bundles'),
                   '-outdir='+str(out)],job/'workspace','unbundle-motion')
    files=[]
    for src in cooked.rglob('*'):
        if src.is_file() and src.suffix not in ('.db','.log','.xml'):
            dst=required_file(inside(out,src.relative_to(cooked)))
            if digest(src)!=digest(dst):raise RuntimeError('Packed resource differs: '+str(src))
            files.append({'path':src.relative_to(cooked).as_posix(),'sha256':digest(dst)})
    actual={p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()}
    if actual!={x['path'] for x in files}:raise RuntimeError('Packed resources contain unexpected files')
    # Recheck delayed-slot ownership from the native dump even for the first
    # 0.4.8 candidate built before lateActivation metadata was introduced.
    binding=None
    if (manifest.get('deformationBridge') or {}).get('lateActivation') or manifest['version']=='0.4.8-late-graph-test':
        dumps=list(cooked.rglob('*.w2ent.xml'))
        if len(dumps)!=1:raise ValueError('Late graph candidate requires one native entity dump')
        binding=verify_binding(dumps[0],output='direct',require_late=True)
    if ((manifest.get('motionBinding') or {}).get('poseGraph') or {}).get('cookedPoseConnectionsVerified'):
        probe_record=manifest['deformationBridge']
        source=inside(ROOT,probe_record['sourceProbe'])/'deformation-probe.json'
        if digest(source)!=probe_record['sourceProbeSHA256']:raise ValueError('Pose input provenance changed')
        probe=read_json(source)
        pose=verify_graph(cooked/'characters/malemod/behavior/deformation.w2beh.xml',stock_names=probe['stockNames'],
            identity_root=probe.get('identityRoot'),transform_controls=probe.get('fullTransformChannels',False))
        if binding is None:binding={}
        binding['poseGraph']=pose
    result={'package':package.relative_to(ROOT).as_posix(),'native':native,'files':files,
            'additionalMotionBinding':binding}
    write_json(ROOT/'local/motion-package-verification.json',result)
    print('PASS native packed round-trip:',len(files),'resources and buffers')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',type=Path)
    args=parser.parse_args();verify(args.directory or ROOT/read_json(ROOT/'publish/latest.json')['directory'])
