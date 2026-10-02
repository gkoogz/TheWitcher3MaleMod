"""Verify the complete C++ Geralt lineage/field/collar composition offline.

The fixture codec carries geometry only, with zero unused lighting attributes.
It is never installed or presented as a native normal/tangent rendering test.
"""
import argparse,json,struct,subprocess,sys
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix
from mod import ROOT,settings,base_checkout,read_json,write_json,digest


def fixture(surface,mechanics,path):
    with path.open('wb') as f:
        def array(a,t='<f4'):f.write(np.asarray(a,dtype=t).tobytes())
        f.write(struct.pack('<I',3))
        for points,uv in [(surface['positions'],surface['uv']),(surface['body0'],None),(surface['body1'],None)]:
            n=len(points);f.write(struct.pack('<I',n));array(points);array(np.zeros((n,3)));array(np.zeros((n,3)))
            array(uv if uv is not None else np.zeros((n,2)));array(np.arange(n),'<u4')
        indices=surface['indices'].flatten();f.write(struct.pack('<I',len(indices)));array(indices,'<u4')
        array([mechanics['proximalRadius'],mechanics['restLength']])
        for k in ['shaftGuide','restGuide','lobeCenters','lobeAnchors','lobeRadii','lobeAxes','rootDirection','bendMultipliers']:array(mechanics[k])
        metric=mechanics['collarMetric']
        for k in ['root','axis','up']:array(metric[k])
        array([metric['radius'],metric['length']]);f.write(struct.pack('<I',metric['generation']))


def verify(bindings,job,executable,output,source_cases=()):
    cfg=settings();pin=base_checkout(cfg);sys.path.insert(0,str(cfg['base']))
    from malemod_base.graft import topology_ids,boundary_loops
    from malemod_base.graft_collar import GraftCollar
    from malemod_base.collar import CollarFrame,recruitment
    from malemod_base.recruitment_transfer import SourceBodyField
    bindings=Path(bindings).resolve();job=Path(job).resolve();output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    artifact=bindings/'geralt.bindings';receipt=read_json(bindings/'manifest.json')
    if receipt['baseCommit']!=pin['commit'] or receipt['artifactSHA256']!=digest(artifact):raise ValueError('Binding artifact differs')
    bank=read_json(job/'overall.json');source=Path(bank['bank']);manifest=read_json(source/'manifest.json')
    neutral=next(r for r in manifest['rows'] if r['ui']==50);truth=np.load(source/neutral['surface']);source_body=np.vstack([truth['body0'],truth['body1']])
    profile=read_json(ROOT/'characters/geralt-attachment.json');fit_path=ROOT/bank['fit'];fit=read_json(fit_path)
    basis=np.asarray(profile['basis'],float);scale=fit['sourceToFBXScale'];root=np.asarray(fit['sourceRoot']);target=np.asarray(profile['targetRoot'])
    to_source=lambda p:(p-target)@basis/scale+root
    domains=[]
    for lod in range(2):
        b=np.load(fit_path.parent/fit['lods'][lod]['bindings']);motion=np.load(ROOT/bank['cage']/f'motion-lod{lod}.npz')
        lineage=csr_matrix((b['module_lineage_data'],b['module_lineage_indices'],b['module_lineage_indptr']),shape=tuple(b['module_lineage_shape']))
        points=to_source(motion['points']);body=len(points)-lineage.shape[0]
        _,stock_alias=topology_ids(b['body_original_points'],1e-5);boundaries=np.concatenate(boundary_loops(stock_alias[b['body_original_faces']]))
        protected=np.flatnonzero(np.isin(stock_alias,boundaries));domain=GraftCollar(points,b['faces'],b['body_seam'],b['module_seam'],b['body_edge_donors'],protected,1e-5/scale)
        domains.append((b,motion,lineage,points,body,protected,domain,SourceBodyField(source_body,points[:body])))
    reports=[]
    cases=[('overall-'+str(row['ui']),np.load(source/row['surface']),read_json(source/row['mechanics'])) for row in manifest['rows']]
    for directory in source_cases:
        directory=Path(directory).resolve();verification=read_json(directory/'verification.json')
        for case in verification['cases']:
            raw=directory/(case['label']+'.xyz')
            if not raw.is_file():raise ValueError('Missing verified source fixture: '+str(raw))
            arrays=dict(positions=np.fromfile(raw,'<f4').reshape(-1,3),indices=np.fromfile(str(raw)+'.indices','<u2').reshape(-1,3),uv=np.fromfile(str(raw)+'.uv','<f4').reshape(-1,2))
            for i in range(2):arrays['body'+str(i)]=np.fromfile(str(raw)+'.body'+str(i),'<f4').reshape(-1,3)
            cases.append((directory.name+'-'+case['label'],arrays,read_json(str(raw)+'.mechanics.json')))
    for label,data,mechanics in cases:
        wire=output/(label+'.wire');fixture(data,mechanics,wire)
        # Wire values are binary32, as is real source output. Compare the same
        # values; decimal JSON is an export representation, not another solver.
        m={k:np.asarray(v,dtype=np.float32).astype(float) for k,v in mechanics['collarMetric'].items()}
        axis=m['axis'][0];axis/=np.linalg.norm(axis);up=m['up'][0];up/=np.linalg.norm(up)
        frame=CollarFrame(tuple(m['root'][0]),tuple(axis),tuple(up),float(m['radius']),float(m['length']),1.)
        prefix=output/label
        result=subprocess.run([str(executable),str(artifact),pin['commit'],str(wire),str(prefix)],check=True,capture_output=True,text=True)
        timings=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
        for lod,(b,motion,lineage,points,body,protected,domain,field) in enumerate(domains):
            delta=np.zeros_like(points);delta[:body]=field.displacement(np.vstack([data['body0'],data['body1']]))
            delta[:body][recruitment(points,frame)[:body]<=1e-4]=0;delta[body:]=lineage@(data['positions'].astype(float)-truth['positions']);delta[protected]=0
            solved=domain.prepare(frame).solve_displacement(delta[domain.unique])[domain.aliases]
            expected=motion['points']/100+solved@basis.T*scale/100
            actual=np.fromfile(str(prefix)+f'-lod{lod}.bin','<f8').reshape(-1,3)
            error=float(np.linalg.norm(actual-expected,axis=1).max());seam=float(np.linalg.norm(actual[b['body_seam']]-actual[b['module_seam']],axis=1).max())
            boundary=float(np.abs(actual[protected]-motion['points'][protected]/100).max(initial=0))
            if error>1e-9 or seam>1e-10 or boundary!=0:raise ValueError(f'Full target composition failed: {label}, LOD {lod}, error {error}, seam {seam}, boundary {boundary}')
            reports.append(dict(label=label,lod=lod,maximumNativePositionError=error,seamError=seam,protectedBoundaryError=boundary,**{k:v for k,v in timings[lod].items() if k not in ['lod','vertices']}))
        print('PASS complete target composition',label,flush=True)
    report=dict(baseCommit=pin['commit'],artifactSHA256=digest(artifact),recipeSHA256=digest(Path(__file__)),executableSHA256=digest(executable),
        offlineOnly=True,nativeVertexOutput=False,nativeLightingVerified=False,observedGameplay=False,cases=reports)
    write_json(output/'verification.json',report);return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['bindings','job','executable','output']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--source-cases',type=Path,nargs='*',default=[])
    a=p.parse_args();verify(a.bindings,a.job,a.executable.resolve(),a.output,a.source_cases)
