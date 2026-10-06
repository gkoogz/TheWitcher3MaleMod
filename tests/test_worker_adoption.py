import json,struct,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from mod import digest
from worker_adoption import validate_process_library

class Adoption(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.build=self.base/'build';self.build.mkdir()
  self.library=self.build/'solver.lib';self.library.write_bytes(b'actual-current-library')
  exe=self.build/'source.exe';exe.write_bytes(b'actual-executable')
  sources={p:'exact-source' for p in ['src/surface/runtime.cpp','include/malemod/surface/runtime.hpp','include/malemod/surface/wire.hpp','include/malemod/surface/garment_impulse.hpp','include/malemod/garments/reaction_support.hpp','tools/verify_garment_source_reactions.py']}
  hashes={}
  for p,v in sources.items():
   f=self.base/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(v);hashes[p]=digest(f)
  cases=[]
  for state in range(3):
   records={}
   for mode in ['0','2','3','4','5','6']:
    f=self.build/f's{state}m{mode}.bin';f.write_bytes(struct.pack('<II',6,state)+bytes([0 if mode in ['0','2'] else 1]))
    records[mode]={'file':f.name,'sha256':digest(f),'bytes':f.stat().st_size}
   cases.append(dict(state=state,records=records,disabledExactParity=True,cdfRetryExactParity=True,physicalImpulseChangesSource=True,pendingNoSubstepExactParity=True,pendingCoalescingExactParity=True))
  self.proof=dict(schema=2,wire=6,sourceProcessIsolated=True,sourceCommit='a'*40,sourceDirty='',library=dict(path='build/solver.lib',sha256=digest(self.library)),executable=dict(path='build/source.exe',sha256=digest(exe)),sourceHashes=hashes,cases=cases)
  self.path=self.build/'proof.json';self.current=dict(librarySHA256=digest(self.library),serialGeometry=False,wireVersion=6,sourceConsumptionProofPath='build/proof.json')
  self.save()
 def save(self):
  self.path.write_text(json.dumps(self.proof));self.current['sourceConsumptionProofSHA256']=digest(self.path)
  clean=self.build/'physical-reaction-source-proof-aaaaaaa'/'proof.json';clean.parent.mkdir(exist_ok=True);clean.write_text(json.dumps(self.proof))
  for f in self.build.glob('*.bin'):(clean.parent/f.name).write_bytes(f.read_bytes())
 def tearDown(self):self.temp.cleanup()
 def test_actual_wire6(self):validate_process_library(self.base,self.library,self.current)
 def test_old_wire5_supported_only_verified(self):
  c=dict(self.current,wireVersion=5,sessionWireFrameGarmentTestsPassed=True);validate_process_library(self.base,self.library,c)
  c['sessionWireFrameGarmentTestsPassed']=False
  with self.assertRaises(ValueError):validate_process_library(self.base,self.library,c)
 def test_dirty_proof_not_deployable(self):
  validate_process_library(self.base,self.library,self.current,require_clean=True,pin='a'*40)
  self.proof['sourceDirty']=' M runtime.cpp';self.save()
  with self.assertRaises(ValueError):validate_process_library(self.base,self.library,self.current,require_clean=True,pin='a'*40)
 def test_other_pin_not_deployable(self):
  with self.assertRaises((ValueError,FileNotFoundError)):validate_process_library(self.base,self.library,self.current,require_clean=True,pin='b'*40)
 def test_changed_source(self):
  (self.base/'src/surface/runtime.cpp').write_text('different')
  with self.assertRaises(ValueError):validate_process_library(self.base,self.library,self.current)
 def test_changed_receipt(self):
  self.path.write_text('{}')
  with self.assertRaises(ValueError):validate_process_library(self.base,self.library,self.current)
 def test_old_wire_binary(self):
  row=self.proof['cases'][0]['records']['0'];f=self.build/row['file'];f.write_bytes(struct.pack('<II',5,0)+b'0');row.update(sha256=digest(f),bytes=f.stat().st_size);self.save()
  with self.assertRaises(ValueError):validate_process_library(self.base,self.library,self.current)
 def test_impulse_replay_changed(self):
  row=self.proof['cases'][2]['records']['6'];f=self.build/row['file'];f.write_bytes(struct.pack('<II',6,2)+b'2');row.update(sha256=digest(f),bytes=f.stat().st_size);self.save()
  with self.assertRaises(ValueError):validate_process_library(self.base,self.library,self.current)
 def test_wrong_library(self):
  self.library.write_bytes(b'different')
  with self.assertRaises(ValueError):validate_process_library(self.base,self.library,self.current)

if __name__=='__main__':unittest.main()
