"""Refresh the full-runtime checkpoint from specific verified local artifacts.

Never traverses depot junctions, imports geometry into Git, installs or launches.
"""
import argparse,json,subprocess
from pathlib import Path
from mod import ROOT,digest,read_json,write_json


def record():
    base=ROOT.parent/'MaleMod';pin=read_json(ROOT/'dependencies/base.lock.json')['commit']
    head=subprocess.check_output(['git','-C',str(base),'rev-parse','HEAD'],text=True).strip()
    dirty=subprocess.check_output(['git','-C',str(base),'status','--porcelain','--untracked-files=no'],text=True).strip()
    if head!=pin or dirty:raise ValueError('Base must match a clean committed pin')
    target=ROOT/'provenance/full-runtime.json';out=read_json(target)
    old_pin=out['baseCommit'];out['baseCommit']=pin
    out.setdefault('targetCollarVerificationBaseCommit',old_pin)
    files={item['path'] for item in out['files']}
    files.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'native').iterdir() if p.suffix in {'.hpp','.cpp','.txt'})
    files.update(['tools/inspect_packed_mesh.py','tools/packed_mesh_format.py','tools/read_native_probe.py','tools/record_full_runtime.py',
        'tools/run_native_probe.py','tools/prepare_graphics_fingerprints.py','tools/prepare_pose_replay.py','tools/inspect_graphics_hooks.py','tools/prepare_skin_contract.py','probes/native/pose.ws'])
    out['files']=[dict(path=p,sha256=digest(ROOT/p)) for p in sorted(files)]
    binding_path=ROOT/('build/full-runtime/geralt-bindings-'+pin[:7])
    binding=read_json(binding_path/'manifest.json')
    if binding['baseCommit']!=pin or digest(binding_path/'geralt.bindings')!=binding['artifactSHA256']:
        raise ValueError('Binding artifact does not match current pin/proof')
    out['targetBindingArtifact']=binding
    report=ROOT/'build/full-runtime/target-metric-46ac00f/verification.json'
    checks=read_json(report)
    if len(checks['cases'])!=162 or any(c['protectedBoundaryError']!=0 or c['seamError']>1e-10 or c['maximumNativePositionError']>1e-9 for c in checks['cases']):
        raise ValueError('Complete target fixture gate failed')
    out['completeTargetCompositionVerification']=checks
    out['targetCompositionAdoptionNote']='162 fixtures verified Base 46ac00f; 58876e2 changes exact wire packing. Base 4a808e3 adds the exact motion filter and affine calibration without changing surface/collar arithmetic. The current-pin 240 observed-pose replay is separately verified.'
    pipeline=ROOT/'build/full-runtime/pipeline-58876e2.jsonl'
    trace=json.loads(pipeline.read_text().splitlines()[-1])
    if not trace['passed'] or trace['frames']!=180 or trace['exactFreshPlanComparisons']!=48:raise ValueError('Current pipeline coverage failed')
    out['changingPipelineVerification']=dict(baseCommit='58876e24136d3d2c941fa144aa4c7651c98cbb75',reportSHA256=digest(pipeline),**trace)
    service=ROOT/'build/full-runtime/service-58876e2.txt'
    if not service.read_text().startswith('PASS: 48 ordered asynchronous frames'):raise ValueError('Service gate failed')
    out['asynchronousServiceVerification']=dict(baseCommit='58876e24136d3d2c941fa144aa4c7651c98cbb75',frames=48,sourceWireExact=True,bothTargetLODsExact=True,backpressureExercised=True,
        reportSHA256=digest(service),executableSHA256=digest(ROOT/'build/native-observer-v2/Release/surface_service_test.exe'),engineIntegrated=False)
    inspected=ROOT/'build/full-runtime/packed-neutral-verified-4/inspection.json';mesh=read_json(inspected)
    if digest(ROOT/'tools/packed_mesh_format.py')!=mesh['binaryReaderSHA256'] or digest(ROOT/'tools/inspect_packed_mesh.py')!=mesh['recipeSHA256']:raise ValueError('Packed inspection recipes changed')
    if not mesh['exactQuantizationConstantsVerified'] or any(not all(l[k] for k in ['mappingVerified','namedSkinWeightsVerified','exactUVTruncationVerified','nativeTopologyMatchesAuthored','inverseBindVerified']) for l in mesh['lods']):
        raise ValueError('Packed mesh gate failed')
    # Commit verification metadata, not raw native matrices, buffers or captures.
    out['packedMeshVerification']={k:mesh[k] for k in ['meshSHA256','bufferSHA256','dumpSHA256','fbxSHA256','recipeSHA256','binaryReaderSHA256','cookedVersion','exactQuantizationConstantsVerified','nativeVertexOutput','observedGameplay']}
    out['packedMeshVerification']['reportSHA256']=digest(inspected)
    out['packedMeshVerification']['activeInstalledResourceVerified']=False
    out['packedMeshVerification']['lods']=[{k:v for k,v in lod.items() if k not in ['chunkHex','streamOffsets']} for lod in mesh['lods']]
    skin_dir=ROOT/'build/full-runtime/skin-sdk-contract';skin=read_json(skin_dir/'manifest.json')
    for field,path in [('recipeSHA256','tools/prepare_skin_contract.py'),('conversionSHA256','native/skin_output.hpp'),('oracleSHA256','native/skin_sdk_test.cpp')]:
        if digest(ROOT/path)!=skin[field]:raise ValueError('SDK conversion proof source changed: '+path)
    if digest(skin_dir/'owned.skin')!=skin['packetSHA256'] or any(digest(Path(f['path']))!=f['sha256'] for f in skin['sdkFiles']):raise ValueError('Installed shader/packet proof input changed')
    skin_test=ROOT/'build/native-skin-sdk/Testing/Temporary/LastTest.log'
    if not all(s in skin_test.read_text() for s in ['PASS installed SDK skin shader: 36547 vertices x 3 poses; 28150 nonunit weight sums;','Test Passed.']):raise ValueError('Actual installed shader oracle did not pass')
    out['installedShaderConversionVerification']=dict(**skin,testReportSHA256=digest(skin_test),
        executableSHA256=digest(ROOT/'build/native-skin-sdk/Release/skin_sdk_test.exe'),
        oracleUsesInstalledShaderFunctions=True,threeAxisSyntheticPoses=3,nonuniformScaling=True,
        normalizedByteWeightsVerified=True,inverseBlendedSkinVerified=True,unclampedFloatPositionVerified=True,
        liveGPUPaletteLayoutVerified=False,engineOutputConnected=False)
    compile_proof=ROOT/'build/probe/state-machine-verified.json';compiled=read_json(compile_proof)
    if compiled['exitCode'] or not compiled['artifactSHA256'] or compiled['scriptImportsStubbed']:raise ValueError('Compiler gate failed')
    out['stateMachineCorrectionVerification']=dict(reportSHA256=digest(compile_proof),**{k:compiled[k] for k in ['ownedSourceHashes','compilerSHA256','profileSHA256','artifactSHA256','sdkModified','gameModified','scriptImportsStubbed','observedGameInvocation']})
    receipt_path=ROOT/'build/probe/native-live-20261002-072534/receipt.json';receipt=read_json(receipt_path)
    status=read_json(receipt_path.parent/'status.json')
    if not all(status[k] for k in ['scriptInvocationObserved','typedArgumentsObserved','typedRoundtripObserved']) or status['typedProbeFailed'] or status['registrationFailed']:
        raise ValueError('Latest typed probe did not pass')
    out['latestTypedProbe']=dict(receiptSHA256=digest(receipt_path),statusSHA256=digest(receipt_path.parent/'status.json'),
        moduleSHA256=receipt['moduleSHA256'],scriptSHA256=receipt['scriptSHA256'],**status)
    out['latestTypedProbe']['lateInvocationAfterLauncherTimeout']=False
    out['latestTypedProbe']['controlsDriveSolver']=False
    out['latestTypedProbe']['addonRemoved']=receipt['addonRemoved']
    baseline=read_json(ROOT/'local/installation.json')
    if not all(digest(Path(baseline['target'])/f['path'])==f['sha256'] for f in baseline['files']):raise ValueError('Installed baseline changed')
    out['installedBaseline']['allFiveHashesPreserved']=len(baseline['files'])==5
    sdk=ROOT/'build/native-observer-v6/Testing/Temporary/LastTest.log'
    if not all(s in sdk.read_text() for s in ['SDK copy/direct/bundle observer flags: 3087','SDK copy/direct/bundle observer flags: 7695','Test Passed.']):raise ValueError('SDK observer gate failed')
    out['candidateObserver']=dict(moduleSHA256=digest(ROOT/'build/native-observer-v6/Release/malemod_witcher.dll'),
        sdkTestReportSHA256=digest(sdk),sdkTestExecutableSHA256=digest(ROOT/'build/native-observer-v6/Release/graphics_probe_test.exe'),
        multiImplementationDeviceAndListHooks=True,returnedGraphicsInterfaceCoverage=True,supportedGraphicsVersionCoverage=True,
        SDKCopyDirectBundleSmokeTestPassed=True,commandListResetSmokeTestPassed=True,
        ownedDrawMetadataAndResetTestPassed=True,ownedUploadFingerprintTestPassed=True,observedInGame=False,vertexWrites=False)
    pose_proof=ROOT/'build/full-runtime/pose-replay-4a808e3/manifest.json';pose=read_json(pose_proof)
    replay=pose_proof.parent/'replay.jsonl';result=json.loads(replay.read_text().splitlines()[-1])
    if pose['baseCommit']!=pin or result['frames']!=240 or not result['passed'] or result['contactRoundTripErrorNative']>1e-6:
        raise ValueError('Observed-pose numerical replay gate failed')
    out['poseInputReplayVerification']=dict(manifest=pose,reportSHA256=digest(replay),
        executableSHA256=digest(ROOT/'build/native-observer-v4/Release/pose_replay_test.exe'),
        workerSHA256=digest(ROOT/'build/native-x86-motion/Release/surface_worker.exe'),**result)
    graphics=ROOT/receipt['modulePath'];graphics=graphics.parent/f"graphics-probe-{receipt['observations']['processID']}.jsonl"
    rows=[json.loads(s) for s in graphics.read_text().splitlines()]
    hits=sorted({s['label'] for s in rows if s['event']=='ownedBufferFingerprint'})
    if not hits or not status.get('poseSamplingObserved'):raise ValueError('Live ownership/pose observation missing')
    live_pose=graphics.parent/f"pose-probe-{receipt['observations']['processID']}.jsonl"
    pose_rows=[json.loads(s) for s in live_pose.read_text().splitlines()]
    if len(pose_rows)!=240 or any(s['paused'] for s in pose_rows):raise ValueError('Latest unpaused pose coverage is incomplete')
    out['liveReadOnlyObserver']=dict(receiptSHA256=digest(receipt_path),graphicsReportSHA256=digest(graphics),moduleSHA256=receipt['moduleSHA256'],
        fingerprintPacketSHA256=receipt['fingerprintPacketSHA256'],matchedOwnedUploadLabels=hits,
        commandSignatureRecordStrides=sorted({s['recordStride'] for s in rows if s['event']=='commandSignatureCreated'}),
        poseReportSHA256=digest(live_pose),poseSamples=len(pose_rows),unpausedPoseSpanSeconds=pose_rows[-1]['seconds']-pose_rows[0]['seconds'],
        indexedDrawObserved=bool(status['graphicsFlags']&16),commandListResetObserved=bool(status['graphicsFlags']&2048),
        distinctListMethodImplementations=len({s['vertexMethod'] for s in rows if s['event']=='listImplementation'}),
        visibleMeshDrawOwnershipVerified=False,
        vertexWrites=False,observedGameplayOutput=False)
    out['fullNativeVertexOutput']=False;out['overlayImplemented']=False;out['fullRuntimeInstalled']=False;out['fullRuntimeObservedGameplay']=False
    return out


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write',action='store_true');args=parser.parse_args()
    data=record()
    if args.write:write_json(ROOT/'provenance/full-runtime.json',data)
    else:
        if read_json(ROOT/'provenance/full-runtime.json')!=data:raise SystemExit('Checkpoint differs; review and use --write')
    print('Full-runtime checkpoint verified; installation and gameplay remain incomplete.')
