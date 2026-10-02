"""Compare the C++ Base graft solver with the established Geralt Python domain.

This is offline character-binding verification; no game installation or native
vertex output is inferred from it. The source solver still owns morphology.
"""
import argparse,struct,sys,time,subprocess,re
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix
from mod import ROOT,read_json,write_json,digest

def verify(base, executable, job, output):
    base=Path(base).resolve();sys.path.insert(0,str(base))
    from malemod_base.graft import topology_ids,boundary_loops
    from malemod_base.graft_collar import GraftCollar
    from malemod_base.collar import CollarFrame,recruitment
    from malemod_base.recruitment_transfer import SourceBodyField
    job=Path(job).resolve();output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    bank=read_json(job/'overall.json');source=Path(bank['bank']);source_bank=read_json(source/'manifest.json')
    neutral=next(r for r in source_bank['rows'] if r['ui']==50)
    truth=np.load(source/neutral['surface']);source_body=np.vstack([truth['body0'],truth['body1']])
    cage=ROOT/bank['cage'];fit_path=ROOT/bank['fit'];fit=read_json(fit_path);profile=read_json(ROOT/'characters/geralt-attachment.json')
    basis=np.asarray(profile['basis']);scale=fit['sourceToFBXScale'];root=np.asarray(fit['sourceRoot']);target=np.asarray(profile['targetRoot'])
    to_source=lambda p:(p-target)@basis/scale+root
    reports=[]
    for lod in range(2):
        bindings=np.load(fit_path.parent/fit['lods'][lod]['bindings']);motion=np.load(cage/f'motion-lod{lod}.npz')
        lineage=csr_matrix((bindings['module_lineage_data'],bindings['module_lineage_indices'],bindings['module_lineage_indptr']),shape=tuple(bindings['module_lineage_shape']))
        points=to_source(motion['points']);body=len(points)-lineage.shape[0]
        _,stock_alias=topology_ids(bindings['body_original_points'],1e-5)
        boundaries=np.concatenate(boundary_loops(stock_alias[bindings['body_original_faces']]))
        protected=np.flatnonzero(np.isin(stock_alias,boundaries))
        domain=GraftCollar(points,bindings['faces'],bindings['body_seam'],bindings['module_seam'],bindings['body_edge_donors'],protected,1e-5/scale)
        field=SourceBodyField(source_body,points[:body])
        for row in source_bank['rows']:
            data=np.load(source/row['surface']);mechanics=read_json(source/row['mechanics'])
            axis=np.asarray(mechanics['rootDirection'][0]);axis/=np.linalg.norm(axis);up=np.cross(axis,[0,1,0]);up/=np.linalg.norm(up)
            frame=CollarFrame(tuple(mechanics['shaftGuide'][0]),tuple(axis),tuple(up),mechanics['proximalRadius'],mechanics['restLength'],1.)
            delta=np.zeros_like(points);delta[:body]=field.displacement(np.vstack([data['body0'],data['body1']]))
            delta[:body][recruitment(points,frame)[:body]<=1e-4]=0
            delta[body:]=lineage@(data['positions'].astype(float)-truth['positions']);delta[protected]=0
            plan=domain.prepare(frame);expected=plan.solve_displacement(delta[domain.unique])
            fixture=output/f'ui-{row["ui"]}-lod{lod}.graft';actual_path=fixture.with_suffix('.result')
            with fixture.open('wb') as f:
                f.write(b'GRAFT001');f.write(struct.pack('<4I',len(domain.rest),len(domain.faces),len(domain.seams),len(domain.locked)))
                f.write(np.asarray(domain.rest,dtype='<f8').tobytes());f.write(np.asarray(domain.faces,dtype='<u4').tobytes())
                for slave,a,b,w in domain.seams:f.write(struct.pack('<3Id',slave,a,b,w))
                f.write(np.asarray(domain.locked,dtype='<u4').tobytes());f.write(np.asarray([frame.root,frame.axis,frame.up],dtype='<f8').tobytes())
                f.write(struct.pack('<3d',frame.radius,frame.length,frame.source_length_scale));f.write(np.asarray(delta[domain.unique],dtype='<f8').tobytes())
            start=time.perf_counter();process=subprocess.run([str(executable),str(fixture),str(actual_path)],check=True,capture_output=True,text=True)
            elapsed=(time.perf_counter()-start)*1000
            actual=np.fromfile(actual_path,'<f8').reshape(-1,3)
            actual_mask=np.fromfile(str(actual_path)+'.weights','<f8')
            mask_error=float(np.abs(actual_mask-recruitment(domain.rest,frame)).max())
            if mask_error>1e-12:raise ValueError('Shared C++ recruitment weight differs: '+str(mask_error))
            changed_weights=np.fromfile(str(actual_path)+'.updated.weights','<f8').reshape(5,len(domain.rest))
            changed_error=0.
            for i in range(5):
                angle=(i-2)*.011;yaw=(i-2)*.013;a=np.array(frame.axis,float)
                a=np.array([a[0]*np.cos(angle)-a[2]*np.sin(angle),0,a[0]*np.sin(angle)+a[2]*np.cos(angle)])
                a=np.array([a[0]*np.cos(yaw)-a[1]*np.sin(yaw),a[0]*np.sin(yaw)+a[1]*np.cos(yaw),a[2]])
                up=np.cross(a,[0,1,0]);up/=np.linalg.norm(up);root_changed=np.array(frame.root,float);root_changed[2]+=(i-2)*.03
                changed=CollarFrame(tuple(root_changed),tuple(a),tuple(up),frame.radius*(1+(i-2)*.013),frame.length*(1+(i-2)*.007),frame.source_length_scale)
                changed_error=max(changed_error,float(np.abs(changed_weights[i]-recruitment(domain.rest,changed)).max()))
            if changed_error>1e-12:raise ValueError('Three-dimensional C++ support differs from Python: '+str(changed_error))
            if actual.shape!=expected.shape:raise ValueError('C++ graft topology differs')
            error=float(np.linalg.norm(actual-expected,axis=1).max())
            if error>1e-8:raise ValueError(f'C++ graft solve differs: UI {row["ui"]} LOD {lod} {error}')
            welded=actual[domain.aliases]
            seam=float(np.linalg.norm(welded[bindings['body_seam']]-welded[bindings['module_seam']],axis=1).max())
            boundary=float(np.abs(actual[domain.locked]).max(initial=0))
            if seam>1e-12 or boundary>1e-12:raise ValueError('C++ graft broke a weld/protected part boundary')
            timing=re.search(r'planMs=(\S+) cachedSolveMs=(\S+)',process.stdout)
            updated=re.search(r'updatedFrameCases=(\d+) updateMs=(\S+) freshPlanMs=(\S+) exactUpdatedReplay=true',process.stdout)
            if not updated:raise ValueError('Updated-frame replay proof is missing')
            reports.append(dict(ui=row['ui'],lod=lod,maximumSourcePositionError=error,recruitmentWeightError=mask_error,threeDimensionalWeightError=changed_error,seamError=seam,protectedBoundaryError=boundary,processMilliseconds=elapsed,planMilliseconds=float(timing[1]) if timing else None,cachedSolveMilliseconds=float(timing[2]) if timing else None,updatedFrameCases=int(updated[1]),updatedFrameMilliseconds=float(updated[2]),freshFrameMilliseconds=float(updated[3]),exactUpdatedReplay=True,fixtureSHA256=digest(fixture),resultSHA256=digest(actual_path)))
            print('PASS live graft',row['ui'],lod,error,'ms',elapsed,flush=True)
    result=dict(offlineOnly=True,observedGameplay=False,nativeVertexOutput=False,sourceBankSHA256=digest(source/'manifest.json'),fitSHA256=digest(fit_path),characterProfileSHA256=digest(ROOT/'characters/geralt-attachment.json'),executableSHA256=digest(executable),cases=reports)
    write_json(output/'verification.json',result);return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--executable',type=Path,required=True);p.add_argument('--job',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();verify(a.base,a.executable.resolve(),a.job,a.output)
