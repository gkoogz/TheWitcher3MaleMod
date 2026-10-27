"""Emit engine-only draw intervals from the already hash-bound native topology."""
import hashlib,json,struct
from pathlib import Path


def generate(binding,metadata,topology,output):
    binding,metadata,topology,output=map(Path,(binding,metadata,topology,output));data=binding.read_bytes();report=json.loads(metadata.read_text());blob=topology.read_bytes();digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    sectioned=data[:8]==b'MMV2B04\0'
    if data[:8]not in [b'MMV2B03\0',b'MMV2B04\0'] or report['sourceBindingSHA256']!=digest(binding) or report['topologySHA256']!=digest(topology) or blob[:8]!=b'MMV2T01\0':raise ValueError('Native draw contract hash/schema differs')
    count=struct.unpack_from('<I',data,8)[0];sources=struct.unpack_from('<I',data,72)[0];at=76+sources*(36 if sectioned else 24);contracts=[];first=0
    total,triangles=struct.unpack_from('<II',blob,8)
    if count!=2 or len(report['resources'])!=count or len(blob)!=16+triangles*20:raise ValueError('Native topology bounds differ')
    faces=list(struct.iter_unpack('<5I',blob[16:]));counts=[sum(row[3]==part for row in faces)for part in range(count)]
    if sum(counts)!=triangles:raise ValueError('Native topology names an unknown resource')
    for part in range(count):
        vertices,indexbytes,vertexbytes,*reserved=struct.unpack_from('<5I',data,at);at+=44;lod=struct.unpack_from('<8I',data,at);at+=32
        row=report['resources'][part];ranges=[(first,first+lod[2])]
        if sectioned:
            n=struct.unpack_from('<I',data,at)[0];at+=4
            if not vertexbytes or not 2<=n<=16:raise ValueError('Native material section bounds differ')
            fields=['lod','material','firstVertex','vertexCount','positionOffset','uvOffset','lightingOffset','extraOffset','indexFirst','indexCount']
            sections=[];nextvertex=0;lodcounts=[0,0]
            for _ in range(n):
                s=dict(zip(fields,struct.unpack_from('<10I',data,at)));at+=40
                if s['lod']>1 or s['material']>2 or(part and s['material'])or not s['vertexCount']or s['firstVertex']!=nextvertex or not s['indexCount']or s['indexCount']%3 or s['indexFirst']*2>indexbytes or s['indexCount']*2>indexbytes-s['indexFirst']*2:raise ValueError('Native material section interval differs')
                if s['firstVertex']<lod[s['lod']]or s['firstVertex']+s['vertexCount']>lod[s['lod']]+lod[2+s['lod']]:raise ValueError('Native material section leaves its LOD')
                for key,stride in [('positionOffset',16),('uvOffset',4),('lightingOffset',8),('extraOffset',8)]:
                    if s[key]>vertexbytes or s['vertexCount']*stride>vertexbytes-s[key]:raise ValueError('Native material stream leaves allocation')
                nextvertex+=s['vertexCount'];lodcounts[s['lod']]+=s['vertexCount'];sections.append(s)
            if nextvertex!=vertices or tuple(lodcounts)!=lod[2:4]:raise ValueError('Native material vertex closure differs')
            physical=[s for s in sections if not s['lod']and s['material']!=2];reported=row.get('physicalSections',[])
            if len(physical)!=len(reported)or any(any(a[k]!=b[k]for k in fields)for a,b in zip(physical,reported))or row['vertices']!=sum(s['vertexCount']for s in physical)or row['triangles']*3!=sum(s['indexCount']for s in physical):raise ValueError('Native physical material section metadata differs')
            intervals=[]
            for level in range(2):
                pieces=sorted((s['indexFirst'],s['indexFirst']+s['indexCount'])for s in sections if s['lod']==level)
                if not pieces:raise ValueError('Native LOD material intervals missing')
                begin,end=pieces[0]
                for start,stop in pieces[1:]:
                    if start>end:raise ValueError('Native LOD material index gap')
                    end=max(end,stop)
                intervals.append((begin,end))
            indices0=intervals[0][1];indices1=intervals[1][1]-intervals[1][0]
            if intervals[0][0]or intervals[1][0]!=indices0 or intervals[1][1]*2!=indexbytes:raise ValueError('Native material index closure differs')
            ranges=[(first+s['firstVertex'],first+s['firstVertex']+s['vertexCount'])for s in physical]
        else:
            indices0=3*row['triangles'];indices1=indexbytes//2-indices0
            if vertexbytes or row['vertices']!=lod[2]:raise ValueError('Native LOD draw metadata differs')
        palette=struct.unpack_from('<I',data,at)[0];at+=4+palette*68+vertices*52
        if any(reserved) or indexbytes%2 or counts[part]!=row['triangles'] or lod[:2]!=(0,lod[2]) or lod[2]+lod[3]!=vertices or min(indices0,indices1)<=0 or indices1%3:raise ValueError('Native LOD draw metadata differs')
        if any(any(not any(begin<=id<end for begin,end in ranges)for id in face[:3])for face in faces if face[3]==part):raise ValueError('Native receiver resource lineage differs')
        contracts.append((vertices,indexbytes,(lod[0],lod[1]),(lod[2],lod[3]),(0,indices0),(indices0,indices1)));first+=vertices
    if at!=len(data) or first!=total:raise ValueError('Native binding closure differs')
    def arr(values):return '{{'+','.join(str(v)+'u'for v in values)+'}}'
    rows=['{'+f'{v}u,{n}u,'+','.join(arr(a)for a in [starts,vertices,indices,counts])+'}'for v,n,starts,vertices,indices,counts in contracts]
    text='#pragma once\nnamespace malemod::witcher::native_draw {\ninline constexpr char metadataSHA256[]="'+digest(metadata)+'";\ninline constexpr Contract resources[2]={'+','.join(rows)+'};\n}\n'
    output.parent.mkdir(parents=True,exist_ok=True)
    if not output.exists() or output.read_text()!=text:output.write_text(text)
    return contracts
