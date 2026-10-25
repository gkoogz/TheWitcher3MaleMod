"""Decode one captured native modular delivery for offline surface auditing.

This is the pre-skeletal surface, not a reconstructed screenshot. UV aliases
are joined at an explicit subpixel tolerance; the report records every dropped
zero-area index triangle. Inspect native images separately.
"""
import argparse,hashlib,json,struct
from pathlib import Path
import numpy as np

def decode(capture,render,lod=0,tolerance=1e-7):
    raw=Path(render).read_bytes()
    if raw[:8]!=b'MMRND006':raise ValueError('Measured multipart render contract required')
    offset=240;count=struct.unpack_from('<I',raw,offset)[0];offset+=4+132*count
    count=struct.unpack_from('<I',raw,offset)[0];offset+=4;resources=[]
    for _ in range(count):
        row=struct.unpack_from('<5I6f',raw,offset);offset+=44
        resources.append((np.array(row[5:8]),np.array(row[8:11])))
    data=Path(capture).read_bytes()
    if data[:8]!=b'MMMCAP01':raise ValueError('Native modular capture required')
    epoch,sequence=struct.unpack_from('<IQ',data,8);palette=struct.unpack_from('<I',data,148)[0];offset=152+128*palette
    points=[];faces=[];vertex_count=0
    vertex=np.dtype([('position','<f4',3),('rest','u1',28)])
    for _ in range(4):
        resource,level,nv,ni=struct.unpack_from('<4I',data,offset);offset+=16
        values=np.frombuffer(data,vertex,nv,offset);offset+=40*nv
        index=np.frombuffer(data,'<u4',ni,offset).reshape(-1,3);offset+=4*ni
        if level!=lod:continue
        scale,bias=resources[resource];p=values['position'].astype(np.float64)*scale+bias
        if not np.isfinite(p).all() or np.any(index>=nv):raise ValueError('Invalid native geometry')
        points.append(p);faces.append(index+vertex_count);vertex_count+=nv
    if offset!=len(data):raise ValueError('Incomplete capture parse')
    p=np.concatenate(points);f=np.concatenate(faces)
    _,first,inverse=np.unique(np.rint(p/tolerance).astype(np.int64),axis=0,return_index=True,return_inverse=True)
    joined=p[first];f=inverse[f];keep=(f[:,0]!=f[:,1])&(f[:,0]!=f[:,2])&(f[:,1]!=f[:,2])
    report=dict(captureSHA256=hashlib.sha256(data).hexdigest(),renderSHA256=hashlib.sha256(raw).hexdigest(),epoch=epoch,sequence=sequence,lod=lod,preSkinning=True,units='centimetres',aliasJoinToleranceMetres=tolerance,aliasedVertices=vertex_count,joinedVertices=len(joined),omittedCoincidentIndexTriangles=int((~keep).sum()),triangles=int(keep.sum()))
    return joined*100,f[keep],report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('capture',type=Path);parser.add_argument('render',type=Path);parser.add_argument('output',type=Path);parser.add_argument('--lod',type=int,choices=(0,1),default=0);a=parser.parse_args()
    if a.output.exists() or a.output.with_suffix('.json').exists():raise ValueError('Preserve existing decoded evidence')
    p,f,r=decode(a.capture,a.render,a.lod);a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('w') as out:np.savetxt(out,p,fmt='v %.17g %.17g %.17g');np.savetxt(out,f+1,fmt='f %d %d %d')
    a.output.with_suffix('.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
