"""Validate an MMGP1 bank against its selected immutable geometry and pose.

CPU-only; never launches, stages, cooks, compiles, or changes runtime bindings.
The normal command fails if current-frame identity or selected-pose parity fails.
"""
import argparse,json,struct,sys
from pathlib import Path
import numpy as np
from mod import ROOT,digest,read_json,write_json
from v2_native_binding import read_binding,cooked_resource
sys.path.insert(0,str(ROOT.parent/'Work/python'))
import trimesh


def skin_selected(binding,raw,pose):
    """Same ordered float32 affine operations as skin_output.hpp/pose.hpp."""
    data=np.frombuffer(raw,'u1').reshape(-1,28)
    if len(data)!=binding['totalVertices']or len(pose)!=95*64:raise ValueError('Selected row/pose dimensions differ')
    matrices=np.frombuffer(pose,'<f4').reshape(95,4,4);actor=matrices[0];poses=matrices[1:]
    result=np.empty((len(data),3),np.float32)
    for r in binding['resources']:
        sl=slice(r['firstVertex'],r['firstVertex']+r['vertexCount']);rows=data[sl]
        native=rows[:,:12].copy().view('<f4').reshape(-1,3)*np.asarray(r['scale'],np.float32)+np.asarray(r['bias'],np.float32)
        ids=rows[:,12:16];w=rows[:,16:20].astype(np.float32)/np.float32(255)
        total=np.zeros(len(rows),np.float32)
        for k in range(4):total+=w[:,k]
        if (total==0).any():raise ValueError('Zero skin weights')
        palette=np.zeros((len(r['palette']),4,4),np.float32)
        for i,(bone,inverse)in enumerate(r['palette']):
            inv=np.asarray(inverse,np.float32).reshape(4,4)
            for k in range(4):palette[i]+=poses[bone,:,k:k+1]*inv[k:k+1,:]
        blend=np.zeros((len(rows),4,4),np.float32)
        for k in range(4):
            m=palette[ids[:,k]].copy();m[:,3,3]=1
            blend+=m*(w[:,k]/total)[:,None,None]
        local=blend[:,:3,3].copy()
        for k in range(3):local+=blend[:,:3,k]*native[:,k:k+1]
        world=np.broadcast_to(actor[:3,3],local.shape).copy()
        for k in range(3):world+=actor[:3,k]*local[:,k:k+1]
        result[sl]=world
    if not np.isfinite(result).all():raise ValueError('Nonfinite selected CPU skin')
    return result


def statistics(values):
    return dict(median=float(np.median(values)),p95=float(np.quantile(values,.95)),
                p99=float(np.quantile(values,.99)),maximum=float(np.max(values)))


def compare(cpu,faces,world):
    mask=world[:,:,3]>0;gpu=world[mask,:3].astype(float);alpha=world[mask,3]
    if len(gpu)<3 or not np.isfinite(gpu).all()or not np.equal(alpha,np.rint(alpha)).all():raise ValueError('Missing/invalid actual GPU evidence')
    ids=alpha.astype(np.int64)-1
    if ids.min()<0 or ids.max()>=len(faces):raise ValueError('Actual primitive ID leaves selected draw')
    tri=cpu[faces[ids]].astype(float);normal=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);length=np.linalg.norm(normal,axis=1)
    if (length<1e-14).any():raise ValueError('GPU rasterized a degenerate CPU reference face')
    normal/=length[:,None];plane=np.abs(((gpu-tri[:,0])*normal).sum(1))
    closest=trimesh.triangles.closest_point(tri,gpu);distance=np.linalg.norm(gpu-closest,axis=1)
    return dict(pixels=len(gpu),observedPrimitives=len(np.unique(ids)),
                absolutePlaneErrorMeters=statistics(plane),triangleDistanceMeters=statistics(distance)),mask,ids


def analyze(bank,bindings,output,next_pose=None,diagnose=False):
    bank=Path(bank).resolve();bindings=Path(bindings).resolve();output=Path(output).resolve()
    if output.exists()or not output.is_relative_to(bank):raise ValueError('Choose a fresh analysis output inside this bank')
    observation=read_json(bank/'observation.json');manifest=read_json(bindings/'manifest.json')
    if digest(observation['preview'])!=observation['previewSHA256']:raise ValueError('Captured preview changed')
    preview=read_json(observation['preview']);native={Path(r['path']).name:r['sha256']for r in preview['files']if r['path'].startswith('bin/x64_dx12/malemod-native/')}
    for name in ('geralt-source-binding.bin','geralt-meridian-binding.bin','geralt-meridian-coverage.bin'):
        if digest(bindings/name)!=native.get(name):raise ValueError('Analysis binding differs from actual staged source: '+name)
    inventory={r['path']:r['SHA256']for r in observation['files']}
    input_hashes={}
    def source(path):
        path=Path(path);relative=str(path.relative_to(bank)).replace('\\','/')
        sha=digest(path)
        if inventory.get(relative)!=sha:raise ValueError('Captured file changed or is not in closed inventory: '+relative)
        input_hashes[relative]=sha;return path.read_bytes()
    binding=read_binding(bindings/'geralt-source-binding.bin');metas=[];stems=[]
    for component in range(7):
        paths=list(bank.glob('position-*-c'+str(component)+'.json'))
        if len(paths)!=1:raise ValueError('One actual capture per component required')
        metas.append(json.loads(source(paths[0])));stems.append(paths[0].with_suffix(''))
    identities=[(m['epoch'],m['sequence'],m['presentationSerial'],m['nativePresentSerial'],m['poseRevision'])for m in metas]
    coherent=len(set(identities))==1 and all(m['poseEnvelopeKnown']for m in metas)
    current=all(m['sequence']==m['latestSequence']and m['frameSequence']in(0,m['sequence'])and m['recordingSequence']in(0,m['sequence'])for m in metas)
    if any(m['morph']or m['wholeMorph']or m['nativeTopologyType']!=3 or m['nativePSWritesDepth']for m in metas):raise ValueError('Observed pipeline requires an unsupported reference oracle')
    pose=source(str(stems[0])+'.pose');selected=source(str(stems[0])+'-body-input.bin');cpu_body=skin_selected(binding,selected,pose)
    alternative=None
    if next_pose is not None:
        alt=Path(next_pose).resolve()
        if not alt.is_relative_to(bank):raise ValueError('Diagnostic alternative pose must be captured in the same bank')
        alternative=skin_selected(binding,selected,source(alt))
    reports=[];worlds=[];depths=[];facebanks=[];masks=[];primitive_ids=[]
    for component,(m,stem)in enumerate(zip(metas,stems)):
        if source(str(stem)+'.pose')!=pose:raise ValueError('Selected pose envelopes differ')
        width,height=m['roi'][2:];world=np.frombuffer(source(str(stem)+'-world.bin'),'<f4').reshape(height,width,4)
        depth=np.frombuffer(source(str(stem)+'-depth.bin'),'<f4').reshape(height,width)
        if not np.isfinite(depth).all():raise ValueError('Nonfinite depth evidence')
        if component<3:
            if source(str(stem)+'-body-input.bin')!=selected:raise ValueError('Selected body inputs differ')
            r=binding['resources'][m['resource']];section=r['sections'][m['section']]
            _,mesh,raw,_=cooked_resource(m['resource'],bindings)
            if m['resource']==0:indices=np.frombuffer(source(str(stem)+'-covered-indices.bin'),'<u2')
            else:
                offset=struct.unpack('<I',mesh.get(mesh.cooked,'indexBufferOffset','Uint32'))[0]
                indices=np.frombuffer(raw,'<u2',count=r['indexBytes']//2,offset=offset)
            faces=indices[m['normalizedFirst']:m['normalizedFirst']+m['indexCount']].reshape(-1,3).astype(int)+r['firstVertex']+section['firstVertex'];cpu=cpu_body
        else:
            cpu=np.frombuffer(source(str(stem)+'-cloth-input.bin'),'<f4').reshape(-1,12)[:,:3]
            triangles=np.frombuffer(source(str(stem)+'-cloth-indices.bin'),'<u4').reshape(-1,4);faces=triangles[triangles[:,3]==m['kind'],:3]
            if len(faces)*3!=m['indexCount']:raise ValueError('Selected cloth topology differs from actual draw')
        report,mask,ids=compare(cpu,faces,world);report.update(component=component,resource=m['resource'],lod=m['lod'],sequence=m['sequence'],poseRevision=m['poseRevision'])
        report['selectedPoseParityPassed']=report['absolutePlaneErrorMeters']['p99']<(25e-6 if component<3 else 10e-6)and report['triangleDistanceMeters']['p99']<50e-6
        if alternative is not None and component<3:report['diagnosticAlternativePose']=compare(alternative,faces,world)[0]
        reports.append(report);worlds.append(world);depths.append(depth);facebanks.append(faces);masks.append(mask);primitive_ids.append(ids)
    # Same-pixel ray gaps are useful evidence, but back-band/body overlap is
    # legitimate. These measurements alone never establish visual acceptance.
    body_depth=np.full(depths[0].shape,-np.inf);body_world=np.zeros_like(worlds[0][:,:,:3])
    for c in range(3):
        take=masks[c]&(depths[c]>body_depth);body_depth[take]=depths[c][take];body_world[take]=worlds[c][take,:3]
    band=[]
    for c in (4,5,6):
        mask=masks[c].copy();faceids=primitive_ids[c];f=facebanks[c][faceids]
        inside=(f.min(1)>=2561)&(f.max(1)<3247);mask[masks[c]]=inside
        overlap=mask&np.isfinite(body_depth);distance=np.linalg.norm(body_world[overlap]-worlds[c][overlap,:3],axis=1)
        behind=body_depth[overlap]>np.nextafter(np.nextafter(depths[c][overlap],np.float32(np.inf)),np.float32(np.inf))
        band.append(dict(component=c,overlappingBandPixels=int(overlap.sum()),bodyInFrontPixels=int(behind.sum()),
                         bodyInFrontWithin20mmPixels=int((behind&(distance<.02)).sum()),
                         absoluteSameRayGapMeters=statistics(distance)if len(distance)else None,
                         caution='Back band and intervening limbs can be legitimately behind body; overlap is not alone an intersection proof'))
    passed=coherent and current and all(r['selectedPoseParityPassed']for r in reports)
    result=dict(schema='malemod.MMGP1-selected-pose-regression/1',passed=passed,coherentSelectedIdentity=coherent,allSevenSelectedCurrent=current,
                components=reports,actualBandDepth=band,observationSHA256=digest(bank/'observation.json'),
                bindingSHA256=digest(bindings/'geralt-source-binding.bin'),bindingManifestSHA256=digest(bindings/'manifest.json'),
                workerSHA256=native.get('canonical_worker.exe'),runtimeSHA256=observation['runtimeSHA256'],capturedInputHashes=input_hashes,
                diagnosticAlternativePose=str(next_pose)if next_pose is not None else None,
                sourceGeometryChanged=False,gameLaunched=False,visualAcceptance=False,
                limits=['CPU reference uses same ordered float32 affine law; raster-edge extrapolation can enlarge maximum triangle distance',
                        'Fresh selected-pose parity and native visual/temporal acceptance remain separate gates'])
    output.mkdir();write_json(output/'analysis.json',result)
    print(json.dumps({k:result[k]for k in ('passed','coherentSelectedIdentity','allSevenSelectedCurrent','actualBandDepth')},indent=2))
    if not passed and not diagnose:raise ValueError('Actual GPU does not match the current selected pose; see '+str(output/'analysis.json'))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bank',type=Path,required=True);p.add_argument('--bindings',type=Path,default=ROOT/'v2/build/runtime-binding');p.add_argument('--output',type=Path,required=True);p.add_argument('--diagnostic-next-pose',type=Path);p.add_argument('--diagnose',action='store_true',help='Write a failing historical diagnosis without a nonzero exit; never changes passed')
    a=p.parse_args();analyze(a.bank,a.bindings,a.output,a.diagnostic_next_pose,a.diagnose)
