"""Owned quiet v2 performance run. Default preflight never launches a game.

Uses existing exact-child launch/finish transactions. CPU scopes are compared
separately from native cadence and actual screenshot resolution.
"""
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import struct
import time
import uuid
from mod import ROOT,digest,read_json,write_json,verify_package
from native_preview import load_preview


def complete_jsonl(path):
    if not path.exists():return []
    return [json.loads(line)for line in path.read_bytes().splitlines(keepends=True)if line.endswith(b'\n')]


def stable_json(path):
    try:return read_json(path)
    except (json.JSONDecodeError,PermissionError):return None


def distribution(values):
    values=sorted(float(v)for v in values)
    if not values or any(not math.isfinite(v)or v<0 for v in values):raise ValueError('Missing or invalid timing values')
    return dict(count=len(values),mean=statistics.mean(values),median=statistics.median(values),p95=values[max(0,math.ceil(.95*len(values))-1)],maximum=max(values))


def analyze_case(index,start,end,rows):
    state,style=index%3,index//3
    for cp,stage in [(start,650+index),(end,600+index)]:
        if cp['stage']!=stage or cp['garment']!=style or cp['controls']!=[state]+[50]*17 or cp.get('throb')!=0 or cp.get('idleChatter')or cp.get('clinicalActive'):raise ValueError('Checkpoint control/feature identity differs')
    by_sequence={r['completed']:r for r in rows if 'frame'in r}
    first,last=by_sequence.get(start['sequence']),by_sequence.get(end['sequence'])
    if not first or not last:raise ValueError('Checkpoint is not bound to an observed native callback')
    measured=[r for r in rows if 'frame'in r and start['sequence']<r['completed']<=end['sequence']]
    if len(measured)<300:raise ValueError('Performance case has fewer than300accepted physics frames')
    for r in [first]+measured:
        if r['request']!=r['completed']or r['input'][:18]!=[state]+[50]*17 or r['input'][-1]!=style or r['garmentStyle']!=style:raise ValueError('Actual worker request/control/garment differs')
        if r.get('nativeRendererFailed')or r.get('resourceMask')!=3:raise ValueError('Renderer failed or complete source banks were not active')
        if r.get('visiblePhysicsServices')!=r.get('visibleSDKTicks')or 'visibleSDKTicks'not in r:raise ValueError('Visible SDK tick was not serviced exactly')
        if r.get('features',{}).get('throb')!=0 or r.get('features',{}).get('active')or r.get('clinical',{}).get('active'):raise ValueError('Animated/clinical work entered baseline case')
    physics=last['physicsServices']-first['physicsServices'];surfaces=last['surfaceServices']-first['surfaceServices']
    if physics!=len(measured):raise ValueError('Accepted frame/physics service counters disagree')
    visible=last['visibleSDKTicks']-first['visibleSDKTicks'];serviced=last['visiblePhysicsServices']-first['visiblePhysicsServices']
    if visible!=serviced or visible!=physics:raise ValueError('Measured baseline includes hidden/skipped/unserviced SDK ticks')
    intervals=[(b['seconds']-a['seconds'])*1000 for a,b in zip([first]+measured,measured)]
    clocks=[r['features']['milliseconds']for r in [first]+measured]
    wall=[float((b-a)&0xffffffff)for a,b in zip(clocks,clocks[1:])]
    result=dict(case=index,state=state,garment=style,startSequence=start['sequence'],endSequence=end['sequence'],startEngineSeconds=first['seconds'],endEngineSeconds=last['seconds'],acceptedFrames=len(measured),physicsServices=physics,surfaceServices=surfaces,surfaceServiceRatio=surfaces/physics,visibleSDKTicks=visible,visiblePhysicsServices=serviced,hiddenSkippedTicks=last['hiddenSkippedTicks']-first['hiddenSkippedTicks'])
    result['cpuMilliseconds']={key:distribution([r[key]for r in measured])for key in ['physicsMs','surfaceMs','callbackMs','sourceWaitMs','bindingMs']}
    result['surfaceMillisecondsPerService']=sum(r['surfaceMs']for r in measured)/surfaces if surfaces else None
    result['sdkEngineFrameIntervalMs']=distribution(intervals)
    result['sdkWallFrameIntervalMs']=distribution(wall)
    result['sdkDeltaSeconds']=distribution([r['dt']for r in measured])
    result['workerDeltaSeconds']=distribution([r['input'][18]for r in measured])
    step=1/(120 if style else 240)
    result['sourceFixedStepBudget']=dict(stepSeconds=step,maximumSubstepsPerCallback=12 if style else 24,maximumAccumulatedInputSeconds=.1,actualSubstepsObserved=False)
    result['boundedInputStepEquivalent']=distribution([min(r['input'][18],.1)/step for r in measured])
    result['stepEquivalentCaveat']='Bounded dt divided by fixedstep; actual floor/accumulator/substeps are not exported, so this is not a measured solver-step count'
    result['wallClock']='Unsigned GetTickCount observations; millisecond/coarse timer quantization, not a GPU timer'
    present_delta=last['visibility']['present']-first['visibility']['present'];elapsed=sum(wall)
    result['observedRendererPresentCounterDelta']=present_delta
    result['rendererCounterMeanIntervalMs']=elapsed/present_delta if present_delta else None
    result['nativePresentTimestampMedianP95Available']=False
    return result


def production_script_context(compiled,preview):
    sources=list((ROOT/'v2/scripts').glob('*.ws'))+[ROOT/'v2/build/runtime-binding/render_bones.ws']
    expected={'local/malemod/'+p.name:digest(p)for p in sources}
    observed={p:sha for p,sha in compiled['ownedSourceHashes'].items()if p!='local/malemod/v2_performance.ws'}
    staged={r['path'].split('/content/scripts/',1)[1]:r['sha256']for r in preview['files']
        if r['path'].startswith('Mods/modMaleModNative/content/scripts/')}
    if observed!=expected:raise ValueError('Production scripts, including render_bones.ws, changed since performance compilation')
    if staged!=expected:raise ValueError('Performance compiler production context differs from exact preview scripts')


def native_import_context(compiled,integrated):
    if not integrated.get('imports')or compiled.get('imports')!=integrated['imports']:
        raise ValueError('Performance official native imports differ from the integrated feature proof')


def preflight(args):
    game,preview=load_preview(args.preview)
    module=game/'bin/x64_dx12/malemod-native/malemod_witcher.dll'
    if digest(module)!=digest(args.module):raise ValueError('Explicit expected module differs from preview module')
    compile_path=ROOT/'v2/build/performance/compile.json';compiled=read_json(compile_path)
    driver=ROOT/'probes/native/v2_performance.ws'
    if compiled['exitCode']or compiled['ownedSourceHashes'].get('local/malemod/v2_performance.ws')!=digest(driver):raise ValueError('Exact official performance compile proof required')
    native_import_context(compiled,read_json(ROOT/'v2/build/features/compile.json'))
    production_script_context(compiled,preview)
    verify_package(args.package)
    output=args.output.resolve()
    if not output.is_relative_to((ROOT/'v2/build/performance').resolve())or output.exists():raise ValueError('Choose new owned performance output under v2/build/performance')
    return game,module,compile_path,driver,dict(preflightPassed=True,expectedModule=str(args.module.resolve()),moduleSHA256=digest(module),preview=str(args.preview.resolve()),previewSHA256=digest(args.preview),driverSHA256=digest(driver),compileProofSHA256=digest(compile_path),package=str(args.package.resolve()),productionFilesModified=False,gameLaunched=False)


def panel_command(directory,identity,revision,key):
    path=directory/'panel-command.ini';temp=path.with_suffix('.pending')
    temp.write_text('[Control]\nRevision='+str(revision)+'\nToken='+identity['token']+'\nProcessID='+str(identity['processID'])+'\nCreationTime='+identity['processCreationTime']+'\nKey='+key+'\nAction=Press\n',encoding='ascii');os.replace(temp,path)
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        receipt=directory/('panel-receipt-'+str(revision)+'.json')
        if receipt.exists():
            row=read_json(receipt)
            if row['processID']!=identity['processID']or row['processCreationTime']!=identity['processCreationTime']or row['token']!=identity['token']or row['physicalInputUsed']or row['hostFocusUsed']:raise ValueError('Panel command identity differs')
            return row
        time.sleep(.1)
    raise TimeoutError('Owned panel command was not acknowledged')


def run(args):
    from run_iteration_world import launch,finish
    game,module,compile_path,driver,proof=preflight(args)
    output=args.output.resolve();output.mkdir(parents=True)
    shutil.copy2(compile_path,output/'compile.json');shutil.copy2(driver,output/'driver-source.ws')
    if digest(output/'compile.json')!=proof['compileProofSHA256']or digest(output/'driver-source.ws')!=proof['driverSHA256']:
        raise ValueError('Performance official source proof changed during archival')
    documents=Path.home()/'Documents/The Witcher 3';screens=documents/'screenshots';screens.mkdir(exist_ok=True)
    if any(p.is_symlink()for p in screens.iterdir()):raise ValueError('Preserve redirected screenshot items')
    setting_names=['user.settings','dx12user.settings','input.settings','mods.settings','user.settings.bak','dx12user.settings.bak','input.settings.bak']
    settings={};saved=output/'settings-original';saved.mkdir()
    for name in setting_names:
        path=documents/name;settings[name]=digest(path)if path.exists()else None
        if path.exists():shutil.copy2(path,saved/name)
    token=uuid.uuid4().hex;panel=output/('panel-probe-'+token);panel.mkdir()
    env={k:os.environ.get(k)for k in ['MALEMOD_PANEL_PROBE','MALEMOD_PANEL_PROBE_TOKEN','MALEMOD_PANEL_PROBE_DIR']}
    os.environ.update(MALEMOD_PANEL_PROBE='1',MALEMOD_PANEL_PROBE_TOKEN=token,MALEMOD_PANEL_PROBE_DIR=str(panel))
    receipt=None;error=None;results=[];artifacts=[];closed=None;settings_verified=False;photos_verified=False
    try:
        receipt=launch(args.package,driver_source=driver,compile_proof=compile_path,native_preview=args.preview)
        session=read_json(receipt)
        if session['moduleSHA256']!=proof['moduleSHA256']:raise ValueError('Launched module identity differs')
        native=module.parent;pid=session['observations']['processID'];trace=native/('v2-frames-'+str(pid)+'.jsonl')
        deadline=time.monotonic()+args.timeout
        while not(panel/'panel-ready.json').exists():
            if time.monotonic()>deadline:raise TimeoutError('Actual owned panel did not become ready')
            time.sleep(.2)
        identity=read_json(panel/'panel-ready.json');child=session['observations']
        if identity['processID']!=child['processID']or identity['processCreationTime']!=child['processCreationTime']or not identity['noninteractiveWindowStation']:raise ValueError('Panel is not the exact isolated child')
        initial=panel_command(panel,identity,1,'Capture');revision=1
        if initial['expanded']:revision+=1;initial=panel_command(panel,identity,revision,'F6')
        if initial['expanded']:raise ValueError('Owned F6 did not close actual panel')
        for index in range(6):
            paths=[native/('v2-checkpoint-'+str(stage)+'.json')for stage in [650+index,600+index]]
            while not all(p.exists()and p.stat().st_mtime>=session['launchedUnixSeconds']and stable_json(p)is not None for p in paths):
                rows=complete_jsonl(trace)
                if any(r.get('failed')or r.get('garmentFailed')or r.get('nativeRendererFailed')for r in rows):raise ValueError('Native runtime reported a failure')
                if time.monotonic()>deadline:raise TimeoutError('Performance checkpoint did not complete')
                time.sleep(.25)
            rows=complete_jsonl(trace);start,end=map(read_json,paths);result=analyze_case(index,start,end,rows)
            for path in paths:
                target=output/path.name;shutil.copy2(path,target)
                source=path.with_suffix('.source')
                if source.exists():shutil.copy2(source,output/source.name)
            capture_time=paths[1].stat().st_mtime
            candidates=[];capture_deadline=time.monotonic()+8
            while time.monotonic()<capture_deadline:
                candidates=[p for p in screens.glob('*.png')if capture_time-.25<=p.stat().st_mtime<=capture_time+5]
                if candidates:time.sleep(.2);break
                time.sleep(.1)
            if len(candidates)!=1:raise ValueError('Checkpoint screenshot identity is missing or ambiguous')
            photo=candidates[0];data=photo.read_bytes()
            if data[:8]!=b'\x89PNG\r\n\x1a\n'or data[-8:-4]!=b'IEND':raise ValueError('Native screenshot is incomplete')
            target=output/('case-'+str(index)+'.png');shutil.copy2(photo,target)
            result.update(capture=str(target),captureSHA256=digest(target),captureSize=list(struct.unpack_from('>II',data,16)),startCheckpointSHA256=digest(paths[0]),endCheckpointSHA256=digest(paths[1]))
            results.append(result);write_json(output/'progress.json',dict(cases=results));print(json.dumps(dict(case=index,frames=result['acceptedFrames'],physicsMs=result['cpuMilliseconds']['physicsMs']['mean'],surfaceRatio=result['surfaceServiceRatio'])),flush=True)
        revision+=1;final_panel=panel_command(panel,identity,revision,'Capture')
        if final_panel['expanded']:raise ValueError('Menu opened during baseline run')
        rows=complete_jsonl(trace)
        if any(r.get('failed')or r.get('garmentFailed')or r.get('nativeRendererFailed')for r in rows):raise ValueError('Native failure appeared outside measured windows')
        shutil.copy2(trace,output/'native-frames.jsonl')
    except Exception as exc:error=str(exc)
    finally:
        for key,value in env.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
        if receipt:
            try:
                finish(receipt);closed=read_json(receipt)
                if not closed.get('closed')or not(closed.get('audioRestored')or closed.get('audioSessionsGone'))or not closed.get('iterationWorldFilesRemoved'):raise RuntimeError('Exact native closure/audio/world cleanup is not certified')
                for name,wanted in settings.items():
                    target=documents/name
                    if wanted is None:
                        if target.exists():target.unlink()
                    else:
                        if digest(saved/name)!=wanted:raise ValueError('Settings original changed')
                        if not target.exists()or digest(target)!=wanted:shutil.copy2(saved/name,target)
                        if digest(target)!=wanted:raise ValueError('Original settings did not restore exactly')
                settings_verified=True
                from screenshot_transaction import verify as verify_photos
                transaction=read_json(closed['iterationScreenshotTransaction'])
                if not closed.get('iterationScreenshotFilesRestored')or not transaction.get('restored'):
                    raise ValueError('Durable screenshot transaction did not restore originals')
                verify_photos(screens,transaction['files'])
                artifacts=closed.get('iterationScreenshotArchive',[])
                photos_verified=True
                if digest(module)!=proof['moduleSHA256']:raise ValueError('Module changed during run')
            except Exception as cleanup_error:
                error=(error+"; "if error else"")+"Cleanup incomplete: "+str(cleanup_error)
                closed=read_json(receipt)

    report=dict(proof,schema='malemod.witcher-v2-quiet-performance/1',gameLaunched=receipt is not None,receipt=str(receipt)if receipt else None,cases=results,error=error,passed=error is None and len(results)==6,closed=closed,settingsOriginalsVerified=settings_verified,ordinaryScreenshotOriginalsVerified=photos_verified,screenshotTransaction=closed.get('iterationScreenshotTransaction')if closed else None,archivedNativePhotos=artifacts,comparison='CPU kernel scopes are comparable separately; report actual native image dimensions. No cross-engine FPS equivalence or native Present median/P95 claimed from SDK timestamps.')
    write_json(output/'performance.json',report)
    if error:raise RuntimeError(error)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--preview',type=Path,required=True);p.add_argument('--package',type=Path,required=True);p.add_argument('--module',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--timeout',type=float,default=420);p.add_argument('--run',action='store_true',help='Explicitly launch; default is read-only preflight')
    a=p.parse_args();print(json.dumps(run(a)if a.run else preflight(a)[-1],indent=2))
