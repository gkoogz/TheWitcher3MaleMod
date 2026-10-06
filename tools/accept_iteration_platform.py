"""Bind observed grey-room movement/rendering to its exact launch artifacts.

The frame must be inspected before running this acceptance command. A successful
cook or changing idle mesh alone cannot satisfy the movement gate.
"""
import argparse,json,math,shutil
from pathlib import Path
from mod import ROOT,digest,read_json,settings,verify_package,write_json

def accept(receipt,frame, *, visual_review_passed=False, known_floor_artifact=False):
    if visual_review_passed and known_floor_artifact:
        raise ValueError('Known rendering defect cannot pass final visual acceptance')
    receipt=Path(receipt).resolve();frame=Path(frame).resolve()
    if not receipt.is_relative_to((ROOT/'build/probe').resolve()):
        raise ValueError('Expected exact private session receipt')
    session=read_json(receipt);pid=session['observations']['processID']
    if not session['observations']['noninteractiveWindowStation'] or session['observations']['physicalInputUsed']:
        raise ValueError('Expected isolated verification')
    source=ROOT/'probes/native/iteration_platform.ws'
    if session['temporaryContinueSHA256']!=digest(source):
        raise ValueError('Driver changed since this session')
    trace=Path(session['modulePath']).parent/f'verification-{pid}.jsonl'
    rows=[json.loads(line) for line in trace.read_text().splitlines()]
    if [r['stage'] for r in rows]!=[200,201]:
        raise ValueError('Expected ordered grounded/start and movement/end captures')
    a,b=rows
    distance=math.dist(a['actorOrigin'],b['actorOrigin'])
    if distance<1.0 or abs(a['actorOrigin'][2]-b['actorOrigin'][2])>.3:
        raise ValueError('No observed grounded locomotion: '+str(distance))
    if any(r['bodyResourceMask']!=3 or r['vertices']!=49884 or r['runtimeFlags']&8==0 for r in rows):
        raise ValueError('Complete native anatomy output not observed')
    if b['poseSeconds']-a['poseSeconds']<3 or b['sequence']-a['sequence']<20 or a['uploadFNV64']==b['uploadFNV64']:
        raise ValueError('Live simulation publication not observed')
    pose=Path(session['modulePath']).parent/f'pose-probe-{pid}.jsonl'
    packets=[json.loads(line) for line in pose.read_text().splitlines()]
    grounded=[p for p in packets if p['actorLocal'][0][3]==-251 and p['actorLocal'][4][:3]==[1,1,1]]
    if not grounded:raise ValueError('No exact owned-floor physics trace')
    if not frame.is_relative_to((Path.home()/'Documents/The Witcher 3/screenshots').resolve()) or frame.stat().st_mtime<session['launchedUnixSeconds']:
        raise ValueError('Expected current native renderer screenshot')
    package=Path(session['iterationWorldPackage']);manifest=verify_package(package)
    game=settings()['game'];installed=read_json(ROOT/'local/native-installation.json')
    fallback=read_json(ROOT/'local/installation.json')
    for row in installed['files']:
        if digest(game/row['path'])!=row['sha256']:raise ValueError('Installed runtime changed')
    for row in fallback['files']:
        if digest(Path(fallback['target'])/row['path'])!=row['sha256']:raise ValueError('Rig fallback changed')
    dst=receipt.parent/'accepted-render.png';shutil.copy2(frame,dst)
    shutil.copy2(trace,receipt.parent/'accepted-checkpoints.jsonl')
    shutil.copy2(pose,receipt.parent/'accepted-lifecycle.jsonl')
    output=receipt.parent/'platform-acceptance.json'
    write_json(output,dict(schema='malemod.iteration-platform-acceptance/1',
        packageManifestSHA256=digest(package/'build-manifest.json'),driverSHA256=digest(source),
        installationReceiptSHA256=digest(ROOT/'local/native-installation.json'),
        fallbackReceiptSHA256=digest(ROOT/'local/installation.json'),
        groundedPlayer=True,movementObserved=True,movementDistance=distance,
        nativeModObserved=True,f6IntegrationUnchanged=True,f6VisualTest=False,
        visualReviewPassed=visual_review_passed,
        visualReviewPerformed=visual_review_passed or known_floor_artifact,
        knownIssues=['native-motion-floor-artifact'] if known_floor_artifact else [],
        renderedFrame=str(dst),renderedFrameSHA256=digest(dst),
        nativeCheckpointsSHA256=digest(trace),nativeLifecycleSHA256=digest(pose),
        sourceSession=str(receipt),underlyingStockWorldStillLoaded=True,
        measuredSimulationIntervalMs=b['presentationIntervalMs']))
    print(output)
    return output

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--frame',type=Path,required=True)
    p.add_argument('--visual-reviewed',action='store_true',help='Confirm the current native frame has been visually inspected and accepted')
    p.add_argument('--known-floor-artifact',action='store_true',help='Record reviewed playable preview with the unresolved native motion floor defect; does not pass final visual acceptance')
    a=p.parse_args();accept(a.receipt,a.frame,visual_review_passed=a.visual_reviewed,known_floor_artifact=a.known_floor_artifact)
