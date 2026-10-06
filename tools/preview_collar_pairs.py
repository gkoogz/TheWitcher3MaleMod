"""Render camera-matched original-pelvis/candidate pairs from measured meshes.

Software geometry preview only: no generated imagery, game launch or install.
The left mesh includes the original uncut lower-body triangles, not an opening
filled by an invented cap. Both panels use identical cameras and lighting.
"""
import argparse,subprocess
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from mod import ROOT,read_json,write_json,digest,settings
from review_collar_integrity import VERTEX,contract

def unit(a):
    return a/np.maximum(np.linalg.norm(a,axis=-1,keepdims=True),1e-20)

def original(binding,job):
    receipt=read_json(binding/'manifest.json')
    lower=np.load(ROOT/receipt['lods'][0]['bindingPath'])
    upper=np.load(job/'part2.npz')
    p=np.vstack([lower['body_original_points'],upper['points']])/100
    f=np.vstack([lower['body_original_faces'],upper['faces']+len(lower['body_original_points'])])
    n=np.zeros_like(p)
    face=np.cross(p[f[:,1]]-p[f[:,0]],p[f[:,2]]-p[f[:,0]])
    for i in range(3):np.add.at(n,f[:,i],face)
    return p,f,unit(n)

def candidate(directory,label,lods):
    v=np.fromfile(directory/(label+'-render.bin'),VERTEX)
    p=[];f=[];n=[];offset=0
    for l in lods:
        if l['lod']:continue
        rows=v[l['first']:l['first']+l['n']]
        p.append(rows['position'].astype(float));n.append(rows['normal'].astype(float))
        f.append(l['faces']+offset);offset+=len(rows)
    return np.vstack(p),np.vstack(f),unit(np.vstack(n))

def render(surface,azimuth,size=680,span=.90,center=(0.,.18,.985)):
    p,f,n=surface
    # Looking from front, side or oblique with a slight downward elevation.
    az=np.deg2rad(azimuth);elevation=np.deg2rad(7)
    view=np.array([np.cos(az)*np.cos(elevation),np.sin(az)*np.cos(elevation),np.sin(elevation)])
    right=unit(np.cross([0.,0.,1.],view));up=np.cross(view,right)
    q=p-np.asarray(center)
    x=q@right/span*size+size/2;y=size/2-q@up/span*size;depth=q@view
    normal=unit(n)
    light=unit(view*.65+np.array([-.25,.15,.7]));fill=unit(-view*.3+np.array([.4,.2,.5]))
    shade=.40+.45*np.maximum(normal@light,0)+.15*np.maximum(normal@fill,0)
    # A neutral clay material makes geometry readable; it is not a skin preview.
    colors=np.clip(shade[:,None]*np.array([.83,.78,.71]),0,1)
    image=np.empty((size,size,3),float);image[:]=[.92,.93,.94]
    zbuffer=np.full((size,size),-np.inf)
    for face in f:
        xx=x[face];yy=y[face]
        left=max(0,int(np.floor(xx.min())));rightPixel=min(size-1,int(np.ceil(xx.max())))
        top=max(0,int(np.floor(yy.min())));bottom=min(size-1,int(np.ceil(yy.max())))
        if left>rightPixel or top>bottom:continue
        denominator=(yy[1]-yy[2])*(xx[0]-xx[2])+(xx[2]-xx[1])*(yy[0]-yy[2])
        if abs(denominator)<1e-9:continue
        gy,gx=np.mgrid[top:bottom+1,left:rightPixel+1];gx=gx+.5;gy=gy+.5
        a=((yy[1]-yy[2])*(gx-xx[2])+(xx[2]-xx[1])*(gy-yy[2]))/denominator
        b=((yy[2]-yy[0])*(gx-xx[2])+(xx[0]-xx[2])*(gy-yy[2]))/denominator;c=1-a-b
        z=a*depth[face[0]]+b*depth[face[1]]+c*depth[face[2]]
        sub=zbuffer[top:bottom+1,left:rightPixel+1]
        mask=(a>=-1e-7)&(b>=-1e-7)&(c>=-1e-7)&(z>sub)
        if not mask.any():continue
        rgb=a[:,:,None]*colors[face[0]]+b[:,:,None]*colors[face[1]]+c[:,:,None]*colors[face[2]]
        image[top:bottom+1,left:rightPixel+1][mask]=rgb[mask];sub[mask]=z[mask]
    return Image.fromarray(np.uint8(np.clip(image,0,1)*255))

def font(size):
    return ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',size)

def main():
    a=argparse.ArgumentParser(description=__doc__)
    for k in ['binding','render','job','output']:a.add_argument('--'+k,type=Path,required=True)
    a.add_argument('--case',action='append',required=True,help='label=artifact-directory')
    a.add_argument('--span',type=float,default=.90)
    a.add_argument('--center',type=float,nargs=3,default=[0.,.18,.985])
    a.add_argument('--reference-candidate',type=Path,help='Compare with an earlier export of the same labeled cases instead of the bare pelvis')
    args=a.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    if not np.isfinite(args.span) or args.span<=0 or not np.isfinite(args.center).all():raise ValueError('Invalid preview camera')
    baseline=original(args.binding,args.job);lods=contract(args.render/'geralt.render')
    views=[(90,'Front'),(0,'Side'),(45,'Oblique')]
    bare={name:render(baseline,angle,span=args.span,center=args.center) for angle,name in views}
    base=Path(settings()['base'])
    sourceRevision=subprocess.check_output(['git','-C',str(base),'rev-parse','HEAD'],text=True).strip()
    sourceDirty=subprocess.check_output(['git','-C',str(base),'status','--porcelain','--untracked-files=no'],text=True).strip()
    proof=dict(kind='camera-matched measured geometry preview',gameplay=False,installed=False,
        bindingSHA256=digest(args.binding/'geralt.bindings'),renderSHA256=digest(args.render/'geralt.render'),
        bindingBaseCommit=read_json(args.binding/'manifest.json')['baseCommit'],sourceBaseCommit=sourceRevision,sourceDirty=bool(sourceDirty),
        sourceHashes=dict(rootTransition=digest(base/'include/malemod/surface/root_transition.hpp'),targetSurface=digest(ROOT/'native/target_surface.cpp'),
            graftHeader=digest(base/'include/malemod/surface/graft_runtime.hpp'),graftImplementation=digest(base/'src/surface/graft_runtime.cpp'),
            lighting=digest(base/'include/malemod/surface/lighting.hpp'),renderContract=digest(ROOT/'native/render_contract.hpp')),
        originalLowerSourceSHA256=read_json(args.binding/'manifest.json')['lods'][0]['bindingSHA256'],
        camera=dict(center=args.center,span=args.span,elevationDegrees=7),material='neutral clay; no game texture or shadow simulation',cases=[])
    for spec in args.case:
        label,directory=spec.split('=',1);directory=Path(directory)
        data=candidate(directory,label,lods)
        leftName='bare pelvis'
        leftPanels=bare
        referenceHash=None
        if args.reference_candidate:
            reference=candidate(args.reference_candidate,label,lods)
            leftPanels={name:render(reference,angle,span=args.span,center=args.center) for angle,name in views}
            leftName='previous candidate'
            referenceHash=digest(args.reference_candidate/(label+'-render.bin'))
        canvas=Image.new('RGB',(1400,2300),(244,246,248));draw=ImageDraw.Draw(canvas)
        case=next(r for r in read_json(directory/'cases.json') if r['label']==label)
        overall,width,angle=(int(case['controls'][i]) for i in [1,3,7])
        state=['Erect','Semi','Full Floppy'][int(case['controls'][0])]
        title=f'Overall {overall} / Width {width} / Angle {angle} / {state}'
        draw.text((24,15),title,font=font(30),fill='#24313b')
        leftTitle='Previous candidate' if args.reference_candidate else 'Original uncut pelvis'
        draw.text((24,58),leftTitle+'     |     Proposed attachment — identical camera, scale and lighting',font=font(23),fill='#46545f')
        for row,(azimuth,name) in enumerate(views):
            y=105+row*710
            canvas.paste(leftPanels[name],(10,y+25));canvas.paste(render(data,azimuth,span=args.span,center=args.center),(710,y+25))
            draw.text((24,y),name+' / '+leftName,font=font(23),fill='#24313b')
            draw.text((724,y),name+' / candidate',font=font(23),fill='#24313b')
        draw.text((24,2250),'Offline measured mesh render. Not installed; game materials, skinning and motion remain to be reviewed.',font=font(20),fill='#46545f')
        path=args.output/(label+'.png');canvas.save(path)
        proof['cases'].append(dict(label=label,controls=case['controls'],nativeExportSHA256=digest(directory/(label+'-render.bin')),referenceExportSHA256=referenceHash,image=path.name,imageSHA256=digest(path)))
        print(path,flush=True)
    write_json(args.output/'manifest.json',proof)

if __name__=='__main__':main()
