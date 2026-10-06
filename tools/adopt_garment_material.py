"""Prepare/apply a bounded material preview onto the verified installed runtime.

The original cook keeps its own Base pin. No solver, shape, scripts, bindings,
settings, or graphics fingerprint bytes are adopted from a different runtime.
Native appearance remains unverified until a separate observation receipt.
"""
import argparse,copy,json,shutil,struct,subprocess,time
from pathlib import Path
from mod import ROOT,read_json,write_json,digest,inside,verify_package,settings

PREFIX='Mods/modMaleModGarments/content/'
PACKAGE_FILES={PREFIX+p for p in ['bundles/blob0.bundle','bundles/buffers0.bundle','dep.cache','metadata.store','texture.cache']}
RUNTIME='bin/x64_dx12/malemod-native/'

def installed_integrity(receipt):
 game=Path(receipt['game']).resolve();rows=receipt['files'];names=[r['path'] for r in rows]
 if len(names)!=len(set(names)):raise ValueError('Duplicate managed installed path')
 for row in rows:
  if digest(inside(game,row['path']))!=row['sha256']:raise ValueError('Installed managed file changed: '+row['path'])
 return game

def validate_identity(old_packet,new_packet,old_fingerprints,new_fingerprints):
 old_packet,new_packet=bytes(old_packet),bytes(new_packet)
 if len(new_packet)!=120 or new_packet[:8]!=b'MMCLT001' or old_packet!=new_packet:raise ValueError('Material preview must preserve exact installed four-owner carrier ABI')
 for i in range(4):
  values=struct.unpack_from('<6fI',new_packet,8+i*28)
  if any(not __import__('math').isfinite(x) for x in values[:6]) or any(x<=0 for x in values[:3]) or values[6]!=384:raise ValueError('Invalid measured carrier quantization/index budget')
 if old_fingerprints!=new_fingerprints or bytes(new_fingerprints)[:8]!=b'MMGPH01\0':raise ValueError('Material preview may not alter any installed fingerprint record')

def validate_optics(optical):
 import math
 if optical.get('graph')!='characters/malemod/garments/cloth_soft.w2mg' or optical.get('sortGroup')!='RSG_Transparent' or optical.get('blendMode')!='RBM_AlphaBlend' or not optical.get('compiledNormal') or not optical.get('compiledDiffuse'):raise ValueError('Supported compiled soft material missing')
 for key,value in [('Opacity',.95),('Roughness',.88),('Specularity',.015)]:
  actual=optical.get(key,{}).get('value')
  if not isinstance(actual,(float,int)) or not math.isclose(actual,value,abs_tol=1e-7,rel_tol=0):raise ValueError('Compiled authored optical value differs: '+key)

def validate_instance_opacity(resources):
 import math
 if len(resources)!=4 or {r.get('kind') for r in resources}!={'ribbed','elastic','red','blue'}:raise ValueError('Complete four native material owners missing')
 for row in resources:
  value=row.get('material',{}).get('parameters',{}).get('Opacity')
  if not isinstance(value,(float,int)) or not math.isclose(value,.95,rel_tol=0,abs_tol=1e-7):raise ValueError('Actual native material instance Opacity must be .95: '+str(row.get('kind')))

def prepare(job,fingerprints,output):
 job,fingerprints,output=map(lambda p:Path(p).absolute(),(job,fingerprints,output))
 if not job.is_relative_to(ROOT/'build') or not fingerprints.is_relative_to(ROOT/'build') or not output.is_relative_to(ROOT/'build') or output.exists():raise ValueError('Use existing owned sources and a fresh owned output')
 installed_path=ROOT/'local/native-installation.json';installed=read_json(installed_path);game=installed_integrity(installed)
 carrier=read_json(job/'package.json');package=ROOT/carrier['directory'];manifest=verify_package(package)
 if manifest['project']!='modMaleModGarments' or manifest['baseCommit']!=carrier['baseCommit'] or {r['path'] for r in manifest['files']}!=PACKAGE_FILES:raise ValueError('Material cook does not own exactly the five existing garment package files')
 if not PACKAGE_FILES<={r['path'] for r in installed['files']}:raise ValueError('Installed garment ownership differs')
 optical=read_json(job/'material-proof.json');validate_optics(optical['opticalContract']);validate_instance_opacity(optical['resources'])
 from prepare_garment_carrier import verify_material
 native=[]
 for row in carrier['resources']:
  mesh=Path(carrier['cooked'])/'characters/malemod/garments'/(row['kind']+'.w2mesh')
  material=verify_material(mesh,row['kind'],'characters/malemod/garments/cloth_soft.w2mg')
  if material['meshSHA256']!=row['meshSHA256']:raise ValueError('Native material mesh differs from cook receipt')
  native.append(dict(kind=row['kind'],material=material))
 validate_instance_opacity(native)
 abi=read_json(job/'forward-abi-proof.json')
 if abi.get('actualCookBaseCommit')!=carrier['baseCommit'] or not abi.get('actualCompiledSourceRestorationParity') or abi.get('packetSHA256')!=digest(job/'garment.render') or carrier['packetSHA256']!=digest(job/'garment.render'):raise ValueError('Actual cooked forward material ABI proof differs')
 validate_identity((game/(RUNTIME+'garment.render')).read_bytes(),(job/'garment.render').read_bytes(),(game/(RUNTIME+'graphics-owned-fingerprints.bin')).read_bytes(),(fingerprints/'graphics-owned-fingerprints.bin').read_bytes())
 output.mkdir(parents=True);old={r['path']:r['sha256'] for r in installed['files']};updates=[]
 for row in manifest['files']:
  source=inside(package,row['path']);staged=inside(output/'payload',row['path']);staged.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,staged)
  updates.append(dict(path=row['path'],beforeSHA256=old[row['path']],afterSHA256=digest(staged),staged='payload/'+row['path']))
 artifacts=[job/n for n in ['package.json','material-proof.json','forward-abi-proof.json','garment.render','graph-resave-final.json','authoring.json']]+[package/'build-manifest.json',fingerprints/'graphics-owned-fingerprints.bin',fingerprints/'graphics-owned-fingerprints.json']
 receipt=dict(schema=1,kind='frozen-native-garment-material-only-adoption',runtimeBaseCommit=installed['baseCommit'],materialCookBaseCommit=manifest['baseCommit'],sourceCookAttributionPreserved=True,game=str(game),installationReceiptSHA256=digest(installed_path),installedBefore=installed,updates=updates,preservedPaths=[r for r in installed['files'] if r['path'] not in PACKAGE_FILES],verificationArtifacts=[dict(path=str(p.absolute()),sha256=digest(p)) for p in artifacts],carrierPacketByteIdentical=True,allFingerprintRecordsByteIdentical=True,completeAnatomyAndControlsUnchanged=True,sharedWalkingClothAdopted=False,newNumericalWorkerAdopted=False,nativeAppearanceVerified=False,nativeInstanceOpacityVerified=True,materialProofPath=str((job/'material-proof.json').absolute()),cookedOpticalScalarsPresent=optical['opticalContract'].get('cookedOpticalScalarsPresent'),recipeSHA256=digest(Path(__file__)))
 write_json(output/'adoption.json',receipt);print(output/'adoption.json');return receipt

def validate_plan(receipt,output,installed_path):
 output=Path(output).absolute();installed=read_json(installed_path)
 if receipt.get('kind')!='frozen-native-garment-material-only-adoption' or receipt.get('sourceCookAttributionPreserved') is not True or receipt.get('sharedWalkingClothAdopted') is not False or receipt.get('newNumericalWorkerAdopted') is not False or receipt.get('recipeSHA256')!=digest(Path(__file__)):raise ValueError('Material adoption contract changed')
 if digest(installed_path)!=receipt['installationReceiptSHA256'] or installed!=receipt['installedBefore'] or installed['baseCommit']!=receipt['runtimeBaseCommit']:raise ValueError('Installed runtime receipt changed')
 if receipt.get('nativeInstanceOpacityVerified') is not True:raise ValueError('Native instance opacity has not been verified')
 validate_instance_opacity(read_json(receipt['materialProofPath'])['resources'])
 game=installed_integrity(installed);rows=receipt['updates']
 if len(rows)!=5 or {r['path'] for r in rows}!=PACKAGE_FILES:raise ValueError('Material update changes unrelated or duplicate paths')
 old={r['path']:r['sha256'] for r in installed['files']}
 for row in rows:
  if row['beforeSHA256']!=old[row['path']] or digest(inside(output,row['staged']))!=row['afterSHA256']:raise ValueError('Staged material or original target changed')
 preserved=[r for r in installed['files'] if r['path'] not in PACKAGE_FILES]
 if preserved!=receipt['preservedPaths']:raise ValueError('Non-material preservation proof changed')
 for item in receipt['verificationArtifacts']:
  if digest(Path(item['path']))!=item['sha256']:raise ValueError('Material source proof changed')
 return game,installed

def apply(path):
 path=Path(path).absolute()
 if not path.is_relative_to(ROOT/'build'):raise ValueError('Use owned adoption receipt')
 receipt=read_json(path);game,installed=validate_plan(receipt,path.parent,ROOT/'local/native-installation.json')
 query=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command','Get-Process witcher3 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id'],capture_output=True,text=True)
 if query.stdout.strip():raise RuntimeError('Preserve the running Witcher; material update requires it closed')
 backup=ROOT/'local'/('material-only-backup-'+time.strftime('%Y%m%d-%H%M%S'));backup.mkdir();shutil.copy2(ROOT/'local/native-installation.json',backup/'receipt.json')
 for row in receipt['updates']:
  target=inside(backup,row['path']);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(inside(game,row['path']),target)
 changed=[]
 try:
  for row in receipt['updates']:
   changed.append(row['path']);shutil.copy2(inside(path.parent,row['staged']),inside(game,row['path']))
   if digest(inside(game,row['path']))!=row['afterSHA256']:raise RuntimeError('Installed material hash differs')
  updated=copy.deepcopy(installed);hashes={r['path']:r['afterSHA256'] for r in receipt['updates']}
  for row in updated['files']:
   if row['path'] in hashes:row['sha256']=hashes[row['path']]
  updated['materialOnlyAdoption']=dict(receipt=str(path),sha256=digest(path),runtimeBaseCommit=receipt['runtimeBaseCommit'],materialCookBaseCommit=receipt['materialCookBaseCommit'],backup=str(backup),nativeAppearanceVerified=False,walkingClothAdopted=False)
  installed_integrity(updated);temporary=ROOT/'local/native-installation.pending.json';write_json(temporary,updated);temporary.replace(ROOT/'local/native-installation.json')
 except BaseException:
  for rel in reversed(changed):shutil.copy2(inside(backup,rel),inside(game,rel))
  raise
 print('Applied only five verified garment material package files; complete existing runtime preserved; appearance pending observation.');return updated

def rollback(backup):
 backup=Path(backup).absolute()
 if not backup.is_relative_to(ROOT/'local'):raise ValueError('Use the managed material backup')
 current_path=ROOT/'local/native-installation.json';current=read_json(current_path);game=installed_integrity(current);old=read_json(backup/'receipt.json')
 adopted=current.get('materialOnlyAdoption',{})
 if Path(adopted.get('backup','')).absolute()!=backup or current['baseCommit']!=old['baseCommit'] or current['game']!=old['game']:raise ValueError('Backup does not match current material preview')
 before={r['path']:r['sha256'] for r in old['files']};after={r['path']:r['sha256'] for r in current['files']}
 if set(before)!=set(after) or any(before[p]!=after[p] for p in before if p not in PACKAGE_FILES):raise ValueError('Runtime changed since material preview')
 for p in PACKAGE_FILES:
  if digest(inside(backup,p))!=before[p]:raise ValueError('Original material backup changed')
 query=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command','Get-Process witcher3 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id'],capture_output=True,text=True)
 if query.stdout.strip():raise RuntimeError('Material rollback requires Witcher closed')
 retained={p:inside(game,p).read_bytes() for p in PACKAGE_FILES};changed=[]
 try:
  for p in sorted(PACKAGE_FILES):
   changed.append(p);shutil.copy2(inside(backup,p),inside(game,p))
  installed_integrity(old);temporary=ROOT/'local/native-installation.pending.json';shutil.copy2(backup/'receipt.json',temporary);temporary.replace(current_path)
 except BaseException:
  for p in reversed(changed):inside(game,p).write_bytes(retained[p])
  raise
 print('Restored exact pre-preview material files and managed receipt; runtime and settings unchanged.');return old

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True);a=sub.add_parser('prepare')
 for key in ['job','fingerprints','output']:a.add_argument('--'+key,type=Path,required=True)
 a=sub.add_parser('apply');a.add_argument('receipt',type=Path);a=sub.add_parser('rollback');a.add_argument('backup',type=Path);args=p.parse_args()
 if args.command=='prepare':prepare(args.job,args.fingerprints,args.output)
 elif args.command=='apply':apply(args.receipt)
 else:rollback(args.backup)
