import copy,json,struct,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import adopt_garment_material as m
from mod import digest,write_json

class MaterialOnly(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.game=self.root/'game';self.output=self.root/'build/preview';self.output.mkdir(parents=True);self.local=self.root/'local';self.local.mkdir()
  names=sorted(m.PACKAGE_FILES)+[m.RUNTIME+'runtime'+str(i) for i in range(30)]
  rows=[]
  for i,n in enumerate(names):
   p=self.game/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(('original-'+str(i)).encode());rows.append(dict(path=n,sha256=digest(p)))
  self.installed=dict(game=str(self.game),baseCommit='99ff',files=rows,settingsPreserved=True)
  self.path=self.local/'native-installation.json';write_json(self.path,self.installed)
  updates=[]
  for n in sorted(m.PACKAGE_FILES):
   p=self.output/'payload'/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(('new-material-'+n).encode());updates.append(dict(path=n,beforeSHA256=next(r['sha256'] for r in rows if r['path']==n),afterSHA256=digest(p),staged='payload/'+n))
  self.material=self.output/'material-proof.json';write_json(self.material,dict(resources=[dict(kind=k,material=dict(parameters=dict(Opacity=.95))) for k in ['ribbed','elastic','red','blue']]))
  self.receipt=dict(nativeInstanceOpacityVerified=True,materialProofPath=str(self.material),kind='frozen-native-garment-material-only-adoption',runtimeBaseCommit='99ff',materialCookBaseCommit='377',sourceCookAttributionPreserved=True,sharedWalkingClothAdopted=False,newNumericalWorkerAdopted=False,recipeSHA256=digest(Path(m.__file__)),installationReceiptSHA256=digest(self.path),installedBefore=self.installed,updates=updates,preservedPaths=[r for r in rows if r['path'] not in m.PACKAGE_FILES],verificationArtifacts=[])
  self.adoption=self.output/'adoption.json';write_json(self.adoption,self.receipt)
 def tearDown(self):self.temp.cleanup()
 def test_preserves_runtime_scope(self):
  m.validate_plan(self.receipt,self.output,self.path)
  with patch.object(m,'ROOT',self.root),patch.object(m.subprocess,'run',return_value=SimpleNamespace(stdout='')):result=m.apply(self.adoption)
  self.assertEqual(result['baseCommit'],'99ff');self.assertEqual(len(result['files']),35);self.assertFalse(result['materialOnlyAdoption']['walkingClothAdopted']);self.assertTrue(result['settingsPreserved'])
  self.assertEqual([r for r in result['files'] if r['path'] not in m.PACKAGE_FILES],self.receipt['preservedPaths'])
 def test_explicit_rollback_original_bytes(self):
  original_receipt=self.path.read_bytes();original={r['path']:(self.game/r['path']).read_bytes() for r in self.installed['files']}
  with patch.object(m,'ROOT',self.root),patch.object(m.subprocess,'run',return_value=SimpleNamespace(stdout='')):
   updated=m.apply(self.adoption);m.rollback(updated['materialOnlyAdoption']['backup'])
  self.assertEqual(self.path.read_bytes(),original_receipt)
  self.assertTrue(all((self.game/n).read_bytes()==data for n,data in original.items()))
 def test_copy_failure_exact_rollback(self):
  original=m.shutil.copy2;failed=[False];before={r['path']:(self.game/r['path']).read_bytes() for r in self.installed['files']}
  def fail(source,target,*args,**kw):
   if Path(target).resolve().is_relative_to(self.game.resolve()) and not failed[0]:failed[0]=True;raise OSError('injected write failure')
   return original(source,target,*args,**kw)
  with patch.object(m,'ROOT',self.root),patch.object(m.subprocess,'run',return_value=SimpleNamespace(stdout='')),patch.object(m.shutil,'copy2',side_effect=fail):
   with self.assertRaises(OSError):m.apply(self.adoption)
  self.assertEqual(json.loads(self.path.read_text()),self.installed)
  self.assertTrue(all((self.game/n).read_bytes()==data for n,data in before.items()))
 def test_non_garment_target_rejected(self):
  bad=copy.deepcopy(self.receipt);bad['updates'][0]['path']=m.RUNTIME+'runtime0'
  with self.assertRaises(ValueError):m.validate_plan(bad,self.output,self.path)
 def test_staged_change_rejected(self):
  (self.output/self.receipt['updates'][0]['staged']).write_bytes(b'changed')
  with self.assertRaises(ValueError):m.validate_plan(self.receipt,self.output,self.path)
 def test_runtime_changed_rejected(self):
  (self.game/(m.RUNTIME+'runtime0')).write_bytes(b'changed')
  with self.assertRaises(ValueError):m.validate_plan(self.receipt,self.output,self.path)
 def test_duplicate_target_rejected(self):
  bad=copy.deepcopy(self.receipt);bad['updates'][1]=bad['updates'][0]
  with self.assertRaises(ValueError):m.validate_plan(bad,self.output,self.path)
 def test_carrier_and_fingerprint_identity(self):
  packet=b'MMCLT001'+b''.join(struct.pack('<6fI',256,256,256,-128,-128,-128,384) for _ in range(4));fingerprints=b'MMGPH01\0'+struct.pack('<I',0)
  m.validate_identity(packet,packet,fingerprints,fingerprints)
  with self.assertRaises(ValueError):m.validate_identity(packet,packet[:-1]+b'1',fingerprints,fingerprints)
  with self.assertRaises(ValueError):m.validate_identity(packet,packet,fingerprints,fingerprints+b'changed')
 def test_zero_native_opacity_rejected(self):
  resources=[dict(kind=k,material=dict(parameters=dict(Opacity=.95))) for k in ['ribbed','elastic','red','blue']]
  resources[0]['material']['parameters']['Opacity']=0;write_json(self.material,dict(resources=resources))
  with self.assertRaises(ValueError):m.validate_plan(self.receipt,self.output,self.path)
 def test_invalid_optics_rejected(self):
  optical=dict(graph='characters/malemod/garments/cloth_soft.w2mg',sortGroup='RSG_Transparent',blendMode='RBM_AlphaBlend',compiledNormal=True,compiledDiffuse=True,Opacity={'value':.95},Roughness={'value':.88},Specularity={'value':.015});m.validate_optics(optical)
  optical['Opacity']['value']=0
  with self.assertRaises(ValueError):m.validate_optics(optical)

if __name__=='__main__':unittest.main()
