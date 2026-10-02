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
    files.update(['tools/inspect_packed_mesh.py','tools/packed_mesh_format.py','tools/read_native_probe.py','tools/record_full_runtime.py'])
    out['files']=[dict(path=p,sha256=digest(ROOT/p)) for p in sorted(files)]
    binding=read_json(ROOT/'build/full-runtime/geralt-bindings-58876e2/manifest.json')
    if binding['baseCommit']!=pin or digest(ROOT/'build/full-runtime/geralt-bindings-58876e2/geralt.bindings')!=binding['artifactSHA256']:
        raise ValueError('Binding artifact does not match current pin/proof')
    out['targetBindingArtifact']=binding
    report=ROOT/'build/full-runtime/target-metric-46ac00f/verification.json'
    checks=read_json(report)
    if len(checks['cases'])!=162 or any(c['protectedBoundaryError']!=0 or c['seamError']>1e-10 or c['maximumNativePositionError']>1e-9 for c in checks['cases']):
        raise ValueError('Complete target fixture gate failed')
    out['completeTargetCompositionVerification']=checks
    out['targetCompositionAdoptionNote']='162 fixtures verified Base 46ac00f; 58876e2 changes only exact wire packing. The current-pin 180-frame pipeline is separately verified.'
    pipeline=ROOT/'build/full-runtime/pipeline-58876e2.jsonl'
    trace=json.loads(pipeline.read_text().splitlines()[-1])
    if not trace['passed'] or trace['frames']!=180 or trace['exactFreshPlanComparisons']!=48:raise ValueError('Current pipeline coverage failed')
    out['changingPipelineVerification']=dict(baseCommit=pin,reportSHA256=digest(pipeline),**trace)
    service=ROOT/'build/full-runtime/service-58876e2.txt'
    if not service.read_text().startswith('PASS: 48 ordered asynchronous frames'):raise ValueError('Service gate failed')
    out['asynchronousServiceVerification']=dict(baseCommit=pin,frames=48,sourceWireExact=True,bothTargetLODsExact=True,backpressureExercised=True,
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
    compile_proof=ROOT/'build/probe/state-machine-verified.json';compiled=read_json(compile_proof)
    if compiled['exitCode'] or not compiled['artifactSHA256'] or compiled['scriptImportsStubbed']:raise ValueError('Compiler gate failed')
    out['stateMachineCorrectionVerification']=dict(reportSHA256=digest(compile_proof),**{k:compiled[k] for k in ['ownedSourceHashes','compilerSHA256','profileSHA256','artifactSHA256','sdkModified','gameModified','scriptImportsStubbed','observedGameInvocation']})
    receipt_path=ROOT/'build/probe/native-live-20261002-053312/receipt.json';receipt=read_json(receipt_path)
    status=read_json(receipt_path.parent/'status.json')
    if not all(status[k] for k in ['scriptInvocationObserved','typedArgumentsObserved','typedRoundtripObserved']) or status['typedProbeFailed'] or status['registrationFailed']:
        raise ValueError('Latest typed probe did not pass')
    out['latestTypedProbe']=dict(receiptSHA256=digest(receipt_path),statusSHA256=digest(receipt_path.parent/'status.json'),
        moduleSHA256=receipt['moduleSHA256'],scriptSHA256=receipt['scriptSHA256'],**status)
    out['latestTypedProbe']['lateInvocationAfterLauncherTimeout']=True
    out['latestTypedProbe']['controlsDriveSolver']=False
    out['latestTypedProbe']['addonRemoved']=receipt['addonRemoved']
    baseline=read_json(ROOT/'local/installation.json')
    if not all(digest(Path(baseline['target'])/f['path'])==f['sha256'] for f in baseline['files']):raise ValueError('Installed baseline changed')
    out['installedBaseline']['allFiveHashesPreserved']=len(baseline['files'])==5
    sdk=ROOT/'build/native-observer-v2/Testing/Temporary/LastTest.log'
    if 'SDK copy/direct observer flags: 15' not in sdk.read_text() or 'Test Passed.' not in sdk.read_text():raise ValueError('SDK observer gate failed')
    out['candidateObserver']=dict(moduleSHA256=digest(ROOT/'build/native-observer-v2/Release/malemod_witcher.dll'),
        sdkTestReportSHA256=digest(sdk),sdkTestExecutableSHA256=digest(ROOT/'build/native-observer-v2/Release/graphics_probe_test.exe'),
        multiImplementationHooks=True,SDKCopyDirectSmokeTestPassed=True,observedInGame=False,vertexWrites=False)
    out['fullNativeVertexOutput']=False;out['overlayImplemented']=False;out['fullRuntimeInstalled']=False;out['fullRuntimeObservedGameplay']=False
    return out


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write',action='store_true');args=parser.parse_args()
    data=record()
    if args.write:write_json(ROOT/'provenance/full-runtime.json',data)
    else:
        if read_json(ROOT/'provenance/full-runtime.json')!=data:raise SystemExit('Checkpoint differs; review and use --write')
    print('Full-runtime checkpoint verified; installation and gameplay remain incomplete.')
