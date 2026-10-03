"""Bounded read-only inspection of the observed single-CMesh cooked format 164.

Property lengths/CRCs are checked against actual native resources. Custom mesh
field order is cross-checked with the pinned WolvenKit-7 CMesh schema; this is
an independent diagnostic reader, not an authoring converter or engine writer.
"""
import math,struct,zlib
from player_rig_redirect import header_crc


class CookedMesh:
    def __init__(self,raw,allow_rigid=False):
        self.allow_rigid=allow_rigid
        self.raw=raw
        if len(raw)<160 or raw[:4]!=b'CR2W' or struct.unpack_from('<I',raw,4)[0]!=164:
            raise ValueError('Expected observed cooked mesh 164')
        if header_crc(raw,0)!=struct.unpack_from('<I',raw,32)[0]:raise ValueError('Mesh header CRC differs')
        def table(index,stride):
            offset,count,crc=struct.unpack_from('<III',raw,40+index*12)
            size=count*stride
            if offset<160 or size>len(raw)-offset:raise ValueError('Mesh table leaves resource')
            block=raw[offset:offset+size]
            if zlib.crc32(block)!=crc:raise ValueError('Mesh table CRC differs')
            return block
        strings=table(0,1);names=table(1,8);self.names=[]
        for offset,_ in struct.iter_unpack('<II',names):
            end=strings.find(b'\0',offset)
            if offset>=len(strings) or end<offset:raise ValueError('Mesh name leaves pool')
            self.names.append(strings[offset:end].decode('utf-8'))
        exports=table(4,24)
        entries=list(struct.iter_unpack('<HHIIIII',exports))
        # A locally authored material adds a CMaterialInstance child export.
        # Select the sole mesh by its actual class and validate every bounded
        # child export independently; no assumption about its table ordinal.
        found=[]
        for entry in entries:
            kind,flags,parent,size,position,template,crc=entry
            if kind>=len(self.names) or self.names[kind] not in ['CMesh','CMaterialInstance'] or size>len(raw)-position:raise ValueError('Unobserved native mesh child export')
            if zlib.crc32(raw[position:position+size])!=crc:raise ValueError('Child mesh export CRC differs')
            if self.names[kind]=='CMesh':found.append(entry)
        if len(found)!=1:raise ValueError('Expected one CMesh export')
        kind,flags,parent,size,position,template,crc=found[0]
        if kind>=len(self.names) or self.names[kind]!='CMesh' or size>len(raw)-position:
            raise ValueError('Unexpected mesh export')
        self.data=raw[position:position+size]
        if zlib.crc32(self.data)!=crc:raise ValueError('Mesh export CRC differs')
        self.properties,tail=self.object(self.data)
        self.cooked,_=self.object(self.get(self.properties,'cookedData','SMeshCookedData'))
        self.scale=self.vector('quantizationScale');self.offset=self.vector('quantizationOffset')
        self.palette,self.inverse_binds,self.bone_mapping=self.tail(tail)

    def object(self,data):
        if not data or data[0]!=0:raise ValueError('Unexpected serialized object flags')
        at=1;properties={}
        while at+2<=len(data):
            name=struct.unpack_from('<H',data,at)[0]
            if not name:return properties,data[at+2:]
            if at+8>len(data):raise ValueError('Truncated mesh property')
            name,kind,size=struct.unpack_from('<HHI',data,at)
            if name>=len(self.names) or kind>=len(self.names) or size<4 or 4+size>len(data)-at:
                raise ValueError('Invalid mesh property bounds')
            key=self.names[name]
            if key in properties:raise ValueError('Repeated mesh property')
            properties[key]=(self.names[kind],data[at+8:at+4+size]);at+=4+size
        raise ValueError('Missing mesh object terminator')

    @staticmethod
    def get(properties,name,kind):
        actual,data=properties[name]
        if actual!=kind:raise ValueError('Unexpected property type '+name)
        return data

    def vector(self,name):
        values,tail=self.object(self.get(self.cooked,name,'Vector'))
        if tail or set(values)!={'X','Y','Z','W'}:raise ValueError('Unexpected quantization vector')
        result=tuple(struct.unpack('<f',self.get(values,a,'Float'))[0] for a in 'XYZW')
        if not all(math.isfinite(x) for x in result):raise ValueError('Non-finite quantization')
        return result

    def tail(self,data):
        at=0
        def read(fmt):
            nonlocal at
            size=struct.calcsize(fmt)
            if size>len(data)-at:raise ValueError('Truncated mesh custom buffer')
            value=struct.unpack_from(fmt,data,at);at+=size;return value
        def count():
            first=read('<B')[0];value=first&63;shift=6;more=bool(first&64)
            while more:
                if shift>27:raise ValueError('Oversize mesh count')
                b=read('<B')[0];value|=(b&127)<<shift;more=bool(b&128);shift+=7
            if (first&128 and value) or value>100000:raise ValueError('Invalid mesh count')
            return value
        groups=count()
        if groups!=2:raise ValueError('Expected both native mesh chunk groups')
        for i in range(groups):
            ids=read('<'+str(count())+'H');padding=read('<f')[0]
            if ids!=(i,) or not math.isfinite(padding):raise ValueError('Unexpected native chunk group')
        palette=[]
        for _ in range(count()):
            index=read('<H')[0]
            if index>=len(self.names):raise ValueError('Bone name leaves pool')
            palette.append(self.names[index])
        matrices=[read('<16f') for _ in range(count())]
        radii=[read('<f')[0] for _ in range(count())]
        mapping=[read('<I')[0] for _ in range(count())]
        if at!=len(data) or (not palette and not self.allow_rigid) or len(matrices)!=len(palette) or len(radii)!=len(palette) or len(mapping)!=len(palette):
            raise ValueError('Unexpected native skin tail dimensions')
        if not all(math.isfinite(x) for m in matrices for x in m) or not all(math.isfinite(x) for x in radii):
            raise ValueError('Non-finite native skin tail')
        return palette,matrices,mapping
