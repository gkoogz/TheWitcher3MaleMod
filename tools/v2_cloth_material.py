"""Native material graph transport, retained independently of v1 cloth mechanics.
The generic graph reader/authoring routines originate in archived engine tooling.
Only owned v2 outputs may be written; no garment simulation is imported here.
"""
import struct,zlib,shutil,hashlib
from pathlib import Path
from mod import ROOT,run_wcc,digest,write_json
from packed_mesh_format import CookedMesh
from player_rig_redirect import header_crc
DRY_GRAPH='characters/malemod/garments/v2a.w2mg'
def native_objects(path):
    """Read only the observed native 164 tables, checking bounds and CRCs."""
    raw=Path(path).read_bytes()
    if len(raw)<160 or raw[:4]!=b'CR2W' or struct.unpack_from('<I',raw,4)[0]!=164 or header_crc(raw,0)!=struct.unpack_from('<I',raw,32)[0]:raise ValueError('Unobserved material/texture header')
    def table(index,stride):
        offset,count,crc=struct.unpack_from('<III',raw,40+index*12);size=count*stride
        if not count and not offset and not crc:return b''
        if offset<160 or size>len(raw)-offset:raise ValueError('Native table leaves resource')
        block=raw[offset:offset+size]
        if zlib.crc32(block)!=crc:raise ValueError('Native table CRC differs')
        return block
    strings=table(0,1)
    def text(offset):
        end=strings.find(b'\0',offset)
        if offset>=len(strings) or end<offset:raise ValueError('Native text leaves string table')
        return strings[offset:end].decode('utf-8')
    reader=CookedMesh.__new__(CookedMesh);reader.names=[text(offset) for offset,_ in struct.iter_unpack('<II',table(1,8))]
    imports=[text(offset) for offset,kind,flags in struct.iter_unpack('<IHH',table(2,8))]
    objects=[]
    for kind,flags,parent,size,offset,template,crc in struct.iter_unpack('<HHIIIII',table(4,24)):
        if kind>=len(reader.names) or offset<160 or size>len(raw)-offset:raise ValueError('Native export leaves resource')
        data=raw[offset:offset+size]
        if zlib.crc32(data)!=crc:raise ValueError('Native export CRC differs')
        properties,tail=reader.object(data);objects.append((reader.names[kind],flags,properties,tail))
    return reader,imports,objects
