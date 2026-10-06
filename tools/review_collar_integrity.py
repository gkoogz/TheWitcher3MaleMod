"""Measure genuine native collar output; produce geometry reviews, not gameplay proof."""
import argparse,json,struct
from pathlib import Path
import numpy as np
from mod import ROOT,digest,write_json,read_json

VERTEX=np.dtype([('position','<f4',3),('bones','<u4'),('weights','<u4'),('normal','<f4',3),('tangent','<f4',3),('sign','<f4'),('reference','<f4',3),('calibration','<u4')])

def contract(path):
    raw=path.read_bytes();at=240
    def u():
        nonlocal at
        x=struct.unpack_from('<I',raw,at)[0];at+=4;return x
    if raw[:8]!=b'MMRND006':raise ValueError('Measured collar donor contract required')
    palette=u();at+=palette*132
    resources=u();at+=resources*44
    lods=[]
    for _ in range(u()):
        header=struct.unpack_from('<9I',raw,at);at+=36
        resource,lod,n,authored,first,*_=header
        binding=raw[at:at+n*156];at+=n*156
        ids=np.array([struct.unpack_from('<I',binding,i*156)[0] for i in range(n)])
        # Original native packing error bounds the orientation of needle-like
        # stock subdivision faces. Keep their raw diagnostic count separately.
        packingError=np.array([np.linalg.norm(np.array(struct.unpack_from('<3d',binding,i*156+88))-np.array(struct.unpack_from('<3d',binding,i*156+132))) for i in range(n)])
        count=u();faces=np.frombuffer(raw,dtype='<u4',count=count*3,offset=at).copy().reshape(-1,3);at+=count*12
        seams=[]
        for _ in range(u()):seams.append(struct.unpack_from('<IIId',raw,at));at+=20
        lods.append(dict(resource=resource,lod=lod,n=n,first=first,ids=ids,faces=faces,seams=seams,packingError=packingError))
    if at!=len(raw):raise ValueError('Render packet parse differs')
    return lods

def review(artifacts,render,job,reference=None):
    artifacts,render,job=map(lambda p:Path(p).absolute(),(artifacts,render,job));lods=contract(render/'geralt.render');cases=read_json(artifacts/'cases.json')
    neutral=np.fromfile(artifacts/'neutral-render.bin',VERTEX);rows=[]
    for case in cases:
        v=np.fromfile(artifacts/(case['label']+'-render.bin'),VERTEX)
        if len(v)!=len(neutral) or not np.isfinite(v['position']).all():raise ValueError('Incomplete native output')
        results=[]
        for l in lods:
            p=v[l['first']:l['first']+l['n']]['position'].astype(float);old=neutral[l['first']:l['first']+l['n']]['position'].astype(float)
            light=v[l['first']:l['first']+l['n']]['normal'].astype(float);low=int(np.load(job/f"part{l['lod']}.npz")['bodyCount']);faces=l['faces']
            root=set(s[0] for s in l['seams']);near=np.array([any(int(i) in root for i in f) for f in faces]);body=np.all(l['ids'][faces]<low,axis=1)&near
            allBody=np.ones(len(faces),dtype=bool) if l['resource'] else np.all(l['ids'][faces]<low,axis=1)
            def cross(x):
                t=x[faces];return np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0])
            n=cross(p);n0=cross(old);length=np.linalg.norm(n,axis=1);oldLength=np.linalg.norm(n0,axis=1)
            stable=body&(oldLength>1e-12);orientation=np.sum(n*n0,axis=1)
            oldTriangles=old[faces];edges=np.linalg.norm(oldTriangles[:,1]-oldTriangles[:,0],axis=1)+np.linalg.norm(oldTriangles[:,2]-oldTriangles[:,0],axis=1)
            resolved=allBody&(oldLength>4*l['packingError'][faces].max(1)*edges)&(oldLength>1e-12)
            gap=0;normalError=0
            for slave,a,b,w in l['seams']:
                gap=max(gap,float(np.linalg.norm(p[slave]-((1-w)*p[a]+w*p[b]))))
                donor=(1-w)*light[a]+w*light[b];donor/=np.linalg.norm(donor);normalError=max(normalError,float(np.linalg.norm(light[slave]/np.linalg.norm(light[slave])-donor)))
            results.append(dict(resource=l['resource'],lod=l['lod'],seamGapMetres=gap,normalDonorError=normalError,bodyCollarFaces=int(stable.sum()),bodyFacesReversedFromNeutral=int((stable&(orientation<=0)).sum()),allBodyFacesReversedFromNeutral=int((allBody&(oldLength>1e-12)&(orientation<=0)).sum()),packingResolvedBodyFacesReversed=int((resolved&(orientation<=0)).sum()),packingAmbiguousBodyFaces=int((allBody&~resolved).sum()),minimumAreaRatio=float((length[stable]/oldLength[stable]).min()) if stable.any() else None,maximumAreaRatio=float((length[stable]/oldLength[stable]).max()) if stable.any() else None))
        rows.append(dict(label=case['label'],lods=results))
    report=dict(renderSHA256=digest(render/'geralt.render'),caseCount=len(rows),rows=rows,
                sourceOnly=False,nativeBufferExport=True,observedGameplay=False,visualAcceptance=False)
    write_json(artifacts/'collar-metrics.json',report)
    worst=sorted(rows,key=lambda r:sum(l['bodyFacesReversedFromNeutral'] for l in r['lods']),reverse=True)[:10]
    print(json.dumps(dict(cases=len(rows),worst=worst),indent=2))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    selected=['neutral','s1-o100-w100-a1','s1-o100-w100-a50','s1-o100-w100-a100','reported1','combined1']
    fig,axes=plt.subplots(2,len(selected),figsize=(3.2*len(selected),8),constrained_layout=True)
    l=lods[0]
    for column,label in enumerate(selected):
        v=np.fromfile(artifacts/(label+'-render.bin'),VERTEX);p=v['position'][l['first']:l['first']+l['n']];tri=p[l['faces']];n=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
        for row,(a,b,c) in enumerate([(1,2,0),(0,2,1)]):
            keep=(tri.mean(1)[:,2]>.7)&(tri.mean(1)[:,2]<1.25)&(tri.mean(1)[:,1]>.01)&(n[:,c]>0)
            colors=np.clip(.55+.4*n[keep,c]/np.maximum(1e-12,np.linalg.norm(n[keep],axis=1)),0,1)
            ax=axes[row,column];ax.add_collection(PolyCollection(tri[keep][:,:,[a,b]],facecolors=plt.cm.Greys(colors),edgecolors='#999',linewidth=.1))
            ax.set(xlim=(.01,.5) if row==0 else (-.3,.3),ylim=(.7,1.25),aspect='equal',title=label+(' / side' if row==0 else ' / front'))
    fig.savefig(artifacts/'geometry-review.png',dpi=130)
    # The lower resource alone hides the abdominal side of the attachment.
    # Cut both native resources together so an apparently sewn root cannot
    # conceal a shoulder at the waist. Comparison data are actual native
    # buffers from an earlier accepted run, not a fitted silhouette.
    from matplotlib.collections import LineCollection
    cuts,axes=plt.subplots(2,3,figsize=(12,9),constrained_layout=True)
    for column,label in enumerate(['reported1','s1-o100-w100-a50','combined1']):
        inputs=[(artifacts,'#cb4938','candidate')]
        if reference:inputs.insert(0,(Path(reference),'#555555','previous'))
        for row,section in enumerate([0.,.04]):
            ax=axes[row,column]
            for directory,color,name in inputs:
                v=np.fromfile(directory/(label+'-render.bin'),VERTEX)
                if len(v)!=len(neutral):raise ValueError('Profile reference topology differs')
                lines=[]
                for l in lods:
                    if l['lod']:continue
                    p=v['position'][l['first']:l['first']+l['n']].astype(float)
                    triangles=p[l['faces']]
                    crosses=(triangles[:,:,0].min(1)<section)&(triangles[:,:,0].max(1)>section)
                    for tri in triangles[crosses]:
                        points=[]
                        for a,b in [(0,1),(1,2),(2,0)]:
                            da,db=tri[a,0]-section,tri[b,0]-section
                            if da*db<0:points.append(tri[a]+(tri[b]-tri[a])*da/(da-db))
                        if len(points)==2 and np.mean(points,axis=0)[1]>.02:lines.append(np.array(points)[:,[1,2]])
                ax.add_collection(LineCollection(lines,colors=color,linewidth=1.1,label=name))
            ax.set(xlim=(.02,.35),ylim=(.84,1.3),aspect='equal',title=f'{label} / lateral {section:g} m')
            ax.legend(fontsize=8)
    cuts.savefig(artifacts/'profile-review.png',dpi=150)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('artifacts','render','job'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--require-valid',action='store_true')
    p.add_argument('--reference-artifacts',type=Path,help='Earlier native-buffer export with identical topology, for meridian comparison')
    a=p.parse_args();report=review(a.artifacts,a.render,a.job,a.reference_artifacts)
    if a.require_valid:
        for row in report['rows']:
            if len(row['lods'])!=4:raise ValueError('Both body resources and LODs required')
            for lod in row['lods']:
                if lod['seamGapMetres']>1e-6 or lod['normalDonorError']>.002 or lod['bodyFacesReversedFromNeutral'] or lod['packingResolvedBodyFacesReversed']:
                    raise ValueError('Attachment geometry gate failed: '+row['label']+' '+str(lod))
        print('PASS exact native seams, donor lighting and body orientation across both resources/LODs; visual review remains required')
