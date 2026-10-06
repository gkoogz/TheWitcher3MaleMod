import sys,struct,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from packed_mesh_format import decode_render_chunks
class RenderChunkContract(unittest.TestCase):
 def payload(self,count):
  records=[]
  for i in range(count):
   r=bytearray(37);r[36]=(i%2)+1;records.append(bytes(r))
  return struct.pack("<I",1+37*count)+bytes([count])+b"".join(records)
 def test_observed_two_and_six(self):
  for count in (2,6):
   raw=self.payload(count);records=decode_render_chunks(raw);self.assertEqual(len(records),count);self.assertEqual(records[:2],[raw[5:42],raw[42:79]])
 def test_closed_on_changed_layout(self):
  for raw in (b"",self.payload(3),self.payload(2)[:-1],self.payload(2)+b"x",struct.pack("<I",76)+self.payload(2)[4:]):
   with self.assertRaises(ValueError):decode_render_chunks(raw)
 def test_closed_on_unmeasured_lod_order(self):
  raw=bytearray(self.payload(2));raw[41]=2
  with self.assertRaises(ValueError):decode_render_chunks(raw)
if __name__=="__main__":unittest.main()
