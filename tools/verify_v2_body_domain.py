"""Replay a complementary-body donor correction against actual source captures.

This is CPU-only diagnosis. The output binding is an isolated comparison input,
never adopted or installed. Source anatomy, stock baselines, skin weights and
physical weld constraints remain byte-exact. Surface orientation relative to a
rest normal is reported as a diagnostic, not a 3D self-intersection certificate.
"""
import argparse,hashlib,json,struct,sys
from pathlib import Path
import numpy as np
from mod import ROOT,digest,write_json
from v2_native_binding import read_binding,cooked_resource
from v2_source_precision import parse_b04
from bind_wolverine_v2 import complete_body_domain,nearest_triangle


def stats(values):
    return dict(median=float(np.median(values)),p95=float(np.quantile(values,.95)),maximum=float(np.max(values)))


def repair_candidate(bindings):
    bindings=Path(bindings);path=bindings/'geralt-source-binding.bin';original=path.read_bytes();b=read_binding(path)
    if b['version']!=4:raise ValueError('The actual B04 baseline is required')
    source=b['positions'];build=ROOT/'v2/build'
    vertices,faces=complete_body_domain([source[17528:32696],source[32696:]],[np.load(build/'source-body0.npz')['faces'],np.load(build/'source-body1.npz')['faces']])
    result=bytearray(original);changes=[];tables=parse_b04(original)
    for r,table in zip(b['resources'],tables):
        for s in r['sections']:
            if s['material']:continue
            sl=slice(s['firstVertex'],s['firstVertex']+s['vertexCount']);rows=r['rows'][sl]
            native=rows['baseline'][:,:12].copy().view('<f4').reshape(-1,3)*np.asarray(r['scale'])+np.asarray(r['bias'])
            donor,weight,distance=nearest_triangle((native*100-b['targetRoot'])@b['rotation']+b['sourceRoot'],vertices,faces);donor+=17528
            # Existing physical welds have exact anatomy CSR lineage. Their
            # rows are never replaced by an independently projected body donor.
            protected=np.any((rows['donors']<17528)&(rows['weights']>1e-12),axis=1)
            for i in np.flatnonzero(~protected):
                at=table['rowoffset']+(s['firstVertex']+int(i))*52+28
                result[at:at+24]=struct.pack('<3I3f',*donor[i],*weight[i])
            changes.append(dict(resource=r['resource'],lod=s['lod'],sectionFirst=s['firstVertex'],protectedWeldRows=int(protected.sum()),bodyRows=int((~protected).sum()),body1Rows=int(np.sum(np.any(donor[~protected]>=32696,axis=1))),donorDistanceNativeUnits=stats(distance[~protected])))
    # Preserve copied LOD1 waist constraints as exact aliases of their actual
    # upper rows after both resources have been evaluated with the new domain.
    manifest=json.loads((bindings/'manifest.json').read_text())
    for row in manifest.get('sourceWaist',{}).get('newTopRows',[]):
        lower=tables[0]['rowoffset']+row['nativeRow']*52
        upper=tables[1]['rowoffset']+(row['upperGlobalRow']-b['resources'][1]['firstVertex'])*52
        result[lower+28:lower+52]=result[upper+28:upper+52]
    # Exact original-row aliases (including material split aliases) must remain
    # exact after donor correction. Distinct anatomy interiors are protected.
    for r,table in zip(b['resources'],tables):
        by_old={}
        for i,row in enumerate(r['rows']):
            key=row.tobytes();at=table['rowoffset']+i*52
            if key in by_old:result[at:at+52]=result[by_old[key]:by_old[key]+52]
            else:by_old[key]=at
    return original,bytes(result),b,changes


def replay(bindings,captures,output):
    output=Path(output)
    if output.exists():raise ValueError('Choose a fresh output directory')
    original,candidate,b,changes=repair_candidate(bindings);output.mkdir(parents=True)
    candidate_path=output/'comparison-only-binding.bin';candidate_path.write_bytes(candidate);new=read_binding(candidate_path)
    protected_exact=True;all_baselines_exact=True;all_module_rows_exact=True;domains=[]
    for old_r,new_r in zip(b['resources'],new['resources']):
        all_baselines_exact &= old_r['rows']['baseline'].tobytes()==new_r['rows']['baseline'].tobytes()
        for s in old_r['sections']:
            sl=slice(s['firstVertex'],s['firstVertex']+s['vertexCount']);old=old_r['rows'][sl];now=new_r['rows'][sl]
            exact=np.any((old['donors']<17528)&(old['weights']>1e-12),axis=1)
            protected_exact &= old[exact].tobytes()==now[exact].tobytes()
            if s['material']:
                all_module_rows_exact &= old.tobytes()==now.tobytes();continue
            _,mesh,raw,_=cooked_resource(old_r['resource'],bindings)
            offset=struct.unpack('<I',mesh.get(mesh.cooked,'indexBufferOffset','Uint32'))[0]
            faces=np.frombuffer(raw,'<u2',s['indexCount'],offset+s['indexFirst']*2).reshape(-1,3)
            p=old['baseline'][:,:12].copy().view('<f4').reshape(-1,3)*old_r['scale']+old_r['bias'];p*=100
            tri=p[faces];center=tri.mean(1);edge=np.linalg.norm(np.roll(tri,-1,axis=1)-tri,axis=2)
            normal=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);area=np.linalg.norm(normal,axis=1);normal/=np.maximum(area[:,None],1e-30)
            mask=(np.abs(center[:,0])>3.6)&(np.abs(center[:,0])<15)&(center[:,2]>80)&(center[:,2]<103)&(center[:,1]>0)
            if mask.any():domains.append((old_r['resource'],s['lod'],old,now,p,faces,edge,normal,mask))
    cases=[]
    for path in sorted(Path(captures).glob('v2-checkpoint-*.source')):
        raw=np.fromfile(path,'u1').reshape(-1,32)
        if len(raw)!=len(b['positions']):raise ValueError('Captured source bank dimensions differ')
        position=raw[:,:12].copy().view('<f4').reshape(-1,3);delta=position-b['positions'];rows=[]
        for resource,lod,old,now,p,faces,edge,normal,mask in domains:
            item=dict(resource=resource,lod=lod)
            for label,table in [('baseline',old),('bothParts',now)]:
                d=(delta[table['donors']]*table['weights'][:,:,None]).sum(1)@b['rotation'].T
                tri=(p+d)[faces];e=np.linalg.norm(np.roll(tri,-1,axis=1)-tri,axis=2)
                n=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-30)
                angle=np.degrees(np.arccos(np.clip((n*normal).sum(1),-1,1)))
                item[label]=dict(faceTurnDegrees=stats(angle[mask]),maximumEdgeRatio=float((e/np.maximum(edge,1e-30))[mask].max()),minimumEdgeRatio=float((e/np.maximum(edge,1e-30))[mask].min()),facesTurnedOver90=int(np.sum(angle[mask]>90)))
            rows.append(item)
        cases.append(dict(checkpoint=int(path.stem.split('-')[-1]),sourceSHA256=digest(path),domains=rows))
    result=dict(schema='malemod.witcher-v2-complementary-body-donor-replay/1',baselineBindingSHA256=hashlib.sha256(original).hexdigest(),comparisonBindingSHA256=digest(candidate_path),allBaselinePositionSkinAndLightingBytesExact=bool(all_baselines_exact),allSourceModuleRowsExact=bool(all_module_rows_exact),allExactAnatomyWeldConstraintsExact=bool(protected_exact),sourceGeometryAndNumericsModified=False,candidateInstalled=False,nativeVisualAccepted=False,bodyDomains=changes,cases=cases,limitations=['Face turn relative to a rest normal is diagnostic; it is not a self-intersection or inversion certificate','Extreme combined shapes still require native front/side/oblique review','This isolated donor correction is comparison-only; production binding must be generated through the normal calibrated pipeline'])
    write_json(output/'replay.json',result);print(json.dumps({k:v for k,v in result.items()if k!='cases'},indent=2));return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bindings',type=Path,required=True);p.add_argument('--captures',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();replay(a.bindings,a.captures,a.output)
