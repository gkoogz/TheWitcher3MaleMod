"""Bounded material-section parsing; native cook acceptance is separate."""
import struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from packed_mesh_format import decode_render_chunks

def payload(flags):
    records=[]
    for flag in flags:
        record=bytearray(37);record[36]=flag;records.append(record)
    return struct.pack('<IB',1+37*len(records),len(records))+b''.join(records)

class SectionReaderTests(unittest.TestCase):
    def test_existing_strict_layout(self):
        self.assertEqual(len(decode_render_chunks(payload([1,2]))),2)
        with self.assertRaises(ValueError):decode_render_chunks(payload([1,1,1,2,2,2]))
    def test_section_lod_membership(self):
        self.assertEqual(len(decode_render_chunks(payload([1,1,1,2,2,2]),[(0,1,2),(3,4,5)])),6)
        with self.assertRaises(ValueError):decode_render_chunks(payload([1,1,2,1,2,2]),[(0,1,2),(3,4,5)])
    def test_reject_duplicate_missing_and_unbounded_ids(self):
        for groups in [[(0,1,1),(2,3,4)],[(0,2),(3,4)],[(0,),()],[(0,),(1,2,3)]]:
            with self.subTest(groups=groups),self.assertRaises(ValueError):decode_render_chunks(payload([1,2]),groups)
    def test_reject_partial_or_extra_record(self):
        for data in [payload([1,2])[:-1],payload([1,2])+b'\0',payload([1,1,2])]:
            with self.assertRaises(ValueError):decode_render_chunks(data,[(0,),(1,)])

if __name__=='__main__':unittest.main()
