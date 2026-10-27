"""Measure rest-only trim clearance against the actual authored Geralt body.

Consumes the native transport probe's garment output. Native animated visual
review remains required; this check makes no gameplay/attachment claim.
"""
import argparse,re
import numpy as np
from pathlib import Path
from mod import ROOT,digest,write_json
from bind_wolverine_v2 import nearest_triangle
from wcc_fbx import Document,triangles


def measure(path):
    build=ROOT/'v2/build'
    garment=np.fromfile(path,'<f4').reshape(-1,12)[:,:3]
    if garment.shape!=(4279,3) or not np.isfinite(garment).all():
        raise ValueError('Unexpected canonical garment probe output')
    lower=np.load(build/'fitted-geralt/lod0.npz')
    vertices=lower['points']*.01
    faces=lower['faces'];faces=faces[np.all(faces<int(lower['bodyCount']),axis=1)]
    torso=Document(build/'geralt-base/torso.fbx').meshes[0]
    faces=np.vstack([faces,triangles(torso)+len(vertices)])
    vertices=np.vstack([vertices,torso.array('Vertices').reshape(-1,3)*.01])
    recipe=(build/'canonical-core/canonical-meridian-recipe.inc').read_text()
    block=recipe.split('::Face faces[]={',1)[1].split('};',1)[0]
    garment_faces=np.asarray([[int(x)for x in re.findall(r'\d+',line)]for line in block.strip().splitlines()])
    results={}
    for name,first,last in [('band',2561,3247),('straps',3247,4239)]:
        selected=garment_faces[(garment_faces.min(1)>=first)&(garment_faces.max(1)<last)]
        points=garment[selected]
        samples=np.vstack([garment[first:last],points.mean(1),
                           (points[:,0]+points[:,1])*.5,
                           (points[:,1]+points[:,2])*.5,
                           (points[:,2]+points[:,0])*.5])
        ids,weights,_=nearest_triangle(samples,vertices,faces)
        tri=vertices[ids]
        normals=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
        normals/=np.linalg.norm(normals,axis=1)[:,None]
        closest=(tri*weights[:,:,None]).sum(1)
        signed=((samples-closest)*normals).sum(1)
        results[name]=dict(samples=len(samples),minimumMeters=float(signed.min()),
                           penetratedSamples=int(np.sum(signed<-.0001)))
    report=dict(schema='malemod.witcher-v2-rest-trim-clearance/1',
                garmentSHA256=digest(path),results=results,
                passed=all(x['penetratedSamples']==0 for x in results.values()),
                nativeAnimatedVisualReviewPassed=False)
    write_json(path.with_suffix(path.suffix+'.clearance.json'),report)
    print(report)
    if not report['passed']:raise ValueError('Rest trim still intersects Geralt')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('probe_garment',type=Path)
    measure(parser.parse_args().probe_garment)
