"""Check native cage round-trip, topology, original body and seam weights."""
from pathlib import Path
import sys
import json
import numpy as np
from scipy.spatial import cKDTree
from mod import ROOT,settings,digest,write_json
from wcc_fbx import Document,triangles
from verify_attachment import skin_weights,oriented_faces
from native_joint_frames import verify_rest_axes


def verify(job):
    job=Path(job).resolve();cfg=settings();sys.path.insert(0,str(cfg['base']))
    from malemod_base.graft import topology_ids
    source=job/'geralt-motion.fbx';native=job/'native-motion.fbx'
    rest_axes=verify_rest_axes(json.loads((job/'motion.json').read_text())['authoredWorldRestFBX'])
    original=Document(source);roundtrip=Document(native);reports=[]
    if len(original.meshes)!=2 or len(roundtrip.meshes)!=2:raise ValueError('Missing LOD')
    for lod,(a,b) in enumerate(zip(original.meshes,roundtrip.meshes)):
        p=a.array('Vertices').reshape(-1,3);q=b.array('Vertices').reshape(-1,3)
        tree=cKDTree(q);dist,nearest=cKDTree(p).query(q)
        if dist.max()>3e-5:raise ValueError('Native vertex drift')
        _,ids=topology_ids(p)
        if oriented_faces(ids[triangles(a)])!=oriented_faces(ids[nearest[triangles(b)]]):raise ValueError('Native topology drift')
        oldskin=original.skin(a);newskin=roundtrip.skin(b);names=[n for n,c in oldskin]
        if names!=[n for n,c in newskin]:raise ValueError('Native bone list drift')
        diffs=[abs(x.array(k)-y.array(k)).reshape(4,4).T for (_,x),(_,y) in zip(oldskin,newskin)
                 for k in ['Transform','TransformLink']]
        bind=max(float(d.max()) for d in diffs)
        rotation_error=max(float(d[:3,:3].max()) for d in diffs)
        translation_error=max(float(d[:3,3].max()) for d in diffs)
        # Native Euler/float import accumulates <1e-6 rotation error. With a
        # 100-FBX-unit bind offset that produces <1e-4 inverse-bind translation
        # error (1e-6 in calibrated native units). Gate the two units separately.
        if rotation_error>1e-6 or translation_error>1e-4:raise ValueError('Native bind drift')
        native_frames=np.array([c.array('TransformLink').reshape(4,4).T for n,c in newskin if n.startswith('mm_')])
        native_axes=verify_rest_axes(native_frames,tolerance=1e-5)
        sw=skin_weights(original,a,names);nw=skin_weights(roundtrip,b,names)
        error=float(np.max(abs(sw[nearest]-nw)))
        if error>1/255+1e-6:raise ValueError('Native skin weight drift')
        binding=np.load(job/('motion-lod%d.npz'%lod))
        seam_position=seam_weight=0.
        for index in binding['body_seam']:
            candidates=tree.query_ball_point(p[index],3e-5)
            if not candidates:raise ValueError('Missing native seam vertex')
            seam_position=max(seam_position,float(np.max(abs(q[candidates]-q[candidates[0]]))))
            seam_weight=max(seam_weight,float(np.max(abs(nw[candidates]-nw[candidates[0]]))))
        if seam_position>3e-5 or seam_weight>1e-6:raise ValueError('Native seam divergence')
        reports.append(dict(lod=lod,bones=names,maximumPositionError=float(dist.max()),maximumBindError=bind,
            maximumBindRotationError=rotation_error,maximumBindTranslationError=translation_error,
            nativeRestAxes=native_axes,
            maximumWeightError=error,maximumSeamPositionError=seam_position,maximumSeamWeightError=seam_weight))
    report=dict(sourceSHA256=digest(source),nativeSHA256=digest(native),lods=reports,nativeRestAxes=rest_axes,
                nativeMeshRoundtripVerified=True,nativeDynamicsVerified=False,observedGameplay=False)
    write_json(job/'native-verification.json',report);print(json.dumps(report,indent=2));return report


if __name__=='__main__':verify(sys.argv[1])
