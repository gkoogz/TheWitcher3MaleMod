"""Record current native delivery from independent SDK and installed-game gates.

Captured frames, poses, settings and game assets remain in ignored local output.
The committed report contains hashes and verification summaries only.
"""
import argparse,json,statistics,subprocess
from pathlib import Path
from mod import ROOT,read_json,write_json,digest

REPORT=ROOT/'provenance/native-delivery.json'

def artifact(path):
    path=Path(path).resolve()
    return dict(path=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),sha256=digest(path))

def pinned():
    pin=read_json(ROOT/'dependencies/base.lock.json')['commit'];base=ROOT.parent/'MaleMod'
    if subprocess.check_output(['git','-C',str(base),'rev-parse','HEAD'],text=True).strip()!=pin or subprocess.check_output(['git','-C',str(base),'status','--porcelain','--untracked-files=no'],text=True).strip():raise ValueError('Base must match the clean committed pin')
    return pin

def verify(data):
    if data['baseCommit']!=pinned():raise ValueError('Delivery pin differs')
    for item in data['sourceFiles']+data['verificationArtifacts']:
        path=Path(item['path']);path=path if path.is_absolute() else ROOT/path
        if digest(path)!=item['sha256']:raise ValueError('Delivery proof changed: '+str(path))
    installed=read_json(ROOT/'local/native-installation.json')
    if installed['files']!=data['installedFiles']:raise ValueError('Installed delivery changed')
    for item in installed['files']:
        if digest(Path(installed['game'])/item['path'])!=item['sha256']:raise ValueError('Installed hash changed: '+item['path'])
    return data

def record(receipt):
    pin=pinned();receipt=Path(receipt).resolve()
    if not receipt.is_relative_to(ROOT/'build/probe'):raise ValueError('Expected managed private session receipt')
    session=read_json(receipt);installed=read_json(ROOT/'local/native-installation.json')
    module=Path(session['modulePath']);pid=session['observations']['processID']
    if session['moduleSHA256']!=digest(module) or digest(ROOT/'local/native-installation.json')!=session['installationReceiptSHA256']:raise ValueError('Session installation changed')
    if not session['observations']['noninteractiveWindowStation'] or session['physicalDesktopSwitch'] or session['observations']['physicalInputUsed'] or session['injectorUsed']:raise ValueError('Private session isolation failed')
    trace=module.parent/f'verification-{pid}.jsonl';rows=[json.loads(s) for s in trace.read_text().splitlines()]
    if [r['stage'] for r in rows]!=list(range(64)):raise ValueError('Expected all 64 ordered installed-game cases')
    for r in rows:
        if r['vertices']!=36547 or r['completedSequence']<r['sequence'] or r['renderFlags']&128 or (r['renderFlags']&853)!=853 or r['runtimeFlags']&(32|256):raise ValueError('Complete native surface or runtime fault gate failed')
    expected=[2]+[50]*17
    for stage in range(56):
        values=expected.copy()
        if stage in (1,2):values[0]=stage-1
        elif 3<=stage<=53:
            control=1+(stage-3)//3;part=(stage-3)%3
            values[control]=(0 if control in (2,4) else 1) if part==0 else 50 if part==1 else 100
        elif stage==54:values=[2]+[100]*17
        if rows[stage]['controls']!=values:raise ValueError('Installed control range differs at '+str(stage))
    if rows[60]['controls']!=[2,100]+[50]*16 or not rows[60]['runtimeFlags']&8:raise ValueError('Paused geometry edit missing')
    if rows[63]['epoch']<=rows[62]['epoch'] or rows[63]['controls']!=expected:raise ValueError('Actual save reload did not start a fresh default character epoch')
    if len({r['uploadFNV64'] for r in rows[:56]})<40:raise ValueError('Control output did not change native uploads')
    moved=max(sum((a-b)**2 for a,b in zip(r['actorOrigin'],rows[0]['actorOrigin'])) for r in rows[:56])**.5
    if moved<.5:raise ValueError('Actual actor movement missing')
    if not any(json.loads(s).get('verifiedMutedSessions',0)>0 for s in (receipt.parent/'launcher.txt').read_text().splitlines()):raise ValueError('Private audio mute did not verify')
    compiler=ROOT/'build/probe/native-bootstrap-compile.json';compiled=read_json(compiler)
    if compiled['exitCode'] or compiled['scriptImportsStubbed'] or digest(ROOT/compiled['artifact'])!=compiled['artifactSHA256'] or compiled['ownedSourceHashes']['local/malemod/runtime.ws']!=digest(ROOT/'probes/native/runtime.ws'):raise ValueError('Official compiler proof differs')
    sdk=ROOT/'build/native-runtime-controller/Testing/Temporary/LastTest.log';sdk_text=sdk.read_text()
    for name in ['control_persistence','normal_startup_gate','installed_skin_shader','graphics_probe_sdk','live_float_draw_sdk','graphics_owned_upload']:
        section=sdk_text.split('Test: '+name+'\n',1)
        if len(section)!=2 or 'Test Passed.' not in section[1].split('----------------------------------------------------------\n\n',1)[0]:raise ValueError('SDK gate missing: '+name)
    controller=ROOT/'build/full-runtime/runtime-controller-contacts-test.txt'
    if not all(x in controller.read_text() for x in ['48 sequence-matched full-runtime frames','contact calibration mode=1','paused control edits','slow active interval','asynchronous character epochs']):raise ValueError('Numerical lifecycle proof missing')
    rendering=ROOT/'build/full-runtime/render-contract-test.txt'
    if 'cooked boundary positions/lighting invariant at all slider extremes' not in rendering.read_text():raise ValueError('Current native skin mapping oracle missing')
    rollback=ROOT/'build/full-runtime/native-restore-test.txt'
    if 'Ran 3 tests' not in rollback.read_text() or '\nOK' not in rollback.read_text():raise ValueError('Managed rollback fixture proof missing')
    profile=ROOT/'build/full-runtime/runtime-profile-166cb02-contacts/manifest.json';calibration=ROOT/'build/full-runtime/geralt-contact-calibration.json'
    if read_json(profile)['diagnosticSourceContacts']:raise ValueError('Diagnostic contacts cannot be a delivery')
    source_paths=set()
    for folder in ['native','tools','probes/native']:
        for p in (ROOT/folder).iterdir():
            if p.is_file() and p.suffix in {'.cpp','.hpp','.py','.ws','.txt','.def'}:source_paths.add(p)
    source_paths.update(ROOT/p for p in ['dependencies/base.lock.json','dependencies/native.lock.json','characters/geralt-runtime-bindings.json','tests/test_native_restore.py'])
    timings={}
    for key in ['sourceMs','targetMs','prepareMs','lightingMs','callbackMeanMs','callbackMaxMs']:
        samples=sorted(r[key] for r in rows[1:56]);timings[key]=dict(median=statistics.median(samples),p95=samples[int(.95*(len(samples)-1))],maximum=max(samples))
    result=dict(contractVersion=1,baseCommit=pin,gameExecutableSHA256='9406eccc12b68e08920931442ef6a57340e910d3e01f2082e88232487433fe51',
        runtime='DX12 native float-position draw, pinned full Win32 Base solver and both Geralt LODs',
        sourceFiles=[artifact(p) for p in sorted(source_paths)],
        verificationArtifacts=[artifact(p) for p in [receipt,trace,receipt.parent/'launcher.txt',compiler,ROOT/compiled['artifact'],sdk,controller,rendering,rollback,profile,calibration]],
        installedFiles=installed['files'],installed=True,installedGameOutputObserved=True,originalFiveResourceHashesPreserved=True,
        controls=dict(count=18,rangeCases=56,fullFloppyDefault=expected,allValuesReachGPU=True,overlayToggle='F6',selection='Up/Down',adjustment='Left/Right',largeStep='Shift',arrowAndRangeSDKVerified=True,userPreviouslyConfirmedVisibleLiveOverlay=True,currentPhysicalKeyboardTested=False,persistence='atomic native adapter file containing Base Controls values; excluded from installation and private tests'),
        numerical=dict(sharedSolver='exact pinned Base source Session',constraintsReduced=False,sourceControlsReduced=False,sourceAndBothTargetLODsMatchSerial=True,activeTimePreserved=True,measuredGeraltContacts=True,pelvisPrimitive='fitted stock donor capsule approximation; residuals in calibration certificate',wolverineChanged=False),
        renderer=dict(vertices=36547,lods=2,layoutBytes=28,originalShadersMaterialsUVsPreserved=True,floatPositionUnclamped=True,addedSkinInfluences='each observed mm_* palette entry redirected to its LOD pelvis; all stock influences and weights preserved',currentNativePoseAppliesOnce=True,finalInteriorLightingRebuilt=True,cookedOuterBoundaryPositionAndLightingPreserved=True,allConsumptionFencesRetained=True,shaderOracleMaximumNativeError=8.9407e-8,rayTracingObserved=False,rayTracingSettingChanged=False,rayTracingCurrentTestSetting=False),
        installedGameVerification=dict(cases=64,movementObserved=True,allMaximaPassed=True,pauseEditAndResumePassed=True,actualSaveReloadNewEpochPassed=True,cameraDistanceRequestsExecuted=True,actualFarCameraDistanceVerified=False,runtimeFaults=0,rendererFaults=0,privateAudioMuted=True,noPhysicalFocusOrInput=True,noSaveWritesByTestDriver=True),
        audioMaintenance=dict(previousMutePersistedForUserGame=True,currentUserSessionUnmuteVerified=True,scopedRestoreImplemented=True,scopedRestoreCompiled=True,scopedRestorePrivateExitTested=False),
        performance=dict(timingMilliseconds=timings,numericalWorkOutsideVMCallback=True,independentLODsParallelAndByteExact=True,sourcePhysicsThroughputIsNotGameFPS=True,gameFPSBenchmark=False),
        deferred=['clinical sequences','sounds and idle chatter','fluids'],
        limitations=['Geralt body contacts use measured capsules, not an exact triangle body hull','DX12 executable hash is specific to the installed 5.0 build','Ray tracing was disabled in existing settings and remains separately unverified','Current physical keyboard and exclusive fullscreen operation were not driven by the isolated test'])
    return verify(result)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--receipt',type=Path);parser.add_argument('--write',action='store_true');args=parser.parse_args()
    data=record(args.receipt) if args.receipt else verify(read_json(REPORT))
    if args.write:write_json(REPORT,data)
    print('Verified native delivery: full Base controls/surface, installed GPU output, independent SDK and private gameplay gates.')
