"""Generate immutable participation from verified source lineage and bindings."""
import argparse, hashlib, importlib.util, json, struct
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse import coo_matrix,diags
from scipy.sparse.linalg import spsolve

def fnv(data):
    h=14695981039346656037
    for byte in data:h=((h^byte)*1099511628211)&((1<<64)-1)
    return h

def build(binding,base,output):
    binding,base,output=map(Path,[binding,base,output])
    manifest=json.loads((base/'provenance/wolverine.json').read_text())
    expected={r['path']:r['sha256'] for r in manifest['files']}
    spec=importlib.util.spec_from_file_location('geometry_export',base/'tools/export_geometry.py')
    export=importlib.util.module_from_spec(spec);spec.loader.exec_module(export)
    bank={};sources=[]
    for header in ['physics_weights','r14_asset','rounded_render_data','neck_render_data','graft_normals']:
        rel='legacy/wolverine/src/runtime/'+header+'.h';path=base/rel
        sha=hashlib.sha256(path.read_bytes()).hexdigest()
        if sha!=expected[rel]:raise ValueError('Source lineage differs: '+rel)
        sources.append(dict(path=rel,sha256=sha))
        for name,value,_ in export.arrays(path):bank[header+'__'+name]=value
    cage=bank['physics_weights__phys_scrotum_weight']
    coarse=csr_matrix((bank['r14_asset__r14Weight'],bank['r14_asset__r14Sources'],bank['r14_asset__r14Offsets']),shape=(len(bank['r14_asset__r14Offsets'])-1,len(cage)))@cage
    fine=bank['rounded_render_data__rsFineSource'].reshape(-1,3);bary=bank['rounded_render_data__rsFineBary'].reshape(-1,3)
    support=np.r_[coarse,(coarse[fine]*bary).sum(1)]
    direct=bank['neck_render_data__nrDirect'];rows=bank['neck_render_data__nrRows']
    role=csr_matrix((bank['neck_render_data__nrWeights'],bank['neck_render_data__nrSources'],rows),shape=(len(direct),len(support)))@support
    keep=direct!=65535;role[keep]=support[direct[keep]]
    cage_flex=bank['physics_weights__phys_flex_coordinate']
    coarse_flex=csr_matrix((bank['r14_asset__r14Weight'],bank['r14_asset__r14Sources'],bank['r14_asset__r14Offsets']),shape=(len(bank['r14_asset__r14Offsets'])-1,len(cage_flex)))@cage_flex
    support_flex=np.r_[coarse_flex,(coarse_flex[fine]*bary).sum(1)]
    flex=csr_matrix((bank['neck_render_data__nrWeights'],bank['neck_render_data__nrSources'],rows),shape=(len(direct),len(support_flex)))@support_flex
    flex[keep]=support_flex[direct[keep]]
    cage_normal=bank['graft_normals__graftBaseNormals'].reshape(-1,3)
    coarse_normal=csr_matrix((bank['r14_asset__r14Weight'],bank['r14_asset__r14Sources'],bank['r14_asset__r14Offsets']),shape=(len(bank['r14_asset__r14Offsets'])-1,len(cage_normal)))@cage_normal
    support_normal=np.vstack([coarse_normal,(coarse_normal[fine]*bary[:,:,None]).sum(1)])
    normals=csr_matrix((bank['neck_render_data__nrWeights'],bank['neck_render_data__nrSources'],rows),shape=(len(direct),len(support_normal)))@support_normal
    normals[keep]=support_normal[direct[keep]]
    raw=binding.read_bytes();at=48
    if raw[:8]!=b'MMBIND03':raise ValueError('Expected shared-waist binding')
    def take(dtype,n):
        nonlocal at
        a=np.frombuffer(raw,dtype,n,at).copy();at+=a.nbytes;return a
    def u():return int(take('<u4',1)[0])
    def seq(dtype,width=1):return take(dtype,u()*width).reshape(-1,width) if width!=1 else take(dtype,u())
    def mapping():
        count=u();offset=seq('<u4');donors=seq('<u4');weights=seq('<f8')
        return csr_matrix((weights,donors,offset),shape=(len(offset)-1,count))
    take('<f8',16);anatomy=seq('<f8',3);seq('<f8',3)
    if len(anatomy)!=len(role):raise ValueError('Source material lineage count differs')
    count=u()
    if count!=2:raise ValueError('Expected both LODs')
    data=bytearray(b'MMPREC03'+raw[8:48]+struct.pack('<QI',fnv(raw),count));reports=[]
    for lod in range(count):
        points=seq('<f8',3);faces=seq('<u4',3)
        take('u1',u()*20);seq('<u4');seq('<u4');rest=seq('<f8',3);seq('<f8',3)
        aliases=seq('<u4');unique=seq('<u4');seq('<u4');body_count=u();mapping();module=mapping()
        mapped=module@role
        t=np.clip((.98-mapped)/.28,0,1)
        weights=np.r_[np.zeros(body_count),t**3*(10+t*(-15+6*t))].astype('<f8')
        normal=module@normals
        angles=np.r_[np.zeros(body_count),np.arctan2(normal[:,2],normal[:,1])].astype('<f8')
        stations=np.r_[np.zeros(body_count),module@flex].astype('<f8')
        # Surface normals are not an injective angular chart at the graft.
        # Extend the ordered body boundary and healthy shaft coordinates over
        # actual connected geometry, with positive graph weights. Positions,
        # source lineage, UVs and boundary bindings are never re-smoothed here.
        opening_unique=np.unique(aliases[np.flatnonzero(np.arange(len(aliases))>=body_count)][aliases[np.flatnonzero(np.arange(len(aliases))>=body_count)]<len(points)])
        shared=np.intersect1d(aliases[:body_count],aliases[body_count:])
        center=points[shared].mean(0)
        ua=angles[unique].copy();us=stations[unique].copy();uw=weights[unique]
        body=unique<body_count
        ua[body]=np.arctan2(points[body,2]-center[2],points[body,1]-center[1]);us[body]=0
        edges=np.unique(np.sort(np.vstack([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1),axis=0)
        x,y=edges.T;w=1/np.maximum(np.linalg.norm(points[x]-points[y],axis=1),.05)
        graph=coo_matrix((np.r_[w,w],(np.r_[x,y],np.r_[y,x])),shape=(len(points),len(points))).tocsr()
        L=diags(np.asarray(graph.sum(1)).ravel())-graph
        free=np.flatnonzero((~body)&(us<.30)&(uw>0));fixed=np.setdiff1d(np.arange(len(points)),free)
        boundary=np.column_stack([np.cos(ua),np.sin(ua),us]);chart=spsolve(L[free][:,free].tocsc(),-L[free][:,fixed]@boundary[fixed]);boundary[free]=chart
        ua=np.arctan2(boundary[:,1],boundary[:,0]);us=boundary[:,2]
        original_stations=stations.copy()
        angles=ua[aliases].astype('<f8');stations=us[aliases].astype('<f8')
        stations[original_stations<=.002]=0
        if len(weights)!=len(rest):raise ValueError('Material binding size differs')
        # Keep the unsaturated source ownership as well: the recruitment
        # response intentionally saturates at role .70 and cannot distinguish
        # shaft tissue from the mixed lower junction during articulation.
        # Subdivision donors can extrapolate slightly outside [0,1]. Bound
        # the classification score; retain the raw range in provenance.
        roles=np.r_[np.ones(body_count),np.clip(mapped,0,1)].astype('<f8')
        data+=struct.pack('<I',len(weights))+weights.tobytes()+angles.tobytes()+stations.tobytes()+roles.tobytes()
        reports.append(dict(lod=lod,renderCount=len(rest),scrotalCoreExcluded=int((mapped>=.98).sum()),uniqueCount=len(points),chartFreeVertices=len(free),stationRange=[float(stations.min()),float(stations.max())],rawRoleRange=[float(mapped.min()),float(mapped.max())],boundedRoleRows=int(((mapped<0)|(mapped>1)).sum())))
    if at!=len(raw):raise ValueError('Trailing binding data')
    data+=struct.pack('<Q',fnv(data));output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(data)
    proof=dict(schema='malemod.progressive-recruitment/3',bindingSHA256=hashlib.sha256(raw).hexdigest(),bindingRevision=raw[8:48].decode(),artifactSHA256=hashlib.sha256(data).hexdigest(),sourceHeaders=sources,lods=reports)
    output.with_suffix('.json').write_text(json.dumps(proof,indent=2),encoding='utf-8');print(json.dumps(proof))
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--binding',required=True);parser.add_argument('--base',required=True);parser.add_argument('--output',required=True);args=parser.parse_args();build(args.binding,args.base,args.output)
