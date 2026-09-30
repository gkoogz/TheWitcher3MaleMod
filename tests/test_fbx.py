from pathlib import Path
import struct
import sys
import tempfile
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from wcc_fbx import Document,Node,Property,triangles


def rawprop(tag,value):
    if tag=='S':
        raw=value.encode();return Property(tag,value,b'S'+struct.pack('<I',len(raw))+raw)
    if tag=='R':return Property(tag,value,b'R'+struct.pack('<I',len(value))+value)
    return Property(tag,value,tag.encode()+struct.pack({'I':'<i','L':'<q','D':'<d'}[tag],value))


def fixture(path,version):
    d=Document.__new__(Document);d.version=version;d.fmt,d.size=('<QQQB',25) if version>=7500 else ('<IIIB',13)
    d.prefix=b'Kaydara FBX Binary  \x00\x1a\x00'+struct.pack('<I',version)
    geometry=Node('Geometry',[rawprop('L',12),rawprop('S','Mesh\x00\x01Geometry'),rawprop('S','Mesh')],[
        Node('Vertices',[Property('d',np.array([0,0,0,1,0,0,0,1,0],dtype=float))]),
        Node('PolygonVertexIndex',[Property('i',np.array([0,1,-3]))]),
        Node('Opaque',[rawprop('R',b'embedded\x00resource'),rawprop('D',3.5)])],True)
    d.nodes=[Node('Objects',[],[geometry],True)]
    d.original_footer_offset=0;d.footer_id=b'opaque-footer-id';d.footer_id=d.footer_id.ljust(16,b'!')
    d.footer_suffix=struct.pack('<I',version)+bytes(120);d.original_footer=d.footer_id+bytes(4)+d.footer_suffix
    d.save(path)


class FbxTests(unittest.TestCase):
    def test_lossless_roundtrip_and_resized_array_keeps_opaque_data(self):
        for version in [7300,7500]:
            with tempfile.TemporaryDirectory() as temp:
                src=Path(temp)/'source.fbx';out=Path(temp)/'out.fbx';fixture(src,version)
                d=Document(src);d.save(out);self.assertEqual(src.read_bytes(),out.read_bytes())
                opaque=d.meshes[0].child('Opaque').props[0].raw
                d.meshes[0].set_array('Vertices',np.arange(600).reshape(-1,3));d.save(out)
                edited=Document(out);np.testing.assert_array_equal(edited.meshes[0].array('Vertices'),np.arange(600))
                self.assertEqual(edited.meshes[0].child('Opaque').props[0].raw,opaque)
                np.testing.assert_array_equal(triangles(edited.meshes[0]),[[0,1,2]])

    def test_rejects_invalid_node_offsets_and_nontriangles(self):
        with tempfile.TemporaryDirectory() as temp:
            src=Path(temp)/'source.fbx';fixture(src,7300)
            d=Document(src);d.meshes[0].set_array('PolygonVertexIndex',[0,-2,2])
            with self.assertRaises(ValueError):triangles(d.meshes[0])
            data=bytearray(src.read_bytes());struct.pack_into('<I',data,27,len(data)+100);src.write_bytes(data)
            with self.assertRaises(ValueError):Document(src)

if __name__=='__main__':unittest.main()
