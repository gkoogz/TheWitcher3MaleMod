"""Inspect independently evaluated source/target radial-graft artifacts.

Consumes radial_progressivity_probe output. Reports rest-normal rotations without
mistaking them for winding inversion; checks nonadjacent strict triangle crossings
on the front-body ramp separately. This is an offline binding/quality gate, not
a proof of global self-intersection freedom or native game rendering.
"""
import argparse
from pathlib import Path
import sys
import numpy as np
from scipy.spatial import cKDTree
from mod import ROOT,settings,read_json,write_json


def segment_triangle(a,b,t):
    e1=t[:,1]-t[:,0];e2=t[:,2]-t[:,0];direction=b-a;p=np.cross(direction,e2);det=(e1*p).sum(1)
    valid=np.abs(det)>1e-14;inv=np.divide(1.,det,out=np.zeros_like(det),where=valid)
    s=a-t[:,0];u=(s*p).sum(1)*inv;q=np.cross(s,e1);v=(direction*q).sum(1)*inv;distance=(e2*q).sum(1)*inv
    eps=1e-7
    return valid&(u>eps)&(v>eps)&(u+v<1-eps)&(distance>eps)&(distance<1-eps)


def crossings(rest,pos,faces):
    center0=rest[faces].mean(1)
    selected=(center0[:,1]>.01)&(center0[:,2]>.85)&(center0[:,2]<1.15)&(np.abs(center0[:,0])<.16)
    faces=faces[selected]
    _,alias=np.unique(np.round(rest/1e-6).astype('i8'),axis=0,return_inverse=True)
    fa=alias[faces];tri=pos[faces];center=tri.mean(1);radius=np.linalg.norm(tri-center[:,None,:],axis=2).max(1)
    pairs=cKDTree(center).query_pairs(float(radius.max()*2),output_type='ndarray')
    a,b=pairs.T
    use=np.linalg.norm(center[a]-center[b],axis=1)<radius[a]+radius[b]
    use&=~np.any(fa[a,:,None]==fa[b,None,:],axis=(1,2));pairs=pairs[use]
    count=0
    for start in range(0,len(pairs),25000):
        a,b=pairs[start:start+25000].T;ta,tb=tri[a],tri[b];hit=np.zeros(len(a),bool)
        for i in range(3):
            hit|=segment_triangle(ta[:,i],ta[:,(i+1)%3],tb)|segment_triangle(tb[:,i],tb[:,(i+1)%3],ta)
        count+=int(hit.sum())
    return dict(testedFrontBodyFaces=len(faces),candidatePairs=len(pairs),strictNonadjacentIntersections=count)


def verify(artifacts,job):
    artifacts,job=Path(artifacts).absolute(),Path(job).absolute()
    if not all(p.is_relative_to(ROOT/'build') for p in [artifacts,job]):
        raise ValueError('Use owned offline build artifacts')
    cfg=settings();sys.path.insert(0,str(cfg['base']))
    from malemod_base.collar import CollarFrame,recruitment
    cases=read_json(artifacts/'cases.json');queries=np.fromfile(artifacts/'queries.bin','<f4').reshape(-1,3)
    parts=[np.load(job/('part%d.npz'%i)) for i in range(4)]
    calibration=read_json(ROOT/'characters/geralt-runtime-bindings.json')['coordinateCalibration']
    basis=np.asarray(calibration['basis']);scale=calibration['nativeUnitsPerSourceUnit']
    neutral=[np.fromfile(artifacts/('neutral-lod%d.bin'%lod),'<f8').reshape(-1,3) for lod in range(2)]
    neutral_collar=np.fromfile(artifacts/'neutral-collar.bin','<f4').reshape(-1,3)
    reports=[]
    for case in cases:
        label=case['label'];axis=np.asarray(case['axis']);up=np.asarray(case['up'])
        frame=CollarFrame(tuple(case['root']),tuple(axis/np.linalg.norm(axis)),tuple(up/np.linalg.norm(up)),case['radius'],case['length'],1)
        weights=recruitment(queries,frame);collar=np.fromfile(artifacts/(label+'-collar.bin'),'<f4').reshape(-1,3)
        offset=0;rows=[];maximum_waist_error=0
        for lod in range(2):
            low,upper=parts[lod],parts[2+lod];nlow=int(low['bodyCount']);nup=len(upper['points'])
            pos=np.fromfile(artifacts/(label+'-lod%d.bin'%lod),'<f8').reshape(-1,3)
            rest=np.vstack([low['points'][:nlow],upper['points']])/100.
            body_faces=np.vstack([low['faces'][np.all(low['faces']<nlow,axis=1)],upper['faces']+nlow])
            for resource,part,p,base,query_start in [('lower',low,pos[:nlow],neutral[lod][:nlow],offset),('upper',upper,pos[nlow:nlow+nup],neutral[lod][nlow:nlow+nup],offset+nlow)]:
                before=part['points'][:len(p)]/100.;faces=part['faces'];faces=faces[np.all(faces<len(p),axis=1)]
                a,b=before[faces],p[faces];c0=np.cross(a[:,1]-a[:,0],a[:,2]-a[:,0]);c1=np.cross(b[:,1]-b[:,0],b[:,2]-b[:,0]);area0=np.linalg.norm(c0,axis=1);area1=np.linalg.norm(c1,axis=1)
                ratios=area1/area0
                if np.any(~np.isfinite(ratios)) or np.any(ratios<1e-6):raise ValueError('Collapsed/nonfinite body ramp triangle: '+label)
                waist=part['waist'];expected=(collar[query_start+waist].astype(float)-neutral_collar[query_start+waist])@basis.T*scale
                error=float(np.linalg.norm(p[waist]-base[waist]-expected,axis=1).max());maximum_waist_error=max(maximum_waist_error,error)
                if error>1e-8:raise ValueError('Native waist deviates from direct source radial displacement: '+label)
                rows.append(dict(lod=lod,resource=resource,supportedVertices=int((weights[query_start:query_start+len(p)]>1e-4).sum()),minimumAreaRatio=float(ratios.min()),restNormalReversals=int(((c0*c1).sum(1)<0).sum()),maximumDisplacementFromNeutral=float(np.linalg.norm(p-base,axis=1).max())))
            if label in ['overall-25','overall-50','overall-75','overall-100','combined-max']:
                intersection=crossings(rest,pos[:nlow+nup],body_faces)
                if intersection['strictNonadjacentIntersections']:raise ValueError('Nonadjacent front ramp triangles intersect: '+label)
                rows[-1]['frontRampIntersectionCheck']=intersection
            offset+=nlow+nup
        rho=np.hypot((queries-np.asarray(case['root']))[:,1],(queries-np.asarray(case['root']))@up)
        rings=[]
        for lo,hi in zip([0,2,4,6,8,10],[2,4,6,8,10,14]):
            mask=(rho>=lo)&(rho<hi);rings.append(dict(innerRadiusSource=lo,outerRadiusSource=hi,supportedQueries=int(((weights>1e-4)&mask).sum()),positiveRadialQueries=int(((np.linalg.norm(collar,axis=1)>1e-6)&mask).sum())))
        reports.append(dict(**case,supportedQueries=int((weights>1e-4).sum()),positiveRadialQueries=int((np.linalg.norm(collar,axis=1)>1e-6).sum()),rings=rings,maximumNativeWaistSourceError=maximum_waist_error,parts=rows))
    overall=[next(c for c in reports if c['label']=='overall-'+str(value)) for value in [1,25,50,75,100]]
    if any(a['supportedQueries']>b['supportedQueries'] for a,b in zip(overall,overall[1:])):raise ValueError('Overall recruitment support is not progressive')
    derivatives=[]
    for start,end in [('overall-75-minus','overall-75'),('overall-75','overall-75-plus'),('overall-100-minus','overall-100')]:
        controls={r['label']:r['overall'] for r in reports};step=controls[end]-controls[start]
        maxima=[]
        for lod in range(2):
            a=np.fromfile(artifacts/(start+'-lod%d.bin'%lod),'<f8').reshape(-1,3);b=np.fromfile(artifacts/(end+'-lod%d.bin'%lod),'<f8').reshape(-1,3)
            body=int(parts[lod]['bodyCount'])+len(parts[2+lod]['points'])
            maxima.append(float(np.linalg.norm((b[:body]-a[:body])/step,axis=1).max()))
        derivatives.append(dict(start=start,end=end,maximumNativeDisplacementPerUIUnit=maxima))
    report=dict(offlineOnly=True,observedGameplay=False,globalIntersectionProof=False,cases=reports,overallSupportMonotonic=True,derivatives=derivatives)
    write_json(artifacts/'quality-verification.json',report)
    print('PASS:',len(cases),'independently initialized radial/control states; progressive Overall support; exact native/source waist field; noncollapsed body triangles; ten front-ramp intersection checks')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--artifacts',type=Path,required=True);p.add_argument('--job',type=Path,required=True)
    a=p.parse_args();verify(a.artifacts,a.job)
