"""Read-only XYZ delivery and surface audit of the restored .28 package.

Uses the actual cooked graph, observed bind frames, controller expressions and
REDkit SIMD instructions. Synthetic motion is not a live game measurement.
"""
import json,sys,uuid
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from mod import ROOT,settings,read_json,write_json,digest
from prepare_motion import rig_world
from fixed_physics import independent_rig
from native_pose_delivery import NativeRotationOracle,script_angles
from verify_deformation_graph import verify_graph


def shortest(a,b):
    q=np.r_[np.cross(a,b),1+np.dot(a,b)]
    return q/np.linalg.norm(q)


def audit():
    cfg=settings();sys.path.insert(0,str(cfg['base']))
    from malemod_base.motion_binding import sample_mechanical_guide
    cage=ROOT/read_json(ROOT/'generated/default-cage.json')['cage']
    installed=read_json(ROOT/'local/installation.json')
    if installed['version']!='0.4.28-bone-local-physics':
        raise ValueError('Audit requires the restored pre-workaround package')
    for f in installed['files']:
        if digest(Path(installed['target'])/f['path'])!=f['sha256']:
            raise ValueError('Installed .28 bytes differ: '+f['path'])
    job=ROOT/'build/motion/player-stack-a52737e5911c'
    probe=read_json(job/'deformation-probe.json')
    cooked=job/'package-12d32f620ff8/cooked/characters/malemod/behavior/deformation.w2beh.xml'
    graph=verify_graph(cooked,stock_names=probe['stockNames'],identity_root=probe['identityRoot'],
                       transform_controls=True,parent_space='attached',rest_joints=True)
    rig=read_json(cage/'motion-dyng.json')
    rig['_chunks']={'CSkeleton #0':rig['_chunks']['CSkeleton #1']}
    rig,_=independent_rig(rig)
    _,_,world=rig_world(rig['_chunks']['CSkeleton #0']['_vars'])
    pelvis=world[9];binds=np.asarray([np.linalg.inv(pelvis)@w for w in world[94:]])
    recipe=read_json(cage/'motion.json');fit=read_json(ROOT/recipe['fitReport'])
    basis=np.asarray(read_json(ROOT/'characters/geralt-attachment.json')['basis'])
    guide=((np.asarray(fit['sourceMechanics']['shaftGuide'])-fit['sourceRoot'])@basis.T*
           fit['sourceToFBXScale']+read_json(ROOT/'characters/geralt-attachment.json')['targetRoot'])/100
    guide=(guide-pelvis[:3,3])@pelvis[:3,:3]
    knots=np.linspace(0,1,8);_,rest_dirs=sample_mechanical_guide(guide,knots)
    script=(ROOT/'probes/runtime/fixedPhysics.ws').read_text()
    native=NativeRotationOracle(cfg['redkit']/'bin/x64_RedKit/editor.exe')
    results=[];surface=[]
    try:
        for i,bind in enumerate(binds):
            b=bind[:3,:3];q=Rotation.from_matrix(b).as_quat();p=bind[:3,3]
            translation_columns=[];rotation_columns=[];position_error=rotation_error=0.
            for axis in range(3):
                # Send a requested displacement along each *pelvis* axis through
                # the same inverse-bind projection as PublishPose.
                requested=np.eye(3)[axis]*.01
                moved=native.translate(q,p,b.T@requested)
                translation_columns.append((moved-p)/.01)
                position_error=max(position_error,float(np.linalg.norm(moved-p-requested)))
                parent=Rotation.from_rotvec(np.eye(3)[axis]*.05)
                local_q=parent.as_quat();local_q[:3]=b.T@local_q[:3]
                actual=native.xyz(b,script_angles(local_q,script))
                observed=actual@b.T
                rotation_columns.append(Rotation.from_matrix(observed).as_rotvec()/.05)
                rotation_error=max(rotation_error,float(np.max(np.abs(observed-parent.as_matrix()))))
            tr=np.column_stack(translation_columns);rr=np.column_stack(rotation_columns)
            if np.linalg.matrix_rank(tr,tol=1e-4)!=3 or np.linalg.matrix_rank(rr,tol=1e-4)!=3:
                raise ValueError('A delivered XYZ degree of freedom is missing')
            if position_error>1e-7 or rotation_error>1e-6:
                raise ValueError('Bind-local delivery differs from requested pelvis-space motion')
            results.append(dict(joint=i,translationRank=3,rotationRank=3,
                translationSingularValues=np.linalg.svd(tr,compute_uv=False).tolist(),
                rotationSingularValues=np.linalg.svd(rr,compute_uv=False).tolist(),
                maximumTranslationError=position_error,maximumRotationMatrixError=rotation_error))
        # A tangent allows two independent bends. Native roll is available,
        # but this controller's shortest-rotation reconstruction never requests
        # an independent material roll (the reference also uses shortest rotation).
        tangent=rest_dirs[4];columns=[]
        for axis in range(3):
            changed=Rotation.from_rotvec(np.eye(3)[axis]*1e-5).apply(tangent)
            columns.append(Rotation.from_quat(shortest(tangent,changed)).as_rotvec()/1e-5)
        tangent_singular=np.linalg.svd(np.column_stack(columns),compute_uv=False)
        if np.sum(tangent_singular>1e-4)!=2:raise ValueError('Tangent lacks both bending freedoms')
        for lod in range(2):
            data=np.load(cage/f'motion-lod{lod}.npz');mesh=data['points']/100
            fields=data['fields'];body=len(mesh)-len(fields);weights=data['weights'][:,-10:]
            faces=data['faces'];edges=np.unique(np.sort(np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1),axis=0)
            head=np.zeros(len(mesh),bool);head[body:]=(fields[:,2]>=.78)&(fields[:,0]>.9)&(fields[:,1]<.05)
            edges=edges[head[edges].all(1)];rest_lengths=np.linalg.norm(mesh[edges[:,1]]-mesh[edges[:,0]],axis=1)
            valid=rest_lengths>1e-6;edges=edges[valid];rest_lengths=rest_lengths[valid]
            if len(edges)<50:raise ValueError('Insufficient real head topology')
            axes=[]
            for axis in range(3):
                moved_guide=guide.copy()
                for i in range(1,11):
                    rotation=Rotation.from_rotvec(np.eye(3)[axis]*np.deg2rad(50)*i/11)
                    moved_guide[i+1]=moved_guide[i]+rotation.apply(guide[i+1]-guide[i])
                points,dirs=sample_mechanical_guide(moved_guide,knots);matrices=[];target_error=0.
                for i,bind in enumerate(binds):
                    cur=bind.copy()
                    if i<8:
                        delta_q=shortest(rest_dirs[i],dirs[i]);delta_q[:3]=bind[:3,:3].T@delta_q[:3]
                        cur[:3,:3]=native.xyz(bind[:3,:3],script_angles(delta_q,script))
                        cur[:3,3]=native.translate(Rotation.from_matrix(bind[:3,:3]).as_quat(),bind[:3,3],bind[:3,:3].T@(points[i]-bind[:3,3]))
                        target_error=max(target_error,float(np.linalg.norm(cur[:3,3]-points[i])))
                    matrices.append((pelvis@cur@np.linalg.inv(world[94+i]))[:3])
                moved=np.einsum('nb,bij,nj->ni',weights,np.asarray(matrices),np.c_[mesh,np.ones(len(mesh))])+mesh*(1-weights.sum(1)[:,None])
                strain=float(np.max(np.abs(np.linalg.norm(moved[edges[:,1]]-moved[edges[:,0]],axis=1)/rest_lengths-1)))
                axes.append(dict(pelvisAxis='XYZ'[axis],guideExcursion=float(np.linalg.norm(moved_guide-guide,axis=1).max()),
                    maximumHeadEdgeStrain=strain,maximumDeliveredJointPositionError=target_error))
            surface.append(dict(lod=lod,headVertices=int(head.sum()),headEdges=len(edges),nonuniformBendTests=axes))
        out=ROOT/'build/motion'/('axis-audit-'+uuid.uuid4().hex[:12]);out.mkdir()
        report=dict(installedVersion=installed['version'],installedHashesVerified=True,cookedGraph=graph,
            cage=cage.relative_to(ROOT).as_posix(),cageSHA256=digest(cage/'motion.json'),
            controllerSHA256=digest(ROOT/'probes/runtime/fixedPhysics.ws'),nativeOracle=native.evidence,
            joints=results,tangentOrientationRank=2,tangentSingularValues=tangent_singular.tolist(),
            independentRollRequested=False,surface=surface,missingDeliveredAxisFound=False,
            observedGameplay=False,limitations=['REDkit instruction emulation is not running-game pose readback',
                'surface tests use controlled 3D bends, not a captured gameplay trajectory',
                'no independent torsional material state in tangent-only reconstruction'])
        write_json(out/'verification.json',report)
        print(json.dumps(dict(evidence=str(out/'verification.json'),joints=len(results),missingDeliveredAxisFound=False,
                              tangentOrientationRank=2,surface=surface),indent=2))
        return report
    finally:native.close()


if __name__=='__main__':audit()
