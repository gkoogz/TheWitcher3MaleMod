"""Read-only native frame oracle and proposed alias-free material field audit.

No colour packing is emitted unless triangle parity and angle continuity are
proven. Native VS axes are transformed independently, without Gram correction.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import numpy as np
from scipy.spatial import cKDTree


def unit(value):
    value=np.asarray(value,float);length=np.linalg.norm(value,axis=-1,keepdims=True)
    if np.any(length<1e-12):raise ValueError('Degenerate native frame axis')
    return value/length


def vs_frame(normal,tangent,handedness,linear):
    """Actual2272 VS: localB=cross(N,T)*h, then independent transform/unit."""
    binormal=unit(np.cross(normal,tangent)*np.asarray(handedness)[...,None])
    axes=[unit(np.einsum('...ij,...j->...i',linear,v))for v in [tangent,binormal,normal]]
    return np.stack(axes,axis=-1)


def parallel_rotation(before,after):
    before,after=unit(before),unit(after);v=np.cross(before,after);c=np.sum(before*after,axis=-1)
    if np.any(c<=-1+1e-8):raise ValueError('Antipodal parallel transport has no unique shortest rotation')
    k=np.zeros(v.shape[:-1]+(3,3));k[...,0,1]=-v[...,2];k[...,0,2]=v[...,1];k[...,1,0]=v[...,2];k[...,1,2]=-v[...,0];k[...,2,0]=-v[...,1];k[...,2,1]=v[...,0]
    return np.eye(3)+k+np.matmul(k,k)/(1+c)[...,None,None]


def exact_transport(source,stock):
    rotation=parallel_rotation(stock[...,2],source[...,2])
    return np.linalg.solve(source,np.matmul(rotation,stock))


def twist_parity(source,stock):
    n=unit(source[...,2]);t=unit(source[...,0]-n*np.sum(n*source[...,0],axis=-1)[...,None])
    source_h=np.sign(np.linalg.det(source));stock_h=np.sign(np.linalg.det(stock));b=np.cross(n,t)*source_h[...,None]
    transported=np.einsum('...ij,...j->...i',parallel_rotation(stock[...,2],n),stock[...,0]);transported=unit(transported-n*np.sum(n*transported,axis=-1)[...,None])
    return np.arctan2(np.sum(b*transported,axis=-1),np.sum(t*transported,axis=-1)),source_h*stock_h


def encoding_audit(weight,angle,parity,faces):
    active=np.any(weight[faces]>0,axis=1);mixed=np.ptp(parity[faces],axis=1)!=0
    edges=np.vstack([faces[active][:,[0,1]],faces[active][:,[1,2]],faces[active][:,[2,0]]])
    raw=abs(angle[edges[:,0]]-angle[edges[:,1]]);wrapped=abs((raw+np.pi)%(2*np.pi)-np.pi)
    return dict(activeTriangles=int(active.sum()),mixedParityTriangles=np.flatnonzero(active&mixed).tolist(),
                rawAngleWrapEdges=int((raw>np.pi).sum()),wrappedEdgeDegrees=np.percentile(np.degrees(wrapped),[0,50,95,99,100]).tolist(),
                twoBytePackingProven=not np.any(active&mixed)and not np.any(raw>np.pi))


def cotangent_frame(native,dpdx,dpdy,duvdx,duvdy):
    """Derivative proposal only: preserve native geometric N, including length."""
    n=unit(native[...,2]);det=duvdx[...,0]*duvdy[...,1]-duvdx[...,1]*duvdy[...,0]
    if np.any(abs(det)<1e-12):raise ValueError('Degenerate UV1 derivatives require explicit native-frame fallback')
    t=(dpdx*duvdy[...,1,None]-dpdy*duvdx[...,1,None])/det[...,None]
    raw_b=(dpdy*duvdx[...,0,None]-dpdx*duvdy[...,0,None])/det[...,None]
    t=unit(t-n*np.sum(n*t,axis=-1)[...,None]);h=np.sign(np.sum(np.cross(t,raw_b)*n,axis=-1))
    if np.any(h==0):raise ValueError('Degenerate UV1 cotangent orientation')
    b=np.cross(n,t)*h[...,None]
    return np.stack([t,b,native[...,2]],axis=-1)


def endpoint_stock_response(stock_ts,native,cotangent,weight):
    """Proposed world-vector blend, exact native endpoint; no endpoint normalize."""
    a=np.einsum('...ij,...j->...i',cotangent,stock_ts);b=np.einsum('...ij,...j->...i',native,stock_ts)
    w=np.asarray(weight)[...,None]
    return np.where(w>=1,b,np.where(w<=0,a,a*(1-w)+b*w))


def sample(image,uv):
    h,w=image.shape[:2];xy=uv*[w,h]-.5;lo=np.floor(xy).astype(int);f=xy-lo
    a=image[lo[:,1]%h,lo[:,0]%w].astype(float)/255;b=image[lo[:,1]%h,(lo[:,0]+1)%w].astype(float)/255;c=image[(lo[:,1]+1)%h,lo[:,0]%w].astype(float)/255;d=image[(lo[:,1]+1)%h,(lo[:,0]+1)%w].astype(float)/255
    return (a*(1-f[:,0,None])+b*f[:,0,None])*(1-f[:,1,None])+(c*(1-f[:,0,None])+d*f[:,0,None])*f[:,1,None]


def palette(raw):
    count=struct.unpack_from('<I',raw,72)[0];at=76+count*36+76
    sections=struct.unpack_from('<I',raw,at)[0];at+=4+sections*40;bones=struct.unpack_from('<I',raw,at)[0];at+=4
    data=np.frombuffer(raw,np.dtype([('id','<u4'),('inverse','<f4',(4,4))]),bones,at)
    return data['id'],data['inverse'].astype(float)


def row_frames(rows,pose,bone_ids,inverses):
    index=np.stack([(rows['bones']>>(k*8))&255 for k in range(4)],axis=-1)
    weights=np.stack([(rows['weights']>>(k*8))&255 for k in range(4)],axis=-1).astype(float);weights/=weights.sum(axis=1,keepdims=True)
    matrices=np.matmul(pose[bone_ids+1],inverses);blend=np.sum(matrices[index]*weights[...,None,None],axis=1);linear=np.matmul(pose[0,:3,:3],blend[:,:3,:3])
    decode=lambda word:np.stack([((word>>(k*10))&1023)/511.5-1 for k in range(3)],axis=-1)
    return vs_frame(decode(rows['normal']),decode(rows['tangent']),(rows['tangent']>>30)/1.5-1,linear)


def audit(root,output):
    root,output=Path(root),Path(output)
    if output.exists():raise ValueError('Use a fresh private frame-audit directory')
    output.mkdir(parents=True);materials=root/'v2/build/materials';reports=[];posed=[]
    fixture=materials/'seam-normal-07/posed-proof/root-after-164928.bin';bank=root/'v2/build/features/native-20261026-164928';cases=sorted(bank.glob('*.packet'))
    if len(cases)!=31:raise ValueError('Expected31 captured native cases')
    dtype=np.dtype([('position','<f4',3),('bones','<u4'),('weights','<u4'),('normal','<u4'),('tangent','<u4')]);rows=np.memmap(fixture,dtype,mode='r',shape=(31,78337))
    bone_ids,inverses=palette((root/'v2/build/runtime-binding/geralt-source-binding.bin').read_bytes());fields=[]
    for lod in range(2):
        f=np.load(materials/f'seam-native-frames-03/lod{lod}-native-frames.npz');d=np.load(materials/f'source-anatomy-01/lod{lod}-material-donor.npz');fit=np.load(root/f'v2/build/fitted-geralt/lod{lod}.npz')
        points=fit['points'][int(fit['bodyCount']):];seam=d['seamModule'];near=cKDTree(points[seam]).query(points)[1];body_ids=fit['seamBody'][near];weight=d['seamBlend'];active=np.flatnonzero(weight>0)
        source=f['moduleFrame'];stock=f['bodyFrame'][body_ids];angle,parity=twist_parity(source,stock);report=encoding_audit(weight,angle,parity,d['moduleFaces']);report.update(lod=lod,authoredModuleRows=len(weight),activeRows=len(active),
            parityValues=np.unique(parity[active],return_counts=True)[1].tolist(),angleDegrees=np.percentile(np.degrees(angle[active]),[0,50,95,100]).tolist(),
            nativeAbsNdotT=np.percentile(abs(np.sum(source[active,:,0]*source[active,:,2],axis=1)),[50,95,99,100]).tolist(),weldFrameMaxDifference=float(np.max(abs(source[seam]-f['bodyFrame'][fit['seamBody']]))))
        np.savez(output/f'lod{lod}-diagnostic.npz',physicalWeight=weight,stockNearestBodyRow=body_ids,angle=angle,parity=parity,failedTriangleIDs=np.asarray(report['mixedParityTriangles']))
        fields.append((f,fit,seam,active,body_ids));reports.append(report)
    for i,case in enumerate(cases):
        pose=np.fromfile(case.with_suffix('.pose'),'<f4').reshape(95,4,4).astype(float)
        for lod,(f,fit,seam,active,body_ids)in enumerate(fields):
            source=row_frames(rows[i][f['moduleNativeRows'][active]],pose,bone_ids,inverses);stock=row_frames(rows[i][f['bodyNativeRows'][body_ids[active]]],pose,bone_ids,inverses)
            exact=exact_transport(source,stock);flat=np.broadcast_to([0.,0.,1.],(len(active),3));flat_world=np.einsum('nij,njk,nk->ni',source,exact,flat)
            flat_error=np.degrees(np.arccos(np.clip(np.sum(unit(flat_world)*unit(source[:,:,2]),axis=1),-1,1)))
            module_weld=row_frames(rows[i][f['moduleNativeRows'][seam]],pose,bone_ids,inverses);body_weld=row_frames(rows[i][f['bodyNativeRows'][fit['seamBody']]],pose,bone_ids,inverses)
            posed.append(dict(stage=int(case.stem.split('-')[-1]),lod=lod,flatPreservingParallelTransportMaxDegrees=float(flat_error.max()),weldVSFrameMaxAbsDifference=float(np.max(abs(module_weld-body_weld)))))
    proof=dict(schema='malemod.native-physical-material-frame-audit/1',reports=reports,posed=posed,posedCases=31,packedFieldEmitted=False,
        twoBytePackingProven=all(r['twoBytePackingProven']for r in reports),
        donorLimitation='Nearest boundary stock-frame extension reproduces previousNormal07 donor choice; not a proven continuous UV1 material frame.',
        nativeOracle='Actual2272 VS localB=normalize(h*cross(N,T)), then independent skin/world transform+normalize ofT/B/N; noGram. CPU decodedpose model, not captured nativeGPU palette bytes.',
        sourcePhysicsOrGeometryChanged=False,gameLaunched=False)
    (output/'proof.json').write_text(json.dumps(proof,indent=2)+'\n');return proof


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();d=audit(a.root,a.output);print(json.dumps({k:v for k,v in d.items()if k not in ['reports','posed']},indent=2))
