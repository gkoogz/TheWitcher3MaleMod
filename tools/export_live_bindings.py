"""Export the observed Geralt topology/lineage for the full C++ surface path.

Geometry-derived outputs stay ignored. Shared shape/recruitment math comes from
the pinned Base; this recipe owns only character calibration and engine lineage.
"""
import argparse,struct,sys
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix
from mod import ROOT,settings,base_checkout,read_json,write_json,digest


def export(job,output):
    cfg=settings();pin=base_checkout(cfg);sys.path.insert(0,str(cfg['base']))
    from malemod_base.graft import topology_ids,boundary_loops
    from malemod_base.graft_collar import GraftCollar
    from malemod_base.recruitment_transfer import SourceBodyField
    job=Path(job).resolve();output=Path(output).resolve()
    if not job.is_relative_to(ROOT/'build') or not output.is_relative_to(ROOT/'build'):
        raise ValueError('Character binding artifacts must stay in owned build jobs')
    if output.exists():raise ValueError('Do not overwrite a binding artifact')
    output.mkdir(parents=True)
    bank=read_json(job/'overall.json');source=Path(bank['bank']);manifest=read_json(source/'manifest.json')
    row=next(r for r in manifest['rows'] if r['ui']==50)
    truth=np.load(source/row['surface']);source_body=np.vstack([truth['body0'],truth['body1']])
    profile=read_json(ROOT/'characters/geralt-attachment.json');fit_path=ROOT/bank['fit'];fit=read_json(fit_path)
    calibration=read_json(ROOT/'characters/geralt-runtime-bindings.json')['coordinateCalibration']
    basis=np.asarray(profile['basis'],float);scale=fit['sourceToFBXScale'];root=np.asarray(fit['sourceRoot']);target=np.asarray(profile['targetRoot'])
    to_source=lambda p:(p-target)@basis/scale+root
    rows=[]
    artifact=output/'geralt.bindings'
    with artifact.open('wb') as f:
        def array(a,dtype):
            a=np.asarray(a,dtype=dtype);f.write(struct.pack('<I',len(a)));f.write(a.tobytes())
        def sparse(m):
            m=csr_matrix(m);f.write(struct.pack('<I',m.shape[1]));array(m.indptr,'<u4');array(m.indices,'<u4');array(m.data,'<f8')
        f.write(b'MMBIND02');f.write(pin['commit'].encode('ascii'))
        f.write(np.asarray(basis,dtype='<f8').tobytes());f.write(np.asarray(root,dtype='<f8').tobytes())
        f.write(np.asarray(calibration['targetRootNative'],dtype='<f8').tobytes())
        f.write(struct.pack('<d',calibration['nativeUnitsPerSourceUnit']))
        array(truth['positions'],'<f8');array(source_body,'<f8');f.write(struct.pack('<I',2))
        for lod in range(2):
            binding_path=fit_path.parent/fit['lods'][lod]['bindings'];bindings=np.load(binding_path)
            motion_path=ROOT/bank['cage']/f'motion-lod{lod}.npz';motion=np.load(motion_path)
            lineage=csr_matrix((bindings['module_lineage_data'],bindings['module_lineage_indices'],bindings['module_lineage_indptr']),shape=tuple(bindings['module_lineage_shape']))
            points=to_source(motion['points']);body=len(points)-lineage.shape[0]
            _,stock_alias=topology_ids(bindings['body_original_points'],1e-5)
            boundaries=np.concatenate(boundary_loops(stock_alias[bindings['body_original_faces']]))
            protected=np.flatnonzero(np.isin(stock_alias,boundaries))
            domain=GraftCollar(points,bindings['faces'],bindings['body_seam'],bindings['module_seam'],bindings['body_edge_donors'],protected,1e-5/scale)
            field=SourceBodyField(source_body,points[:body])
            field_matrix=csr_matrix((field.weights.flatten(),field.donors.flatten(),np.arange(body+1)*field.donors.shape[1]),shape=(body,len(source_body)))
            array(domain.rest,'<f8');array(domain.faces,'<u4');f.write(struct.pack('<I',len(domain.seams)))
            for slave,a,b,w in domain.seams:f.write(struct.pack('<3Id',slave,a,b,w))
            array(domain.locked,'<u4');array(points,'<f8');array(motion['points']/100,'<f8')
            array(domain.aliases,'<u4');array(domain.unique,'<u4');array(protected,'<u4');f.write(struct.pack('<I',body))
            sparse(field_matrix);sparse(lineage)
            rows.append(dict(lod=lod,renderVertices=len(points),uniqueVertices=len(domain.rest),bodyVertices=body,
                bindingPath=binding_path.relative_to(ROOT).as_posix(),bindingSHA256=digest(binding_path),motionSHA256=digest(motion_path)))
    receipt=dict(contractVersion=2,baseCommit=pin['commit'],sourceGeometryCommit=read_json(cfg['base']/'provenance/wolverine.json')['commit'],
        artifact=artifact.name,artifactSHA256=digest(artifact),recipeSHA256=digest(Path(__file__)),
        neutralSourceSHA256=digest(source/row['surface']),sourceBankSHA256=digest(source/'manifest.json'),
        fitSHA256=digest(fit_path),coordinateCalibration=calibration,lods=rows,nativeVertexOutput=False,observedGameplay=False)
    write_json(output/'manifest.json',receipt);print('Exported full Geralt bindings:',output)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--job',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();export(a.job,a.output)
