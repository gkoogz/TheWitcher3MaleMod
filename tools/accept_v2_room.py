"""Bind observed v2 grey-room grounding, movement and rendering to installed bytes."""
import argparse
import json
import math
import shutil
import time
from pathlib import Path
from mod import ROOT, digest, read_json, settings, verify_package, write_json


def archived_frame(session,frame):
    frame=Path(frame).resolve();screens=(Path.home()/'Documents/The Witcher 3/screenshots').resolve()
    if frame.is_relative_to(screens):
        matches=[r for r in session.get('iterationScreenshotArchive',[])if r['name']==frame.name]
        if len(matches)!=1:raise ValueError('Current native image is not in the exact closed screenshot archive')
        candidate=Path(matches[0]['path']).resolve()
        if digest(candidate)!=matches[0]['sha256']:raise ValueError('Archived native room image changed')
        return candidate
    return frame


def room_closure(session,receipt):
    """Final installed-room delivery requires normal closure and photo recovery."""
    if (session.get('closed')is not True or session.get('exitCode')not in(None,0)
            or session.get('audioRestored')is not True or not session.get('iterationWorldFilesRemoved')):
        raise ValueError('Installed showroom needs normal exit, restored audio and removed room files')
    value=session.get('iterationScreenshotTransaction')
    if not value:raise ValueError('Installed showroom needs its exact screenshot restoration receipt')
    photo_path=Path(value).resolve()
    if not photo_path.is_relative_to((ROOT/'v2/build/screenshot-transactions').resolve()):
        raise ValueError('Showroom screenshot receipt leaves owned preservation storage')
    photos=read_json(photo_path)
    if (photos.get('schema')!='malemod.screenshot-transaction/1'or photos.get('restored')is not True
            or not isinstance(photos.get('files'),list)or photos.get('originalsVerified')!=len(photos['files'])
            or Path(photos.get('session','')).resolve()!=Path(receipt).resolve()
            or photos.get('identity')!=session['observations']):
        raise ValueError('Exact showroom screenshot restoration proof is incomplete')
    # The durable receipt is authoritative. Older fully restored snapshots may
    # omit the duplicated summary fields; when present they must agree.
    if ('iterationScreenshotFilesRestored'in session and session['iterationScreenshotFilesRestored']is not True
            or 'iterationScreenshotOriginalsVerified'in session and session['iterationScreenshotOriginalsVerified']!=photos['originalsVerified']
            or 'iterationScreenshotArchive'in session and session['iterationScreenshotArchive']!=photos.get('archive',[])):
        raise ValueError('Showroom screenshot summary differs from its restoration receipt')


def observations(rows):
    geometry=[r for r in rows if r.get('iterationReadback')and len(r.get('vectors',[]))==8
        and [r['vectors'][i][3]for i in range(3)]==[-251,-252,-253]
        and r['vectors'][4][:3]==[1,1,1]and r['vectors'][4][3]in(0,1)]
    floor=[r for r in geometry if r['vectors'][4][3]==1]
    grounded=[r for r in floor if abs(r['vectors'][3][2]-r['vectors'][6][2])<=.3]
    # The showroom stops its floor-creation branch once the room starts, while
    # its independent lifecycle readbacks keep sampling the real player. Use
    # those positions only after a verified, stable horizontal owned floor.
    lifecycle=[]
    # A successful owned-floor trace before player placement is valid geometry
    # evidence, but never a grounded player sample. Require two stable owned
    # traces and at least one player-ready trace before lifecycle movement.
    if len(geometry)>=2 and floor:
        reference=floor[0];height=reference['vectors'][6][2]
        stable=all(math.dist(r['vectors'][5][:3],reference['vectors'][5][:3])<1e-5
            and abs(r['vectors'][6][2]-height)<1e-5
            and math.dist(r['vectors'][7][:3],[0,0,1])<1e-5 for r in geometry)
        if stable:
            lifecycle=[r for r in rows if r.get('iterationReadback')and len(r.get('vectors',[]))==8
                and [r['vectors'][i][3]for i in range(3)]==[-201,-202,-203]
                and r['vectors'][4][2]==1 and r['seconds']>=reference['seconds']
                and all(math.isfinite(v)for v in r['vectors'][3][:3])
                and abs(r['vectors'][3][2]-height)<=.3]
            grounded+=lifecycle
    movement=[]
    for a in grounded:
        for b in grounded:
            if b['seconds']-a['seconds']>=2 and abs(a['vectors'][3][2]-b['vectors'][3][2])<=.3:
                movement.append((math.dist(a['vectors'][3][:3],b['vectors'][3][:3]),a,b))
    if not movement or max(x[0]for x in movement)<1:raise ValueError('No observed grounded native locomotion')
    distance,a,b=max(movement,key=lambda x:x[0])
    frames=[r for r in rows if 'frame'in r]
    if len(frames)<100 or any(r.get('failed')or r.get('garmentFailed')or r.get('nativeRendererFailed')for r in rows):
        raise ValueError('Insufficient or failed native simulation')
    if any(r['request']!=r['completed']for r in frames):raise ValueError('Native physics request left incomplete')
    if (not max((r.get('visibleSDKTicks',0)for r in frames),default=0)
            or any('visibleSDKTicks'not in r or 'visiblePhysicsServices'not in r or r['visibleSDKTicks']!=r['visiblePhysicsServices']for r in frames)):
        raise ValueError('A visible SDK tick was not serviced or independently counted')
    active=[r for r in frames if r.get('resourceMask')==3 and r.get('coverageDraws',0)>0]
    if len(active)<100 or active[-1]['completed']-active[0]['completed']<20:
        raise ValueError('Complete live native surface publication was not observed')
    return dict(movementDistance=distance,movementStart=a['vectors'][3][:3],movementEnd=b['vectors'][3][:3],
        movementSeconds=b['seconds']-a['seconds'],groundedReadbacks=len(grounded),floorReadbacks=len(geometry),readyFloorReadbacks=len(floor),
        groundedLifecycleReadbacks=len(lifecycle),sourceFrames=len(frames),activeSurfaceFrames=len(active),everyVisibleSDKTickServiced=True)


def accept(receipt,frame,*,visual_review_passed=False):
    receipt=Path(receipt).resolve();frame=Path(frame).resolve()
    if not visual_review_passed:raise ValueError('Inspect the actual room render before accepting it')
    if not receipt.is_relative_to((ROOT/'build/probe').resolve()):raise ValueError('Expected exact owned native session receipt')
    session=read_json(receipt);room_closure(session,receipt);frame=archived_frame(session,frame);identity=session['observations'];source=ROOT/'probes/native/v2_showroom.ws'
    if (not identity['noninteractiveWindowStation']or identity['physicalInputUsed']or not session.get('closed')
            or not(session.get('audioRestored')or session.get('audioSessionsGone'))or not session.get('iterationWorldFilesRemoved')
            or session['temporaryContinueSHA256']!=digest(source)):
        raise ValueError('Exact isolated showroom closure and driver proof required')
    game=settings()['game'];module=game/'bin/x64_dx12/malemod-native/malemod_witcher.dll'
    if Path(session['modulePath']).resolve()!=module.resolve()or session['moduleSHA256']!=digest(module):
        raise ValueError('Showroom must observe the actual installed v2 module')
    installed=read_json(ROOT/'local/native-installation.json');fallback=read_json(ROOT/'local/installation.json')
    if not installed.get('v2')or installed['game']!=str(game):raise ValueError('Expected installed v2 ownership receipt')
    for row in installed['files']:
        if digest(game/row['path'])!=row['sha256']:raise ValueError('Installed payload changed')
    for row in fallback['files']:
        if digest(Path(fallback['target'])/row['path'])!=row['sha256']:raise ValueError('Fallback receipt changed')
    native_acceptance=Path(installed['acceptance'])
    reviewed=read_json(native_acceptance)
    if digest(native_acceptance)!=installed['acceptanceSHA256']or not reviewed.get('panelPassed')or reviewed.get('runtimeSHA256')!=session['moduleSHA256']:
        raise ValueError('Installed F6 panel acceptance differs from showroom runtime')
    native=module.parent;trace=native/f"v2-frames-{identity['processID']}.jsonl"
    rows=[json.loads(line)for line in trace.read_text().splitlines()];metrics=observations(rows)
    checkpoints=[]
    for stage in (0,1,2,69,70,71):
        path=native/f'v2-checkpoint-{stage}.json'
        if path.stat().st_mtime<session['launchedUnixSeconds']:raise ValueError('Current naked and jockstrap views required')
        row=read_json(path)
        if row['stage']!=stage or row['garment']!=int(stage>=69):raise ValueError('Showroom garment state differs')
        checkpoints.append(row)
    if (not any(frame.is_relative_to(p.resolve())for p in [ROOT/'build',ROOT/'v2/build',Path.home()/'Documents/The Witcher 3/screenshots'])
            or frame.stat().st_mtime<session['launchedUnixSeconds']):raise ValueError('Expected current native-rendered frame')
    package=Path(session['iterationWorldPackage']);verify_package(package)
    proof=read_json(ROOT/'v2/build/showroom/compile.json')
    if proof['exitCode']or proof['ownedSourceHashes'].get('local/malemod/v2_showroom.ws')!=digest(source)or session['driverCompileProofSHA256']!=digest(ROOT/'v2/build/showroom/compile.json'):
        raise ValueError('Official showroom compile proof changed')
    destination=receipt.parent/'accepted-v2-render.png';shutil.copy2(frame,destination)
    shutil.copy2(trace,receipt.parent/'accepted-v2-frames.jsonl')
    output=receipt.parent/'v2-room-acceptance.json'
    write_json(output,dict(schema='malemod.witcher-v2-room-acceptance/1',sourceSession=str(receipt),
        packageManifestSHA256=digest(package/'build-manifest.json'),driverSHA256=digest(source),
        installationReceiptSHA256=digest(ROOT/'local/native-installation.json'),fallbackReceiptSHA256=digest(ROOT/'local/installation.json'),
        groundedPlayer=True,movementObserved=True,nativeModObserved=True,f6IntegrationUnchanged=True,f6VisualTest=reviewed['panelPassed'],
        visualReviewPassed=True,visualReviewPerformed=True,knownIssues=[],renderedFrame=str(destination),renderedFrameSHA256=digest(destination),
        nativeTraceSHA256=digest(trace),checkpoints=checkpoints,audioRestored=bool(session.get('audioRestored')),
        audioSessionsGone=bool(session.get('audioSessionsGone')),**metrics))
    return output


def activate(acceptance):
    """Switch the stable room entry only after its complete read-only preflight."""
    from play_iteration_platform import play
    from install_v2 import atomic_json
    acceptance=Path(acceptance).resolve();data=read_json(acceptance)
    if data.get('schema')!='malemod.witcher-v2-room-acceptance/1':raise ValueError('Expected accepted installed v2 room')
    session=read_json(data['sourceSession']);package=Path(session['iterationWorldPackage'])
    play(package,acceptance,check_only=True)
    config=ROOT/'local/grey-room-launch.json'
    backup=ROOT/'v2/build/installation'/('grey-room-launch-before-v2-'+str(time.time_ns())+'.json')
    if config.exists():
        backup.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(config,backup)
        if digest(backup)!=digest(config):raise ValueError('Previous room entry backup differs')
    atomic_json(config,dict(schema='malemod.grey-room-launch/1',package=str(package),acceptance=str(acceptance),
        previousConfiguration=str(backup)if backup.exists()else None))
    return dict(configuration=str(config),acceptance=str(acceptance),previousConfiguration=str(backup)if backup.exists()else None)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--frame',type=Path,required=True);parser.add_argument('--visual-reviewed',action='store_true')
    parser.add_argument('--make-default',action='store_true',help='After acceptance and preflight, switch the stable grey-room entry')
    args=parser.parse_args();output=accept(args.receipt,args.frame,visual_review_passed=args.visual_reviewed)
    print(activate(output)if args.make_default else output)
