"""Replace only the closed owned preview with the standalone v2 payload."""
import json,shutil,time,argparse
from pathlib import Path
from mod import ROOT,read_json,write_json,digest,verify_package
from native_preview import load_preview
from build_v2_carriers import adopt
from adopt_v2_skin_bindings import FILES


def verify_prepared_bindings(info,runtime,binding,prepared_dir=None):
    """Read-only guard for the complete inventory already adopted by the owner."""
    info=Path(info).resolve();runtime=Path(runtime)
    prepared_dir=Path(prepared_dir)if prepared_dir is not None else info.parent/'bindings'
    prepared_path=prepared_dir/'prepared.json';adopted_path=prepared_dir/'adopted.json'
    marked='bodyPackageInfo'in binding or 'bodyPackageInfoSHA256'in binding
    if not marked:
        if not binding.get('schema','').endswith('/3')or prepared_path.exists()or adopted_path.exists():
            raise ValueError('Prepared sectioned bindings require their complete adoption provenance')
        return None # Retain the original B03-only authoring workflow.
    if Path(binding['bodyPackageInfo']).resolve()!=info or binding.get('bodyPackageInfoSHA256')!=digest(info):
        raise ValueError('Adopted bindings belong to a different body package')
    prepared=read_json(prepared_path);adopted=read_json(adopted_path)
    expected=set(FILES)|({'source-lighting.json'}if 'sourceLighting'in binding else set())
    rows=prepared.get('files',[])
    if len(rows)!=len(expected)or {r['path']for r in rows}!=expected:
        raise ValueError('Prepared binding inventory is incomplete or duplicated')
    if (Path(prepared['bindings']).resolve()!=prepared_dir.resolve()or prepared.get('adopted')is not False
            or Path(prepared['bodyPackageInfo']).resolve()!=info
            or prepared.get('bodyPackageInfoSHA256')!=digest(info)):
        raise ValueError('Prepared binding receipt identity differs')
    if adopted!={**prepared,'adopted':True}:
        raise ValueError('Complete prepared binding inventory was not adopted')
    package=read_json(info)
    if binding.get('bodyPackageManifestSHA256')!=digest(Path(package['directory'])/'build-manifest.json'):
        raise ValueError('Prepared package manifest changed')
    for row in rows:
        name=row['path'];wanted=row['sha256']
        if digest(prepared_dir/name)!=wanted or digest(runtime/name)!=wanted:
            raise ValueError('Preserve adopted prepared binding bytes: '+name)
    # This also binds the caller's parsed manifest to the verified inventory.
    if read_json(runtime/'manifest.json')!=binding:
        raise ValueError('Current binding manifest changed during staging checks')
    return dict(path=str(prepared_path.resolve()),sha256=digest(prepared_path),
                adoptedReceiptSHA256=digest(adopted_path),fileCount=len(rows))


def stage(body_package=None,prepared_bindings=None):
    build=ROOT/'v2/build';pointer=build/'grey-fit/preview-path.json'
    old=Path(read_json(pointer)['preview']);game,data=load_preview(old)
    receipt=Path(read_json(build/'grey-runtime/session.json')['receipt']);closed=read_json(receipt)
    # Every unlaunched successor must have a hash-verified ancestry to this
    # exact closed session. Rebuilding before launch does not invent a session.
    bound=False;ancestor=old;seen=set()
    for _ in range(64):
        checksum=digest(ancestor)
        if checksum in seen:break
        seen.add(checksum)
        if checksum==closed.get('nativePreviewSHA256'):bound=True;break
        row=read_json(ancestor)
        if row.get('previousClosedSession')!=str(receipt) or row.get('previousClosedSessionSHA256')!=digest(receipt):break
        previous=Path(row['previousManifest'])
        if not previous.resolve().is_relative_to(old.parent.resolve()) or digest(previous)!=row.get('previousManifestSHA256'):break
        ancestor=previous
    import subprocess
    running = subprocess.check_output(['tasklist','/FI','IMAGENAME eq witcher3.exe','/FO','CSV','/NH'],text=True)
    if 'witcher3.exe' in running.lower() or not(closed.get('closed') and closed.get('audioRestored') and closed.get('iterationWorldFilesRemoved') and bound):
        raise ValueError('Preserve the current preview: exact closed receipt and no game process required')
    selection=build/'standalone-package-current.json'
    if body_package is None and selection.exists():
        selected=read_json(selection);body_package=Path(selected['packageInfo'])
        if digest(body_package)!=selected['packageInfoSHA256']:raise ValueError('Selected standalone package changed')
    info=Path(body_package).resolve()if body_package is not None else build/'standalone-assets-02/package.json'
    if info.name not in ('package.json','package-with-shaders.json') or not info.resolve().is_relative_to(build.resolve()):raise ValueError('Expected an owned body package descriptor')
    job=info.parent;package_info=read_json(info);package=Path(package_info['directory'])
    import mod
    prior=mod.ROOT;mod.ROOT=job
    try:manifest=verify_package(package)
    finally:mod.ROOT=prior
    cook=next(c for c in manifest['nativeCommands']if c['command']=='cook')
    cooked=Path(next(a.split('=',1)[1]for a in cook['args']if a.startswith('-outdir=')))
    binding=read_json(build/'runtime-binding/manifest.json')
    prepared=verify_prepared_bindings(info,build/'runtime-binding',binding,prepared_bindings)
    for row in binding['resources']:
        name=row['resource']
        relative='characters/models/geralt/body/model/'+name+'.w2mesh.1.buffer'
        if digest(cooked/relative)!=row['bufferSHA256']:raise ValueError('Native body buffer changed; regenerate the measured bindings')
        if binding['schema'].endswith('/4') and digest(cooked/relative.removesuffix('.1.buffer'))!=row['cookedSHA256']:
            raise ValueError('Sectioned body metadata differs from its measured binding')
    if prepared is not None:
        if Path(package_info['cooked']).resolve()!=cooked.resolve():
            raise ValueError('Prepared package cooked location differs from its native command')
    else:
        package_info['cooked']=str(cooked);write_json(info,package_info)
        mod.ROOT=job
        try:adopt(job,package_info=info)
        finally:mod.ROOT=prior
    # Rebuild identities from the preserved complete set, never reorder its fingerprints.
    import subprocess,sys
    subprocess.run([sys.executable,str(ROOT/'tools/build_v2_runtime.py')],check=True)
    if prepared is not None:verify_prepared_bindings(info,build/'runtime-binding',binding,prepared_bindings)
    legacy={'modMaleMod','modMaleModNative','modMaleModClinical','modMaleModGarments','mod0000MaleModBodyBoundary','mod00000MaleModNeckMaterial','mod000000V2Fabric','mod000000WitcherV2'}
    rows={}
    for row in data['files']:
        rel=row['path'];parts=Path(rel).parts
        remove=(len(parts)>1 and parts[0]=='Mods' and parts[1]in legacy) or rel.startswith('bin/x64_dx12/malemod-native/')
        if remove:
            target=game/rel
            if not target.resolve().is_relative_to(game):raise ValueError('Preview file leaves owned game')
            target.unlink()
        else:rows[rel]=row
    def put(source,relative):
        target=game/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target);rows[relative]=dict(path=relative,source=str(source),sha256=digest(source))
    for row in manifest['files']:put(package/row['path'],row['path'])
    clinical=build/'materials/clinical-adoption-01/native-assets';clinical_proof=read_json(build/'runtime-binding/clinical-carrier-binding.json')
    for row in clinical_proof['nativeCarrierFiles']:
        source=clinical/row['path']
        if digest(source)!=row['sha256']:raise ValueError('Reviewed native clinical carrier changed')
        put(source,row['path'])
    native={'malemod_witcher.dll':build/'native-runtime/cmake/Release/malemod_witcher.dll','canonical_worker.exe':build/'canonical-core/canonical_worker.exe','geralt-source-binding.bin':build/'runtime-binding/geralt-source-binding.bin','graphics-owned-fingerprints.bin':build/'runtime-binding/graphics-owned-fingerprints.bin','geralt-meridian-binding.bin':build/'runtime-binding/geralt-meridian-binding.bin','garment.render':build/'runtime-binding/garment.render','geralt-meridian-coverage.bin':build/'runtime-binding/geralt-meridian-coverage.bin'}
    for name in ['geralt-clinical-topology.bin','clinical-splat-bakes.bin','clinical.render']:native[name]=build/'runtime-binding'/name
    for name,source in native.items():put(source,'bin/x64_dx12/malemod-native/'+name)
    private=read_json(ROOT/'local/v2-private-assets.json')
    if not private.get('localOnly') or private.get('publicRedistribution') is not False:raise ValueError('Private local asset scope differs')
    for row in private['files']:
        source=Path(row['source'])
        if digest(source)!=row['sha256']:raise ValueError('Local user recording/configuration changed')
        put(source,row['path'])
    for source in (ROOT/'v2/scripts').glob('*.ws'):put(source,'Mods/modMaleModNative/content/scripts/local/malemod/'+source.name)
    put(build/'runtime-binding/render_bones.ws','Mods/modMaleModNative/content/scripts/local/malemod/render_bones.ws')
    data.update(files=list(rows.values()),v1BootstrapPresent=False,v1NumericsDisabled=True,legacyBootstrapScriptsPresent=False,v2PhysicsPresent=True,v2Purpose='standalone-v2-acceptance',previousManifest=str(old),previousManifestSHA256=digest(old),previousClosedSession=str(receipt),previousClosedSessionSHA256=digest(receipt))
    if prepared is not None:data['preparedBindingInventory']=prepared
    new=old.parent/('preview-'+str(time.time_ns())+'.json');write_json(new,data);load_preview(new);write_json(pointer,dict(preview=str(new)))
    write_json(selection,dict(packageInfo=str(info),packageInfoSHA256=digest(info),packageManifestSHA256=digest(package/'build-manifest.json')))
    print('Standalone v2 preview staged; installed game unchanged')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--body-package',type=Path);parser.add_argument('--prepared-bindings',type=Path);args=parser.parse_args();stage(args.body_package,args.prepared_bindings)
