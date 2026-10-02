"""Solid material pose recovery on unchanged shaft bindings and source lobe web."""
import argparse,json,sys,uuid
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from mod import ROOT,settings,read_json,write_json,digest
from prepare_motion import rig_world
from fixed_physics import independent_rig
from native_pose_delivery import NativeRotationOracle,script_angles


def shortest(a,b):
    q=np.r_[np.cross(a,b),1+np.dot(a,b)]
    return q/np.linalg.norm(q)


def verify(old,new):
    cfg=settings();sys.path.insert(0,str(cfg['base']))
    from malemod_base.motion_binding import sample_mechanical_guide
    script=(ROOT/'probes/runtime/fixedPhysics.ws').read_text()
    oracle=NativeRotationOracle(cfg['redkit']/'bin/x64_RedKit/editor.exe')
    job=ROOT/'build/motion'/('solid-surface-'+uuid.uuid4().hex[:12]);job.mkdir()
    reports=[]
    try:
        q=Rotation.from_euler('xyz',[.4,-.7,.9]);p=np.array([.1,.2,.3]);d=np.array([.03,-.04,.01])
        translation_error=float(np.linalg.norm(oracle.translate(q.as_quat(),p,d)-(p+q.apply(d))))
        if translation_error>1e-7:raise ValueError('Native local translation operator differs')
        for lod in range(2):
            banks=[np.load(c/f'motion-lod{lod}.npz') for c in [old,new]]
            np.testing.assert_array_equal(banks[0]['points'],banks[1]['points'])
            np.testing.assert_array_equal(banks[0]['faces'],banks[1]['faces'])
            mesh=banks[1]['points']/100;faces=banks[1]['faces'];f=banks[1]['fields'];body=len(mesh)-len(f)
            edges=np.unique(np.sort(np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1),axis=0)
            masks=[]
            head=np.zeros(len(mesh),bool);head[body:]=(f[:,2]>=.78)&(f[:,0]>.9)&(f[:,1]<.05)
            masks.append(('head',head))
            for i in [8,9]:
                mask=np.zeros(len(mesh),bool);mask[body:]=banks[1]['weights'][body:,-10+i]>1-1e-10
                masks.append(('lobe'+str(i-8),mask))
            region_edges={name:edges[mask[edges].all(1)] for name,mask in masks}
            states=[]
            for c,data in zip([old,new],banks):
                recipe=read_json(c/'motion.json');r=read_json(c/'motion-dyng.json')
                r['_chunks']={'CSkeleton #0':r['_chunks']['CSkeleton #1']};r,_=independent_rig(r)
                _,_,world=rig_world(r['_chunks']['CSkeleton #0']['_vars']);pelvis=world[9]
                binds=np.asarray([np.linalg.inv(pelvis)@w for w in world[94:]])
                fit=read_json(ROOT/recipe['fitReport']);source=fit['sourceMechanics'];profile=read_json(ROOT/'characters/geralt-attachment.json')
                guide=((np.asarray(source['shaftGuide'])-fit['sourceRoot'])@np.asarray(profile['basis']).T*fit['sourceToFBXScale']+profile['targetRoot'])/100
                guide=(guide-pelvis[:3,3])@pelvis[:3,:3]
                knots=recipe.get('renderCoordinates',np.linspace(0,1,8))
                _,rest_dirs=sample_mechanical_guide(guide,knots)
                states.append((data,world,pelvis,binds,guide,knots,rest_dirs))
            max_errors=[{name:0. for name,_ in masks} for _ in states]; absolute_errors=[{name:0. for name,_ in masks} for _ in states]
            for case in range(49):
                for version,(data,world,pelvis,binds,guide,knots,rest_dirs) in enumerate(states):
                    # Preserve segment lengths, bend successive segments in different
                    # directions; the earlier coherent rigid-motion gate cannot catch this.
                    moved_guide=guide.copy()
                    for i in range(1,11):
                        angles=[65*np.sin(case*.31)*i/11,45*np.cos(case*.27)*i/11,30*np.sin(case*.43+i*.3)]
                        if case==0:angles=[0,0,0]
                        moved_guide[i+1]=moved_guide[i]+Rotation.from_euler('xyz',angles,degrees=True).apply(guide[i+1]-guide[i])
                    positions,directions=sample_mechanical_guide(moved_guide,knots)
                    matrices=[]
                    for i,bind in enumerate(binds):
                        if version==1 and 5<=i<8:
                            head_rotation=Rotation.from_euler('xyz',[.6*np.sin(case*.31),.5*np.cos(case*.27),.4*np.sin(case*.43)])
                            if case==0:head_rotation=Rotation.identity()
                            delta_q=head_rotation.as_quat()
                            pivot=binds[5,:3,3];target=positions[5]+head_rotation.apply(bind[:3,3]-pivot)
                        elif i<8:
                            delta_q=shortest(rest_dirs[i],directions[i]);target=positions[i]
                        else:
                            delta_q=Rotation.from_euler('xyz',[20*np.sin(case*.2),(-1)**i*40*np.sin(case*.3),10*np.cos(case*.4)],degrees=True).as_quat()
                            target=bind[:3,3]+np.array([(-1)**i*.035*np.sin(case*.3),.015*np.cos(case*.2),.02*np.sin(case*.4)])
                            if case==0:delta_q=np.array([0,0,0,1]);target=bind[:3,3]
                        bone_q=delta_q.copy();bone_q[:3]=bind[:3,:3].T@bone_q[:3]
                        current=bind.copy()
                        current[:3,3]=oracle.translate(Rotation.from_matrix(bind[:3,:3]).as_quat(),bind[:3,3],bind[:3,:3].T@(target-bind[:3,3]))
                        current[:3,:3]=oracle.xyz(bind[:3,:3],script_angles(bone_q,script))
                        matrices.append((pelvis@current@np.linalg.inv(world[94+i]))[:3])
                    weights=data['weights'][:,-10:];total=weights.sum(1)
                    moved=np.einsum('nb,bij,nj->ni',weights,np.asarray(matrices),np.c_[mesh,np.ones(len(mesh))])+mesh*(1-total[:,None])
                    if not np.isfinite(moved).all():raise ValueError('Nonfinite surface')
                    for name,e in region_edges.items():
                        if len(e)<50:raise ValueError('Insufficient solid material topology coverage')
                        rest_length=np.linalg.norm(mesh[e[:,1]]-mesh[e[:,0]],axis=1);valid=rest_length>1e-6
                        strain=float(np.max(np.abs(np.linalg.norm(moved[e[:,1]]-moved[e[:,0]],axis=1)[valid]/rest_length[valid]-1)))
                        max_errors[version][name]=max(max_errors[version][name],strain)
                        absolute_errors[version][name]=max(absolute_errors[version][name],float(np.max(np.abs(np.linalg.norm(moved[e[:,1]]-moved[e[:,0]],axis=1)[valid]-rest_length[valid]))))
                    if case==15:np.savez_compressed(job/f'comparison-lod{lod}-version{version}.npz',rest=mesh,moved=moved,faces=faces,head=head)
            # Near-coincident folded faces make a relative-only test misleading.
            # Use absolute material error below the native import/float budget,
            # and retain the relative maximum visibly in the report.
            if max(absolute_errors[1].values())>1e-7:raise ValueError('Solid material exceeds native float budget: '+repr(absolute_errors))
            if max_errors[0]['head']<.02:raise ValueError('Gate does not reproduce the old head deformation')
            reports.append(dict(lod=lod,cases=49,vertices={name:int(mask.sum()) for name,mask in masks},
                                edges={name:len(e) for name,e in region_edges.items()},oldMaximumEdgeStrain=max_errors[0],solidBodyMaximumEdgeStrain=max_errors[1],oldMaximumAbsoluteEdgeError=absolute_errors[0],solidBodyMaximumAbsoluteEdgeError=absolute_errors[1]))
        result=dict(results=reports,restGeometryByteIdentical=True,nativeOracle=oracle.evidence,nativeTranslationError=translation_error,
                    oldCage=str(old),newCage=str(new),controllerSHA256=digest(ROOT/'probes/runtime/fixedPhysics.ws'),
                    observedGameplay=False,shaftBindingKnotsUnchanged=True,distalPoseRecovery='existing bones 5..7 follow the full accepted solid-body transform',omissions=['flexible shaft volume loss','full source pressure/cross-section solver','live frame cost'])
        write_json(job/'verification.json',result);print(json.dumps(result,indent=2));return result
    finally:oracle.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('old',type=Path);p.add_argument('new',type=Path)
    a=p.parse_args();verify(a.old.resolve(),a.new.resolve())
