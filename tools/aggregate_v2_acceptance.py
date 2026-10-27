"""Aggregate exact native evidence; review flags are explicit human/agent attestations.

This tool never launches, stages, installs, or infers visual acceptance from
numeric tests. All reviewed native images and lower evidence are hash bound.
Native FPS equality is deliberately not claimed by the kernel comparison.
"""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from mod import ROOT,digest,read_json,write_json
from native_preview import load_preview


def need(condition,message):
    if not condition:raise ValueError(message)


def inventory_hash(rows):
    rows=sorted([dict(path=r['path'],sha256=r['sha256'])for r in rows],key=lambda r:r['path'])
    return hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()


class Evidence:
    def __init__(self):self.files={};self.images={}
    def add(self,path):
        path=Path(path).resolve();need(path.is_file(),'Evidence file missing: '+str(path));sha=digest(path)
        previous=self.files.setdefault(str(path),sha);need(previous==sha,'Evidence changed during aggregation: '+str(path));return path
    def json(self,path):return read_json(self.add(path))
    def trace(self,path):
        path=self.add(path)
        return[json.loads(line)for line in path.read_bytes().splitlines(keepends=True)if line.endswith(b'\n')]
    def image(self,row):
        path=self.add(row.get('image',row.get('path')));sha=self.files[str(path)]
        need(sha==row['sha256'],'Reviewed image changed: '+str(path))
        with path.open('rb')as stream:need(stream.read(8)==b'\x89PNG\r\n\x1a\n','Expected actual native PNG: '+str(path))
        self.images[str(path)]=sha


def frame_gates(rows):
    frames=[r for r in rows if'frame'in r]
    need(bool(frames),'No actual native frame observations')
    need(not any(r.get('failed')or r.get('garmentFailed')or r.get('nativeRendererFailed')for r in rows),'Native runtime/renderer fault in actual trace')
    need(all(r['request']==r['completed']==r['physicsServices']for r in frames),'Actual physics requests were not completed')
    need(max(r.get('visibleSDKTicks',0)for r in frames)>0 and all('visibleSDKTicks'in r and r['visibleSDKTicks']==r.get('visiblePhysicsServices')for r in frames),'Visible SDK ticks were not independently serviced')
    return frames


def script_proof_gates(name,path,session,description,evidence,expected_imports=None):
    """Bind the official proof and owned probe to that session's exact scripts."""
    defaults={'feature':'features/compile.json','production':'acceptance/full-final-compile.json',
        'lod1':'acceptance/full-final-compile.json','campaign':'campaign/compile.json','witcher_performance':'performance/compile.json'}
    proof_path=path.parent/'compile.json'
    if not proof_path.exists():proof_path=ROOT/'v2/build'/defaults[name]
    proof=evidence.json(proof_path)
    need(digest(proof_path)==session['driverCompileProofSHA256'],'Official compiler proof differs from native session in '+name)
    need(proof.get('command')=='native-compilescripts'and proof.get('exitCode')==0 and bool(proof.get('imports')),'Official native compiler did not pass in '+name)
    if expected_imports is not None:need(proof['imports']==expected_imports,'Native import surface differs from exact feature compiler proof in '+name)
    driver=path.parent/'driver-source.ws'
    if not driver.exists():driver=Path(session['driver'])
    evidence.add(driver);driver_name='local/malemod/'+Path(session['driver']).name
    need(digest(driver)==session['temporaryContinueSHA256']==proof['ownedSourceHashes'].get(driver_name),'Owned probe source differs from actual native session in '+name)
    scripts={r['path'].split('/content/scripts/',1)[1]:r['sha256']for r in description['files']if r['path'].startswith('Mods/modMaleModNative/content/scripts/')}
    observed={p:sha for p,sha in proof['ownedSourceHashes'].items()if p!=driver_name}
    need(observed==scripts,'Official probe context differs from exact native runtime scripts in '+name)
    return proof['imports']


def panel_gates(panel,identity=None):
    need(panel.get('passed')is True,'Full feature panel did not pass')
    expected_values=[2]+[50]*17;expected_clinical=[0,0,0];tokens=set()
    for i in range(21):
        row=panel.get(str(i),{});need(row.get('selected')==i,'Missing actual canonical panel row '+str(i))
        need(row.get('physicalInputUsed')is False and row.get('hostFocusUsed')is False,'Panel used or failed to certify private input')
        if identity:need(row.get('processID')==identity['processID']and str(row.get('processCreationTime'))==str(identity['processCreationTime']),'Panel receipt belongs to a different native child')
        values=row.get('controls',[]);clinical=row.get('clinical',[])
        expected=(len(values)==18 and len(clinical)==3 and(values[0]==0 if i==0 else clinical[0]==1 if i==1 else clinical[1]==1 if i==2 else clinical[2]==1 if i==20 else values[i-2]==51))
        need(expected,'Actual canonical row result differs: '+str(i))
        if i==0:expected_values[0]=0
        elif i==1:expected_clinical[0]=1
        elif i==2:expected_clinical[1]=1
        elif i==20:expected_clinical[2]=1
        else:expected_values[i-2]=51
        need(values==expected_values and clinical==expected_clinical,'Panel changed unrelated controls at row '+str(i))
        tokens.add(row.get('token'))
    need(len(tokens)==1 and None not in tokens,'Panel command authentication token differs across rows')
    shift=panel.get('shiftStep',{}).get('controls',[]);need(len(shift)==18 and shift[1]==55,'Actual Shift step-of-five receipt missing')
    light=panel.get('lighting',{});need(light.get('passed')and light.get('switched')!=light.get('before')and light.get('restored')==light.get('before'),'Actual F9 toggle/restore evidence missing')
    shortcut=panel.get('teachingShortcut',{});need(shortcut.get('passed')and shortcut.get('cancelFrame',0)>shortcut.get('startFrame',0),'Actual J start/cancel evidence missing')
    message=panel.get('windowJ',{});need(message.get('windowMessagePosted')and message.get('messagesAfter',0)>message.get('messagesBefore',0),'Actual private game-window J fencing missing')
    idle=panel.get('idlePlayback',{});need(idle.get('nativeAutomaticEvent')and idle.get('playedAfter',0)>idle.get('playedBefore',0),'Actual automatic native idle recording missing')
    final=panel.get('final',{});need(final.get('controls')==[2]+[50]*17 and final.get('clinical')==[0,0,0],'Final source reset did not restore defaults')


def feature_gates(report,path,evidence,identity=None):
    panel_gates(report['panel'],identity);rows=evidence.trace(path.parent/'frames.jsonl');frames=frame_gates(rows)
    required={201}|{400+mode*10+i for mode in range(4)for i in range(4)}|set(range(500,507))|set(range(520,527))
    checkpoints={int(p.stem.rsplit('-',1)[1]):evidence.json(p)for p in path.parent.glob('v2-checkpoint-*.json')}
    need(set(checkpoints)==required,'Exact feature checkpoint set differs (including failed/retried phase sentinel)')
    by_sequence={r['completed']:r for r in frames}
    for stage,cp in checkpoints.items():
        need(cp['stage']==stage and cp['controls']==[2]+[50]*17,'Feature checkpoint baseline state differs at '+str(stage))
        need(len(cp.get('effectiveControls',[]))==18 and all(math.isfinite(float(v))for v in cp['effectiveControls']),'Actual effective controls missing/nonfinite')
        actual=by_sequence.get(cp['sequence']);need(actual is not None,'Feature CP lacks its actual source frame: '+str(stage))
        mode=(stage-400)//10 if 400<=stage<=433 else 0;style=int(stage>=520)
        need(cp['throb']==mode and cp['garment']==style and actual['garmentStyle']==style,'Feature CP throb/garment provenance differs')
        need(actual.get('features',{}).get('throb')==mode and actual['input'][0]==2,'Actual source feature/state differs from checkpoint')
        if stage<500:need(not cp['clinicalActive'],'Clinical activity contaminated passive-throb cases')
        else:
            index=stage-(520 if style else 500);target=(0,3,6,8,11,15,20)[index]
            need(target<=cp['clinicalSeconds']<=target+1.5,'Clinical checkpoint did not reach actual phase time')
            need(abs(actual['clinical']['time']-cp['clinicalSeconds'])<.05,'Clinical checkpoint time differs from its actual source frame')
    phases={}
    for base in(500,520):
        first,last=checkpoints[base]['sequence'],checkpoints[base+6]['sequence']
        phase=[r['clinical']for r in frames if first<=r['completed']<=last]
        need(bool(phase),'Clinical phase has no source ledger')
        measured={key:max(r.get(key,0)for r in phase)for key in('emittedVolume','depositedClear','depositedOpaque','finalPumpVolume','finalPumpImpacts','cueMask','audioPlayed','audioFailed','liquidIndices','depositIndices')}
        need(all(measured[key]>0 for key in('emittedVolume','depositedClear','depositedOpaque','finalPumpVolume','finalPumpImpacts','liquidIndices','depositIndices')),'Actual phase20 emission/deposition/final-pump ledger incomplete')
        need(measured['cueMask']&3==3 and measured['audioPlayed']>0 and measured['audioFailed']==0,'Actual clinical audio/cue ledger failed')
        phases[str(base)]=measured
    need(all(r['clinical']['audioPhaseCounts']==[13,11]and r['clinical']['audioIdleCount']==22 and r['clinical']['audioFailed']==0 for r in frames),'Exact local source audio pools failed or differ')
    pairs_path=path.parent/'paired-views.json';pairs=[];used=set()
    if pairs_path.exists():
        paired=evidence.json(pairs_path);need(len(paired)==31 and {p['stage']for p in paired}==required,'Feature native image pairing set differs')
        for pair in paired:
            need(pair['checkpoint']==checkpoints[pair['stage']],'Feature image pairing checkpoint provenance differs')
            image=pair['image'];evidence.image(image);need(image['path']not in used,'Feature checkpoints reuse a native image');used.add(image['path'])
            pairs.append(dict(stage=pair['stage'],path=image['path'],sha256=image['sha256']))
    else:
        for stage,cp in sorted(checkpoints.items()):
            stamp=(path.parent/f'v2-checkpoint-{stage}.json').stat().st_mtime
            candidates=sorted((r for r in report['images']if r['path']not in used and-.03<=r['mtime']-stamp<=2),key=lambda r:r['mtime'])
            need(bool(candidates),'No unique current native image for feature CP '+str(stage));image=candidates[0];used.add(image['path']);evidence.image(image)
            pairs.append(dict(stage=stage,path=image['path'],sha256=image['sha256']))
    return dict(checkpoints=sorted(checkpoints),phaseLedgers=phases,frames=len(frames),automaticIdlePlayback=report['panel']['idlePlayback'],nativeImages=pairs)


def matrix_gates(report,path,evidence,cases):
    need(all(report.get(k)is True for k in('allCaseCheckpointsPresent','caseStatesAndUniqueImagesPassed','panelPassed','allPhysicsRequestsCompleted','everyVisibleSDKTickServiced','lodCoveragePassed')),'Native matrix evidence gates incomplete')
    rows=evidence.trace(path.parent/'frames.jsonl');frame_gates(rows)
    panel=evidence.json(path.parent/'panel-review.json')
    need(panel.get('passed')and panel.get('collapsed',{}).get('expanded')is False and panel.get('expanded',{}).get('expanded')is True
        and panel.get('reset',{}).get('controls')==[2]+[50]*17 and panel.get('reset',{}).get('clinical')==[0,0,0],'Actual matrix F6/F8 receipts incomplete')
    pairs=evidence.json(path.parent/'paired-views.json');need(len(pairs)==90 and {r['stage']for r in pairs}==set(range(90)),'Matrix does not contain all90 native views')
    need(len({r['image']for r in pairs})==90,'Matrix reuses an image for more than one view')
    for pair in pairs:
        stage=pair['stage'];cp=evidence.json(pair['checkpoint']);case=cases[stage//3]
        need(cp['stage']==stage and cp['controls']==case['controls']and cp['garment']==case['garment'],'Actual matrix control/garment mismatch')
        need(cp.get('throb',0)==0 and not cp.get('clinicalActive')and not cp.get('idleChatter'),'Animated features contaminated attachment matrix')
        evidence.image(pair)


def private_save_gates(session,report,evidence):
    transaction_path=Path(session['iterationSaveTransaction']);transaction=evidence.json(transaction_path)
    need(transaction.get('finishedUnixSeconds')and transaction.get('originalsVerified')==0,'Fresh-profile private save transaction did not close cleanly')
    created=transaction.get('archivedPrivateCreated',[])
    need(created and inventory_hash([dict(path=r['name'],sha256=r['sha256'])for r in created])
        ==inventory_hash([dict(path=r['name'],sha256=r['sha256'])for r in report['generatedSaves']]),'Observed private save inventory differs from exact closure archive')
    need(any(Path(r['name']).suffix=='.sav'for r in created),'No actual private save payload was archived')
    metadata=[]
    for row in created:
        path=transaction_path.parent/'private-created'/row['name']
        need(path.resolve().parent==(transaction_path.parent/'private-created').resolve(),'Private save archive path escapes its exact transaction')
        evidence.add(path);need(digest(path)==row['sha256'],'Archived private save changed')
        if path.suffix=='.json':metadata.append(path)
    need(metadata and all(re.search(r'"modName"\s*:\s*"modmalemodcontinuetest"',p.read_text(),re.I)for p in metadata),'Archived save metadata lacks actual private-driver provenance')


def screenshot_gates(session,session_path,evidence):
    need(session.get('iterationScreenshotFilesRestored')is True and session.get('iterationScreenshotTransaction'),'Durable screenshot preservation proof missing')
    receipt=Path(session['iterationScreenshotTransaction']);transaction=evidence.json(receipt)
    need(transaction.get('schema')=='malemod.screenshot-transaction/1'and transaction.get('restored')is True
        and transaction.get('originalsVerified')==len(transaction['files']),'Exact screenshot originals were not restored')
    need(Path(transaction['session']).resolve()==Path(session_path).resolve()and transaction['identity']==session['observations'],'Screenshot transaction belongs to another native session')
    need(session['iterationScreenshotArchive']==transaction.get('archive',[]),'Screenshot archive differs from exact closed transaction')
    for row in transaction.get('archive',[]):
        need(Path(row['path']).resolve()==(receipt.parent/'session-photos'/row['name']).resolve(),'Native photo archive path differs')
        evidence.image(row)


def performance_comparison(port,reference,evidence,port_path,reference_path):
    need(port.get('passed')and port.get('settingsOriginalsVerified')and port.get('ordinaryScreenshotOriginalsVerified')and not port.get('error'),'Quiet Witcher performance evidence incomplete')
    need(reference.get('complete')and reference.get('hostInput')is False and reference.get('hostFocus')is False and reference.get('close',{}).get('audioRestored'),'Quiet Wolverine reference incomplete')
    lock=read_json(ROOT/'v2/wolverine.lock.json');need(reference.get('sourceCommit')==lock['commits']['wolverine']and reference.get('baseCommit')==lock['commits']['wolverineBase'],'Wolverine reference source pins differ')
    need(len(port['cases'])==len(reference['cases'])==6,'Six quiet state/garment cases required on each engine')
    lookup={(r['physicsState'],int(r['garment']=='Jockstrap')):r for r in reference['cases']};comparisons=[]
    need(set(lookup)=={(state,style)for state in range(3)for style in range(2)},'Reference performance state/garment cases differ')
    from run_v2_performance import analyze_case
    actual_frames=evidence.trace(port_path.parent/'native-frames.jsonl');frame_gates(actual_frames)
    for case in port['cases']:
        index=case['case'];start=evidence.json(port_path.parent/f'v2-checkpoint-{650+index}.json');end=evidence.json(port_path.parent/f'v2-checkpoint-{600+index}.json')
        actual=analyze_case(index,start,end,actual_frames)
        need(actual['acceptedFrames']==case['acceptedFrames']and actual['cpuMilliseconds']==case['cpuMilliseconds'],'Performance report differs from actual quiet source frame windows')
        evidence.image(dict(path=case['capture'],sha256=case['captureSHA256']))
        key=(case['state'],case['garment']);need(key in lookup and case['acceptedFrames']>=300 and case['visibleSDKTicks']==case['visiblePhysicsServices']==case['physicsServices'],'Performance case identity/tick scope differs')
        original=lookup[key];need(original['selectedPurePhysicsSamples']>=300 and original['overall']==50 and original['throbMode']==0 and original['menuOpen']is False,'Reference quiet scope differs')
        p=case['cpuMilliseconds']['physicsMs']['mean'];q=original['cpuPhases']['physics']['meanMs']
        raw=evidence.add(reference_path.parent/(original['garment'].lower()+'-state-'+str(original['physicsState'])+'.log')).read_text()
        windows=re.findall(r'CPU phase physics mean=([\d.]+)ms peak=([\d.]+)ms count=(\d+)',raw)
        need(any(abs(float(mean)-q)<1e-9 and int(count)==original['selectedPurePhysicsSamples']for mean,peak,count in windows),'Reference physics summary differs from actual source profile windows')
        comparisons.append(dict(state=key[0],garment=key[1],witcherPhysicsMeanMs=p,wolverinePhysicsMeanMs=q,physicsRatio=p/q if q else None,
            witcherSurfaceScopes=case['cpuMilliseconds']['surfaceMs'],witcherSurfaceServiceRatio=case['surfaceServiceRatio'],wolverineSurfaceScopes=original['cpuPhases'].get('gameplay surface'),
            witcherSDKWallInterval=case['sdkWallFrameIntervalMs'],wolverineNativePresentWeightedMeanMs=original['nativePresentWeightedMeanMs']))
    for image in port.get('archivedNativePhotos',[]):evidence.image(image)
    for case in reference['cases']:
        capture=case.get('capture');need(capture,'Reference native image missing');evidence.image(dict(path=capture,sha256=digest(capture)))
    return dict(reviewed=True,nativeFPSParityClaimed=False,absoluteFPSEqualityClaimed=False,cases=comparisons,
        limitations=['CPU physics scopes are compared separately from surface service frequency.','Wolverine and Witcher rendering engines, image resolution and timing scopes differ.','SDK wall/engine intervals are not native Present timestamp median/P95 or GPU timings.'])


def aggregate(args):
    from install_v2 import load_private_assets,payload_inventory,lod_body_inventory,LOD_MUTABLE_FILES
    evidence=Evidence();preview=Path(args.preview).resolve();game,preview_data=load_preview(preview)
    need(not preview_data.get('testOnlyLODMetadata'),'Restore production LOD metadata before final aggregation')
    evidence.add(preview);contract=read_json(ROOT/'v2/payload.json');private_path,private=load_private_assets(contract)
    evidence.add(ROOT/'v2/payload.json');evidence.add(private_path)
    payload=payload_inventory(preview_data['files'],contract,private);identities={r['path']:r['sha256']for r in payload}
    module=identities['bin/x64_dx12/malemod-native/malemod_witcher.dll'];worker=identities['bin/x64_dx12/malemod-native/canonical_worker.exe']
    paths={key:Path(getattr(args,key)).resolve()for key in('feature','matrices','campaign','witcher_performance','wolverine_performance')}
    reports={key:evidence.json(path)for key,path in paths.items()};pair=reports['matrices']
    reports['production']=evidence.json(pair['production']);reports['lod1']=evidence.json(pair['lod1'])
    native_imports=None
    def session_for(name,test_metadata=False):
        nonlocal native_imports
        report=reports[name];expected=report.get('runtimeSHA256',report.get('moduleSHA256'));need(expected==module,'Module SHA differs in '+name)
        session=evidence.json(report['receipt']);need(session.get('moduleSHA256')==module and session.get('closed')and(session.get('audioRestored')or session.get('audioSessionsGone'))and session.get('iterationWorldFilesRemoved'),'Exact closed native session incomplete in '+name)
        need(session.get('exitCode')in(None,0),'Native child failed in '+name+': '+str(session.get('exitCode')))
        need(session['observations']['noninteractiveWindowStation']and session['observations']['physicalInputUsed']is False
            and session.get('physicalDesktopSwitch')is False and session.get('injectorUsed')is False,'Native session used or did not certify isolation from the physical desktop')
        screenshot_gates(session,report['receipt'],evidence)
        prior=Path(session['nativePreview']);evidence.add(prior);_,description=load_preview(prior,session['nativePreviewSHA256'],False)
        observed={r['path']:r['sha256']for r in description['files']if r['path']in identities}
        excluded=set()
        if test_metadata:
            transaction=evidence.json(pair['lodTransaction']);old={r['path']:r for r in transaction['old']};new={r['path']:r for r in transaction['new']}
            expected=lod_body_inventory(old,new,contract)
            excluded=LOD_MUTABLE_FILES
            need(len(transaction.get('metadataChanges',[]))==2 and all(r['testDistances']==[0,.001]for r in transaction['metadataChanges']),'LOD journal lacks the measured distance-only change')
            for row in transaction['new']:need(observed[row['path']]==row['sha256'],'Native LOD payload differs from exact diagnostic journal')
        need(set(observed)==set(identities)and all(observed[p]==sha for p,sha in identities.items()if p not in excluded),'Payload identity differs in '+name)
        need(bool(description.get('testOnlyLODMetadata'))==test_metadata,'Wrong production/LOD diagnostic scope in '+name)
        report_path=Path(pair[name])if name in('production','lod1')else paths[name]
        registered=script_proof_gates(name,report_path,session,description,evidence,native_imports)
        if name=='feature':native_imports=registered
        need(observed['bin/x64_dx12/malemod-native/canonical_worker.exe']==worker,'Worker SHA differs in '+name)
        if 'workerSHA256'in report:need(report['workerSHA256']==worker,'Reported worker SHA differs in '+name)
        need(not report.get('runtimeFailures'),'Reported native failures in '+name)
        if'rendererFailures'in report:need(report['rendererFailures']==0,'Reported renderer failure in '+name)
        return session
    sessions={name:session_for(name,name=='lod1')for name in('feature','production','lod1','campaign','witcher_performance')}
    feature=feature_gates(reports['feature'],paths['feature'],evidence,sessions['feature']['observations'])
    need(pair.get('passed')and pair.get('productionMetadataRestored')and pair.get('combinedLODMask')==15 and pair.get('runtimeSHA256')==module and pair.get('workerSHA256')==worker,'Full same-module matrix pair or restoration incomplete')
    cases=evidence.json(ROOT/'v2/build/acceptance/cases.json')
    for name in('production','lod1'):matrix_gates(reports[name],Path(pair[name]),evidence,cases)
    transaction=evidence.json(pair['lodTransaction']);need(transaction.get('restored')and transaction.get('runtimeSHA256')==module,'LOD production restoration journal incomplete')
    for row in transaction['old']:need(identities.get(row['path'])==row['sha256'],'Restored production package differs from final payload')
    campaign=reports['campaign'];need(campaign.get('campaignPassed')and campaign.get('privateSaveObserved')and campaign.get('everyVisibleSDKTickServiced')and not campaign.get('runtimeFailures'),'Actual campaign actions/save/load incomplete')
    private_save_gates(sessions['campaign'],campaign,evidence)
    from campaign_observations import analyze
    campaign_rows=evidence.trace(paths['campaign'].parent/'frames.jsonl');frame_gates(campaign_rows)
    cps=[evidence.json(p)for p in paths['campaign'].parent.glob('v2-checkpoint-*.json')]
    need(analyze(campaign_rows,cps)['campaignActionsObserved'],'Campaign lifecycle does not independently prove walk/clothes/pause/load')
    isolation=evidence.json(campaign['isolation']);need(digest(campaign['isolation'])==campaign['isolationSHA256']and isolation.get('restored')and isolation.get('originalsVerified')==len(isolation['files']),'Ordinary saves were not restored and verified')
    for row in isolation['files']:
        save=Path(isolation['root'])/row['name'];need(save.resolve().parent==Path(isolation['root']).resolve()and digest(save)==row['sha256'],'Ordinary save changed after campaign restoration')
    for image in campaign['images']:evidence.image(image)
    performance=performance_comparison(reports['witcher_performance'],reports['wolverine_performance'],evidence,paths['witcher_performance'],paths['wolverine_performance'])
    final=sessions['campaign'];need(final.get('audioRestored')is True and final.get('nativePreviewSHA256')==digest(preview),'Final campaign receipt must certify normal audio restoration and exact final production preview')
    review_inputs={key:dict(path=str(path),sha256=digest(path))for key,path in paths.items()}
    explicit=all(getattr(args,key)for key in('attachment_visual_reviewed','clinical_visual_reviewed','campaign_visual_reviewed','performance_reviewed'))
    if args.review_artifact:
        review=evidence.json(args.review_artifact)
        explicit=(review.get('schema')=='malemod.witcher-v2-explicit-review/1'and review.get('accepted')is True and review.get('runtimeSHA256')==module and review.get('workerSHA256')==worker
            and review.get('reports')==review_inputs and review.get('reviewedImages')==[dict(path=p,sha256=s)for p,s in sorted(evidence.images.items())])
    need(explicit,'Explicit attachment/clinical/campaign image and performance review is required; no acceptance inferred')
    output=Path(args.output).resolve();need(output.is_relative_to((ROOT/'v2/build/acceptance').resolve()),'Choose an owned final aggregate path')
    if not getattr(args,'_verify_only',False):need(not output.exists(),'Preserve existing final aggregate')
    record=dict(schema='malemod.witcher-v2-aggregate-acceptance/1',receipt=reports['campaign']['receipt'],runtimeSHA256=module,workerSHA256=worker,
        nativePreview=str(preview),nativePreviewSHA256=digest(preview),payloadInventorySHA256=inventory_hash(payload),attachmentVisualAccepted=True,
        campaignPassed=True,featureParityPassed=True,clinicalPassed=True,privateAudioVerified=True,panelPassed=True,everyVisibleSDKTickServiced=True,
        allPhysicsRequestsCompleted=True,runtimeFailures=0,lodMask=15,performanceComparisonReviewed=True,performanceParityPassed=False,nativeFPSParityClaimed=False,
        featureEvidence=feature,performanceComparison=performance,review=dict(schema='malemod.witcher-v2-explicit-review/1',accepted=True,
            mode='hashed artifact'if args.review_artifact else'explicit CLI review',runtimeSHA256=module,workerSHA256=worker,reports=review_inputs,
            reviewedImages=[dict(path=p,sha256=s)for p,s in sorted(evidence.images.items())]),
        evidenceFiles=[dict(path=p,sha256=s)for p,s in sorted(evidence.files.items())])
    if getattr(args,'_verify_only',False):return record
    write_json(output,record);return output


def verify_aggregate(review,module,worker,preview_hash,payload):
    need(review.get('schema')=='malemod.witcher-v2-aggregate-acceptance/1','Installer requires the strict lower-evidence aggregate')
    need(review.get('runtimeSHA256')==module and review.get('workerSHA256')==worker and review.get('nativePreviewSHA256')==preview_hash,'Aggregate final binary/preview identity differs')
    need(review.get('payloadInventorySHA256')==inventory_hash(payload),'Aggregate exact payload inventory differs')
    need(review.get('performanceComparisonReviewed')and review.get('nativeFPSParityClaimed')is False,'Observed performance comparison/review missing')
    files=review.get('evidenceFiles',[]);need(bool(files)and len({row['path']for row in files})==len(files),'Aggregate lower evidence inventory is invalid')
    for row in files:need(digest(row['path'])==row['sha256'],'Lower evidence changed: '+row['path'])
    accepted=review.get('review',{});reports=accepted.get('reports',{})
    need(accepted.get('accepted')is True and set(reports)=={'feature','matrices','campaign','witcher_performance','wolverine_performance'},'Explicit reviewed lower-report inventory missing')
    for item in reports.values():need(digest(item['path'])==item['sha256'],'Reviewed report changed')
    from types import SimpleNamespace
    args=SimpleNamespace(**{name:Path(item['path'])for name,item in reports.items()},preview=Path(review['nativePreview']),
        output=ROOT/'v2/build/acceptance/verification-only.json',review_artifact=None,_verify_only=True,
        attachment_visual_reviewed=True,clinical_visual_reviewed=True,campaign_visual_reviewed=True,performance_reviewed=True)
    recomputed=aggregate(args)
    for key in('receipt','runtimeSHA256','workerSHA256','nativePreviewSHA256','payloadInventorySHA256','featureEvidence','performanceComparison'):
        need(recomputed[key]==review.get(key),'Aggregate lower evidence no longer reproduces '+key)
    need(recomputed['review']['reviewedImages']==accepted.get('reviewedImages'),'Explicitly reviewed native image inventory differs')
    recorded={row['path']:row['sha256']for row in files}
    need(all(recorded.get(row['path'])==row['sha256']for row in recomputed['evidenceFiles']),'Aggregate omitted required lower evidence')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in('preview','feature','matrices','campaign','witcher-performance','wolverine-performance','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--review-artifact',type=Path)
    for name in('attachment-visual-reviewed','clinical-visual-reviewed','campaign-visual-reviewed','performance-reviewed'):parser.add_argument('--'+name,action='store_true')
    print(aggregate(parser.parse_args()))
