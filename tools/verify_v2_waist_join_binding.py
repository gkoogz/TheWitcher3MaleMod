"""Replay actual captured packets through compiled SourceBinding, CPU only."""
import argparse,collections,json,struct,subprocess,sys
from pathlib import Path
import numpy as np
from mod import ROOT,digest,read_json,write_json
from v2_native_binding import read_binding
from audit_v2_waist_join import sections,keys,LOWER
from v2_waist_binding import new_top_rows
sys.path.insert(0,str(ROOT.parent/'Work/python'))
import trimesh

def crossings(a,b):
    take=np.all(a.min(1)[:,None]<=b.max(1)[None]+1e-8,axis=2)&np.all(a.max(1)[:,None]>=b.min(1)[None]-1e-8,axis=2);aa,bb=np.nonzero(take);A=a[aa];B=b[bb];found=np.zeros(len(aa),bool)
    for source,target in[(A,B),(B,A)]:
        e1=target[:,1]-target[:,0];e2=target[:,2]-target[:,0]
        for k in range(3):
            v=source[:,(k+1)%3]-source[:,k];h=np.cross(v,e2);det=np.einsum('ij,ij->i',e1,h);valid=abs(det)>1e-13;safe=np.where(valid,det,1);s=source[:,k]-target[:,0];u=np.einsum('ij,ij->i',s,h)/safe;q=np.cross(s,e1);vv=np.einsum('ij,ij->i',v,q)/safe;tt=np.einsum('ij,ij->i',e2,q)/safe
            found|=valid&(tt>1e-6)&(tt<1-1e-6)&(u>1e-6)&(vv>1e-6)&(u+vv<1-1e-6)
    return aa[found],bb[found]

def mapping(old,new):
    bo=read_binding(old/'geralt-source-binding.bin');bn=read_binding(new/'geralt-source-binding.bin');mo=read_json(old/'manifest.json');mn=read_json(new/'manifest.json');pairs=[]
    for ri in(0,1):
        so=sections(mo['resources'][ri]['cookedPath'])[1];sn=sections(mn['resources'][ri]['cookedPath'])[1]
        for a,z in zip(so,sn):
            top=set(new_top_rows(z).tolist())if ri==0 and(z['info']['lod'],z['info']['material'])==(1,0)else set();table=collections.defaultdict(list)
            for i,r in enumerate(a['rows']):table[bytes(np.r_[r[:24],r[28:]])].append(i)
            for i,r in enumerate(z['rows']):
                if i in top:continue
                ni=z['info']['firstVertex']+i;record=bn['resources'][ri]['rows'][ni].tobytes();candidates=[a['info']['firstVertex']+h for h in table[bytes(np.r_[r[:24],r[28:]])]if bo['resources'][ri]['rows'][a['info']['firstVertex']+h].tobytes()==record]
                if not candidates:raise ValueError('An existing active52-byte row changed')
                pairs.append((bo['resources'][ri]['firstVertex']+candidates[0],bn['resources'][ri]['firstVertex']+ni))
    if len(pairs)!=78314:raise ValueError('Protected active row count differs')
    for key in('positions','normals','tangents','rotation','sourceRoot','targetRoot'):
        if not np.array_equal(bo[key],bn[key]):raise ValueError('Canonical source bank/placement changed')
    return np.asarray(pairs),bo,bn

def verify(bindings,baseline,fixture,output):
    bindings,baseline,fixture,output=map(Path,(bindings,baseline,fixture,output))
    if output.exists():raise ValueError('Choose a fresh owned proof directory')
    pairs,bo,bn=mapping(baseline,bindings);manifest=read_json(bindings/'manifest.json');waist=manifest['sourceWaist'];top=waist['newTopRows'];newtop=np.array([v['nativeRow']for v in top]);oldtop=np.array([v['upperGlobalRow']for v in top]);output.mkdir(parents=True)
    oldparts=sections(read_json(baseline/'manifest.json')['resources'][0]['cookedPath'])[1];newparts=sections(manifest['resources'][0]['cookedPath'])[1];op=oldparts[3];np_=newparts[3];proto=np.load(ROOT/'v2/build/acceptance/final-602-lod1/independent-visual-review/one-ring-split.npz');removed=set(proto['removedSectionFaces'].tolist());wanted=collections.Counter(k for i,k in enumerate(keys(op,False))if i not in removed);extra=[]
    for i,k in enumerate(keys(np_,False)):
        if wanted[k]:wanted[k]-=1
        else:extra.append(i)
    if len(extra)!=63:raise ValueError('Actual native patch triangle count differs')
    oldpatch=op['faces'][list(sorted(removed))]+op['info']['firstVertex'];newpatch=np_['faces'][extra]+np_['info']['firstVertex']
    upperparts=sections(read_json(baseline/'manifest.json')['resources'][1]['cookedPath'])[1];upperfaces=upperparts[1]['faces']+upperparts[1]['info']['firstVertex']+bo['resources'][1]['firstVertex']
    cases=[];spec=[(p,p.stem,'features')for p in sorted((ROOT/'v2/build/features/native-20261027-005859').glob('v2-checkpoint-*.packet'))]
    if len(spec)!=31:raise ValueError('Exactly31 source feature checkpoints required')
    for name in('final-602-production','final-602-lod1'):
        spec.extend((ROOT/'v2/build/acceptance'/name/f'v2-checkpoint-{cp}.packet',f'{name}-{cp}','garment')for cp in range(63,72))
    for packet,label,kind in spec:
        pose=packet.with_suffix('.pose');a=output/'old.float40';z=output/'new.float40'
        for binding,target in[(baseline/'geralt-source-binding.bin',a),(bindings/'geralt-source-binding.bin',z)]:subprocess.run([str(fixture),str(binding),str(packet),str(pose),str(target)],check=True,capture_output=True)
        old=np.fromfile(a,'<f4').reshape(-1,10);new=np.fromfile(z,'<f4').reshape(-1,10)
        protected=np.array_equal(old[pairs[:,0]],new[pairs[:,1]]);gap=np.linalg.norm(new[newtop,:3].astype(float)-old[oldtop,:3],axis=1);nt=np.max(abs(new[newtop,3:9].astype(float)-old[oldtop,3:9]));tri=new[newpatch,:3].astype(float);norm=new[newpatch,3:6].mean(1).astype(float);cross=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);cw=np.einsum('ij,ij->i',cross,norm)/(np.linalg.norm(cross,axis=1)*np.linalg.norm(norm,axis=1));area=np.linalg.norm(cross,axis=1)*.5
        row=dict(label=label,kind=kind,packetSHA256=digest(packet),poseSHA256=digest(pose),all78314ProtectedWorldNTFramesByteExact=protected,maximumNewTopGapMeters=float(gap.max()),maximumNewTopNTComponentError=float(nt),nativeCWdotMax=float(cw.max()),minimumAreaSquareMM=float(area.min()*1e6))
        if kind=='garment':
            raw=packet.with_suffix('.garment').read_bytes();magic,epoch,lo,hi,nv,nf=struct.unpack_from('<6I',raw)
            if(magic,nv,nf)!=(0x3143474d,4279,8368):raise ValueError('Actual garment fixture dimensions changed')
            p=np.frombuffer(raw,'<f4',nv*12,24).reshape(-1,12)[:,:3].astype(float);f=np.frombuffer(raw,'<u4',nf*4,24+nv*48).reshape(-1,4)[:,:3];band=np.all((f>=2561)&(f<3247),axis=1);outer=np.all((f>=2561)&(f<2904),axis=1);bandids=np.flatnonzero(band)
            _,ob=crossings(old[oldpatch,:3].astype(float),p[f[band]]);_,ub=crossings(old[upperfaces,:3].astype(float),p[f[band]]);_,nb=crossings(tri,p[f[band]]);_,outerhits=crossings(tri,p[f[outer]])
            row.update(garmentSHA256=digest(packet.with_suffix('.garment')),newContactedBandFaces=sorted(map(int,set(bandids[nb])-(set(bandids[ob])|set(bandids[ub])))),outerBandCrossingPairs=len(outerhits))
        cases.append(row);a.unlink();z.unlink();print(label,'protected',protected,'top um',round(gap.max()*1e6,3),'outer',row.get('outerBandCrossingPairs','-'),flush=True)
    passed=all(r['all78314ProtectedWorldNTFramesByteExact']and r['maximumNewTopGapMeters']<3e-5 and r['maximumNewTopNTComponentError']<1e-4 and r['nativeCWdotMax']<0 and not r.get('newContactedBandFaces')and not r.get('outerBandCrossingPairs')for r in cases)
    result=dict(schema='malemod.local-waist-final-B04-actual-pose-replay/1',passed=passed,bindingSHA256=digest(bindings/'geralt-source-binding.bin'),baselineBindingSHA256=digest(baseline/'geralt-source-binding.bin'),fixtureSHA256=digest(fixture),currentSourceBindingHeaderSHA256=digest(ROOT/'v2/native/source_binding.hpp'),allExisting78314ActiveRows52BytesExact=True,workerModified=False,privateReplayOnly=True,nativeVisualAccepted=False,cases=cases)
    write_json(output/'proof.json',result)
    if not passed:raise ValueError('Actual calibrated binding replay failed; seeproof')
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bindings',type=Path,required=True);p.add_argument('--baseline',type=Path,default=ROOT/'v2/build/materials/physical-skin-cook-01/bindings');p.add_argument('--fixture',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(verify(a.bindings,a.baseline,a.fixture,a.output),indent=2))
