"""Bake evaluated Overall changes onto the approved coupled Geralt graft."""
import argparse,json,sys,uuid
from pathlib import Path
import shutil
import numpy as np
from scipy.sparse import csr_matrix
from mod import ROOT,settings,read_json,write_json,digest
from wcc_fbx import Document

def prepare(bank):
    cfg=settings();sys.path.insert(0,str(cfg['base']))
    from malemod_base.graft import topology_ids,boundary_loops,smooth_normals
    from malemod_base.graft_collar import GraftCollar
    from malemod_base.collar import CollarFrame,recruitment
    from malemod_base.recruitment_transfer import SourceBodyField
    bank=Path(bank).resolve();source=read_json(bank/'manifest.json')
    if source['state']!=2 or source['steps']!=120:raise ValueError('Expected evaluated full-floppy source bank')
    cage=ROOT/read_json(ROOT/'generated/default-cage.json')['cage'];recipe=read_json(cage/'motion.json')
    fit_path=ROOT/recipe['fitReport'];fit=read_json(fit_path);profile=read_json(ROOT/'characters/geralt-attachment.json')
    neutral=next(r for r in source['rows'] if r['ui']==50)
    truth=np.load(bank/neutral['surface']);source_body=np.vstack([truth['body0'],truth['body1']])
    basis=np.asarray(profile['basis']);scale=fit['sourceToFBXScale'];root=np.asarray(fit['sourceRoot']);target=np.asarray(profile['targetRoot'])
    to_source=lambda p:(p-target)@basis/scale+root
    from_source=lambda p:(p-root)@basis.T*scale+target
    job=ROOT/'build/overall'/uuid.uuid4().hex[:12];job.mkdir(parents=True)
    states=[];domains=[]
    for lod in range(2):
        b=np.load(fit_path.parent/fit['lods'][lod]['bindings']);motion=np.load(cage/f'motion-lod{lod}.npz')
        lineage=csr_matrix((b['module_lineage_data'],b['module_lineage_indices'],b['module_lineage_indptr']),shape=tuple(b['module_lineage_shape']))
        points=to_source(motion['points']);body=len(points)-lineage.shape[0]
        _,stock_alias=topology_ids(b['body_original_points'],1e-5)
        boundaries=np.concatenate(boundary_loops(stock_alias[b['body_original_faces']]))
        protected=np.flatnonzero(np.isin(stock_alias,boundaries))
        domain=GraftCollar(points,b['faces'],b['body_seam'],b['module_seam'],b['body_edge_donors'],protected,1e-5/scale)
        field=SourceBodyField(source_body,points[:body])
        np.savez_compressed(job/f'transfer-lod{lod}.npz',donors=field.donors,weights=field.weights,distances=field.distance,protected=protected)
        domains.append((b,motion,lineage,points,body,protected,domain,field))
    for row in source['rows']:
        for key in ['surface','mechanics']:
            if digest(bank/row[key])!=row[key+'SHA256']:raise ValueError('Source bank changed')
        data=np.load(bank/row['surface']);mechanics=read_json(bank/row['mechanics'])
        axis=np.asarray(mechanics['rootDirection'][0]);axis/=np.linalg.norm(axis)
        up=np.cross(axis,[0,1,0]);up/=np.linalg.norm(up)
        frame=CollarFrame(tuple(mechanics['shaftGuide'][0]),tuple(axis),tuple(up),mechanics['proximalRadius'],mechanics['restLength'],1.)
        document=Document(cage/'geralt-motion.fbx');reports=[]
        for lod,(mesh,state) in enumerate(zip(document.meshes,domains)):
            b,motion,lineage,points,body,protected,domain,field=state
            delta=np.zeros_like(points)
            delta[:body]=field.displacement(np.vstack([data['body0'],data['body1']]))
            mask=recruitment(points,frame)
            delta[:body][mask[:body]<=1e-4]=0
            delta[body:]=lineage@(data['positions'].astype(float)-truth['positions'])
            delta[protected]=0
            if row['ui']==50:
                grown=motion['points'].copy();solved=points.copy()
            else:
                solved=domain.solve_recruited(delta,frame);grown=from_source(solved)
            seam=float(np.max(np.linalg.norm(grown[b['body_seam']]-grown[b['module_seam']],axis=1)))
            drift=float(np.max(np.linalg.norm(grown[protected]-motion['points'][protected],axis=1)))
            if seam>1e-8 or drift>1e-8:raise ValueError('Recruitment broke seam/body part boundary')
            triangles=grown[b['faces']];twice=np.linalg.norm(np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0]),axis=1)
            if twice.min()<1e-10:raise ValueError('Recruitment collapsed a triangle')
            mesh.set_array('Vertices',grown)
            # Native importer merges attributes, not just geometric aliases.
            # Independently recomputing normals changed vertex counts across
            # states. Preserve the common approved normal frame and UV/skin
            # classes until native-safe normal transport is calibrated.
            np.savez_compressed(job/f'ui-{row["ui"]}-lod{lod}.npz',points=grown,faces=b['faces'],weights=motion['weights'],fields=motion['fields'])
            reports.append(dict(lod=lod,seamErrorFBX=seam,protectedBoundaryErrorFBX=drift,minimumTwiceTriangleAreaFBX=float(twice.min()),
                                recruitedBodyVertices=int(np.count_nonzero(np.linalg.norm(grown[:body]-motion['points'][:body],axis=1)>1e-7)),
                                maximumBodyMoveFBX=float(np.linalg.norm(grown[:body]-motion['points'][:body],axis=1).max())))
        output=job/f'overall-{row["ui"]}.fbx';document.save(output);shutil.copy2((cage/'geralt-motion.xml'),output.with_suffix('.xml'))
        states.append(dict(ui=row['ui'],fbx=output.relative_to(ROOT).as_posix(),fbxSHA256=digest(output),source=row,reports=reports,mechanics=mechanics))
        print('Prepared Overall',row['ui'],reports,flush=True)
    record=dict(version=1,bank=str(bank),bankSHA256=digest(bank/'manifest.json'),cage=cage.relative_to(ROOT).as_posix(),fit=fit_path.relative_to(ROOT).as_posix(),
                fitSHA256=digest(fit_path),calibratedScale=scale,states=states,neutralRestGeometryUnchanged=True,observedGameplay=False,
                method='evaluated source final anatomy/body deltas; calibrated source-body field and hard original-edge coupled displacement solve',
                normalPolicy='shared approved neutral normal frame to preserve native attribute merge classes; changed-size normal transport deferred')
    write_json(job/'overall.json',record);print(job);return job

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('bank',type=Path);prepare(p.parse_args().bank)
