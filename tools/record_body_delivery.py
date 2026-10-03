"""Verify the installed two-part waist/material/presentation delivery.

Raw gameplay traces and frames stay ignored. The committed certificate records
hashes, gates and measured throughput, without equating display with simulation.
"""
import argparse,json,statistics,subprocess
from pathlib import Path
from mod import ROOT,read_json,write_json,digest,settings,base_checkout,verify_package

REPORT=ROOT/'provenance/body-delivery.json'

def artifact(path):
    path=Path(path).absolute()
    return dict(path=path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path),sha256=digest(path))

def require(ok,message):
    if not ok:raise ValueError(message)

def verify(data):
    require(data['baseCommit']==base_checkout(settings())['commit'],'Committed Base pin differs')
    for item in data['sourceFiles']+data['verificationArtifacts']:
        p=Path(item['path']);p=p if p.is_absolute() else ROOT/p
        require(digest(p)==item['sha256'],'Delivery proof differs: '+str(p))
    installed=read_json(ROOT/'local/native-installation.json')
    require(installed['files']==data['installedFiles'],'Managed receipt differs')
    for item in installed['files']:
        require(digest(Path(installed['game'])/item['path'])==item['sha256'],'Installed file differs: '+item['path'])
    return data

def record(receipt):
    cfg=settings();pin=base_checkout(cfg)['commit'];receipt=Path(receipt).absolute()
    require(receipt.is_relative_to(ROOT/'build/probe'),'Expected a private session receipt')
    session=read_json(receipt);installed=read_json(ROOT/'local/native-installation.json')
    require(session['installationReceiptSHA256']==digest(ROOT/'local/native-installation.json'),'Session installation changed')
    require(session['moduleSHA256']==digest(Path(session['modulePath'])),'Session module changed')
    require(session['observations']['noninteractiveWindowStation'] and not session['observations']['physicalInputUsed'] and not session['physicalDesktopSwitch'] and not session['injectorUsed'],'Private session isolation failed')
    trace=Path(session['modulePath']).parent/('verification-%d.jsonl'%session['observations']['processID'])
    rows=[json.loads(line) for line in trace.read_text().splitlines()]
    require([r['stage'] for r in rows]==list(range(64)),'All 64 ordered game cases required')
    for r in rows:
        require(r['vertices']==43276 and r['bodyResourceMask']==3 and r['completedSequence']>=r['sequence'] and r['renderFlags']&853==853 and not r['renderFlags']&128 and not r['runtimeFlags']&(32|256),'Both completed body resources/runtime required')
    default=[2]+[50]*17
    for stage in range(56):
        values=default.copy()
        if stage in (1,2):values[0]=stage-1
        elif 3<=stage<=53:
            control=1+(stage-3)//3;part=(stage-3)%3
            values[control]=(0 if control in (2,4) else 1) if part==0 else 50 if part==1 else 100
        elif stage==54:values=[2]+[100]*17
        require(rows[stage]['controls']==values,'GPU controls differ at '+str(stage))
    require(rows[60]['controls']==[2,100]+[50]*16 and rows[60]['runtimeFlags']&8,'Paused edit missing')
    require(rows[63]['epoch']>rows[62]['epoch'] and rows[63]['controls']==default,'Actual save reload/fresh epoch missing')
    require(len({r['uploadFNV64'] for r in rows[:56]})>=40,'Sliders did not reach changed native uploads')
    moved=max(sum((a-b)**2 for a,b in zip(r['actorOrigin'],rows[0]['actorOrigin'])) for r in rows[:56])**.5
    require(moved>.5,'Actual game movement missing')
    audio=[json.loads(line) for line in (receipt.parent/'launcher.txt').read_text().splitlines()]
    require(any(r.get('verifiedMutedSessions',0)>0 for r in audio) and any(r.get('restoredAudioSessions',0)>0 for r in audio),'Private audio mute/restore not verified')
    require(any('exitCode' in r for r in audio),'Private session must be closed')
    require(not Path(session['temporaryContinueSource']).exists(),'Remove only the verified temporary driver after exit')
    selection=read_json(ROOT/'build/full-runtime/current-install.json');render=ROOT/selection['render'];binding=ROOT/selection['bindings'];profile=ROOT/selection['profile']
    manifest=read_json(render/'manifest.json');require(manifest['contractVersion']==4 and len(manifest['resources'])==2 and len(manifest['lods'])==4,'Two native body resources/LODs required')
    require(manifest['bindingsSHA256']==read_json(binding/'manifest.json')['artifactSHA256'],'Geometry/binding revision differs')
    package=ROOT/selection['bodyPackage'];verify_package(package)
    job=ROOT/'build/body-boundary/common-waist-6';material=read_json(job/'material-imports.json')
    require(material['nativeHandleVerified'] and {r['channel'] for r in material['materials']}=={'diffuse','normal','ambient'},'Verified complete atlas material handles required')
    for r in material['materials']:
        require(digest(job/'intake/characters/malemod/materials'/('body_'+r['channel']+'.xbm'))==r['nativeSHA256'],'Native material differs')
    compiler=ROOT/'build/probe/native-bootstrap-compile.json';compiled=read_json(compiler)
    require(not compiled['exitCode'] and not compiled['scriptImportsStubbed'] and digest(ROOT/compiled['artifact'])==compiled['artifactSHA256'],'Official native compiler proof differs')
    require(compiled['ownedSourceHashes']['local/malemod/render_bones.ws']==digest(render/'render_bones.ws'),'Actual joint sampler differs')
    body=ROOT/'build/full-runtime/body-render-test-final.txt';sdk=ROOT/'build/full-runtime/float-body-renderer-test.txt'
    require(all(s in body.read_text() for s in ['39 full source cases','51 exact waist positions','torso displacement','pause/control/epoch snap']),'Boundary/recruitment/presentation tests missing')
    require('static LOD slices' in sdk.read_text(),'Actual D3D12 slice/readback gate missing')
    baseline=read_json(ROOT/'local/installation.json')
    require(all(digest(Path(baseline['target'])/r['path'])==r['sha256'] for r in baseline['files']),'.31 attachment/rig baseline changed')
    displays=[];numerical=[]
    for a,b in zip(rows[:55],rows[1:56]):
        dt=b['poseSeconds']-a['poseSeconds']
        if dt>0 and a['epoch']==b['epoch']:
            displays.append((b['displayPublications']-a['displayPublications'])/dt)
            numerical.append((b['sequence']-a['sequence'])/dt)
    require(statistics.median(displays)>35 and statistics.median(displays)>statistics.median(numerical)*1.5,'Intermediate completed presentation cadence missing')
    sources=[p for directory in ['native','tools','probes/native'] for p in (ROOT/directory).iterdir() if p.suffix in {'.cpp','.hpp','.py','.ws','.txt','.def'}]
    sources.append(ROOT/'dependencies/base.lock.json')
    proofs=[receipt,trace,receipt.parent/'launcher.txt',compiler,ROOT/compiled['artifact'],render/'manifest.json',binding/'manifest.json',profile/'manifest.json',package/'build-manifest.json',job/'manifest.json',job/'material-imports.json',body,sdk]
    result=dict(contractVersion=1,baseCommit=pin,sourceFiles=[artifact(p) for p in sorted(sources)],verificationArtifacts=[artifact(p) for p in proofs],installedFiles=installed['files'],
      materials=dict(diffuse='Lossless full Geralt/source atlas, source module UVs and explicit FBX V conversion',normal='Full normal atlas with observed source repeat 16 baked',ambient='Stock Geralt AO plus explicit neutral anatomy AO; specular is not relabeled',officialImportsAndBothResourceHandlesVerified=True,frameInspection='Default and maximum SDK frames inspected; no pixel-perfect Wolverine lighting claim',stateDependentDiffuseSwitch=False),
      boundary=dict(canonicalSamples=51,separateResources=2,lodsPerResource=2,vertices=43276,originalEdgeAttachmentDonorsPreserved=True,positionsAcrossAllPartsAndLODsExact=True,namedWeightBytesAcrossAllPartsAndLODsExact=True,sharedShadingPerLOD=True,protectedOtherBoundaries=True,upperInteriorRecruitedAtOverallMaximum=True,completeGPUResourceMask=3,actualFarLODTransitionObserved=False),
      overlay=dict(doubleBufferedPaint=True,eraseSuppressed=True,paintOnlyOnControlOrVisibilityChange=True,SDKPanelRenderAndNavigationVerified=True,currentPhysicalF6AndPerceptualFlickerTest=False),
      physics=dict(sourceWorkerUnchanged=True,constraintsOrContactsReduced=False,materialFramePresentation=True,rigidCapAndLobeRotationPreserved=True,displayPublicationsPerSecondMedian=statistics.median(displays),completeNumericalSurfacesPerSecondMedian=statistics.median(numerical),displayCadenceIsNotNumericalSolveRate=True,gameFPSBenchmark=False),
      gameVerification=dict(orderedCases=64,allControlsReachGPU=True,combinedMaximum=True,movementDistance=moved,pauseEditResume=True,actualSaveReloadFreshEpoch=True,runtimeFaults=0,rendererFaults=0,privateAudioMuteAndRestore=True,hostFocusAndInputUsed=False,saveWritesByDriver=False),
      wolverineModified=False,deferred=['clinical sequences','fluid physics','sounds and idle chatter'],
      limits=['Existing measured Geralt capsule contacts remain an approximation','Ray tracing and exclusive fullscreen require separate runtime validation','Current isolated test does not synthesize physical F6 input or prove absence of perceptual flicker','Intermediate presentation raises displayed motion cadence without raising full numerical surface throughput','Source specular/SSS and state-dependent diffuse are not pixel-identical native Geralt material equivalents'])
    return verify(result)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--receipt',type=Path);p.add_argument('--write',action='store_true');a=p.parse_args()
    data=record(a.receipt) if a.receipt else verify(read_json(REPORT))
    if a.write:write_json(REPORT,data)
    print('Verified two-part installed delivery:',data['gameVerification']['orderedCases'],'game cases; median display',round(data['physics']['displayPublicationsPerSecondMedian'],2),'Hz; numerical',round(data['physics']['completeNumericalSurfacesPerSecondMedian'],2),'Hz')
