"""Compose and officially compile a private collar review in the grey room."""
from pathlib import Path
import re,shutil
from mod import ROOT,digest,write_json,read_json,settings
from compile_native_scripts import compile_native
IMPORTS=('MaleModNativeSealedSession','MaleModNativeTestCheckpoint','MaleModNativePoseSample','MaleModNativeSetControl','MaleModNativeGarmentControl','MaleModNativeClinicalControl')

def compile_merged(workspace):
    # Compile the actual complete managed mod set, not just the test extension.
    game=settings()['game'];installed=read_json(ROOT/'local/native-installation.json')
    for row in installed['files']:
        if '/content/scripts/' not in row['path']:continue
        source=game/row['path']
        if digest(source)!=row['sha256']:raise ValueError('Installed script changed')
        relative=row['path'].split('/content/scripts/',1)[1];target=workspace/'scripts'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    fallback=read_json(ROOT/'local/installation.json')
    for row in fallback['files']:
        if '/scripts/' not in row['path']:continue
        source=Path(fallback['target'])/row['path']
        if digest(source)!=row['sha256']:raise ValueError('Rig script changed')
        target=workspace/'scripts'/row['path'].split('/scripts/',1)[1];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    names=set()
    for source in (workspace/'scripts').rglob('*.ws'):names.update(re.findall(r'import function (MaleMod\w+)\(',source.read_text()))
    return compile_native(workspace,tuple(sorted(names)))

def prepare(root_review=False, angle_sweep=False, side_profile=False, repair_review=False,physics_review=False,physics_motion=False,modular_review=False,lod_review=False,shape_review=False,lod_level=1,distant_review=False,hang_review=False,skin_review=False,cadence_review=False,motion_default=False):
    if motion_default:physics_motion=repair_review=True
    if distant_review or hang_review or skin_review or cadence_review:modular_review=True
    platform=ROOT/'probes/native/iteration_platform.ws'
    cases=ROOT/'probes/native'/('collar_physics_cases.ws' if physics_review else 'collar_repair_cases.ws' if repair_review else 'collar_profile_cases.ws' if side_profile else 'collar_angle_sweep_cases.ws' if angle_sweep else 'collar_root_cases.ws' if root_review else 'collar_cases.ws')
    case_text=cases.read_text()
    if modular_review or shape_review:
        cases=ROOT/'probes/native/modular_acceptance_cases.ws';case_text=cases.read_text()
    if hang_review:
        cases=ROOT/'probes/native/suspension_hang_cases.ws';case_text=cases.read_text()
    if skin_review:
        cases=ROOT/'probes/native/skin_fold_cases.ws';case_text=cases.read_text()
    if cadence_review:
        cases=ROOT/'probes/native/modular_cadence_cases.ws';case_text=cases.read_text()
    if shape_review:
        case_text=case_text.replace('maleModCollarStage >= 96','maleModCollarStage >= 18').replace('maleModCollarStage>=96','maleModCollarStage>=18').replace('caseIndex=maleModCollarStage/3','caseIndex=23+maleModCollarStage/3')
    if distant_review:
        case_text=case_text.replace('maleModCollarStage >= 96','maleModCollarStage >= 9').replace('maleModCollarStage>=96','maleModCollarStage>=9').replace('caseIndex=maleModCollarStage/3','caseIndex=29+maleModCollarStage/3')
    if physics_motion:
        cases=ROOT/'probes/native/physics_motion_cases.ws';case_text=cases.read_text()
        if motion_default:
            case_text,count=re.subn(r'MaleModNativeSetControl\((\d+),[\d.]+\)',lambda m:f'MaleModNativeSetControl({m[1]},{"2.0" if m[1]=="0" else "50.0"})',case_text)
            if count!=18:raise ValueError('Default motion preset must set all 18 controls')
    if lod_review:
        # Official engine API, declared in REDkit engine/world.ws. This changes
        # native LOD selection in the isolated process, not our skin palette.
        needle='        MaleModNativeGarmentControl(0);'
        if case_text.count(needle)!=1:raise ValueError('LOD review control entry changed')
        case_text=case_text.replace(needle,f'        CPPForceActorLOD(true,{lod_level});\n        theGame.GetWorld().ForceGraphicalLOD({lod_level});\n'+needle)
    camera_context=None
    if side_profile or repair_review or modular_review or shape_review:
        import numpy as np,struct
        render=settings()['game']/'bin/x64_dx12/malemod-native/geralt.render'
        payload=render.read_bytes()
        if payload[:8]!=b'MMRND006':raise ValueError('Expected the measured multipart render contract')
        basis=np.frombuffer(payload,'<f8',9,112).reshape(3,3)
        count=struct.unpack_from('<I',payload,240)[0]
        bones=np.frombuffer(payload,'<u4',count,244)
        inverse=np.frombuffer(payload,'<f8',count*16,244+count*4).reshape(count,4,4)
        index=np.flatnonzero(bones==9)
        if not len(index) or not np.allclose(inverse[index],inverse[index[0]],rtol=0,atol=1e-8):raise ValueError('Observed shared pelvis palette entry differs')
        inv=inverse[int(index[0])]
        # Reference in calibrated native metres, centred on the collar and
        # proximal shaft. Camera direction follows the anatomical lateral
        # axis through the same pelvis skin transform used by the anatomy.
        target=np.array([.005,.116,1.03,1.])
        aim=inv@target;side=inv[:3,:3]@basis[:,1];side/=np.linalg.norm(side)
        if not np.isfinite(aim).all() or not np.isfinite(side).all():raise ValueError('Invalid profile camera frame')
        def vector(v,w):return 'Vector('+','.join(f'{float(x):.12f}' for x in list(v)+[w])+')'
        case_text=case_text.replace('PROFILE_PELVIS_POINT',vector(aim[:3],1.)).replace('PROFILE_PELVIS_SIDE',vector(side,0.))
        camera_context=dict(renderSHA256=digest(render),observedPelvisBone=9,nativeAim=target.tolist(),pelvisAim=aim.tolist(),pelvisSide=side.tolist(),distance=1.25,orientation='Anatomical sagittal-plane normal through observed pelvis skin transform; centred on measured collar')
    text=platform.read_text();needle='    if (maleModIterationFloorReady) { SetShowFlag(SHOW_Particles,false); }'
    if text.count(needle)!=1 or text.count('        MaleModIterationWalk();')!=1:raise ValueError('Maintained room bootstrap changed; review composition')
    text=text.replace(needle,needle+'\n    if (maleModIterationStarted) {MaleModCollarCaseStep();return;}')
    text=text.replace('        MaleModIterationWalk();','        // The collar driver owns its later bounded walk.')
    if distant_review or (modular_review and not (hang_review or skin_review or cadence_review)):
        # A 15 m camera is outside the ordinary walls at +/-14 m. Move only
        # the owned backdrop entities; retain the same floor and native actor.
        for axis in ('X','Y'):
            for sign in ('+','-'):
                old=f'wallPosition.{axis}{sign}=14;'
                if text.count(old)!=1:raise ValueError('Studio wall placement changed')
                text=text.replace(old,f'wallPosition.{axis}{sign}=40;')
    directory=ROOT/'build/collar-sessions'/('physics-motion' if physics_motion else 'repair-review' if repair_review else 'side-profile' if side_profile else 'angle-sweep' if angle_sweep else 'root-review' if root_review else 'grey');workspace=directory/'workspace';source=workspace/'scripts/local/malemod/collar_integrity.ws'
    if modular_review:
        directory=ROOT/'build/collar-sessions/modular-review';workspace=directory/'workspace';source=workspace/'scripts/local/malemod/collar_integrity.ws'
    if shape_review:
        directory=ROOT/'build/collar-sessions/shape-review';workspace=directory/'workspace';source=workspace/'scripts/local/malemod/collar_integrity.ws'
    if distant_review:
        directory=ROOT/'build/collar-sessions/modular-distant';workspace=directory/'workspace';source=workspace/'scripts/local/malemod/collar_integrity.ws'
    if hang_review:
        directory=ROOT/'build/collar-sessions/suspension-hang';workspace=directory/'workspace';source=workspace/'scripts/local/malemod/collar_integrity.ws'
    if skin_review:
        directory=ROOT/'build/collar-sessions/skin-folds';workspace=directory/'workspace';source=workspace/'scripts/local/malemod/collar_integrity.ws'
    if cadence_review:
        directory=ROOT/'build/collar-sessions/modular-cadence';workspace=directory/'workspace';source=workspace/'scripts/local/malemod/collar_integrity.ws'
    if motion_default:
        directory=ROOT/'build/collar-sessions/physics-motion-default';workspace=directory/'workspace';source=workspace/'scripts/local/malemod/collar_integrity.ws'
    if lod_review:
        directory=directory.with_name(directory.name+'-engine-lod'+str(lod_level));workspace=directory/'workspace';source=workspace/'scripts/local/malemod/collar_integrity.ws'
    source.parent.mkdir(parents=True,exist_ok=True);source.write_text(text+'\n'+case_text)
    proof=compile_merged(workspace)
    write_json(directory/'compile.json',proof);write_json(directory/'composition.json',dict(platformSHA256=digest(platform),casesSHA256=digest(cases),source=str(source),sourceSHA256=digest(source),compilerProofSHA256=digest(directory/'compile.json'),physicalInputUsed=False))
    if camera_context:write_json(directory/'camera.json',camera_context)
    print(source)

def campaign():
    bootstrap=ROOT/'probes/native/autocontinue.ws';platform=ROOT/'probes/native/iteration_platform.ws';cases=ROOT/'probes/native/collar_cases.ws'
    stock=bootstrap.read_text();marker='@addField(CR4Game)\nprivate var maleModStartRequested : bool;'
    if stock.count(marker)!=1:raise ValueError('Maintained campaign save bootstrap changed')
    stock=stock[stock.index(marker):].replace('MaleModPrivateVerificationStep();','MaleModCollarCampaignStep();')
    room=platform.read_text();walk=room[room.index('class MaleModIterationWalkController'):room.index('function MaleModIterationDisableStudioShadows')]
    prefix='import function MaleModNativeSealedSession() : bool;\nimport function MaleModNativeTestCheckpoint(stage : int) : bool;\n@addField(CR4Game)\nprivate var maleModIterationStarted : bool;\n@addMethod(CR4Game)\nfunction MaleModCollarCampaignStep(){if(!thePlayer || IsPaused()){return;}maleModIterationStarted=true;MaleModCollarCaseStep();}\n'
    directory=ROOT/'build/collar-sessions/campaign';workspace=directory/'workspace';source=workspace/'scripts/local/malemod/collar_integrity.ws';source.parent.mkdir(parents=True,exist_ok=True)
    campaign_cases=cases.read_text()
    marker='    if (caseIndex<12 && seconds-maleModCollarCaseTime<2.5) {return;}'
    if campaign_cases.count(marker)!=1:raise ValueError('Campaign settling entry changed')
    campaign_cases=campaign_cases.replace(marker,
        '    if (caseIndex==0 && view==0 && seconds-maleModCollarCaseTime<25.0) {return;}\n'
        '    if (caseIndex<12 && view==0 && seconds-maleModCollarCaseTime<12.0) {return;}\n'+marker)
    source.write_text(prefix+stock+'\n'+walk+'\n'+campaign_cases)
    proof=compile_merged(workspace)
    write_json(directory/'compile.json',proof);write_json(directory/'composition.json',dict(bootstrapSHA256=digest(bootstrap),platformSHA256=digest(platform),casesSHA256=digest(cases),source=str(source),sourceSHA256=digest(source),compilerProofSHA256=digest(directory/'compile.json'),physicalInputUsed=False,ordinarySaveWrites=False))
    print(source)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    modes=p.add_mutually_exclusive_group()
    modes.add_argument('--campaign',action='store_true')
    modes.add_argument('--root-review',action='store_true',help='Maximum-size root, upward-angle and underside views with native vertex captures')
    modes.add_argument('--angle-sweep',action='store_true',help='All mechanical states across the full angle slider')
    modes.add_argument('--side-profile',action='store_true',help='Camera aligned with the measured anatomical side plane, both sides at four angles')
    modes.add_argument('--repair-review',action='store_true',help='57 measured side/front/oblique size, angle, state and locomotion captures')
    modes.add_argument('--modular-review',action='store_true',help='Modular geometry control, motion and distant LOD acceptance matrix')
    modes.add_argument('--shape-review',action='store_true',help='Six difficult morphology combinations from the maintained modular matrix')
    modes.add_argument('--distant-review',action='store_true',help='Unobstructed native views at 4, 8 and 15 metres with distant owned backdrops')
    modes.add_argument('--hang-review',action='store_true',help='Low-end suspension travel, size, angle and walking review')
    modes.add_argument('--cadence-review',action='store_true',help='Native pulses and consecutive live slider updates')
    modes.add_argument('--skin-review',action='store_true',help='Close side, front and underside skin-fold views')
    p.add_argument('--lod-review',action='store_true',help='Ask the native engine to select LOD1 inside the isolated review process')
    p.add_argument('--lod-level',type=int,choices=(0,1,2),default=1,help='Official engine override value; actual selected LOD must be observed in GPU completion records')
    modes.add_argument('--physics-review',action='store_true',help='Attachment matrix followed by 24 same-control walking frames')
    modes.add_argument('--physics-motion',action='store_true',help='36 same-control native walking/decay frames at the user settings')
    modes.add_argument('--default-motion',action='store_true',help='36 full-floppy walking/decay frames with all shape and response sliders at 50')
    a=p.parse_args();campaign() if a.campaign else prepare(a.root_review,a.angle_sweep,a.side_profile,a.repair_review or a.physics_review or a.physics_motion,a.physics_review,a.physics_motion,a.modular_review,a.lod_review,a.shape_review,a.lod_level,a.distant_review,a.hang_review,a.skin_review,a.cadence_review,a.default_motion)
