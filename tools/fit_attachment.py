"""Fit the pinned Base reference into observed Geralt FBX, preserving native rig.

Game-derived outputs and numerical binding artifacts remain local. Reusable
fitting/field operations are imported from Base, never maintained here.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import numpy as np
from scipy.spatial import cKDTree

from mod import ROOT, settings, base_checkout, digest, read_json, write_json
from wcc_fbx import Document, triangles


def fit(output):
    cfg=settings()
    base_checkout(cfg)
    sys.path.insert(0,str(cfg['base']))
    from malemod_base.graft import (topology_ids,boundary_loops,fit_graft,
                                   extend_seam_field,smooth_normals,limit_influences,preserve_orientation)
    profile=read_json(ROOT/'characters/geralt-attachment.json')
    source=ROOT/profile['nativeExport'];output=Path(output).resolve()
    if not output.is_relative_to(ROOT/'build') or output.suffix!='.fbx' or output.exists():
        raise ValueError('Choose a new .fbx path inside build/')
    if digest(cfg['depot']/profile['nativeResource'])!=profile['nativeResourceSHA256']:
        raise ValueError('Native stock resource changed; recalibrate explicitly')
    if digest(source)!=profile['referenceExportSHA256']:
        export_provenance=read_json(source.with_suffix('.provenance.json'))
        if (export_provenance['sourceSHA256']!=profile['nativeResourceSHA256'] or
                export_provenance['outputSHA256']!=digest(source)):
            raise ValueError('Export does not match the pinned native stock resource')
    output.parent.mkdir(parents=True,exist_ok=True)
    bank_path=cfg['base']/profile['sourceMesh'];bank=np.load(bank_path)
    p=bank['derived__final_reference_positions'].astype(float)
    f=bank['neck_render_data__nrIndices'].reshape(-1,3)[:,[0,2,1]]
    keep,ids=topology_ids(p);loops=boundary_loops(ids[f])
    if len(loops)!=1:raise ValueError('Expected one reference attachment boundary')
    boundary=p[keep[loops[0]]];root=(boundary.min(0)+boundary.max(0))/2
    scale=profile['targetBoundaryWidth']/np.ptp(boundary[:,1])
    basis=np.asarray(profile['basis']);target=np.asarray(profile['targetRoot']);projection=np.asarray(profile['projection'])
    if not np.allclose(basis@basis.T,np.eye(3)) or np.linalg.det(basis)<0:raise ValueError('Invalid calibrated basis')
    aligned=(p-root)@basis.T*scale+target
    document=Document(source)
    global_properties={n.values[0]:n.values[4:] for n in document.root('GlobalSettings').child('Properties70').children}
    for name in ['UnitScaleFactor','OriginalUnitScaleFactor']:
        expected=profile['units'][name[0].lower()+name[1:]]
        if global_properties[name]!=[expected]:raise ValueError('Native units changed')
    reports=[]
    for lod,mesh in enumerate(document.meshes):
        print(f'Fitting native LOD {lod}',flush=True)
        body=mesh.array('Vertices').reshape(-1,3).copy();body_faces=triangles(mesh)
        k,alias=topology_ids(body);outer=np.concatenate(boundary_loops(alias[body_faces]))
        centroid=body[body_faces].mean(1);rx,rz=profile['openingRadii']
        remove=((centroid[:,0]-target[0])/rx)**2+((centroid[:,2]-target[2])/rz)**2<1
        remove &= centroid[:,1]>0
        remove[np.isin(alias[body_faces],outer).any(1)]=False
        g=fit_graft(body,body_faces,aligned,f,remove,projection,target,profile['supportDistance'])
        n=g.body_count;module=g.points[n:];module_faces=g.faces[len(g.body_face_lineage):]-n
        seam=g.module_seam-n
        repaired,repair=preserve_orientation(g.module_lineage@aligned,module,module_faces,seam,
                                             profile['maximumLocalRepair'])
        g.points[n:]=repaired
        clusters=document.skin(mesh);names=[name for name,_ in clusters]
        if len(set(names))!=len(names) or profile['pelvisBone'] not in names:raise ValueError('Ambiguous or missing pelvis binding')
        weights=np.zeros((len(body),len(names)))
        for j,(_,cluster) in enumerate(clusters):weights[cluster.array('Indexes'),j]=cluster.array('Weights')
        stock_sums=weights.sum(1)
        if np.any(stock_sums<1-4/255) or np.any(stock_sums>1+2e-6):
            raise ValueError('Stock skin weight sums exceed observed byte-quantization tolerance')
        bw=g.body_lineage@weights;far=np.zeros(len(names));far[names.index(profile['pelvisBone'])]=1
        mw=extend_seam_field(module,module_faces,seam,bw[g.body_seam],far,profile['supportDistance'])
        full_weights=np.vstack([bw,mw]);full_weights[np.abs(full_weights)<1e-10]=0
        if np.any(full_weights < -1e-10):raise ValueError('Negative skin weights')
        # Native source has four influences per vertex. Retain the strongest
        # four deterministically, identically for every seam alias.
        full_weights,discarded=limit_influences(full_weights,4,profile['skinDiscardBudget'])
        np.testing.assert_allclose(full_weights[g.body_seam],full_weights[g.module_seam],atol=1e-12)
        for j,(_,cluster) in enumerate(clusters):
            used=np.flatnonzero(full_weights[:,j]>0)
            cluster.set_array('Indexes',used);cluster.set_array('Weights',full_weights[used,j])
        normals=smooth_normals(g.points,g.faces)
        for layer in mesh.children:
            if not layer.name.startswith('LayerElement'):continue
            if layer.name=='LayerElementMaterial':
                material=layer.array('Materials')
                if np.any(material!=0):raise ValueError('Expected one stock skin material per LOD')
                layer.set_array('Materials',np.zeros(len(g.faces),dtype=np.int32));continue
            if layer.child('MappingInformationType').values!=['ByVertice'] or layer.child('ReferenceInformationType').values!=['Direct']:
                raise ValueError('Unsupported native attribute mapping')
            channel,width={'LayerElementNormal':('Normals',3),'LayerElementColor':('Colors',4),
                           'LayerElementUV':('UV',2),'LayerElementReflectionUV':('UV',2)}[layer.name]
            original=layer.array(channel).reshape(-1,width);bvalues=g.body_lineage@original
            if channel=='Normals':
                # Preserve the exact authored outer-body normals, including
                # waist and ankle shading seams. Rebuild locally at the graft.
                distance=cKDTree(g.points[g.body_seam]).query(g.points[:n])[0]
                blend=np.clip(1-distance/3,0,1)[:,None]
                normals[:n]=normals[:n]*blend+bvalues*(1-blend)
                normals[:n]/=np.maximum(np.linalg.norm(normals[:n],axis=1)[:,None],1e-30)
                normals[:n][blend[:,0]==0]=bvalues[blend[:,0]==0]
                normals[g.module_seam]=normals[g.body_seam]
                layer.set_array(channel,normals);continue
            far=bvalues[g.body_seam].mean(0)
            if channel=='UV':
                # Keep a noncollapsed UV field on the whole attachment so the
                # native tangent builder has a valid parameterization. Place
                # the source UV variation in a small stock skin atlas region,
                # then solve an exact boundary correction in Base.
                source_uv=g.module_lineage@bank['derived__final_reference_uv']
                seed=(source_uv-source_uv[seam].mean(0))*profile['stockSkinUVScale']+far
                correction=extend_seam_field(module,module_faces,seam,bvalues[g.body_seam]-seed[seam],
                                             np.zeros(width),profile['supportDistance'])
                mvalues=seed+correction
                _,uv_alias=topology_ids(g.module_lineage@aligned)
                for si,bi in zip(seam,g.body_seam):mvalues[uv_alias==uv_alias[si]]=bvalues[bi]
            else:
                mvalues=extend_seam_field(module,module_faces,seam,bvalues[g.body_seam],far,profile['supportDistance'])
            layer.set_array(channel,np.vstack([bvalues,mvalues]))
        mesh.set_array('Vertices',g.points)
        native_indices=g.faces.copy();native_indices[:,2]=-native_indices[:,2]-1
        mesh.set_array('PolygonVertexIndex',native_indices)
        # Preserve sparse lineage and original UVs in the same versioned binding
        # artifact as generated topology; source support tables stay in Base.
        arrays={'points':g.points,'faces':g.faces,'body_seam':g.body_seam,'module_seam':g.module_seam,
                'body_edge_donors':g.body_edge_donors,'module_edge_donors':g.module_edge_donors,
                'body_face_lineage':g.body_face_lineage,'module_face_lineage':g.module_face_lineage,
                'original_module_uv':bank['derived__final_reference_uv'],'weights':full_weights,
                'removed_body_faces':g.removed_faces,'body_original_points':body,'body_original_faces':body_faces}
        for label,matrix in [('body',g.body_lineage),('module',g.module_lineage)]:
            arrays.update({label+'_lineage_'+key:value for key,value in
                           [('data',matrix.data),('indices',matrix.indices),('indptr',matrix.indptr),('shape',np.array(matrix.shape))]})
        binding=output.with_name(output.stem+f'-lod{lod}.bindings.npz');np.savez_compressed(binding,**arrays)
        tri=g.points[g.faces];areas=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)*.5
        if areas.min()<1e-9:raise ValueError('Degenerate fitted triangle')
        original_normal=np.cross(aligned[f[:,1]]-aligned[f[:,0]],aligned[f[:,2]]-aligned[f[:,0]])
        fitted=g.points[g.faces[len(g.body_face_lineage):]]
        fitted_normal=np.cross(fitted[:,1]-fitted[:,0],fitted[:,2]-fitted[:,0])
        agreement=(original_normal[g.module_face_lineage]*fitted_normal).sum(1)
        if np.any(agreement<=0):
            bad=np.flatnonzero(agreement<=0)
            raise ValueError(f'Rest fitting inverted {len(bad)} attachment triangles; centers {fitted[bad].mean(1)[:8]}')
        # Exercise distinct limb/pelvis affine transforms; seam positions and
        # weights must coincide. This is offline skinning, not game animation.
        rng=np.random.default_rng(417+lod);pose_error=0.
        for _ in range(12):
            transforms=np.tile(np.eye(3),(len(names),1,1))+rng.normal(0,.15,(len(names),3,3))
            translation=rng.normal(0,4,(len(names),3))
            bp=np.einsum('bij,nj->nbi',transforms,g.points[g.body_seam])+translation
            mp=np.einsum('bij,nj->nbi',transforms,g.points[g.module_seam])+translation
            delta=(bp*full_weights[g.body_seam,:,None]).sum(1)-(mp*full_weights[g.module_seam,:,None]).sum(1)
            pose_error=max(pose_error,float(np.max(np.linalg.norm(delta,axis=1))))
        reports.append({'lod':lod,'vertices':len(g.points),'triangles':len(g.faces),'seamSamples':len(seam),
                        'removedFaces':len(g.removed_faces),'bones':names,'minimumTriangleArea':float(areas.min()),
                        'invertedAttachmentTriangles':int(np.sum(agreement<=0)),
                        'maximumDiscardedSkinWeight':float(discarded.max()),'offlinePoseSeamError':pose_error,
                        'stockWeightSumRange':[float(stock_sums.min()),float(stock_sums.max())],
                        'orientationRepair':repair,
                        'bindings':binding.name,'bindingsSHA256':digest(binding),
                        'moduleLOD':'full reference topology retained; dedicated reduction remains future work'})
    document.save(output);shutil.copy2(source.with_suffix('.xml'),output.with_suffix('.xml'))
    report={'contractVersion':1,'feature':'surface.rest-graft','baseCommit':read_json(ROOT/'dependencies/base.lock.json')['commit'],
            'profileSHA256':digest(ROOT/'characters/geralt-attachment.json'),'sourceFBXSHA256':digest(source),
            'sourceBankSHA256':digest(bank_path),'sourceRoot':root.tolist(),'sourceToFBXScale':float(scale),
            'outputSHA256':digest(output),'lods':reports,'observedGameplay':False,
            'limitations':['rest reference pose with native skinning','no secondary motion or live dilation',
                           'stock skin atlas detail; source anatomical material transfer pending','module geometry has not been reduced for distant LOD']}
    write_json(output.with_suffix('.fit.json'),report)
    print(json.dumps(report,indent=2))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path)
    fit(parser.parse_args().output)
