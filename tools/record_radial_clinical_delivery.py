"""Record installed radial/clinical delivery; retain raw captures outside Git."""
import argparse, json, statistics
from pathlib import Path
from mod import ROOT, settings, base_checkout, read_json, write_json, digest
from record_body_delivery import artifact, require, verify

REPORT = ROOT/'provenance/radial-clinical-delivery.json'

def record(receipt):
    receipt = Path(receipt).resolve()
    require(receipt.is_relative_to(ROOT/'build/probe'), 'Expected owned private receipt')
    session = read_json(receipt)
    installed = read_json(ROOT/'local/native-installation.json')
    pin = base_checkout(settings())['commit']
    require(session['closed'] and session['audioRestored'], 'Private process/audio not restored')
    require(session['moduleSHA256'] == digest(Path(session['modulePath'])), 'Observed DLL differs')
    require(session['installationReceiptSHA256'] == digest(ROOT/'local/native-installation.json'), 'Observed installation differs')
    require(session['observations']['noninteractiveWindowStation'] and not session['observations']['physicalInputUsed'] and not session['physicalDesktopSwitch'] and not session['injectorUsed'], 'Private station not verified')
    require(not Path(session['temporaryContinueSource']).exists(), 'Temporary Continue source remains')
    pid = session['observations']['processID']
    trace = receipt.parent/'verification.jsonl'
    source = Path(installed['game'])/'bin/x64_dx12/malemod-native'/f'verification-{pid}.jsonl'
    if not trace.exists(): trace.write_bytes(source.read_bytes())
    rows = [json.loads(line) for line in trace.read_text().splitlines()]
    rows = [r for r in rows if 64 <= r['stage'] <= 83]
    require([r['stage'] for r in rows] == list(range(64,84)), 'Clinical/ramp ordered cases incomplete')
    require(all(r['renderFlags'] == 853 and r['bodyResourceMask'] == 3 and not r['runtimeFlags'] & (32|256|512) for r in rows), 'Body runtime/render fault')
    require(all(r['runtimeFlags'] == 135 for r in rows), 'Full source runtime output incomplete')
    require(all(not r['fluidRenderFlags'] & 128 for r in rows), 'Fluid renderer fault')
    require({r['clinicalMode'] for r in rows} == {0,1,2,3}, 'Ambient modes incomplete')
    require(rows[8]['clinicalCueMask'] == 3, 'Both dialogue phases not delivered by sequence completion')
    require(max(r['liquidIndices'] for r in rows)>0 and max(r['depositIndices'] for r in rows)>0, 'No liquid/deposit geometry')
    require(max(r['sceneHits'] for r in rows)>0 and max(r['fluidRenderFlags'] & 28 for r in rows)==28, 'Actual scene/render integration missing')
    require(rows[8]['clinicalTime'] == 20 and not rows[8]['clinicalActive'], 'Sequence did not complete at source duration')
    require(rows[8]['sceneHits'] > 0 and rows[8]['depositIndices'] > 0 and rows[8]['fluidRenderFlags'] & 28 == 28, 'Completed sequence lacks actual scene deposits and native draws')
    require(rows[9]['clinicalActive'] and 0 < rows[9]['clinicalTime'] < 20, 'Second sequence did not restart')
    cancelled = rows[10]
    require(not cancelled['clinicalActive'] and cancelled['clinicalTime'] == 0 and cancelled['liquidIndices'] == 0 and cancelled['depositIndices'] == 0 and cancelled['pendingQueries'] == 0, 'Explicit cancellation did not clear sequence, liquid, deposits and contacts')
    selection = read_json(ROOT/'build/full-runtime/current-install.json')
    job = ROOT/selection['bodyJob']
    render = ROOT/selection['render']
    geometry = read_json(job/'manifest.json')
    from verify_radial_materials import verify as verify_materials
    material_audit = verify_materials(job)
    materials = read_json(job/'material-imports.json')
    require(materials['nativeHandleVerified'], 'Native atlas handles not verified')
    clinical_manifest = read_json(ROOT/selection['clinical']/'manifest.json')
    clinical_authoring = ROOT/clinical_manifest['authoring']
    require(digest(clinical_authoring/'authoring.json') == clinical_manifest['authoringSHA256'], 'Clinical material authoring receipt differs')
    from prepare_clinical_render import verify_materials as verify_clinical_materials
    verify_clinical_materials(clinical_authoring)
    visual = receipt.parent/'visual-review.json'
    review = read_json(visual)
    require(review['processID'] == pid and review['moduleSHA256'] == session['moduleSHA256'], 'Visual review belongs to another build')
    require(all(review['checks'].get(key) is True for key in ['skinDetailAndColor', 'rearPatchAbsent', 'radialRampAndWaist', 'liquidAndFloorDeposits']), 'Required visual review incomplete')
    quality = ROOT/'build/radial-quality-agent-4/quality-verification.json'
    radial_audit = read_json(quality)
    require(radial_audit['overallSupportMonotonic'] and len(radial_audit['cases']) == 28, 'Independent radial quality audit missing')
    require(all(r['vertices'] == sum(l['nativeVertices'] for l in read_json(render/'manifest.json')['lods']) for r in rows), 'Actual native dimensions differ')
    body = ROOT/'build/full-runtime/body-render-radial-test.txt'
    require(all(s in body.read_text() for s in ['39 full source cases',f"{geometry['knots']} exact waist",'torso displacement','pause/control/epoch snap']), 'Coupled source/body proof missing')
    compiler = ROOT/'build/probe/native-bootstrap-compile.json'
    compiled = read_json(compiler)
    require(compiled['exitCode']==0 and compiled['ownedSourceHashes']['local/malemod/clinical.ws']==digest(ROOT/'probes/native/clinical.ws'), 'Official current script proof differs')
    rates=[]; solves=[]
    for a,b in zip(rows,rows[1:]):
        dt=b['poseSeconds']-a['poseSeconds']
        if dt>0:
            rates.append((b['displayPublications']-a['displayPublications'])/dt)
            solves.append((b['sequence']-a['sequence'])/dt)
    sources=[p for folder in ['native','tools','probes/native'] for p in (ROOT/folder).iterdir() if p.suffix in {'.cpp','.hpp','.py','.ws','.txt','.def'}]
    sources.append(ROOT/'dependencies/base.lock.json')
    proofs=[receipt,trace,receipt.parent/'launcher.txt',visual,quality,compiler,ROOT/compiled['artifact'],body,render/'manifest.json',job/'manifest.json',job/'skin-match.json',job/'ambient-match.json',job/'material-imports.json']
    for key in ['profile','bindings','clinical']: proofs.append(ROOT/selection[key]/'manifest.json')
    proofs.append(ROOT/selection['fingerprints']/'graphics-owned-fingerprints.json')
    for name in ['radial-clinical-production-ctest.txt','radial-clinical-production-amd.txt','radial-clinical-production-fluid-amd.txt','radial-clinical-final-python.txt']:
        proof=ROOT/'build'/name;require(proof.exists(),'Final regression proof missing: '+name);proofs.append(proof)
    require('100% tests passed' in (ROOT/'build/radial-clinical-production-ctest.txt').read_text(),'Final native tests failed')
    require('PASS:' in (ROOT/'build/radial-clinical-production-amd.txt').read_text() and 'PASS native rigid fluid draw' in (ROOT/'build/radial-clinical-production-fluid-amd.txt').read_text(),'Hardware renderer tests failed')
    result=dict(contractVersion=1,baseCommit=pin,sourceFiles=[artifact(p) for p in sorted(sources)],verificationArtifacts=[artifact(p) for p in proofs],installedFiles=installed['files'],
        materials=dict(method='Deterministic linear RGB seam matching; source detail and alpha retained; measured native character texture encoding',imageGeneratorUsed=False,correction=material_audit['linearRGBGain'],packedAmbient=read_json(job/'ambient-match.json'),nativeEncodings=[dict(channel=r['channel'],textureGroup=r['textureGroup'],compression=r['compression']) for r in materials['materials']]),
        boundary=dict(canonicalSamples=geometry['knots'],separateResources=2,lodsPerResource=2,nativeVertices=rows[0]['vertices'],method='Direct source UnifiedCollar radial query and concentric target triangle refinement',originalEdgeDonorsAndUVAliasesPreserved=True,sharedPositionWeightAndShadingProof=True),
        clinical=dict(sourceTimelineSeconds=20,ambientModes=[0,1,2,3],fluidNumericalSource='Pinned Base',engineContact='REDkit SweepTest with calibrated sphere radius',inventedFloor=False,actualSceneHits=max(r['sceneHits'] for r in rows),peakLiquidIndices=max(r['liquidIndices'] for r in rows),peakDepositIndices=max(r['depositIndices'] for r in rows),opaqueAndClearNativeMaterialsDrawn=True,dialoguePhases=[0,1],dialogueAssetsInstalled=False),
        renderInput=dict(nativeLightingStrideBytes=8,finalVertexHardwareRegressionPassed=True,fluidShiftedViewPaddingBytes=24,temporaryBypassesInstalled=False),
        gameVerification=dict(orderedCases=20,finalModuleObserved=True,renderFaults=0,scriptPauseAndCharacterEpochGated=True,hostInputUsed=False,privateAudioRestored=True,saveWritesByDriver=False,visualChecks=review['checks']),
        performance=dict(displayPublicationsPerSecondMedian=statistics.median(rates),numericalSurfacesPerSecondMedian=statistics.median(solves),displayIsNotSolverRate=True,gameFPSBenchmark=False),
        wolverineModified=False,
        limits=['Earlier all-slider movement proof is separate from these twenty final clinical/ramp cases','Ray tracing, far LOD transitions and perceptual F6 flicker require separate observation','Character capsule contacts remain the measured adapter approximation','Native skin lighting is not pixel-identical to Wolverine'])
    return verify(result)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt',type=Path)
    parser.add_argument('--verify',action='store_true')
    args=parser.parse_args()
    if args.verify: verify(read_json(REPORT))
    else:
        if not args.receipt: parser.error('--receipt required')
        write_json(REPORT,record(args.receipt))
    print('PASS radial/clinical installed delivery hashes and recorded runtime gates')
