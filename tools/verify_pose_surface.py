"""Compare native XYZ rotation delivery on both approved skinned mesh LODs."""
import argparse,json,uuid
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from mod import ROOT,settings,read_json,write_json,digest
from prepare_motion import rig_world
from native_pose_delivery import NativeRotationOracle,bone_angles,script_angles

def verify(cage,rig_path):
    cage=Path(cage).resolve();rig_path=Path(rig_path).resolve()
    _,_,worlds=rig_world(read_json(rig_path)['_chunks']['CSkeleton #0']['_vars'])
    pelvis=worlds[9];binds=np.asarray([np.linalg.inv(pelvis)@w for w in worlds[94:]])
    pivot=binds[0,:3,3]
    job=ROOT/'build/motion'/('pose-surface-test-'+uuid.uuid4().hex[:12]);job.mkdir()
    oracle=NativeRotationOracle(settings()['redkit']/'bin/x64_RedKit/editor.exe')
    cases=[('neutral',Rotation.identity())]
    for axis in 'xyz':
        for angle in [-30,30]:cases.append((axis+str(angle),Rotation.from_euler(axis,angle,degrees=True)))
    cases += [('combined',Rotation.from_euler('xyz',[35,-25,40],degrees=True))]
    script=(ROOT/'probes/runtime/fixedPhysics.ws').read_text()
    reports=[];worst_old=worst_fixed=worst_strain=0
    try:
        # Noncommuting rotations distinguish multiplication direction.
        a=Rotation.from_euler('xyz',[.3,-.6,.8]);b=Rotation.from_euler('xyz',[-.5,.7,.4])
        native=Rotation.from_quat(oracle.update(a.as_quat(),b.as_quat())).as_matrix()
        right_error=float(np.linalg.norm(native-(a*b).as_matrix()));left_error=float(np.linalg.norm(native-(b*a).as_matrix()))
        if right_error>1e-6 or left_error<.1:raise ValueError('Native local multiplication direction differs')
        for lod in range(2):
            data=np.load(cage/f'motion-lod{lod}.npz');points=data['points']/100;weights=data['weights'];faces=data['faces']
            total=weights.sum(1);dynamic=weights[:,-10:].sum(1);stock=total-dynamic
            local=(points-pelvis[:3,3])@pelvis[:3,:3]
            # Interior source shaft: avoids the intentional collar blending.
            body=len(points)-len(data['fields']);shaft=np.zeros(len(points),dtype=bool)
            shaft[body:]=data['fields'][:,0]>.9
            active=shaft&(dynamic>.99)
            edges=np.unique(np.sort(np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1),axis=0)
            edges=edges[active[edges].all(1)]
            for name,delta in cases:
                intended=delta.as_matrix();transformed=(local-pivot)@intended.T+pivot
                expected=(transformed@pelvis[:3,:3].T+pelvis[:3,3])*dynamic[:,None]+points*stock[:,None]
                posed=[]
                for corrected in [False,True]:
                    matrices=[]
                    for i,bind in enumerate(binds):
                        if corrected:
                            q=delta.as_quat();q[:3]=bind[:3,:3].T@q[:3]
                            angles=script_angles(q,script)
                            np.testing.assert_allclose(Rotation.from_euler('XYZ',angles,degrees=True).as_matrix(),
                                Rotation.from_euler('XYZ',bone_angles(bind[:3,:3],intended),degrees=True).as_matrix(),atol=1e-12)
                        else:angles=delta.as_euler('xyz',degrees=True)
                        current=bind.copy();current[:3,:3]=oracle.xyz(bind[:3,:3],angles)
                        current[:3,3]=intended@(bind[:3,3]-pivot)+pivot
                        matrices.append((pelvis@current@np.linalg.inv(worlds[94+i]))[:3])
                    moved=np.einsum('nb,bij,nj->ni',weights[:,-10:],np.asarray(matrices),np.c_[points,np.ones(len(points))])+points*stock[:,None]
                    posed.append(moved)
                old_error=float(np.linalg.norm(posed[0]-expected,axis=1).max());fixed_error=float(np.linalg.norm(posed[1]-expected,axis=1).max())
                el=np.linalg.norm(expected[edges[:,1]]-expected[edges[:,0]],axis=1)
                valid=el>1e-7
                strain=[float(np.max(np.abs(np.linalg.norm(p[edges[:,1]]-p[edges[:,0]],axis=1)[valid]/el[valid]-1))) for p in posed]
                if fixed_error>1e-6 or strain[1]>1e-4:raise ValueError('Corrected pose distorts the approved surface')
                worst_old=max(worst_old,old_error);worst_fixed=max(worst_fixed,fixed_error);worst_strain=max(worst_strain,strain[1])
                reports.append(dict(lod=lod,case=name,oldMaximumSurfaceErrorNative=old_error,correctedMaximumSurfaceErrorNative=fixed_error,
                    oldMaximumInteriorEdgeStrain=strain[0],correctedMaximumInteriorEdgeStrain=strain[1],edges=len(edges)))
                if name=='z30':np.savez_compressed(job/f'comparison-lod{lod}.npz',rest=points,old=posed[0],corrected=posed[1],expected=expected,faces=faces,active=active)
        if worst_old<.01:raise ValueError('Fixture failed to reproduce material distortion')
        result=dict(nativeOracle=oracle.evidence,nativeRightProductError=right_error,nativeLeftProductError=left_error,
            nativeRotationOperator='current quaternion right-multiplied by local delta',nativeXYZOrder='intrinsic XYZ',
            parentToBoneConversion='inverse bind rotation * parent delta * bind rotation',
            rigSHA256=digest(rig_path),cage=cage.relative_to(ROOT).as_posix(),results=reports,
            maximumOldSurfaceErrorNative=worst_old,maximumCorrectedSurfaceErrorNative=worst_fixed,maximumCorrectedInteriorEdgeStrain=worst_strain,
            geometryAndPhysicsUnchanged=True,observedGameplay=False,omissions=['nonuniform bending volume loss from linear skinning','gameplay collision response','native gameplay/frame cost'])
        result['controllerTemplateSHA256']=digest(ROOT/'probes/runtime/fixedPhysics.ws')
        result['controllerAngleExpressionsEvaluated']=True
        write_json(job/'verification.json',result);print(json.dumps(result,indent=2));return result
    finally:oracle.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('cage',type=Path);p.add_argument('rig',type=Path)
    args=p.parse_args();verify(args.cage,args.rig)
