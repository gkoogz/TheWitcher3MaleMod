import sys,unittest,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from verify_collar_replay import verify

class ReplayTest(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.a=Path(self.folder.name)/'a';self.b=Path(self.folder.name)/'b'
        for p in (self.a,self.b):
            p.mkdir();(p/'cases.json').write_text(json.dumps([dict(label='neutral',controls=[50]*18,characterContactsCalibrated=True)]))
            for s in ('-lod0.bin','-lod1.bin','-render.bin'):(p/('neutral'+s)).write_bytes(b'complete buffer')
    def test_equal(self):self.assertTrue(verify(self.a,self.b)['byteIdentical'])
    def test_second_lod_drift(self):
        (self.b/'neutral-lod1.bin').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'Native buffer differs'):verify(self.a,self.b)
    def test_missing_render(self):
        (self.b/'neutral-render.bin').unlink()
        with self.assertRaisesRegex(ValueError,'Missing complete'):verify(self.a,self.b)
    def test_contact_status_drift(self):
        rows=json.loads((self.b/'cases.json').read_text());rows[0]['characterContactsCalibrated']=False
        (self.b/'cases.json').write_text(json.dumps(rows))
        with self.assertRaisesRegex(ValueError,'contact status'):verify(self.a,self.b)
if __name__=='__main__':unittest.main()
