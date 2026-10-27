"""Read hash-bound v2 bindings and their actual cooked section layout."""
import struct
from pathlib import Path
import numpy as np
from mod import ROOT,read_json,digest
from packed_mesh_format import CookedMesh

ROW_DTYPE=np.dtype([('baseline','u1',28),('donors','<u4',3),('weights','<f4',3)])
SECTION_KEYS=('lod','material','firstVertex','vertexCount','positionOffset','uvOffset','lightingOffset','extraOffset','indexFirst','indexCount')

def read_binding(path):
    data=Path(path).read_bytes();at=0
    def take(size):
        nonlocal at
        if size<0 or size>len(data)-at:raise ValueError('Truncated native binding')
        part=data[at:at+size];at+=size;return part
    def unpack(fmt):return struct.unpack(fmt,take(struct.calcsize(fmt)))
    magic=take(8)
    if magic not in (b'MMV2B03\0',b'MMV2B04\0'):raise ValueError('Unknown native binding')
    version=int(chr(magic[6]));count=unpack('<I')[0]
    if count!=2:raise ValueError('Both native resources required')
    rotation=np.frombuffer(take(36),'<f4').reshape(3,3);root=np.frombuffer(take(12),'<f4');target=np.frombuffer(take(12),'<f4')
    sources=unpack('<I')[0]
    if sources!=17528+15168+5615:raise ValueError('Canonical bank dimensions differ')
    positions=np.frombuffer(take(sources*12),'<f4').reshape(-1,3);normals=np.frombuffer(take(sources*12),'<f4').reshape(-1,3)
    tangents=np.frombuffer(take(sources*12),'<f4').reshape(-1,3)if version==4 else None
    resources=[];first=0
    for resource in range(count):
        vertices,index_bytes,vertex_bytes,reserved0,reserved1=unpack('<5I')
        if not 0<vertices<=100000 or not 0<index_bytes<=2000000 or index_bytes%2 or reserved0 or reserved1 or (version==3 and vertex_bytes):
            raise ValueError('Native allocation bounds differ')
        scale=unpack('<3f');bias=unpack('<3f');ranges=unpack('<8I')
        if ranges[0]!=0 or ranges[1]!=ranges[2]or sum(ranges[2:4])!=vertices:raise ValueError('Native LOD intervals differ')
        sections=[]
        if version==4:
            section_count=unpack('<I')[0]
            if not 2<=section_count<=16 or not vertex_bytes:raise ValueError('Native section dimensions differ')
            for _ in range(section_count):sections.append(dict(zip(SECTION_KEYS,unpack('<10I'))))
            next_vertex=0;lod_counts=[0,0];intervals=[]
            for section in sections:
                lod=section['lod'];n=section['vertexCount'];indices=section['indexCount']
                if lod not in (0,1)or section['material']not in (0,1,2)or (resource and section['material'])or not 0<n<=65535 or not indices or indices%3:
                    raise ValueError('Invalid native section')
                if section['firstVertex']!=next_vertex or n>vertices-next_vertex or section['indexFirst']>index_bytes//2 or indices>index_bytes//2-section['indexFirst']:
                    raise ValueError('Native sections do not partition allocation')
                if next_vertex<ranges[lod]or next_vertex+n>ranges[lod]+ranges[2+lod]:raise ValueError('Native section leaves LOD')
                for key,stride in zip(SECTION_KEYS[4:8],(16,4,8,8)):
                    if section[key]>vertex_bytes or n*stride>vertex_bytes-section[key]:raise ValueError('Native section stream leaves allocation')
                for other in intervals:
                    overlaps=section['indexFirst']<other['indexFirst']+other['indexCount']and other['indexFirst']<section['indexFirst']+indices
                    if overlaps and (section['lod']!=other['lod']or {section['material'],other['material']}!={1,2}or n!=other['vertexCount']):
                        raise ValueError('Unobserved overlapping native material index intervals')
                next_vertex+=n;lod_counts[lod]+=n;intervals.append(section)
            covered=0
            for index_first,index_end in sorted((s['indexFirst'],s['indexFirst']+s['indexCount'])for s in sections):
                if index_first>covered:raise ValueError('Native index interval gap')
                covered=max(covered,index_end)
            if next_vertex!=vertices or covered*2!=index_bytes or tuple(lod_counts)!=ranges[2:4]:raise ValueError('Incomplete native sections')
        bones=unpack('<I')[0]
        if not 0<bones<=256:raise ValueError('Native palette bounds differ')
        palette=[(unpack('<I')[0],unpack('<16f'))for _ in range(bones)]
        if any(i>=94 for i,_ in palette):raise ValueError('Nonstock native bone')
        rows=np.frombuffer(take(vertices*52),ROW_DTYPE)
        resources.append(dict(resource=resource,firstVertex=first,vertexCount=vertices,indexBytes=index_bytes,vertexBufferBytes=vertex_bytes,
            scale=scale,bias=bias,lodFirstVertex=ranges[:2],lodVertexCount=ranges[2:4],lodUVOffset=ranges[4:6],lodExtraOffset=ranges[6:8],
            sections=sections,palette=palette,rows=rows))
        first+=vertices
    if at!=len(data):raise ValueError('Trailing native binding')
    return dict(version=version,rotation=rotation,sourceRoot=root,targetRoot=target,positions=positions,normals=normals,tangents=tangents,resources=resources,totalVertices=first)

def cooked_resource(resource,output=None):
    output=Path(output)if output is not None else ROOT/'v2/build/runtime-binding'
    manifest=read_json(output/'manifest.json');row=manifest['resources'][resource]
    if digest(output/'geralt-source-binding.bin')!=manifest['bindingSHA256']:raise ValueError('Binding provenance changed')
    path=Path(row['cookedPath'])if row.get('cookedPath')else next((ROOT/'v2/build/native-fit-02/build').glob('package-*/cooked/characters/models/geralt/body/model/'+row['resource']+'.w2mesh'))
    buffer_path=Path(str(path)+'.1.buffer')
    if digest(path)!=row['cookedSHA256']or digest(buffer_path)!=row['bufferSHA256']:raise ValueError('Native source differs from binding provenance')
    mesh=CookedMesh(path.read_bytes(),allow_stock_torso_mapping=resource==1,allow_multi_section=True)
    buffer=buffer_path.read_bytes();sections=mesh.skin_sections(buffer)
    bound=read_binding(output/'geralt-source-binding.bin')['resources'][resource]['sections']
    if bound:
        described=row['sections']
        if len(bound)!=len(described)or len(bound)!=len(sections):raise ValueError('Native bound section count differs')
        for actual,section,description in zip(sections,bound,described):
            if any(section[key]!=description[key]for key in SECTION_KEYS)or any(actual[key]!=section[key]for key in SECTION_KEYS if key!='material'):
                raise ValueError('Native section differs from bound material layout')
            if actual['material']!=description.get('nativeMaterial',section['material']):raise ValueError('Native material slot differs from observed contract')
            actual['nativeMaterial']=actual['material'];actual['material']=section['material']
    return path,mesh,buffer,sections
