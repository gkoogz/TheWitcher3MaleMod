"""Prepare an ignored packet from a verified automatic actor-local pose probe."""
import argparse,json,struct
from pathlib import Path
import numpy as np
from mod import ROOT,settings,base_checkout,read_json,digest,write_json
from packed_mesh_format import CookedMesh


def prepare(receipt,output):
    receipt=Path(receipt).resolve();output=Path(output).resolve()
    if not receipt.is_relative_to(ROOT/'build/probe') or not output.is_relative_to(ROOT/'build/full-runtime'):
        raise ValueError('Replay data belongs in owned ignored build directories')
    if output.exists():raise ValueError('Do not overwrite a replay artifact')
    pin=base_checkout(settings());r=read_json(receipt);status=read_json(receipt.parent/'status.json')
    if not status.get('poseSamplingObserved') or status['registrationFailed'] or status['typedProbeFailed']:
        raise ValueError('Probe has no verified automatic pose invocation')
    module=ROOT/r['modulePath']
    if digest(module)!=r['moduleSHA256']:raise ValueError('Probe module changed')
    pose=module.parent/f"pose-probe-{r['observations']['processID']}.jsonl"
    rows=[json.loads(line) for line in pose.read_text().splitlines()]
    if len(rows)!=240 or any(row['sample']!=i or row['paused'] for i,row in enumerate(rows)):
        raise ValueError('Incomplete or paused pose coverage')
    times=np.array([row['seconds'] for row in rows],float)
    values=np.array([row['actorLocal'] for row in rows],float)
    if values.shape!=(240,8,4) or not np.isfinite(values).all() or not np.isfinite(times).all() or np.any(np.diff(times)<=0):
        raise ValueError('Invalid chronological pose samples')
    mesh=ROOT/'build/motion/player-stack-138649950289/package-cfb0915d89d2/cooked/characters/malemod/body/geralt_motion.w2mesh'
    cooked=CookedMesh(mesh.read_bytes());ids=[i for i,n in enumerate(cooked.palette) if n=='pelvis']
    if len(ids)!=2:raise ValueError('Expected observed pelvis palette in both LODs')
    inverse=np.array(cooked.inverse_binds[ids[0]],float).reshape(4,4).T
    if not np.array_equal(inverse,np.array(cooked.inverse_binds[ids[1]],float).reshape(4,4).T):
        raise ValueError('Pelvis inverse bind differs between native LODs')
    calibration=read_json(ROOT/'characters/geralt-runtime-bindings.json')['coordinateCalibration']
    output.mkdir(parents=True)
    packet=output/'observed.pose'
    with packet.open('wb') as f:
        f.write(b'MMPOSE01')
        for a in [calibration['basis'],calibration['sourceRoot'],calibration['targetRootNative'],[calibration['nativeUnitsPerSourceUnit']],inverse]:
            f.write(np.asarray(a,dtype='<f8').tobytes())
        f.write(struct.pack('<I',len(rows)))
        for seconds,v in zip(times,values):
            matrix=np.eye(4);matrix[:3,:3]=v[:3,:3].T;matrix[:3,3]=v[3,:3]
            if abs(np.linalg.det(matrix[:3,:3])-1)>1e-4:raise ValueError('Measured pelvis basis is not rigid')
            f.write(struct.pack('<d',seconds));f.write(matrix.astype('<f8').tobytes());f.write(v[4:,:3].astype('<f8').tobytes())
    report=dict(baseCommit=pin['commit'],poseSamples=len(rows),spanSeconds=float(times[-1]-times[0]),
        poseProbeSHA256=digest(pose),probeReceiptSHA256=digest(receipt),probeModuleSHA256=digest(module),
        cookedMeshSHA256=digest(mesh),recipeSHA256=digest(Path(__file__)),readerSHA256=digest(ROOT/'tools/packed_mesh_format.py'),
        packetSHA256=digest(packet),actorWorldRemoved=True,skinDeltaIncludesNativeInverseBind=True,
        characterContactsCalibrated=False,nativeVertexOutput=False,observedGameplayOutput=False)
    write_json(output/'manifest.json',report);print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('receipt',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();prepare(a.receipt,a.output)
