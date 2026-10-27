import struct,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from v2_native_binding import read_binding

def binding(*,version=4,bad_index=False,bad_stream=False):
    sources=17528+15168+5615
    identity=(1.,0.,0.,0.,1.,0.,0.,0.,1.)
    data=bytearray(b'MMV2B04\0'if version==4 else b'MMV2B03\0')
    data+=struct.pack('<I15fI',2,*identity,*([0.]*6),sources)
    data+=struct.pack('<3f',0,0,0)*sources+struct.pack('<3f',0,0,1)*sources
    if version==4:data+=struct.pack('<3f',1,0,0)*sources
    matrix=(1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.)
    row=bytes(28)+struct.pack('<3I3f',0,0,0,1,0,0)
    for _ in range(2):
        data+=struct.pack('<5I6f8I',2,12,72 if version==4 else 0,0,0,1,1,1,0,0,0,0,1,1,1,16,52,28,64)
        if version==4:
            data+=struct.pack('<I',2)
            data+=struct.pack('<10I',0,0,0,1,0,16,20,28,0,3)
            data+=struct.pack('<10I',1,0,1,1,36,52,56,1000 if bad_stream else 64,4 if bad_index else 3,3)
        data+=struct.pack('<I',1)+struct.pack('<I16f',9,*matrix)+row*2
    return bytes(data)

class BindingReaderTests(unittest.TestCase):
    def read(self,data):
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'binding.bin';path.write_bytes(data);return read_binding(path)
    def test_b03_and_b04_preserve_rows(self):
        legacy=self.read(binding(version=3));sectioned=self.read(binding())
        self.assertEqual(sectioned['version'],4);self.assertEqual(sectioned['totalVertices'],4)
        self.assertIsNone(legacy['tangents']);self.assertEqual(sectioned['tangents'].shape,(38311,3))
        for a,b in zip(legacy['resources'],sectioned['resources']):self.assertEqual(a['rows'].tobytes(),b['rows'].tobytes())
    def test_reject_section_index_gap(self):
        with self.assertRaisesRegex(ValueError,'partition'):self.read(binding(bad_index=True))
    def test_reject_stream_overflow(self):
        with self.assertRaisesRegex(ValueError,'stream'):self.read(binding(bad_stream=True))
    def test_reject_truncation_and_trailing_bytes(self):
        for data in (binding()[:-1],binding()+b'\0'):
            with self.assertRaises(ValueError):self.read(data)

if __name__=='__main__':unittest.main()
