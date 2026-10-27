"""Bounded read-only inspection of the observed single-CMesh cooked format 164.

Property lengths/CRCs are checked against actual native resources. Custom mesh
field order is cross-checked with the pinned WolvenKit-7 CMesh schema; this is
an independent diagnostic reader, not an authoring converter or engine writer.
"""
import math,struct,zlib
from player_rig_redirect import header_crc

def decode_render_chunks(payload,section_groups=None):
    """Read the observed native two-LOD packed records, opaque or forward.

    The official opaque rigid cook has six records (two full lighting records
    and four reduced shadow records); the forward alpha cook has two. Classify
    the actual bounded payload rather than choosing an opaque count by garment
    filename. This does not establish an unmeasured soft-cloth cook.
    """
    if len(payload)<5:raise ValueError('Truncated packed render chunk prefix')
    length=struct.unpack_from('<I',payload)[0];count=payload[4]
    if length!=1+37*count or len(payload)!=4+length:
        raise ValueError('Unobserved packed render chunk record layout')
    records=[payload[5+37*i:5+37*(i+1)] for i in range(count)]
    if section_groups is None:
        if count not in (2,6):raise ValueError('Unobserved packed render chunk record count')
        if [r[36] for r in records[:2]]!=[1,2]:raise ValueError('Full packed records do not identify the two native LODs')
    else:
        # Group membership comes from this same CRC-checked CMesh tail. This
        # is a bounded reader; callers still verify the official cook's actual
        # material IDs, streams, index ranges and geometry before adoption.
        if len(section_groups)!=2 or not all(section_groups):raise ValueError('Both native section groups are required')
        ids=tuple(i for group in section_groups for i in group)
        if ids!=tuple(range(len(ids)))or len(ids)>count:raise ValueError('Native section IDs are not a complete ordered prefix')
        if count not in (len(ids),len(ids)*3):raise ValueError('Unobserved section shadow record count')
        for lod,group in enumerate(section_groups):
            if any(records[i][36]!=(1<<lod)for i in group):raise ValueError('Native section LOD flag disagrees with its group')
    return records


class CookedMesh:
    def __init__(self,raw,allow_rigid=False,allow_stock_torso_mapping=False,allow_multi_section=False):
        self.allow_rigid=allow_rigid
        self.allow_stock_torso_mapping=allow_stock_torso_mapping
        self.allow_multi_section=allow_multi_section
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
            # Untouched stock Geralt torso also carries SMeshSoundInfo. It is
            # independent of skin/render data; retain its bounded CRC check.
            if kind>=len(self.names) or self.names[kind] not in ['CMesh','CMaterialInstance','SMeshSoundInfo'] or size>len(raw)-position:raise ValueError('Unobserved native mesh child export')
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
        if allow_multi_section:
            decode_render_chunks(self.get(self.cooked,'renderChunks','array:47,0,Uint8'),self.chunk_groups)

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

    def skin_sections(self,buffer):
        """Cross-check typed CPU chunks against their packed GPU records.

        Returned row origins are resource-local. No chunk is inferred from a
        filename, material ordering, equal vertex position, or stale IA slot.
        """
        payload=self.get(self.properties,'chunks','array:2,0,SMeshChunkPacked')
        if len(payload)<4:raise ValueError('Truncated native skin section table')
        count=struct.unpack_from('<I',payload)[0];tail=payload[4:]
        ids=tuple(i for group in self.chunk_groups for i in group)
        if count!=len(ids):raise ValueError('CPU and LOD section counts differ')
        packed=decode_render_chunks(self.get(self.cooked,'renderChunks','array:47,0,Uint8'),self.chunk_groups)
        vertex_bytes=struct.unpack('<I',self.get(self.cooked,'vertexBufferSize','Uint32'))[0]
        index_bytes=struct.unpack('<I',self.get(self.cooked,'indexBufferSize','Uint32'))[0]
        index_offset=struct.unpack('<I',self.get(self.cooked,'indexBufferOffset','Uint32'))[0]
        if vertex_bytes>len(buffer)or index_offset<vertex_bytes or index_offset>len(buffer)or index_bytes>len(buffer)-index_offset:
            raise ValueError('Native skin allocation leaves buffer')
        result=[];next_vertex=next_index=0
        for index in range(count):
            properties,tail=self.object(tail);record=packed[index]
            allowed={'materialID','vertexType','numBonesPerVertex','numVertices','numIndices','firstVertex','firstIndex','useForShadowmesh'}
            if set(properties)-allowed:raise ValueError('Unobserved typed skin section property')
            def integer(name,kind='Uint32',default=0):
                if name not in properties:return default
                return struct.unpack({'Uint8':'<B','Uint16':'<H','Uint32':'<I'}[kind],self.get(properties,name,kind))[0]
            vertex_type=struct.unpack('<H',self.get(properties,'vertexType','EMeshVertexType'))[0]
            bones=integer('numBonesPerVertex','Uint8',4 if self.allow_stock_torso_mapping else 0)
            if 'useForShadowmesh'in properties and self.get(properties,'useForShadowmesh','Bool')not in (b'\0',b'\1'):
                raise ValueError('Invalid native shadow section flag')
            if vertex_type>=len(self.names)or self.names[vertex_type]!='MVT_SkinnedMesh'or bones!=4 or record[0]!=3:
                raise ValueError('Native section is not observed four-bone skin')
            vertices=integer('numVertices');indices=integer('numIndices');first_vertex=integer('firstVertex');first_index=integer('firstIndex')
            if not vertices or vertices!=struct.unpack_from('<H',record,27)[0]or not indices or indices%3 or indices!=struct.unpack_from('<I',record,29)[0]:
                raise ValueError('CPU/GPU native skin dimensions differ')
            if first_vertex!=next_vertex or first_index!=next_index:
                raise ValueError('Native skin row/index origin differs')
            gpu_index_bytes=struct.unpack_from('<I',record,22)[0]
            if gpu_index_bytes%2:raise ValueError('Unaligned native GPU index origin')
            gpu_first=gpu_index_bytes//2
            offsets=[struct.unpack_from('<I',record,1+4*slot)[0]for slot in range(4)]
            if any(offset>vertex_bytes or vertices*stride>vertex_bytes-offset for offset,stride in zip(offsets,[16,4,8,8])):
                raise ValueError('Native skin stream leaves allocation')
            if gpu_index_bytes>index_bytes or indices*2>index_bytes-gpu_index_bytes:
                raise ValueError('Native section indices leave allocation')
            values=struct.unpack_from('<'+str(indices)+'H',buffer,index_offset+gpu_index_bytes)
            if max(values)>=vertices:raise ValueError('Unobserved nonlocal native section indices')
            material=integer('materialID','Uint32')
            lod=next(lod for lod,group in enumerate(self.chunk_groups)if index in group)
            result.append(dict(lod=lod,material=material,firstVertex=first_vertex,vertexCount=vertices,
                positionOffset=offsets[0],uvOffset=offsets[1],lightingOffset=offsets[2],extraOffset=offsets[3],
                indexFirst=gpu_first,indexCount=indices,cpuIndexFirst=first_index))
            next_vertex+=vertices;next_index+=indices
        covered=0
        for first,end in sorted((s['indexFirst'],s['indexFirst']+s['indexCount'])for s in result):
            if first>covered:raise ValueError('Unobserved gap in native GPU indices')
            covered=max(covered,end)
        if tail or covered*2!=index_bytes:raise ValueError('Unconsumed native skin section data')
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
        self.chunk_groups=[];self.chunk_distances=[]
        for i in range(groups):
            ids=read('<'+str(count())+'H');padding=read('<f')[0]
            if not math.isfinite(padding)or not ids or (not self.allow_multi_section and ids!=(i,)):
                raise ValueError('Unexpected native chunk group')
            self.chunk_groups.append(ids);self.chunk_distances.append(padding)
        all_ids=tuple(i for group in self.chunk_groups for i in group)
        if all_ids!=tuple(range(len(all_ids)))or len(all_ids)>16:raise ValueError('Invalid native material section IDs')
        palette=[]
        for _ in range(count()):
            index=read('<H')[0]
            if index>=len(self.names):raise ValueError('Bone name leaves pool')
            palette.append(self.names[index])
        matrices=[read('<16f') for _ in range(count())]
        radii=[read('<f')[0] for _ in range(count())]
        mapping=[read('<I')[0] for _ in range(count())]
        mapping_matches=len(mapping)==len(palette) or (self.allow_stock_torso_mapping and len(palette)==81 and len(mapping)==32)
        if at!=len(data) or (not palette and not self.allow_rigid) or len(matrices)!=len(palette) or len(radii)!=len(palette) or not mapping_matches:
            raise ValueError('Unexpected native skin tail dimensions')
        if not all(math.isfinite(x) for m in matrices for x in m) or not all(math.isfinite(x) for x in radii):
            raise ValueError('Non-finite native skin tail')
        return palette,matrices,mapping
