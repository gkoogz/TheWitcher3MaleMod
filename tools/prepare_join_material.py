"""Bake a continuous skin field over both sides of the two suspension joins."""
from pathlib import Path
import argparse, json, sys, struct, hashlib, shutil
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt
from mod import ROOT

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ['base','assets','previous','output','job']:parser.add_argument('--'+key,type=Path,required=True)
    a=parser.parse_args();B=a.base.resolve();N=a.assets.resolve();P=a.previous.resolve();R=a.output.resolve();J=a.job.resolve()
    if R.exists() or J.exists():raise ValueError('Use fresh candidate directories')
    if J.parent!=(ROOT/'build/body-boundary').resolve():raise ValueError('Use owned native intake directory')
    sys.path.insert(0,str(B))
    from malemod_base.join_material import support_weights, common_detail, pixel_triangles, smooth
    from malemod_base.skin_match import linear, encoded
    from malemod_base.loft_material import sample, chart
    R.mkdir(parents=True);J.mkdir(parents=True)
    previous=json.loads((P/'bake-manifest.json').read_text())
    raw=(P/'materials.bin').read_bytes();nv,nf,nm=struct.unpack_from('<3I',raw,200);offset=216+nv*25+nf+nf*3*92
    mat=np.frombuffer(raw,dtype='<f4',offset=offset).reshape(nm,3,23).copy()
    m=np.load(N/'assembly-01/body-union.npz');o=np.load(N/'runtime-01/ownership.npz');p=m['points'];f=m['faces'];rings=o['neck_rings']
    core=np.unique(np.r_[np.flatnonzero(np.any((o['frames']>=13)&(o['weights']>0),axis=1)),rings.ravel()])
    protected=np.unique(np.r_[np.flatnonzero(o['body']),o['ramp_rings'].ravel()])
    weights=support_weights(p,f,core,3.,protected)
    generated,*_=chart(p,rings,f,previous['rectangle'])
    lobe=np.any((o['frames']>=13)&(o['weights']>0),axis=1)
    ramp=np.isin(f,o['ramp_rings']).all(1)
    shaft=(~generated)&(~lobe[f].all(1))&(~o['body'][f].any(1))&(~ramp)
    section=float(np.load(N/'module-02/attachment.npz')['section_center'][0])
    remapped=shaft&(p[f][:,:,0].min(1)<section+1e-6)
    old_uv=mat[:,:,:2].astype('f2').astype(float)
    mat[remapped,:,1]+=.5
    uv=mat[:,:,:2].astype('f2').astype(float)
    if (uv[remapped,:,1]>=.99).any():raise ValueError('Relocated shaft chart exceeds atlas')
    relevant=(~o['body'][f].any(1))&(~ramp)&(~remapped)
    if (uv[relevant,:,1]>=.5).any():raise ValueError('Reserved lower atlas is occupied')
    active=(weights[f].max(1)>0)|remapped
    assert (uv[active,:,0]>=.5).all()
    # Rasterize the runtime's half-precision UVs, including their texel-center
    # convention. The old boundary-only check used unquantized authoring UVs.
    ys=[];xs=[];positions=[];normals=[];mix=[];source_uv=[];moved=[]
    for fi in np.flatnonzero(active):
        for y,x,b in pixel_triangles(uv[fi],8192,4096):
            ys.append(y);xs.append(x);positions.append(b@p[f[fi]])
            normals.append(b@mat[fi,:,2:5]);mix.append(b@weights[f[fi]])
            source_uv.append(b@old_uv[fi]);moved.append(np.full(len(y),remapped[fi]))
    y=np.concatenate(ys);x=np.concatenate(xs);position=np.concatenate(positions);normal=np.concatenate(normals);mix=np.concatenate(mix)
    source_uv=np.concatenate(source_uv);moved=np.concatenate(moved)
    normal/=np.maximum(np.linalg.norm(normal,axis=1,keepdims=True),1e-12)
    np.savez_compressed(R/'support.npz',weights=weights,core=core,protected=protected,faces=np.flatnonzero(active))
    # Neighbouring retained islands can share UV aliases. Refuse any overlap
    # with the protected pelvis instead of silently repainting it.
    changed=np.zeros((4096,8192),bool);changed[y,x]=(mix>1e-8)|moved
    # The dynamic pelvic ramp does not consume these authoring UV triangles;
    # its adapter constructs its own source strip. Check original body faces.
    for fi in np.flatnonzero(o['body'][f].all(1)):
        if uv[fi,:,0].max()<.5:continue
        for yy,xx,_ in pixel_triangles(uv[fi],8192,4096):
            if changed[yy,xx].any():raise ValueError('Material support overlaps protected atlas island')
    maps={q['channel']:q for q in previous['textures']};diffuse=np.asarray(Image.open(maps['diffuse']['path']).convert('RGBA'))
    # Sample retained shaft donors only when measuring the common pigment.
    shaft_uv=np.zeros((len(p),2));shaft_uv[f[~generated]]=old_uv[~generated]
    root_color=np.median(linear(sample(diffuse,shaft_uv[rings[-1]])[:,:3]),axis=0)
    cx,cy=np.rint(np.asarray(previous['tileCenter'])*4095).astype(int);rad=max(4,int(previous['tileRadius']*4096))
    tile=linear(diffuse[cy-rad:cy+rad,4096+cx-rad:4096+cx+rad,:3])
    repeats=maps['diffuse']['measuredRetainedDensity']/(previous['tileRadius']*4)
    detail=common_detail(tile,position,normal,repeats)
    upper_z=float(p[rings[-1],2].mean());bottom=float(p[core,2].min());span=max(upper_z-bottom,1.)
    pigment=root_color[None]*(1-.12*smooth((upper_z-position[:,2])/span))[:,None]+detail
    # Both retained and generated sides receive this common field. The small
    # overlap into the shaft fades to the unchanged original source material.
    reports=[]
    for channel in ['diffuse','normal']:
        original=np.asarray(Image.open(maps[channel]['path']).convert('RGBA'));out=original.copy()
        from scipy.ndimage import map_coordinates
        coords=np.stack([source_uv[:,1]*4096-.5,source_uv[:,0]*8192-.5])
        source=np.stack([map_coordinates(original[:,:,k].astype(float),coords,order=1,mode='nearest') for k in range(3)],-1)
        if channel=='diffuse':
            values=linear(source)*(1-mix[:,None])+pigment*mix[:,None]
            out[y,x,:3]=np.where(((mix>1e-8)|moved)[:,None],encoded(values),original[y,x,:3])
        else:
            n=source/127.5-1
            n=n*(1-mix[:,None])+np.array([0.,0.,1.])*mix[:,None]
            n/=np.maximum(np.linalg.norm(n,axis=1,keepdims=True),1e-12)
            out[y,x,:3]=np.where(((mix>1e-8)|moved)[:,None],np.clip(np.rint((n+1)*127.5),0,255).astype('u1'),original[y,x,:3])
        # Extend the edited field over its filter footprint. Treating unused
        # authoring ramp UVs as occupied blocked this gutter and left old color
        # in the bilinear footprint at the cut. The body tile stays protected.
        dist,nearest=distance_transform_edt(~changed,return_indices=True)
        gutter=(dist<=8)&(~changed)&(np.indices(changed.shape)[1]>=4096)
        out[gutter]=out[nearest[0][gutter],nearest[1][gutter]]
        assert np.array_equal(out[:,:4096],original[:,:4096])
        mask=changed|gutter
        assert np.array_equal(out[~mask],original[~mask])
        dest=J/f'atlas-{channel}.tga';Image.fromarray(out,'RGBA').save(dest)
        reports.append(dict(channel=channel,path=str(dest),sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),changedPixels=int(np.any(out!=original,axis=2).sum()),bodyPixelsExact=True,outsideSupportExact=True))
        print(channel,reports[-1],flush=True)
    updated=raw[:offset]+mat.tobytes();(R/'materials.bin').write_bytes(updated)
    (R/'materials.bin.sha256').write_text(hashlib.sha256(updated).hexdigest()+'\n')
    (R/'bake-manifest.json').write_text(json.dumps(dict(textures=reports,materialSHA256=hashlib.sha256(updated).hexdigest(),source=str(P),geometryChanged=False,materialBindingsExact=False,relocatedProximalShaftFaces=int(remapped.sum()),relocationUV=[0,.5],onlyUVBindingChanged=True,shaftBandWidth=3.,rootColorLinear=root_color.tolist(),commonPigmentFalloff=.12,sourceFineDetail='Measured retained skin tile sampled in common rest-space coordinates',normalTreatment='Map relief fades on both sides; native measured surface normals and dynamic folds retained',supportVertices=int((weights>0).sum()),protectedWeightMaximum=float(weights[protected].max())),indent=2))

if __name__=='__main__':main()
