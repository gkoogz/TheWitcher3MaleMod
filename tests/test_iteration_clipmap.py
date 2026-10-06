"""Native tail boundaries and import validation; independent of the SDK depot."""
import struct
import sys
import unittest
import zlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from iteration_clipmap import read_tiles,inspect_clipmap
from player_rig_redirect import header_crc


def resource(count=1,handles=(-1,),extra=b'',tile_class='CTerrainTile',flags=0,mips=None):
    labels=['','CClipMap',tile_class,'levels\\own\\tile.w2ter','DataBuffer']+list((mips or {}).keys())
    strings=b'';offsets=[]
    for label in labels:offsets.append(len(strings));strings+=label.encode()+b'\0'
    names=b''.join(struct.pack('<II',o,0) for o in offsets)
    imports=struct.pack('<IHH',offsets[3],2,flags)
    properties=b''
    for i,(name,payload) in enumerate((mips or {}).items()):
        properties+=struct.pack('<HHI',5+i,4,4+len(payload))+payload
    data=b'\0'+properties+b'\0\0'+struct.pack('<I',count)+b''.join(struct.pack('<i',h) for h in handles)+extra
    start=160+len(strings)+len(names)+len(imports)+24
    exports=struct.pack('<HHIIIII',1,0,0,len(data),start,0,zlib.crc32(data))
    raw=bytearray(160)+strings+names+imports+exports+data
    raw[:4]=b'CR2W';struct.pack_into('<I',raw,4,163)
    at=160
    for i,table,stride in [(0,strings,1),(1,names,8),(2,imports,8),(4,exports,24)]:
        struct.pack_into('<III',raw,40+12*i,at,len(table)//stride,zlib.crc32(table));at+=len(table)
    struct.pack_into('<I',raw,32,header_crc(raw,0))
    return raw


class ClipmapTailTests(unittest.TestCase):
    def test_real_hard_import_path(self):
        self.assertEqual(read_tiles(resource()),['levels/own/tile.w2ter'])

    def test_empty_tail_cannot_pass_native_world_gate(self):
        with self.assertRaises(ValueError):read_tiles(resource(0,()))

    def test_duplicate_empty_then_nonempty_tail_rejected(self):
        with self.assertRaises(ValueError):read_tiles(resource(0,(),struct.pack('<Ii',1,-1)))

    def test_duplicate_tile_rejected(self):
        with self.assertRaises(ValueError):read_tiles(resource(2,(-1,-1)))

    def test_null_internal_wrong_class_and_soft_import_rejected(self):
        for args in [dict(handles=(0,)),dict(handles=(1,)),dict(tile_class='CMesh'),dict(flags=4)]:
            with self.subTest(args=args),self.assertRaises(ValueError):read_tiles(resource(**args))

    def test_crc_and_truncation_rejected(self):
        raw=resource();raw[-1]^=1
        with self.assertRaises(ValueError):read_tiles(raw)
        with self.assertRaises(ValueError):read_tiles(resource()[:-1])

    def test_native_inline_mip_size_and_invalid_count(self):
        raw=resource(mips={'cookedMipStackHeight':struct.pack('<I',8)+bytes(8)})
        self.assertEqual(inspect_clipmap(raw)['mipSizes'],{'cookedMipStackHeight':8})
        with self.assertRaises(ValueError):
            inspect_clipmap(resource(mips={'cookedMipStackHeight':struct.pack('<I',8)+bytes(7)}))


if __name__=='__main__':unittest.main()
