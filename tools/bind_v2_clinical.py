"""Bind original LOD0 native body triangles for current skinned receivers."""
import struct,argparse
from pathlib import Path
from mod import ROOT,write_json,digest
from v2_native_binding import read_binding,cooked_resource

def bind(output=None):
    out=Path(output)if output is not None else ROOT/'v2/build/runtime-binding'
    binding=read_binding(out/'geralt-source-binding.bin');triangles=[];proof=[]
    for resource,description in enumerate(binding['resources']):
        path,mesh,buffer,sections=cooked_resource(resource,out)
        offset=struct.unpack('<I',mesh.get(mesh.cooked,'indexBufferOffset','Uint32'))[0]
        face_id=0;physical_vertices=0;used=[]
        for section in sections:
            if section['lod']!=0 or section['material']==2:continue # Same physical surface, alternate state material.
            n=section['indexCount'];indices=struct.unpack_from('<'+str(n)+'H',buffer,offset+section['indexFirst']*2)
            first=description['firstVertex']+section['firstVertex']
            for face in range(n//3):
                a,b,c=indices[face*3:face*3+3];triangles.append((first+a,first+b,first+c,resource,face_id));face_id+=1
            physical_vertices+=section['vertexCount'];used.append(section)
        proof.append(dict(resource=path.stem,nativeSHA256=digest(path),bufferSHA256=digest(Path(str(path)+'.1.buffer')),vertices=physical_vertices,triangles=face_id,physicalSections=used))
    target=out/'geralt-clinical-topology.bin'
    target.write_bytes(b'MMV2T01\0'+struct.pack('<II',binding['totalVertices'],len(triangles))+b''.join(struct.pack('<5I',*t)for t in triangles))
    report=dict(schema='malemod.witcher-v2-clinical-topology/1',sourceBindingSHA256=digest(out/'geralt-source-binding.bin'),topologySHA256=digest(target),resources=proof,totalVertices=binding['totalVertices'],triangles=len(triangles),originalCompleteSurface=True,materialVariantsDeduplicated=True)
    write_json(out/'clinical-topology.json',report);print(report)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path);args=parser.parse_args();bind(args.output)
