"""Bake a compound attachment chart from measured native boundary aliases.

The probe supplies actual packed UV/normal/tangent fields. No geometry, original
skin chart, or retained atlas pixel is changed. Outputs stay in an owned build job.
"""
import argparse,json,hashlib,sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from PIL import Image
from mod import ROOT

def unit(x):return x/np.maximum(np.linalg.norm(x,axis=-1,keepdims=True),1e-20)
def unpack(w):return unit(np.stack([(w>>k)&1023 for k in (0,10,20)],axis=-1)/511.5-1)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def prepare(base,probe,atlas,job,output):
    job=job.absolute();output=output.resolve()
    if job.parent.resolve()!=(ROOT/'build/body-boundary').resolve() or job.exists() or output.exists():
        raise ValueError('Use fresh owned material job/output directories')
    sys.path.insert(0,str(base))
    from malemod_base.loft_material import sample,bake_patch,retained_skin_tile,surface_uv_gradients
    from malemod_base.skin_match import linear,encoded
    dtype=np.dtype([('p','<f8',(3,)),('normal','<u4'),('tangent','<u4'),('uv','<f2',(2,))])
    attrs=np.fromfile(str(probe)+'-native-attributes.bin',dtype);faces=np.fromfile(str(probe)+'-native-triangles.bin','<u4').reshape(-1,3)
    uv=attrs['uv'].astype(float);p=attrs['p'];n=unpack(attrs['normal']);t=unpack(attrs['tangent']);t=unit(t-n*np.sum(n*t,axis=1)[:,None]);sign=np.where((attrs['tangent']>>30)==0,-1.,1.);b=np.cross(n,t)*sign[:,None]
    rect=np.array([.7625,.395,.9875,.485]);inside=(uv[:,0]>rect[0]-.0005)&(uv[:,0]<rect[2]+.0005)&(uv[:,1]>rect[1]-.0002)&(uv[:,1]<rect[3]+.0002)
    patch=inside[faces].all(1);patch_ids=np.unique(faces[patch]);retained=np.unique(faces[~patch]);retained=retained[~inside[retained]]
    if not patch.any() or not len(retained):raise ValueError('Missing compound patch or retained aliases')
    tree=cKDTree(p[retained]);boundaries=[]
    for row in (rect[1],rect[3]):
        ids=patch_ids[abs(uv[patch_ids,1]-row)<.0002]
        distance,match=tree.query(p[ids]);good=distance<2e-6;ids=ids[good];match=retained[match[good]]
        if len(ids)<100:raise ValueError('Incomplete measured material boundary')
        u=np.clip((uv[ids,0]-rect[0])/(rect[2]-rect[0]),0,1);order=np.argsort(u);u=u[order];ids=ids[order];match=match[order]
        _,first=np.unique(u,return_index=True);boundaries.append((u[first],ids[first],match[first]))
    results=[];W,H=8192,4096;x0,y0,x1,y1=np.rint(rect*[W-1,H-1,W-1,H-1]).astype(int)
    gradients=surface_uv_gradients(p,faces[~patch],uv)
    width,height=x1-x0+1,y1-y0+1
    queries=np.linspace(0,1,width)
    interpolate=lambda s,v:np.stack([np.interp(queries,s,v[:,k],period=1) for k in range(v.shape[1])],axis=1)
    continuation_geometry=[]
    rows=np.unique(uv[patch_ids,1])
    for endpoint,(s,ids,match) in enumerate(boundaries):
        # The first interior meridian supplies the direction out of the
        # retained surface. Extend its original UV differential through the
        # removed atlas region; do not extrude a single row of skin texels.
        v0=uv[ids[0],1];v1=rows[1] if endpoint==0 else rows[-2]
        inner=patch_ids[uv[patch_ids,1]==v1]
        iu=np.clip((uv[inner,0]-rect[0])/(rect[2]-rect[0]),0,1)
        order=np.argsort(iu);iu=iu[order];inner=inner[order]
        _,unique=np.unique(iu,return_index=True);iu=iu[unique];inner=inner[unique]
        target=np.stack([np.interp(s,iu,p[inner,k],period=1) for k in range(3)],axis=1)
        direction=(target-p[ids])/abs((v1-v0)/(rect[3]-rect[1]))
        duv=np.einsum('nij,nj->ni',gradients[match],direction)
        depth=np.linspace(0,1,height) if endpoint==0 else np.linspace(1,0,height)
        coords=interpolate(s,uv[match])[None]+depth[:,None,None]*interpolate(s,duv)[None]
        frames=[interpolate(s,field[index]) for field,index in
                ((t,match),(b,match),(n,match),(t,ids),(b,ids),(n,ids))]
        continuation_geometry.append((coords,frames))
    normal_source=np.asarray(Image.open(atlas/'atlas-normal.tga').convert('RGB'))
    center,half,density,skin_faces=retained_skin_tile(p,faces,uv,patch,boundaries[0][2],W,H,normal_source)
    del normal_source
    # Measure actual geometry lengths instead of hardcoding a repeat count.
    boundary_points=[]
    for s,ids,match in boundaries:
        boundary_points.append(np.stack([np.interp(np.linspace(0,1,512,endpoint=False),s,p[ids,k],period=1) for k in range(3)],axis=1))
    circumference=np.linalg.norm(np.roll(boundary_points[0],-1,axis=0)-boundary_points[0],axis=1).sum()
    length=np.median(np.linalg.norm(boundary_points[1]-boundary_points[0],axis=1))
    repeats=[float(circumference*density/(4*half[0])),float(length*density/(4*half[1]))]
    job.mkdir(parents=True);output.mkdir(parents=True)
    u=np.linspace(0,1,2048,endpoint=False)
    for channel in ('diffuse','normal'):
        src=atlas/f'atlas-{channel}.tga';original=np.asarray(Image.open(src).convert('RGBA'));values=[]
        if original.shape[:2]!=(H,W):raise ValueError('Atlas dimensions differ')
        for s,ids,match in boundaries:
            v=sample(original,uv[match])[:,:3]
            if channel=='diffuse':v=linear(v)
            else:
                v=unit(v/127.5-1);world=t[match]*v[:,0,None]+b[match]*v[:,1,None]+n[match]*v[:,2,None]
                v=unit(np.stack([np.sum(world*t[ids],axis=1),np.sum(world*b[ids],axis=1),np.sum(world*n[ids],axis=1)],axis=1))
            values.append(np.stack([np.interp(u,s,v[:,k],period=1) for k in range(3)],axis=1))
        # Use a retained skin sample, with exact measured endpoint values.
        sx,sy=center;rx,ry=half
        tile=np.array(original[sy-ry:sy+ry,sx-rx:sx+rx,:3]);tile=unit(tile/127.5-1) if channel=='normal' else linear(tile)
        continuations=[]
        for coords,frames in continuation_geometry:
            field=sample(original,coords)[:,:,:3]
            if channel=='diffuse':field=linear(field)
            else:
                field=unit(field/127.5-1);st,sb,sn,dt,db,dn=frames
                world=st[None]*field[:,:,0,None]+sb[None]*field[:,:,1,None]+sn[None]*field[:,:,2,None]
                field=unit(np.stack([np.sum(world*f[None],axis=2) for f in (dt,db,dn)],axis=2))
            continuations.append(field)
        patch_data=bake_patch(values[0],values[1],u,tile,width,height,repeats,channel=='normal',continuations)
        pixels=np.clip(np.rint((patch_data+1)*127.5),0,255).astype('u1') if channel=='normal' else encoded(patch_data)
        result=original.copy();result[y0:y1+1,x0:x1+1,:3]=pixels
        for pad in range(1,9):
            result[y0-pad,x0:x1+1,:3]=pixels[0];result[y1+pad,x0:x1+1,:3]=pixels[-1]
            result[y0-8:y1+9,x0-pad]=result[y0-8:y1+9,x0];result[y0-8:y1+9,x1+pad]=result[y0-8:y1+9,x1]
        check=result.copy();check[y0-8:y1+9,x0-8:x1+9]=original[y0-8:y1+9,x0-8:x1+9]
        if not np.array_equal(check,original):raise ValueError('Retained atlas pixels changed')
        path=job/f'atlas-{channel}.tga';Image.fromarray(result,'RGBA').save(path)
        results.append(dict(channel=channel,path=str(path),sha256=digest(path),sourceSHA256=digest(src),retainedPixelsExact=True))
    report=dict(schema='malemod.compound-native-material/2',probeSHA256=digest(Path(str(probe)+'-native-attributes.bin')),patchFaces=int(patch.sum()),boundarySamples=[len(x[0]) for x in boundaries],rectangle=rect.tolist(),skinTileCenter=center.tolist(),skinTileHalfSize=half.tolist(),retainedSkinFaces=skin_faces,measuredTexelDensity=density,repeats=repeats,textures=results,nativeObserved=False,installed=False)
    (output/'bake-manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('base','probe','atlas','job','output'):p.add_argument('--'+name,type=Path,required=True)
    prepare(**vars(p.parse_args()))
