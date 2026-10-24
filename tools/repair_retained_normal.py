"""Repair empty normal-map bands only inside the measured retained sac chart."""
from pathlib import Path
import argparse,json,shutil
import numpy as np
from PIL import Image,ImageDraw
from scipy.spatial import cKDTree
from mod import digest,write_json
from malemod_base.loft_material import retained_skin_faces,retained_skin_tile,fill_normal_voids,fill_color_voids


def repair(probe,atlas,output):
    if output.exists():raise ValueError('Use a fresh material repair directory')
    dtype=np.dtype([('p','<f8',(3,)),('normal','<u4'),('tangent','<u4'),('uv','<f2',(2,))])
    attrs=np.fromfile(str(probe)+'-native-attributes.bin',dtype)
    faces=np.fromfile(str(probe)+'-native-triangles.bin','<u4').reshape(-1,3)
    uv=attrs['uv'].astype(float);points=attrs['p']
    inside=(uv[:,0]>.762)&(uv[:,0]<.988)&(uv[:,1]>.3948)&(uv[:,1]<.4852)
    patch=inside[faces].all(1);patch_ids=np.unique(faces[patch]);retained=np.unique(faces[~patch]);retained=retained[~inside[retained]]
    boundary=patch_ids[abs(uv[patch_ids,1]-.395)<.0002]
    distance,match=cKDTree(points[retained]).query(points[boundary]);seeds=retained[match[distance<2e-6]]
    if len(seeds)<100:raise ValueError('Missing measured retained source boundary')
    normal=np.asarray(Image.open(atlas/'atlas-normal.tga').convert('RGBA'))
    height,width=normal.shape[:2]
    triangles=retained_skin_faces(points,faces,uv,patch,seeds,include_chart_bridges=True)
    mask=Image.new('L',(width,height));draw=ImageDraw.Draw(mask)
    for tri in uv[triangles]:draw.polygon([tuple(p*[width-1,height-1]) for p in tri],fill=255)
    center,half,_,_=retained_skin_tile(points,faces,uv,patch,seeds,width,height,normal)
    x,y=center;rx,ry=half;tile=normal[y-ry:y+ry,x-rx:x+rx,:3]
    changed,count=fill_normal_voids(normal,np.asarray(mask)>0,tile)
    if not count:raise ValueError('No broad empty normal bands were found')
    outside=np.asarray(mask)==0
    if not np.array_equal(changed[outside],normal[outside]):raise ValueError('Normal repair escaped measured retained skin')
    output.mkdir(parents=True)
    Image.fromarray(changed).save(output/'atlas-normal.tga')
    diffuse=np.asarray(Image.open(atlas/'atlas-diffuse.tga').convert('RGBA'))
    # The retained seam spans atlas padding between the original skin islands.
    # Measure that constant padding value rather than inventing a skin color.
    colors,counts=np.unique(diffuse[np.asarray(mask)>0,:3],axis=0,return_counts=True)
    background=colors[counts.argmax()]
    color,color_count=fill_color_voids(diffuse,np.asarray(mask)>0,diffuse[y-ry:y+ry,x-rx:x+rx],background)
    if not np.array_equal(color[outside],diffuse[outside]):raise ValueError('Color repair escaped measured retained skin')
    Image.fromarray(color).save(output/'atlas-diffuse.tga')
    write_json(output/'repair.json',dict(source=str(atlas),probeSHA256=digest(Path(str(probe)+'-native-attributes.bin')),
        sourceNormalSHA256=digest(atlas/'atlas-normal.tga'),normalSHA256=digest(output/'atlas-normal.tga'),
        sourceDiffuseSHA256=digest(atlas/'atlas-diffuse.tga'),diffuseSHA256=digest(output/'atlas-diffuse.tga'),
        changedNormalPixels=count,changedColorPixels=color_count,paddingColor=background.tolist(),retainedTriangles=len(triangles),outsideMaskExact=True,sourceTileCenter=center.tolist(),sourceTileHalf=half.tolist(),nativeObserved=False))
    print(json.dumps(dict(changedNormalPixels=count,retainedTriangles=len(triangles))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('probe','atlas','output'):p.add_argument('--'+key,type=Path,required=True)
    repair(**vars(p.parse_args()))
