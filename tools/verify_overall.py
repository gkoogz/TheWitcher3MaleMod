"""Native pair layout, welded interpolation and actual instruction pivot tests."""
import argparse,re
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from mod import ROOT,settings,read_json,write_json,digest
from wcc_fbx import Document
from verify_attachment import skin_weights
from prepare_motion import rig_world
from native_pose_delivery import NativeRotationOracle,script_angles

def verify(job):
    job=Path(job).resolve();bank=read_json(job/'overall.json');native=read_json(job/'native-bank.json')
    if not native['complete']:raise ValueError('Native bank incomplete')
    paths=[ROOT/Path(s['verification']).parent/'native-motion.fbx' for s in native['states']]
    baseline=Document(paths[0]);reports=[]
    for state,path in zip(native['states'],paths):
        if digest(ROOT/'generated/workspace'/state['resource'])!=state['sha256']:raise ValueError('Native resource changed')
        other=Document(path)
        for lod,(a,b) in enumerate(zip(baseline.meshes,other.meshes)):
            if len(a.array('Vertices'))!=len(b.array('Vertices')):raise ValueError('Morph vertex count mismatch')
            np.testing.assert_array_equal(a.array('PolygonVertexIndex'),b.array('PolygonVertexIndex'))
            for layer in [c for c in a.children if c.name=='LayerElementUV']:
                target=next(c for c in b.children if c.name==layer.name and c.values==layer.values)
                np.testing.assert_array_equal(layer.array('UV'),target.array('UV'))
            sa,sb=baseline.skin(a),other.skin(b)
            if [n for n,c in sa]!=[n for n,c in sb]:raise ValueError('Morph skin names differ')
            for (_,ca),(_,cb) in zip(sa,sb):
                for field in ['Indexes','Weights','Transform','TransformLink']:np.testing.assert_array_equal(ca.array(field),cb.array(field))
            reports.append(dict(ui=state['ui'],lod=lod,vertices=len(b.array('Vertices'))//3,indices=len(b.array('PolygonVertexIndex')),nativeLayoutIdentical=True))
    cage=ROOT/bank['cage'];seam=area=0.;minimum_area=float('inf')
    for lod in range(2):
        old=np.load(cage/f'motion-lod{lod}.npz');neutral=np.load(job/f'ui-50-lod{lod}.npz')
        np.testing.assert_array_equal(old['points'],neutral['points'])
        fit=read_json(ROOT/bank['fit']);bindings=np.load((ROOT/bank['fit']).parent/fit['lods'][lod]['bindings'])
        for a,b in zip(bank['states'],bank['states'][1:]):
            pa=np.load(job/f'ui-{a["ui"]}-lod{lod}.npz')['points'];pb=np.load(job/f'ui-{b["ui"]}-lod{lod}.npz')['points']
            for ratio in np.linspace(0,1,11):
                points=pa+(pb-pa)*ratio;f=points[neutral['faces']]
                minimum_area=min(minimum_area,float(np.linalg.norm(np.cross(f[:,1]-f[:,0],f[:,2]-f[:,0]),axis=1).min()))
                seam=max(seam,float(np.linalg.norm(points[bindings['body_seam']]-points[bindings['module_seam']],axis=1).max()))
    if seam>1e-8 or minimum_area<1e-10:raise ValueError('Interpolated geometry breaks weld or collapses a triangle')
    # Replay the native translation/rotation instruction blocks with grown pivots.
    rig=read_json(ROOT/'build/motion/player-stack-257de2350512/player-rig.json');_,_,world=rig_world(rig['_chunks']['CSkeleton #0']['_vars'])
    bind=np.asarray([np.linalg.inv(world[9])@w for w in world[94:]])
    from fixed_physics import generate
    oracle=NativeRotationOracle(settings()['redkit']/'bin/x64_RedKit/editor.exe');max_error=0.;count=0
    try:
        for state in bank['states']:
            folder=job/('pivot-ui-'+str(state['ui']));folder.mkdir(exist_ok=True)
            script,_=generate(settings()['base'],rig,folder,cage=cage,mechanics=state['mechanics'],surface_points=np.load(job/f'ui-{state["ui"]}-lod0.npz')['points'])
            pivots=np.asarray([[float(v) for v in text.split(',')[:3]] for text in re.findall(r'jointRestPoints\[\d+\] = Vector\(([^)]+)\);',script)])
            if len(pivots)!=10:raise ValueError('Incomplete material pivots')
            for i in range(10):
                p=bind[i,:3,3];b=bind[i,:3,:3];m=pivots[i]
                for axis in range(3):
                    for angle in [-.8,0,.8]:
                        q=Rotation.from_rotvec(np.eye(3)[axis]*angle);r=q.as_matrix();current=m+np.array([.01,-.02,.03])
                        translation=current-m+(m-p)-r@(m-p)
                        delivered=oracle.translate(Rotation.from_matrix(b).as_quat(),p,b.T@translation)
                        local=q.as_quat();local[:3]=b.T@local[:3]
                        rb=oracle.xyz(b,script_angles(local,script));skin=rb@b.T
                        vertices=np.vstack([m,m+np.eye(3)*.07])
                        actual=(vertices-p)@skin.T+delivered;expected=(vertices-m)@r.T+current
                        max_error=max(max_error,float(np.abs(actual-expected).max()));count+=1
        evidence=oracle.evidence
    finally:oracle.close()
    if max_error>1e-6:raise ValueError('Native fixed bind does not rotate around grown material pivot')
    report=dict(nativeLayouts=reports,nativeMorphLayoutVerified=True,neutralPointBytesIdentical=True,maximumInterpolatedSeamErrorFBX=seam,minimumInterpolatedTwiceAreaFBX=minimum_area,nativePivotCases=count,maximumNativePivotError=max_error,nativeOracle=evidence,observedGameplay=False,normalPolicy=bank['normalPolicy'])
    write_json(job/'verification.json',report);print('PASS Overall layout/weld/native material pivots',max_error);return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('job',type=Path);verify(p.parse_args().job)
