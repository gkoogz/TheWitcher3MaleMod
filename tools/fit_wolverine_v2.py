"""Fit actual canonical anatomy into untouched Geralt through shared exact cutting."""
import hashlib,json,shutil,sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from mod import ROOT,digest,read_json,write_json
from wcc_fbx import Document,triangles
from witcher_v2 import checked_reference


def fit():
    lock,roots=checked_reference()
    sys.path[:0]=[str(roots['base']),str(ROOT.parent/'Work/python')]
    from malemod_base.graft import topology_ids,boundary_loops,extend_seam_field,smooth_normals,limit_influences
    from malemod_base.reference_graft import cut_reference
    profile=read_json(ROOT/'v2/geralt-fit.json')
    base=ROOT/'v2/build/geralt-base/pelvis-legs.fbx'
    source=ROOT/'v2/build/wolverine-reference'/profile['sourceCase']
    receipt=read_json(source.parent/'manifest.json')
    case=next(x for x in receipt['cases']if x['state']==2)
    for name,expected in case['files'].items():
        if digest(source/name)!=expected:raise ValueError('Canonical reference changed: '+name)
    packed=np.fromfile(source/'anatomy.packed','u1').reshape(-1,32)
    module=packed[:,:12].copy().view('<f4').reshape(-1,3).astype(float)
    source_faces=np.fromfile(source/'anatomy.indices','<u2').reshape(-1,3)
    source_normals=packed[:,16:19].astype(float)/255*2-1
    tri=module[source_faces]
    agreement=np.sum(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])*source_normals[source_faces].mean(1),axis=1)
    # Canonical D3D9 anatomy is clockwise. Native Geralt FBX is counterclockwise.
    # Convert the adapter convention, retaining every vertex and face identity.
    if np.mean(agreement<0)>.99:faces=source_faces[:,[0,2,1]]
    elif np.mean(agreement>0)>.99:faces=source_faces.copy()
    else:raise ValueError('Canonical source winding is not a known convention')
    source_uv=packed[:,28:32].copy().view('<f2').reshape(-1,2).astype(float)
    keep,ids=topology_ids(module,1e-4);loop=boundary_loops(ids[faces])[0]
    root=(module[keep[loop]].min(0)+module[keep[loop]].max(0))*.5
    angle=np.radians(profile['pitchDegrees']);c,s=np.cos(angle),np.sin(angle)
    rotation=np.array([[1,0,0],[0,c,-s],[0,s,c]])@np.asarray(profile['basis'])
    aligned=(module-root)@rotation.T+profile['targetRoot']
    document=Document(base);out=ROOT/'v2/build/fitted-geralt';out.mkdir(exist_ok=True)
    output=out/'geralt-wolverine.fbx';reports=[]
    for lod,mesh in enumerate(document.meshes):
        body=mesh.array('Vertices').reshape(-1,3);body_faces=triangles(mesh)
        g=cut_reference(body,body_faces,aligned,faces,profile['projection'],profile['forward'],profile['maximumBodyAdjustmentNativeUnits'])
        n=g.body_count;module_points=g.points[n:];seam=g.seam_module-n
        clusters=document.skin(mesh);names=[name for name,_ in clusters]
        if profile['pelvisBone']not in names:raise ValueError('Observed native pelvis joint missing')
        stock=np.zeros((len(body),len(names)))
        for j,(_,cluster)in enumerate(clusters):stock[cluster.array('Indexes').astype(int),j]=cluster.array('Weights')
        bw=g.body_lineage@stock
        # Repeated geometric seam aliases must share one exact skin field.
        _,aliases=topology_ids(g.points,1e-5)
        for group in np.unique(aliases[g.seam_body]):
            target=np.flatnonzero(aliases[:n]==group);bw[target]=bw[target].mean(0)
        far=np.zeros(len(names));far[names.index(profile['pelvisBone'])]=1
        unique,selected=np.unique(seam,return_index=True)
        mw=extend_seam_field(module_points,g.module_faces,unique,bw[g.seam_body[selected]],far,profile['skinSupportNativeUnits'])
        weights,discarded=limit_influences(np.vstack([bw,mw]),4,.1)
        for b,m in zip(g.seam_body,g.seam_module):weights[m]=weights[b]
        for j,(_,cluster)in enumerate(clusters):
            used=np.flatnonzero(weights[:,j]>0);cluster.set_array('Indexes',used);cluster.set_array('Weights',weights[used,j])
        normals=smooth_normals(g.points,g.faces)
        for layer in mesh.children:
            if not layer.name.startswith('LayerElement'):continue
            if layer.name=='LayerElementMaterial':
                if np.any(layer.array('Materials')!=0):raise ValueError('Unexpected stock material mapping')
                layer.set_array('Materials',np.zeros(len(g.faces),np.int32));continue
            if layer.child('MappingInformationType').values!=['ByVertice']or layer.child('ReferenceInformationType').values!=['Direct']:
                raise ValueError('Unobserved native attribute mapping')
            channel,width={'LayerElementNormal':('Normals',3),'LayerElementColor':('Colors',4),'LayerElementUV':('UV',2),'LayerElementReflectionUV':('UV',2)}[layer.name]
            original=layer.array(channel).reshape(-1,width);body_values=g.body_lineage@original
            if channel=='Normals':
                distance=cKDTree(g.points[g.seam_body]).query(g.points[:n])[0];blend=np.clip(1-distance/3,0,1)[:,None]
                normals[:n]=normals[:n]*blend+body_values*(1-blend);normals[:n]/=np.maximum(np.linalg.norm(normals[:n],axis=1)[:,None],1e-30)
                normals[:n][blend[:,0]==0]=body_values[blend[:,0]==0]
                layer.set_array(channel,normals);continue
            far_value=body_values[g.seam_body].mean(0)
            if channel=='UV':
                source_values=g.module_lineage@source_uv;seed=(source_values-source_values[unique].mean(0))*profile['stockSkinUVScale']+far_value
                correction=extend_seam_field(module_points,g.module_faces,unique,body_values[g.seam_body[selected]]-seed[unique],np.zeros(width),3)
                mv=seed+correction
            else:mv=extend_seam_field(module_points,g.module_faces,unique,body_values[g.seam_body[selected]],far_value,3)
            for b,m in zip(g.seam_body,g.seam_module):mv[m-n]=body_values[b]
            layer.set_array(channel,np.vstack([body_values,mv]))
        mesh.set_array('Vertices',g.points);native=g.faces.copy();native[:,2]=-native[:,2]-1;mesh.set_array('PolygonVertexIndex',native)
        # Exact original stock rows and original canonical module rows remain
        # unchanged; only barycentric edge/face refinement adds source vertices.
        body_move=np.linalg.norm(g.points[:len(body)]-body,axis=1)
        if body_move.max()>profile['maximumBodyAdjustmentNativeUnits']+1e-7:raise ValueError('Original target adjustment exceeds budget')
        np.testing.assert_array_equal(g.points[n:n+len(module)],aligned)
        arrays=dict(points=g.points,faces=g.faces,bodyOriginalPoints=body,bodyOriginalFaces=body_faces,
            seamBody=g.seam_body,seamModule=g.seam_module,bodyCount=n,weights=weights,
            moduleOriginalUV=source_uv,moduleOriginalFaces=source_faces,rotation=rotation,sourceRoot=root,targetRoot=profile['targetRoot'])
        for label,matrix in [('body',g.body_lineage),('module',g.module_lineage)]:
            arrays.update({label+'_'+key:value for key,value in [('data',matrix.data),('indices',matrix.indices),('indptr',matrix.indptr),('shape',matrix.shape)]})
        binding=out/('lod'+str(lod)+'.npz');np.savez_compressed(binding,**arrays)
        tri=g.points[g.faces];area=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)*.5
        if area.min()<1e-9:raise ValueError('Degenerate fitted triangle')
        reports.append(dict(lod=lod,vertices=len(g.points),triangles=len(g.faces),sourceGeometryUnchanged=True,
            originalBodyVerticesChanged=int(np.sum(body_move>1e-12)),maximumOriginalBodyAdjustmentNativeUnits=float(body_move.max()),maximumNewSeamAdjustmentNativeUnits=g.maximum_body_move,
            seamSamples=len(g.seam_body),minimumTriangleArea=float(area.min()),maximumDiscardedWeight=float(discarded.max()),
            bindingsSHA256=digest(binding)))
    document.save(output);shutil.copy2(base.with_suffix('.xml'),output.with_suffix('.xml'))
    report=dict(schema='malemod.witcher-v2-fit/1',profileSHA256=digest(ROOT/'v2/geralt-fit.json'),
        sourceManifestSHA256=digest(source.parent/'manifest.json'),stockExportSHA256=digest(base),
        fbxSHA256=digest(output),lods=reports,sharedFitterSHA256=digest(roots['base']/'malemod_base/reference_graft.py'),
        nativeRoundTripPassed=False,observedGreyRoom=False,attachmentGatePassed=False,
        nativeWindingConversion='canonical clockwise to observed Geralt counterclockwise')
    write_json(out/'manifest.json',report);print(json.dumps(report,indent=2))
    return report


if __name__=='__main__':fit()
