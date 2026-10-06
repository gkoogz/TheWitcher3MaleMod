"""Bounded read-only native clipmap-tail check, measured from official SDK data."""
import struct,zlib
from player_rig_redirect import header_crc

def inspect_clipmap(raw):
    if raw[:4]!=b'CR2W' or struct.unpack_from('<I',raw,4)[0] not in (159,163,164):
        raise ValueError('Unobserved clipmap container version')
    if len(raw)<160 or header_crc(raw,0)!=struct.unpack_from('<I',raw,32)[0]:
        raise ValueError('Clipmap header CRC differs')
    def table(i,stride):
        at,count,crc=struct.unpack_from('<III',raw,40+i*12)
        if at<160 or count*stride>len(raw)-at:raise ValueError('Clipmap table out of bounds')
        b=raw[at:at+count*stride]
        if zlib.crc32(b)!=crc:raise ValueError('Clipmap table CRC differs')
        return b
    strings=table(0,1)
    def string(at):
        end=strings.find(b'\0',at)
        if end<at:raise ValueError('Clipmap string out of bounds')
        return strings[at:end].decode('utf-8')
    names=[string(at) for at,_ in struct.iter_unpack('<II',table(1,8))]
    imports=[(string(at),names[cls],flags) for at,cls,flags in struct.iter_unpack('<IHH',table(2,8))]
    exports=[e for e in struct.iter_unpack('<HHIIIII',table(4,24)) if names[e[0]]=='CClipMap']
    if len(exports)!=1:raise ValueError('Expected one native clipmap')
    _,_,_,size,start,_,crc=exports[0]
    if size>len(raw)-start:raise ValueError('Clipmap export out of bounds')
    data=raw[start:start+size]
    if zlib.crc32(data)!=crc or data[0]!=0:raise ValueError('Clipmap export CRC/flags differ')
    at=1;mip_sizes={}
    while at+2<=len(data) and struct.unpack_from('<H',data,at)[0]:
        if at+8>len(data):raise ValueError('Clipmap property truncated')
        name,kind,length=struct.unpack_from('<HHI',data,at)
        if name>=len(names) or kind>=len(names) or length<4 or at+4+length>len(data):raise ValueError('Clipmap property invalid')
        if names[name].startswith('cookedMipStack'):
            if names[kind]!='DataBuffer' or length<8 or names[name] in mip_sizes:
                raise ValueError('Native mip buffer type/header differs')
            payload=data[at+8:at+4+length]
            count_bytes=struct.unpack_from('<I',payload)[0]
            if count_bytes+4!=len(payload):raise ValueError('Native inline mip buffer count/bounds differ')
            mip_sizes[names[name]]=count_bytes
        at+=4+length
    at+=2
    if at+4>len(data):raise ValueError('Native clipmap tile tail missing')
    count=struct.unpack_from('<I',data,at)[0];at+=4
    if not count or count>10000 or at+count*4!=len(data):raise ValueError('Native clipmap tile count/bounds differ')
    tiles=[]
    for handle, in struct.iter_unpack('<i',data[at:]):
        index=-handle-1
        if handle>=0 or index>=len(imports):raise ValueError('Native tile reference is NULL/internal/invalid')
        path,cls,flags=imports[index]
        if cls!='CTerrainTile' or flags!=0:raise ValueError('Native tile import type/flags differ')
        tiles.append(path.replace('\\','/'))
    if len(set(tiles))!=len(tiles):raise ValueError('Native tile topology duplicates a resource')
    return dict(tiles=tiles,mipSizes=mip_sizes)


def read_tiles(raw):
    return inspect_clipmap(raw)['tiles']
