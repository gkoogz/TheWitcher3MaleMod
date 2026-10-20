"""Author an owned skin graph with a second-UV root material transition.

Preserves the stock skin lighting graph. Only its four texture samples receive
an optional second-UV sample, selected by 1 - vertex alpha. Stock vertices use
alpha=1. The adapter supplies the measured pelvis UV and weight on the annulus.
Official REDkit resave/cooking and native review are required before adoption.
"""
from pathlib import Path
import argparse, copy, hashlib, json, struct, zlib
from soft_cloth_material import _graph
from player_rig_redirect import header_crc
from prepare_garment_carrier import native_objects


def encoded_string(value):
    data=value.encode('ascii');n=len(data);out=bytearray([(n&63)|128]);n>>=6
    if n:out[0]|=64
    while n:
        value=n&127;n>>=7;out.append(value|(128 if n else 0))
    return bytes(out)+data


def name_hash(value):
    h=2166136261
    for b in value.encode('latin1')+b'\0':h=((h^b)*16777619)&0xffffffff
    return h if value else 0


class Graph:
    def __init__(self,source):
        self.raw=Path(source).read_bytes()
        self.reader,self.imports,self.original,self.name,self.ptr,self.array=_graph(source)
        self.objects=copy.deepcopy(self.original);self.names=list(self.reader.names)
        self.root=next(i for i,v in enumerate(self.objects) if v[0]=='CMaterialGraph')
        self.blocks=self.ids(self.root,'blocks')
    def nid(self,name):
        if name not in self.names:self.names.append(name)
        return self.names.index(name)
    def prop(self,i,key,ty,data):self.objects[i][2][key]=(ty,data)
    def ids(self,i,key):
        data=self.objects[i][2].get(key,('',struct.pack('<I',0)))[1]
        return [x[0]-1 for x in struct.iter_unpack('<i',data[4:])]
    def pointers(self,i,key,ty,ids):self.prop(i,key,ty,struct.pack('<I',len(ids))+b''.join(struct.pack('<i',j+1) for j in ids))
    def named(self,i,key='name'):return self.names[struct.unpack('<H',self.objects[i][2][key][1])[0]]
    def socket(self,i,name):return next(j for j in self.ids(i,'sockets') if self.named(j)==name)
    def peer(self,i):
        edges=self.ids(i,'connections')
        if len(edges)!=1:raise ValueError('Expected one upstream socket')
        return struct.unpack('<i',self.objects[edges[0]][2]['destination'][1])[0]-1
    def connect(self,src,dst):
        if self.ids(dst,'connections'):raise ValueError('Input already connected')
        template=next(v for v in self.original if v[0]=='CGraphConnection')
        first=len(self.objects)
        for a,b in [(src,dst),(dst,src)]:
            c=copy.deepcopy(template);c[2].clear()
            c[2].update(source=('ptr:CGraphSocket',struct.pack('<i',a+1)),destination=('ptr:CGraphSocket',struct.pack('<i',b+1)))
            self.objects.append(c)
        self.pointers(src,'connections','array:2,0,ptr:CGraphConnection',self.ids(src,'connections')+[first])
        self.pointers(dst,'connections','array:2,0,ptr:CGraphConnection',[first+1])
    def disconnect(self,src,dst):
        for a,b in [(src,dst),(dst,src)]:
            keep=[e for e in self.ids(a,'connections') if struct.unpack('<i',self.objects[e][2]['destination'][1])[0]-1!=b]
            self.pointers(a,'connections','array:2,0,ptr:CGraphConnection',keep)
    def clone_block(self,index):
        block=copy.deepcopy(self.objects[index]);block[2].pop('position',None)
        i=len(self.objects);self.objects.append(block);sockets=[]
        for old in self.ids(index,'sockets'):
            socket=copy.deepcopy(self.objects[old]);socket[2].pop('connections',None)
            socket[2]['block']=('ptr:CGraphBlock',struct.pack('<i',i+1))
            sockets.append(len(self.objects));self.objects.append(socket)
        self.pointers(i,'sockets','array:2,0,ptr:CGraphSocket',sockets);self.blocks.append(i)
        return i
    def function(self,code,args):
        template=next(v for v in self.original if v[0]=='CMaterialBlockCustomFunction')
        block=copy.deepcopy(template);block[2].pop('position',None)
        block[2]['customCode']=('String',encoded_string(code))
        i=len(self.objects);self.objects.append(block);ids=[]
        for label,kind in [('Out','CMaterialOutputSocket')]+[(a,'CMaterialInputSocket')for a in args]:
            socket=copy.deepcopy(next(v for v in self.original if v[0]==kind))
            socket[2].pop('connections',None);socket[2]['block']=('ptr:CGraphBlock',struct.pack('<i',i+1))
            socket[2]['name']=('CName',struct.pack('<H',self.nid(label)))
            ids.append(len(self.objects));self.objects.append(socket)
        self.pointers(i,'sockets','array:2,0,ptr:CGraphSocket',ids);self.blocks.append(i)
        return i
    def write(self,path):
        self.pointers(self.root,'blocks','array:2,0,ptr:CGraphBlock',self.blocks)
        raw=self.raw;tables=[];strides=[1,8,8,16,24]
        for k,stride in enumerate(strides):
            offset,count,crc=struct.unpack_from('<III',raw,40+12*k);tables.append(raw[offset:offset+count*stride])
        if any(struct.unpack_from('<II',raw,40+12*k)!=(0,0)for k in range(5,10)):raise ValueError('External graph buffers unsupported')
        strings=bytearray(tables[0]);names=bytearray(tables[1])
        for name in self.names[len(self.reader.names):]:
            names+=struct.pack('<II',len(strings),name_hash(name));strings+=name.encode('latin1')+b'\0'
        tables[0]=strings;tables[1]=names
        entries=list(struct.iter_unpack('<HHIIIII',tables[4]));payloads=[]
        for kind,flags,props,tail in self.objects:
            blob=b'\0'
            for key,(ty,value) in props.items():
                blob+=struct.pack('<HHI',self.nid(key),self.nid(ty),4+len(value))+value
            payloads.append(blob+b'\0\0'+tail)
        # Property names/types must have been registered before table encoding.
        if len(names)!=len(self.names)*8:raise ValueError('Unregistered graph property name/type')
        at=160+sum(len(t) for t in tables[:4])+24*len(self.objects);table=bytearray();data=bytearray()
        for i,(obj,payload) in enumerate(zip(self.objects,payloads)):
            entry=entries[i] if i<len(entries) else next(e for e in entries if self.reader.names[e[0]]==obj[0])
            kind,flags,parent,_,_,template,_=entry
            table+=struct.pack('<HHIIIII',kind,flags,parent,len(payload),at,template,zlib.crc32(payload));data+=payload;at+=len(payload)
        tables[4]=table;out=bytearray(raw[:160]);at=160
        for k,t in enumerate(tables):
            struct.pack_into('<III',out,40+k*12,at if t else 0,len(t)//strides[k],zlib.crc32(t));out+=t;at+=len(t)
        out+=data;struct.pack_into('<II',out,24,len(out),len(out));struct.pack_into('<I',out,32,header_crc(out,0))
        Path(path).parent.mkdir(parents=True,exist_ok=True);Path(path).write_bytes(out);native_objects(path)


def author(source,target):
    g=Graph(source);o=g.original;cache={}
    uv=next(i for i,v in enumerate(o) if v[0]=='CMaterialBlockTexCoords')
    secondary=g.clone_block(uv);g.nid('coordinatesIndex');g.nid('Int32')
    g.prop(secondary,'coordinatesIndex','Int32',struct.pack('<i',1));cache[uv]=secondary
    color=next(i for i,v in enumerate(o) if v[0]=='CMaterialBlockVertexColor')
    blend=g.socket(color,'Alpha')
    for i,v in enumerate(o):
        if v[0]=='CMaterialBlockVertexColor' and (g.ids(g.socket(i,'Alpha'),'connections') or g.ids(g.socket(i,'Color'),'connections')):
            raise ValueError('Reserved alpha channel is already used')
    # Clone only the UV computation chain; keep texture and scalar parameters
    # shared so all character material-instance settings remain authoritative.
    def duplicate(block):
        if block in cache:return cache[block]
        if o[block][0].startswith('CMaterialParameter'):return block
        new=g.clone_block(block);cache[block]=new
        for old in g.ids(block,'sockets'):
            if not o[old][0].startswith('CMaterialInput') or not g.ids(old,'connections'):continue
            peer=g.peer(old);owner=g.ptr(o[peer][2],'block');upstream=duplicate(owner)
            g.connect(g.socket(upstream,g.named(peer)),g.socket(new,g.named(old)))
        return new
    samples=[]
    for block,(kind,_,props,_) in enumerate(o):
        if kind!='CMaterialBlockSamplerTexture':continue
        new=g.clone_block(block)
        for old in g.ids(block,'sockets'):
            if not o[old][0].startswith('CMaterialInput'):continue
            label=g.named(old);dst=g.socket(new,label)
            if label=='UV':
                if g.ids(old,'connections'):
                    peer=g.peer(old);owner=g.ptr(o[peer][2],'block');g.connect(g.socket(duplicate(owner),g.named(peer)),dst)
                else:g.connect(g.socket(secondary,'UV'),dst)
            elif g.ids(old,'connections'):g.connect(g.peer(old),dst)
        source_texture=g.peer(g.socket(block,'Texture'));parameter=g.ptr(o[source_texture][2],'block')
        channel=g.named(parameter,'parameterName');samples.append(channel)
        for label,component in [('Color',''),('Red','.x'),('Green','.y'),('Blue','.z'),('Alpha','.w')]:
            old=g.socket(block,label);destinations=[struct.unpack('<i',g.objects[e][2]['destination'][1])[0]-1 for e in g.ids(old,'connections')]
            if not destinations:continue
            ty='float4' if not component else 'float'
            function=g.function(f'{ty} rootBlend{channel}{label}( {ty} first, {ty} second, float cutoff )\n{{\n return lerp(second, first, saturate(cutoff));\n}}',['first','second','cutoff'])
            for dst in destinations:g.disconnect(old,dst);g.connect(g.socket(function,'Out'),dst)
            g.connect(old,g.socket(function,'first'));g.connect(g.socket(new,label),g.socket(function,'second'));g.connect(blend,g.socket(function,'cutoff'))
    if set(samples)!={'Diffuse','Normal','Ambient','DetailNormal'}:raise ValueError('Unexpected stock skin sampling graph')
    g.write(target)
    return dict(sourceSHA256=hashlib.sha256(Path(source).read_bytes()).hexdigest(),outputSHA256=hashlib.sha256(Path(target).read_bytes()).hexdigest(),channels=samples,secondaryUV=1,blendChannel='vertex alpha: 1 original, 0 pelvis',officialResaveRequired=True,nativeObserved=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('target',type=Path);a=p.parse_args()
    if a.target.exists():raise ValueError('Use a fresh owned graph path')
    proof=author(a.source,a.target);a.target.with_suffix('.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof))
