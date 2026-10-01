"""Redirect observed equal-length rig/parent imports without rewriting entities.

Preserve every other byte, including native/compiled entity data. Only string
tables and their dependent CRCs may change. Nested CR2W resources are handled
inside-out; reject unknown headers, mismatched CRCs or references outside tables.
"""
import struct
import zlib

OLD_RIG='characters\\base_entities\\man_base\\man_base.w2rig'
NEW_RIG='characters\\base_entities\\man_base\\malebase.w2rig'


def header_crc(data, start):
    header=bytearray(data[start:start+160])
    struct.pack_into('<I',header,32,0xdeadbeef)
    return zlib.crc32(header)


def redirect(data, old_path=OLD_RIG, new_path=NEW_RIG, expected_matches=2, *, expected_version=164):
    if expected_version not in (163,164):
        raise ValueError('Uncalibrated native entity version')
    old=old_path.encode()+b'\0';new=new_path.encode()+b'\0'
    if len(old)!=len(new):raise ValueError('Import redirection must preserve length')
    result=bytearray(data);headers=[];matches=[];allowed=set()
    start=0
    while True:
        start=data.find(b'CR2W',start)
        if start<0:break
        if start+160>len(data) or struct.unpack_from('<I',data,start+4)[0]!=expected_version:
            raise ValueError('Unexpected embedded CR2W header')
        if header_crc(data,start)!=struct.unpack_from('<I',data,start+32)[0]:
            raise ValueError('Native entity header CRC mismatch')
        offset,size,crc=struct.unpack_from('<III',data,start+40)
        if offset<160 or start+offset+size>len(data) or zlib.crc32(data[start+offset:start+offset+size])!=crc:
            raise ValueError('Native entity string table CRC mismatch')
        table_start=start+offset;table_end=table_start+size
        pos=table_start
        while True:
            pos=data.find(old,pos,table_end)
            if pos<0:break
            matches.append(pos);result[pos:pos+len(old)]=new
            allowed.update(range(pos,pos+len(old)));pos+=len(old)
        headers.append(start);start+=4
    if len(headers)!=2 or len(matches)!=expected_matches or headers[0]!=0:
        raise ValueError('Expected observed top/compiled entity and exact imports')
    if data.count(old)!=len(matches):raise ValueError('Rig import occurs outside verified string tables')
    for start in headers[::-1]:
        offset,size,_=struct.unpack_from('<III',data,start+40)
        struct.pack_into('<I',result,start+48,zlib.crc32(result[start+offset:start+offset+size]))
        allowed.update(range(start+48,start+52))
        offset,count,crc=struct.unpack_from('<III',data,start+40+4*12)
        end=start+offset+count*24
        if offset<160 or end>len(data) or zlib.crc32(data[start+offset:end])!=crc:
            raise ValueError('Native export table CRC mismatch')
        for i in range(count):
            entry=start+offset+i*24
            size,position=struct.unpack_from('<II',data,entry+8)
            a=start+position;b=a+size
            if b>len(data):raise ValueError('Native export leaves resource')
            if data[a:b]!=result[a:b]:
                if zlib.crc32(data[a:b])!=struct.unpack_from('<I',data,entry+20)[0]:
                    raise ValueError('Changed native export CRC mismatch')
                struct.pack_into('<I',result,entry+20,zlib.crc32(result[a:b]))
                allowed.update(range(entry+20,entry+24))
        struct.pack_into('<I',result,start+40+4*12+8,zlib.crc32(result[start+offset:end]))
        allowed.update(range(start+40+4*12+8,start+40+4*12+12))
        struct.pack_into('<I',result,start+32,header_crc(result,start))
        allowed.update(range(start+32,start+36))
    changed=[i for i,(a,b) in enumerate(zip(data,result)) if a!=b]
    if not set(changed)<=allowed or len(result)!=len(data) or result.count(old) or result.count(new)!=expected_matches:
        raise ValueError('Entity changes exceed rig imports and dependent CRCs')
    return bytes(result),dict(formatVersion=expected_version,embeddedHeaders=headers,rigImportOffsets=matches,
        changedByteOffsets=changed,onlyImportsAndCRCsChanged=True,
        onlyRigImportsAndCRCsChanged=(old_path==OLD_RIG),oldImport=old_path,newImport=new_path)
