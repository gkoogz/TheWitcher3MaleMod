"""Record the separately verified angle, garment and liquid-phase adoption.

Raw screenshots, game frames and user data remain outside Git. Numerical,
native GPU and observed game evidence have separate fields.
"""
import argparse,json,math,statistics,struct,sys
from pathlib import Path
from mod import ROOT,settings,base_checkout,read_json,write_json,digest
from record_body_delivery import artifact,require,verify

REPORT=ROOT/'provenance/extended-delivery.json'

def validate_source_reactions(report, base, pin, worker):
    """Bind actual source consumption to the clean library adopted by this port."""
    report,base=Path(report).resolve(),Path(base).resolve()
    require(report.is_relative_to(base/'build'),'Source reaction receipt is outside owned builds')
    proof=read_json(report)
    require(proof.get('schema')==2 and proof.get('wire')==6 and proof.get('sourceProcessIsolated') is True,'Actual wire6 source reaction proof missing')
    require(proof.get('sourceCommit')==pin and proof.get('sourceDirty')=='','Source reaction proof is dirty or pinned to another revision')
    require(worker.get('baseCommit')==pin and worker.get('baseDirty') is False and worker.get('wireVersion')==6 and worker.get('frames')==48 and worker.get('byteIdentical') is True and worker.get('exitCode')==0,'Clean current wire6 worker parity proof missing')
    paths=[report]
    for name in ['executable','library']:
        item=proof.get(name,{})
        path=(base/item.get('path','')).resolve()
        require(path.is_relative_to(base/'build') and path.is_file() and item.get('sha256')==digest(path),'Source reaction binary changed')
        paths.append(path)
    require(proof['library']['sha256']==worker.get('librarySHA256'),'Source reaction proof uses a different numerical library')
    hashes=proof.get('sourceHashes',{})
    required={'src/surface/runtime.cpp','tools/extract_surface_runtime.py',
              'tests/garment_support_runtime_cli.cpp','include/malemod/surface/wire.hpp',
              'include/malemod/surface/runtime.hpp','include/malemod/surface/garment_impulse.hpp',
              'include/malemod/garments/reaction_support.hpp',
              'legacy/wolverine/src/runtime/compliant_dynamics.h',
              'provenance/wolverine.json','provenance/source-surface.json',
              'tools/verify_garment_source_reactions.py'}
    require(required<=set(hashes),'Source consumption receipt omits source provenance')
    for relative,expected in hashes.items():
        path=(base/relative).resolve()
        require(path.is_relative_to(base) and path.is_file() and digest(path)==expected,'Source reaction source hash changed')
    cases=proof.get('cases',[])
    require(len(cases)==3 and {case.get('state') for case in cases}=={0,1,2},'Source consumption does not cover all three mechanical states')
    for case in cases:
        require(all(case.get(key) is True for key in ['disabledExactParity','cdfRetryExactParity','physicalImpulseChangesSource']),'Source reaction behavior failed')
        records=case.get('records',{})
        require({'0','2','3','4','5','6'}<=set(records),'Source consumption or pending-step comparison missing')
        data={}
        for mode,item in records.items():
            path=(report.parent/item.get('file','')).resolve()
            require(path.is_relative_to(report.parent) and path.is_file(),'Source comparison output missing')
            raw=path.read_bytes()
            require(len(raw)>=8 and struct.unpack_from('<I',raw)[0]==6,'Source comparison is not a wire6 encoded output')
            require(len(raw)==item.get('bytes') and digest(path)==item.get('sha256'),'Source comparison bytes changed')
            data[mode]=raw;paths.append(path)
        require(data['0']==data['2'] and data['3']==data['4'] and data['0']!=data['3'],'Encoded source consumption lacks disabled/retry parity or an actual physical response')
        require(case.get('pendingNoSubstepExactParity') is True and case.get('pendingCoalescingExactParity') is True and data['3']==data['5']==data['6'],'Queued or coalesced cloth impulses are lost or applied twice before a source step')
    return paths

def validate_cloth_reaction(row):
    """Require measured optical intent and conserved physical contact feedback.

    Native shader/cook validation and consumed-source cadence are separate
    artifacts; telemetry alone cannot prove either of them.
    """
    opacity=row.get('garmentMaterialOpacity',[])
    require(len(opacity)==4 and all(isinstance(a,(int,float)) and math.isfinite(a) and math.isclose(a,.95,rel_tol=0,abs_tol=1e-9) for a in opacity),'Shared cloth opacity differs from 95%')
    require(isinstance(row.get('clothMass'),(int,float)) and math.isfinite(row['clothMass']) and row['clothMass']>0,'Measured relative cloth mass missing')
    require(isinstance(row.get('clothReactionSeconds'),(int,float)) and math.isfinite(row['clothReactionSeconds']) and row['clothReactionSeconds']>=0,'Invalid solved cloth reaction duration')
    for name in ['clothReactionContacts','clothReactionRecords']:
        require(isinstance(row.get(name),int) and row[name]>=0,'Invalid physical cloth reaction count')
    names=['clothContactImpulse','anatomyContactImpulse','clothContactMoment','anatomyContactMoment',
           'clothParticleContactImpulse','clothParticleContactMoment',
           'clothPrescribedSupportImpulse','clothPrescribedSupportMoment']
    for name in names:
        values=row.get(name,[])
        require(len(values)==3 and all(isinstance(v,(int,float)) and math.isfinite(v) for v in values),'Invalid contact impulse or moment')
    for first,second in [(names[0],names[1]),(names[2],names[3])]:
        a,b=row[first],row[second]
        error=math.sqrt(sum((x+y)**2 for x,y in zip(a,b)))
        magnitude=max(1.,math.sqrt(sum(x*x for x in a)),math.sqrt(sum(y*y for y in b)))
        require(error<=1e-8*magnitude,'Cloth/tissue reaction is not equal and opposite')
    for total,particle,support in [(names[0],names[4],names[6]),(names[2],names[5],names[7])]:
        a,b,c=row[total],row[particle],row[support]
        error=math.sqrt(sum((x-y-z)**2 for x,y,z in zip(a,b,c)))
        magnitude=max(1.,math.sqrt(sum(x*x for x in a)),math.sqrt(sum(y*y for y in b)),math.sqrt(sum(z*z for z in c)))
        require(error<=1e-8*magnitude,'Contact load is not accounted for by actual particles and prescribed material support')
    if row['clothReactionRecords']:
        require(row.get('garmentReactionMode') and row.get('garmentSupportEnabled') and row['clothReactionContacts']>0 and row['clothReactionSeconds']>0,'Recorded contacts do not reach physical reaction mode')
    else:
        require(all(abs(v)<=1e-12 for name in names for v in row[name]),'Nonzero reaction has no retained tissue records')

def record(receipt):
    receipt=Path(receipt).resolve();require(receipt.is_relative_to(ROOT/'build/probe'),'Expected private receipt')
    session=read_json(receipt);installed=read_json(ROOT/'local/native-installation.json')
    require(session.get('closed') and session.get('audioRestored'),'Private game/audio still active')
    require(session['installationReceiptSHA256']==digest(ROOT/'local/native-installation.json'),'Installation changed after observation')
    require(session['moduleSHA256']==digest(Path(session['modulePath'])),'Observed module changed')
    require(session['observations']['noninteractiveWindowStation'] and not session['observations']['physicalInputUsed'] and not session['physicalDesktopSwitch'],'Private isolation failed')
    require(not Path(session['temporaryContinueSource']).exists(),'Temporary driver remains installed')
    pid=session['observations']['processID'];trace=receipt.parent/'verification.jsonl'
    if not trace.exists():trace.write_bytes((Path(session['modulePath']).parent/f'verification-{pid}.jsonl').read_bytes())
    rows=[json.loads(line) for line in trace.read_text().splitlines()];rows=[r for r in rows if 64<=r['stage']<=116]
    require([r['stage'] for r in rows]==list(range(64,117)),'53 ordered game checkpoints missing')
    require(all(r['bodyResourceMask']==3 and r['renderFlags']&853==853 and not r['renderFlags']&128 and r['runtimeFlags']==135 for r in rows),'Body/garment runtime fault')
    require(all(not r['fluidRenderFlags']&128 and not r['garmentFlags']&(128|2) and not r['garmentServiceError'] for r in rows),'Native carrier fault')
    by={r['stage']:r for r in rows}
    require(by[90]['vertices']>0 and all(by[s]['vertices']==by[90]['vertices'] for s in range(90,108)),'Clothing toggle removed native body/anatomy vertices')
    for stage in range(84,90):
        r=by[stage];case=stage-84
        require(r['controls'][0]==case//2 and r['controls'][1]==100 and r['controls'][7]==(1 if case%2==0 else 100),'Extreme angle did not reach native geometry')
    for stage in range(90,108):
        r=by[stage];style=(stage-90)//6 if stage<102 else (stage-102)//3
        require(r['garmentStyle']==style,'Clothing toggle did not reach game')
        if style:
            require(r['garmentVertices']>0 and r['garmentTriangles']>0 and r['garmentContactBudgetSatisfied'],'Garment fit not accepted')
            validate_cloth_reaction(r)
            require(r['garmentFlags']&125==125 and r['garmentPublications']>0,'Four garment materials not drawn')
            require(r.get('clothActive') and r.get('clothStateReady') and r.get('clothMaterialBudgetSatisfied'),'Persistent cloth solver not accepted')
            require(isinstance(r.get('clothFineStretchRatio'),(int,float)) and math.isfinite(r['clothFineStretchRatio']) and 0<=r['clothFineStretchRatio']<=1.15,'Displayed fine fabric exceeds the material stretch budget')
            require(r.get('garmentLayoutRevision')==2 and r.get('pouchSheetRows',0)>=8 and r.get('pouchSheetColumns',0)>=8,'Single walking material sheet missing')
            require(math.isclose(r.get('pouchUpperArcRadians',0),math.radians(80),rel_tol=0,abs_tol=1e-8),'Upper seam does not follow the requested total 80-degree arc')
            require(r.get('pouchTopSeamVertices',0)==r['pouchSheetColumns']+1 and len(r.get('pouchBottomSeamVertices',[]))==2 and all(n>=2 for n in r['pouchBottomSeamVertices']),'Broad top seam or two short lower strap seams missing')
            require(r.get('pouchSideHemSections')==[r['pouchSheetRows']+1]*2 and r.get('pouchSideBoundaryVertices')==[r['pouchSheetRows']+1]*2,'Two continuous side hems missing')
            require(r.get('clothNodes',0)>0 and r.get('clothConstraints',0)>0 and r.get('clothAccumulatedSeconds',0)>0,'Cloth has not advanced in game')
            require(r.get('bandTopAttachments',0)>=8 and r.get('bandBottomAttachments',0)>=8,'Measured seated upper/lower waistband attachments missing')
            band_keys=['bandTopCircumference','bandBottomCircumference','bandPreferredClearance','bandMinimumInnerClearance','bandMaximumInnerClearance']
            require(all(isinstance(r.get(k),(int,float)) and math.isfinite(r[k]) for k in band_keys),'Invalid actual waistband fit measurement')
            require(r['bandTopCircumference']>0 and r['bandBottomCircumference']>0 and r['bandPreferredClearance']>0 and r['bandMinimumInnerClearance']>=0 and r['bandMaximumInnerClearance']>=r['bandMinimumInnerClearance'],'Waistband fits through the measured body')
        else:require(r['garmentVertices']==0 and r['garmentTriangles']==0 and not r['garmentSupportEnabled'] and not r.get('clothActive',False),'Naked retains cloth/support')
    require(max(sum((a-b)**2 for a,b in zip(by[s]['actorOrigin'],by[102]['actorOrigin'])) for s in range(102,108))>.04,'Garment movement cases did not move')
    moving=[by[s] for s in range(105,108)]
    require(any(r.get('garmentReactionMode') and r.get('clothReactionRecords',0)>0 for r in moving),'Movement never exercised physical cloth support')
    require(any(r.get('clothSubsteps',0)>0 and r.get('clothRmsSpeed',0)>0 and r.get('clothDisplacement',0)>0 for r in moving),'Moving cloth remained a static fit')
    final=by[114];require(final['clinicalTime']==20 and not final['clinicalActive'],'Clinical timeline failed to finish')
    require(final['finalPumpDepositedVolume']>0 and final['finalPumpDepositedImpacts']>0 and final['depositIndices']>0,'Final-born pumps did not mark actual terrain')
    require(final['depositedVolume'][0]>0 and final['depositedVolume'][1]>0,'Both liquid phases lack deposition')
    cancelled=by[116];require(cancelled['clinicalTime']==0 and not cancelled['clinicalActive'] and cancelled['depositIndices']==0 and cancelled['liquidIndices']==0 and cancelled['pendingQueries']==0,'Cancel retains liquid/contact state')
    visual=receipt.parent/'visual-review.json';review=read_json(visual)
    require(review['processID']==pid and review['moduleSHA256']==session['moduleSHA256'],'Visual review identity differs')
    keys=['stablePelvisExtremeAngles','skinAndRearWaist','garmentWaistbandStripes','garmentPouchAndStraps','garmentMovingCoverage','whiteMainAndFinalFlow','finalPumpGroundMarks']
    require(all(review['checks'].get(k) is True for k in keys),'Required observed visual checks incomplete')
    for item in review['images']:require(digest(Path(item['path']))==item['sha256'],'Reviewed image changed')
    selection=read_json(ROOT/'build/full-runtime/current-install.json')
    clinical=read_json(ROOT/selection['clinical']/'manifest.json')
    garment_binding=read_json(ROOT/selection['garments']/'manifest.json')
    require(garment_binding.get('contractVersion')==3 and garment_binding.get('bodyContactResources')==[0,1],'Garment lacks semantic bindings and both measured body resources')
    semantics=garment_binding.get('anatomySemantics',{})
    require(semantics.get('version')==1 and semantics.get('nativeDrawIndicesChanged') is False,'Garment changed native anatomy topology or lacks authored tissue semantics')
    require(semantics.get('fullAnatomyVertices',0)>0 and semantics.get('fullAnatomyTriangles',0)>0,'Complete underlying anatomy missing')
    require(set(semantics.get('groupCounts',{}))=={'shaft','glans','leftLobe','rightLobe'} and all(isinstance(n,int) and n>0 for n in semantics['groupCounts'].values()),'Walking sheet lacks all four authored anatomy support regions')
    require(all(isinstance(semantics.get(k),str) and len(semantics[k])==64 for k in ['sourceAssetSHA256','exporterSHA256','partLineageSHA256']),'Tissue support provenance missing')
    reaction_binding=garment_binding.get('physicalReactionBinding',{})
    reaction_packet=ROOT/selection['garments']/'garment.reactions'
    require(reaction_binding.get('version')==1 and reaction_binding.get('generalizedBodies')==14 and reaction_binding.get('nativeVertices')==semantics['fullAnatomyVertices'] and reaction_binding.get('nonlinearSurfaceJacobian') is False,'Measured source mechanical ownership is missing or misrepresented')
    require(reaction_packet.is_file() and digest(reaction_packet)==reaction_binding.get('packetSHA256'),'Mechanical reaction companion changed')
    require(reaction_binding.get('sourceAssetSHA256')==semantics['sourceAssetSHA256'],'Mechanical reaction source differs from anatomical source')
    require(garment_binding.get('bodyContactVertices',0)>0 and garment_binding.get('bodyContactTriangles',0)>0,'Garment actual body contact surface missing')
    require(len(garment_binding.get('bodyContactWinding',[]))==2 and all(not r['nativeDrawBuffersChanged'] for r in garment_binding['bodyContactWinding']),'Measured contact winding proof missing')
    phase=clinical['phasePresentation']
    opacity=next(t for t in clinical['textures'] if t['name']=='opacity')
    require(clinical['nativeCooked'] and phase['alphaSource']=='native Diffuse.a' and phase['clearFlowOpacity']==.14 and phase['opaqueFlowMaterial']=='pbr_std','Native liquid phase presentation differs')
    require(opacity['nativeMetadataVerified'] and opacity['textureGroup']=='CharacterDiffuseWithAlpha' and opacity['compression']=='TCM_DXTAlpha','Native clear alpha was not retained')
    sources=[ROOT/'dependencies/base.lock.json',*[p for folder in ['native','probes/native','tools'] for p in (ROOT/folder).iterdir() if p.suffix in {'.cpp','.hpp','.ws','.py','.txt','.def'}]]
    proofs=[receipt,trace,receipt.parent/'launcher.txt',visual,ROOT/'build/probe/native-bootstrap-compile.json',ROOT/'build/probe/native-session-compile.json']
    for key in ['profile','render','bindings','clinical','garments']:proofs.append(ROOT/selection[key]/'manifest.json')
    proofs.extend([ROOT/selection['bodyAdoption'],ROOT/selection['garmentCarrier']/'package.json',ROOT/selection['fingerprints']/'graphics-owned-fingerprints.json'])
    compiler=read_json(ROOT/'build/probe/native-session-compile.json')
    require(not compiler['exitCode'] and not compiler['scriptImportsStubbed'] and digest(ROOT/compiler['artifact'])==compiler['artifactSHA256'],'Official session compilation proof changed')
    require(compiler['ownedSourceHashes']['local/malemod/autocontinue.ws']==digest(ROOT/'probes/native/autocontinue.ws'),'Observed driver does not match official compilation')
    proofs.append(ROOT/compiler['artifact'])
    pin=base_checkout(settings())['commit']
    base=Path(settings()['base']).resolve()
    sys.path.insert(0,str(base))
    from malemod_base.garment_geometry_audit import validate_geometry_receipt
    geometry_receipt=base/('build/garment-geometry-'+pin[:7]+'/proof.json')
    proofs.extend(validate_geometry_receipt(geometry_receipt,base,pin))
    fit=ROOT/('build/garment-final-'+pin[:7])
    for name in ['garment_fit_test.txt','garment_presentation_test.txt','garment_dynamics_test.txt']:
        evidence=fit/name
        require(evidence.exists() and 'PASS' in evidence.read_text(),'Final actual-character garment gate missing')
        proofs.append(evidence)
    dynamics=fit/'dynamics/dynamics-cases.jsonl'
    dynamic_rows=[json.loads(line) for line in dynamics.read_text().splitlines()]
    require(len(dynamic_rows)==48 and {r['morphology'] for r in dynamic_rows}=={0,1,2},'Actual evaluated garment dynamics cases missing')
    require(all(r['contactBudget'] and r['materialBudget'] for r in dynamic_rows),'Calibrated moving cloth gate failed')
    require(all(isinstance(r.get('maxRenderStretchRatio'),(int,float)) and math.isfinite(r['maxRenderStretchRatio']) and 0<=r['maxRenderStretchRatio']<=1.15 for r in dynamic_rows),'Actual displayed cloth strain is missing or exceeds its budget')
    require(sum(r['substeps'] for r in dynamic_rows)>60 and dynamic_rows[-1]['accumulatedSeconds']>0,'Offline cloth test did not advance')
    proofs.append(dynamics)
    steady_path=fit/'dynamics/steady-performance.json'
    steady=read_json(steady_path)
    require(steady.get('steadySamples',0)>0 and steady.get('initialAndMorphologyRefitsExcluded') is True and steady.get('diagnosticWritesExcluded') is True,'Steady cloth performance measurement missing')
    timing_keys=['workerMeanMilliseconds','activeIntervalMeanMilliseconds','maximumAccumulatedLagMilliseconds','finalAccumulatedLagMilliseconds']
    require(all(isinstance(steady.get(k),(int,float)) and math.isfinite(steady[k]) and steady[k]>=0 for k in timing_keys),'Invalid cloth timing measurement')
    require(steady['workerMeanMilliseconds']<steady['activeIntervalMeanMilliseconds'],'Steady cloth worker is slower than retained active time')
    require(steady['finalAccumulatedLagMilliseconds']<=100 and steady['maximumAccumulatedLagMilliseconds']<=250,'Cloth presentation age exceeds its tested budget')
    proofs.append(steady_path)
    worker_path=ROOT/('build/full-runtime/worker-proof-'+pin[:7]+'-contact-shape/manifest.json')
    proofs.extend([fit/'fit/shape-cases.jsonl',worker_path,reaction_packet])
    source_reaction=settings()['base']/('build/physical-reaction-source-proof-'+pin[:7]+'/proof.json')
    proofs.extend(validate_source_reactions(source_reaction,settings()['base'],pin,read_json(worker_path)))
    material=ROOT/selection['garmentCarrier']/'material-proof.json'
    require(material.exists(),'Actual cooked garment channel proof missing')
    optical=read_json(material).get('opticalContract',{})
    require(optical.get('graph')=='characters/malemod/garments/cloth_soft.w2mg' and optical.get('sortGroup')=='RSG_Transparent' and optical.get('blendMode')=='RBM_AlphaBlend','Garment lacks the supported native opacity path')
    for channel,value in [('Opacity',.95),('Roughness',.88),('Specularity',.015)]:
        actual=optical.get(channel,{}).get('value')
        require(isinstance(actual,(int,float)) and math.isfinite(actual) and math.isclose(actual,value,rel_tol=0,abs_tol=1e-6),'Cooked soft cloth optical constants differ')
    require(all(optical.get(k) is True for k in ['normalFeedsForwardLight','diffuseFeedsForwardLight','compiledNormal','compiledDiffuse']),'Cooked cloth lost native texture lighting')
    proofs.append(material)
    result=dict(contractVersion=3,baseCommit=base_checkout(settings())['commit'],sourceFiles=[artifact(p) for p in sorted(sources)],verificationArtifacts=[artifact(p) for p in proofs],installedFiles=installed['files'],
        numerical=dict(sharedSource='Pinned Base',wireVersion=6,pelvicRecruitmentFrame='Stable measured neutral body frame',garmentSupport='Measured equal-opposite tissue contact impulse and moment; cumulative source consumption',garmentSimulation='Persistent shared walking material sheet with stretch, bending, sewn seams and contacts',pouchTopAttachmentArcDegrees=80,garmentOpacity=.95,garmentBodyContacts='Current measured upper and lower body surfaces; independent outward contact winding',waistbandAttachments='Snug nonlevel band seated on the actual body contour, with weighted native upper/lower surface donors',geometryAcceptance='Independent clean-pin 72-case actual geometry matrix; zero crossing/overlap/degeneracy/winding, authored seams and smooth straps/hems',anatomySemantics=semantics),
        gameVerification=dict(orderedCases=53,angleCases=6,garmentStatesAndSizes=12,garmentMovementCases=6,fullNativeAnatomyRetainedThroughClothingToggle=True,nativeBodyAndAnatomyVertices=by[90]['vertices'],actualFinalPumpVolume=final['finalPumpDepositedVolume'],actualFinalPumpHits=final['finalPumpDepositedImpacts'],visualChecks=review['checks'],clearPhaseNativeAlphaVerified=True,clearPhaseDirectlyVisible=review['checks'].get('clearPhaseDirectlyVisible',False),physicalInputUsed=False,privateAudioRestored=True),
        performance=dict(steadyCloth=steady,garmentWorkerMsMedian=statistics.median(r['garmentMs'] for r in rows if r['garmentStyle']),garmentWorkerMsMaximum=max(r['garmentMs'] for r in rows),garmentPresentationMsMedian=statistics.median(r['garmentPresentationMs'] for r in rows if r['garmentStyle']),garmentPresentationMsMaximum=max(r['garmentPresentationMs'] for r in rows),callbackMsMaximum=max(r['callbackMaxMs'] for r in rows),gameFPSBenchmark=False),
        audioAssetsAdded=False,limits=['Anatomy collision still uses its calibrated body capsules','Garment constraints are a bounded real-time fabric approximation','Far LOD/ray-tracing transitions require separate observation'])
    return verify(result)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--receipt',type=Path);p.add_argument('--verify',action='store_true');a=p.parse_args()
    if a.verify:
        delivery=read_json(REPORT)
        verify(delivery)
        cfg=settings();pin=base_checkout(cfg)['commit'];base=Path(cfg['base']).resolve()
        require(delivery.get('baseCommit')==pin,'Extended delivery uses a stale Base pin')
        sys.path.insert(0,str(base))
        from malemod_base.garment_geometry_audit import validate_geometry_receipt
        geometry_receipt=base/('build/garment-geometry-'+pin[:7]+'/proof.json')
        require(artifact(geometry_receipt) in delivery.get('verificationArtifacts',[]),'Extended delivery lacks its exact 72-case geometry receipt')
        validate_geometry_receipt(geometry_receipt,base,pin)
    else:
        if not a.receipt:p.error('--receipt required')
        write_json(REPORT,record(a.receipt))
    print('PASS extended installed delivery and observed proof hashes')
