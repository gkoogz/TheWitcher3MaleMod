"""Prepare/adopt measured skin bindings; never modify the installed game."""
import argparse,os,shutil
from pathlib import Path
import mod
from mod import ROOT,read_json,write_json,digest
from build_v2_carriers import adopt as adopt_carriers
from adopt_v2_clinical_carriers import records
from v2_native_binding import read_binding,cooked_resource
from campaign_save_isolation import quiet

FILES=('geralt-source-binding.bin','graphics-owned-fingerprints.bin','geralt-meridian-binding.bin',
       'geralt-meridian-coverage.bin','geralt-clinical-topology.bin','garment.render','clinical.render',
       'clinical-splat-bakes.bin','render_bones.ws','manifest.json','meridian-binding.json','coverage.json',
       'clinical-topology.json','carrier-binding.json','clinical-carrier-binding.json','source-precision.json')

def owned(path):
    path=Path(path).resolve()
    if not path.is_relative_to((ROOT/'v2/build').resolve()):raise ValueError('Expected owned v2 authoring output')
    return path

def inventory(bindings):
    manifest=read_json(bindings/'manifest.json')
    return FILES+(('source-lighting.json',)if 'sourceLighting'in manifest else())

def validate_waist_manifest(manifest):
    """The optional calibration is embedded in the existing manifest payload."""
    waist=manifest.get('sourceWaist')
    if waist is None:return
    if(waist.get('schema')!='malemod.stock-waist-B04-baseline-calibration/1'
            or waist.get('bindingSHA256')!=manifest.get('sourcePrecision',{}).get('rawBindingSHA256')
            or not waist.get('onlyDeclaredNewRowsAndOldPackedTChanged')
            or waist.get('sourceNumericsModified')is not False
            or len(waist.get('newTopRows',[]))!=34):
        raise ValueError('Measured stock-waist calibration does not precede source precision')

def prepare(bindings,body_package):
    bindings=owned(bindings);body_package=owned(body_package);old=ROOT/'v2/build/runtime-binding'
    if bindings==old.resolve()or body_package.name not in ('package.json','package-with-shaders.json'):raise ValueError('Prepare a separate measured binding output')
    binding=read_binding(bindings/'geralt-source-binding.bin')
    if binding['version']!=4:raise ValueError('Sectioned source skin binding required')
    manifest=read_json(bindings/'manifest.json')
    validate_waist_manifest(manifest)
    if 'sourceWaist'in manifest:
        if(digest(bindings/'source-waist.json')!=manifest.get('sourceWaistReceiptSHA256')
                or read_json(bindings/'source-waist.json')!=manifest['sourceWaist']):
            raise ValueError('Explicit source-waist calibration receipt changed')
    if digest(bindings/'source-precision.json')!=manifest.get('sourcePrecisionReceiptSHA256'):
        raise ValueError('Source precision receipt differs from measured binding')
    if read_json(bindings/'source-precision.json')!=manifest.get('sourcePrecision'):
        raise ValueError('Source precision measurements differ from binding manifest')
    if 'sourceLighting'in manifest:
        lighting=read_json(bindings/'source-lighting.json')
        if digest(bindings/'source-lighting.json')!=manifest.get('sourceLightingReceiptSHA256')or lighting!=manifest['sourceLighting']:
            raise ValueError('Source lighting receipt differs from measured binding')
        if lighting['inputBindingSHA256']!=manifest['sourcePrecision']['bindingSHA256']or lighting['bindingSHA256']!=manifest['bindingSHA256']:
            raise ValueError('Source lighting restoration does not follow the measured precision stage')
    for resource in (0,1):cooked_resource(resource,bindings)
    package=read_json(body_package);job=body_package.parent;prior=mod.ROOT;mod.ROOT=job
    try:adopt_carriers(job,bindings,body_package)
    finally:mod.ROOT=prior
    if digest(bindings/'garment.render')!=digest(old/'garment.render'):raise ValueError('Retained garment carrier bounds changed')
    retained=ROOT/'v2/build/materials/clinical-adoption-01';clinical=read_json(retained/'clinical-carrier-binding.json')
    for row in clinical['nativeCarrierFiles']:
        if digest(retained/'native-assets'/row['path'])!=row['sha256']:raise ValueError('Retained clinical carrier changed')
    fragment=retained/'clinical-fingerprints.bin'
    if digest(fragment)!=clinical['fingerprintFragmentSHA256']:raise ValueError('Retained clinical fingerprint fragment changed')
    current=records(bindings/'graphics-owned-fingerprints.bin');fluid=records(fragment)
    if not fluid or any(not label.startswith('fluid_')for label in fluid):raise ValueError('Unexpected retained clinical labels')
    current={key:value for key,value in current.items()if not key.startswith('fluid_')};current.update(fluid)
    import struct
    (bindings/'graphics-owned-fingerprints.bin').write_bytes(b'MMGPH01\0'+struct.pack('<I',len(current))+b''.join(current.values()))
    for name in ('clinical.render','clinical-splat-bakes.bin'):shutil.copy2(old/name,bindings/name)
    clinical.update(mergedFingerprintSHA256=digest(bindings/'graphics-owned-fingerprints.bin'),retainedCarrierReceiptSHA256=digest(retained/'clinical-carrier-binding.json'))
    write_json(bindings/'clinical-carrier-binding.json',clinical)
    manifest=read_json(bindings/'manifest.json');manifest.update(bodyFingerprintsSHA256=manifest.get('bodyFingerprintsSHA256',manifest['fingerprintsSHA256']),fingerprintsSHA256=digest(bindings/'graphics-owned-fingerprints.bin'),
        bodyPackageInfo=str(body_package),bodyPackageInfoSHA256=digest(body_package),bodyPackageManifestSHA256=digest(Path(package['directory'])/'build-manifest.json'))
    write_json(bindings/'manifest.json',manifest)
    result=dict(schema='malemod.witcher-v2-skin-bindings/1',bindings=str(bindings),bodyPackageInfo=str(body_package),bodyPackageInfoSHA256=digest(body_package),
        files=[dict(path=name,sha256=digest(bindings/name))for name in inventory(bindings)],adopted=False,nativeAppearanceAccepted=False)
    write_json(bindings/'prepared.json',result);return result

def check(bindings):
    bindings=owned(bindings);result=read_json(bindings/'prepared.json')
    validate_waist_manifest(read_json(bindings/'manifest.json'))
    if result['bindings']!=str(bindings)or {row['path']for row in result['files']}!=set(inventory(bindings)):raise ValueError('Prepared binding inventory differs')
    if digest(result['bodyPackageInfo'])!=result['bodyPackageInfoSHA256']:raise ValueError('Prepared body package changed')
    for row in result['files']:
        if digest(bindings/row['path'])!=row['sha256']:raise ValueError('Prepared native binding changed: '+row['path'])
    for resource in (0,1):cooked_resource(resource,bindings)
    return result

def adopt(bindings):
    quiet();result=check(bindings);bindings=Path(result['bindings']);destination=ROOT/'v2/build/runtime-binding'
    originals={row['path']:(destination/row['path']).read_bytes()if(destination/row['path']).exists()else None for row in result['files']}
    try:
        for row in result['files']:
            target=destination/row['path']
            if target.is_symlink():raise ValueError('Preserve redirected native binding')
            pending=target.with_suffix(target.suffix+'.pending');shutil.copy2(bindings/row['path'],pending);os.replace(pending,target)
            if digest(target)!=row['sha256']:raise ValueError('Native binding adoption changed bytes')
    except BaseException:
        for name,data in originals.items():
            target=destination/name
            if data is None:target.unlink(missing_ok=True)
            else:target.write_bytes(data)
        raise
    result['adopted']=True;write_json(bindings/'adopted.json',result);return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('prepare','check','adopt'));parser.add_argument('--bindings',required=True,type=Path)
    parser.add_argument('--body-package',type=Path);args=parser.parse_args()
    if args.action=='prepare'and args.body_package is None:parser.error('--body-package required to prepare')
    import json
    print(json.dumps(prepare(args.bindings,args.body_package)if args.action=='prepare'else adopt(args.bindings)if args.action=='adopt'else check(args.bindings),indent=2))
