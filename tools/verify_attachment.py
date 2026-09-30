"""Verify official WCC round-trip anatomy geometry, rig and outer seams."""
import argparse
from collections import Counter
from pathlib import Path
import sys
import numpy as np
from scipy.spatial import cKDTree
from mod import ROOT,settings,digest,write_json
from wcc_fbx import Document,triangles


def oriented_faces(faces):
    return Counter(tuple(np.roll(f,-int(np.argmin(f)))) for f in faces)


def skin_weights(document,mesh,names):
    count=len(mesh.array('Vertices'))//3;weights=np.zeros((count,len(names)))
    for name,cluster in document.skin(mesh):weights[cluster.array('Indexes'),names.index(name)]=cluster.array('Weights')
    return weights


def verify(source,native,output):
    cfg=settings();sys.path.insert(0,str(cfg['base']))
    from malemod_base.graft import topology_ids,boundary_loops
    source,native=Path(source),Path(native)
    original=Document(source);roundtrip=Document(native)
    stock=Document(ROOT/'build/probe/geralt_lower.fbx')
    torso=Document(ROOT/'build/inspection/candidates/t_01_mg__body_hires.fbx')
    if len(original.meshes)!=2 or len(roundtrip.meshes)!=2:raise ValueError('Missing native LOD')
    reports=[]
    for lod,(a,b,s,t) in enumerate(zip(original.meshes,roundtrip.meshes,stock.meshes,torso.meshes)):
        p=a.array('Vertices').reshape(-1,3);q=b.array('Vertices').reshape(-1,3)
        distance,nearest=cKDTree(p).query(q)
        if distance.max()>3e-5:raise ValueError('Native geometry changed beyond float32 tolerance')
        keep,ids=topology_ids(p)
        if oriented_faces(ids[triangles(a)])!=oriented_faces(ids[nearest[triangles(b)]]):
            raise ValueError('Native triangle topology or winding changed')
        oldskin=original.skin(a);newskin=roundtrip.skin(b);names=[n for n,c in oldskin]
        if names!=[n for n,c in newskin]:raise ValueError('Native skin bone list changed')
        bind_error=0.
        for (_,x),(_,y) in zip(oldskin,newskin):
            for key in ['Transform','TransformLink']:
                delta=float(np.max(abs(x.array(key)-y.array(key))));bind_error=max(bind_error,delta)
        if bind_error>3e-5:raise ValueError('Native bind transforms changed')
        sw=skin_weights(original,a,names);nw=skin_weights(roundtrip,b,names)
        skin_error=float(np.max(abs(sw[nearest]-nw)))
        if skin_error>1/255+1e-6:raise ValueError('Native skin weights changed beyond one quantization step')
        binding=np.load(source.with_name(source.stem+f'-lod{lod}.bindings.npz'))
        body=binding['body_original_points'];k,bi=topology_ids(body)
        border=np.concatenate(boundary_loops(bi[binding['body_original_faces']]))
        border=k[border]
        np.testing.assert_array_equal(p[border],body[border])
        stock_names=[name for name,c in stock.skin(s)]
        if stock_names!=names:raise ValueError('Original body skeleton differs')
        stock_w=skin_weights(stock,s,names)
        np.testing.assert_allclose(sw[border],stock_w[border],atol=1e-12,rtol=0)
        # Position duplicates at the graft may have different UVs but must use
        # the same native weights after cooker packing/quantization.
        seam_error=0.;weight_seam_error=0.
        for index in binding['body_seam']:
            candidates=cKDTree(q).query_ball_point(p[index],3e-5)
            if not candidates:raise ValueError('Native graft seam vertex missing')
            pts=q[candidates];ws=nw[candidates]
            seam_error=max(seam_error,float(np.linalg.norm(pts-pts[0],axis=1).max()))
            weight_seam_error=max(weight_seam_error,float(abs(ws-ws[0]).max()))
        if seam_error>3e-5 or weight_seam_error>1e-6:raise ValueError('Native seam aliases diverged')
        loops=boundary_loops(bi[binding['body_original_faces']]);waist=k[max(loops,key=lambda l:body[k[l],2].mean())]
        upper=t.array('Vertices').reshape(-1,3);waist_dist,upper_idx=cKDTree(upper).query(body[waist])
        # This measures stock resource alignment; nearest vertices are not
        # necessarily matching donors when LOD tessellations differ.
        common_names=sorted(set(names)|{n for n,c in torso.skin(t)})
        lower_w=skin_weights(stock,s,common_names)[waist];upper_w=skin_weights(torso,t,common_names)[upper_idx]
        report={'lod':lod,'nativeVertices':len(q),'triangles':len(triangles(b)),
                'maximumPositionError':float(distance.max()),'maximumBindTransformError':bind_error,
                'maximumSkinWeightError':skin_error,'maximumSeamAliasPositionError':seam_error,
                'maximumSeamAliasWeightError':weight_seam_error,'outerBoundaryUnchanged':True,
                'stockWaistNearestVertexMaximumDistance':float(waist_dist.max()),
                'stockWaistNearestVertexMaximumWeightDifference':float(abs(lower_w-upper_w).max()),
                'stockWaistVertices':len(waist)}
        reports.append(report)
    report={'schemaVersion':1,'sourceFBXSHA256':digest(source),'nativeExportSHA256':digest(native),
            'verification':'official WCC import/export; not observed gameplay','lods':reports}
    write_json(output,report);print(report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path);parser.add_argument('native',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();verify(args.source,args.native,args.output)
