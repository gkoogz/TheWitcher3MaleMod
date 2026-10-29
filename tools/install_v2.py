"""Prepare, install and restore the exact reviewed standalone v2 payload."""
import argparse
import json
import os
import shutil
import stat
import subprocess
import time
import tempfile
import wave
from pathlib import Path, PurePosixPath
from mod import ROOT, digest, read_json, write_json, settings
from native_preview import load_preview

BODY_PACKAGE_PREFIX='Mods/mod000000WitcherV2/content/'
BODY_CORE_FILES=frozenset(BODY_PACKAGE_PREFIX+p for p in ('bundles/blob0.bundle','bundles/buffers0.bundle','dep.cache','metadata.store','texture.cache'))
LOD_MUTABLE_FILES=frozenset(BODY_PACKAGE_PREFIX+p for p in ('bundles/blob0.bundle','metadata.store'))


def body_package_paths(contract=None):
    """Return the exact reviewed body inventory, including declared shader caches."""
    contract=read_json(ROOT/'v2/payload.json')if contract is None else contract
    paths=[p for p in contract.get('requiredFiles',[])if p.startswith(BODY_PACKAGE_PREFIX)]
    if (contract.get('schema')!='malemod.witcher-v2-payload/1'or len({p.casefold()for p in paths})!=len(paths)
            or not BODY_CORE_FILES.issubset(paths)):
        raise ValueError('Body package contract is incomplete or ambiguous')
    for relative in paths:target(Path('body-package'),relative)
    return frozenset(paths)


def lod_body_inventory(old,new,contract=None):
    """Permit only repacked mesh metadata and its regenerated metadata store."""
    expected=body_package_paths(contract)
    if set(old)!=expected or set(new)!=expected:raise ValueError('LOD body inventory differs from exact payload contract')
    for relative in expected-LOD_MUTABLE_FILES:
        if old[relative]['sha256']!=new[relative]['sha256']:
            raise ValueError('LOD probe changed immutable body buffer/texture/dependency/shader bytes: '+relative)
    return expected


def target(root, relative):
    p = PurePosixPath(relative)
    if not p.parts or p.as_posix()!=relative or p.is_absolute() or '..' in p.parts or '\\' in relative or ':' in relative:
        raise ValueError('Invalid managed relative path: '+relative)
    result = root.joinpath(*p.parts)
    if not result.resolve().is_relative_to(root.resolve()):
        raise ValueError('Managed path redirects outside game: '+relative)
    return result


def verify(root, rows):
    for row in rows:
        if digest(target(root, row['path'])) != row['sha256']:
            raise ValueError('Preserve changed managed file: '+row['path'])


def copy_owned(source, destination):
    """Publish complete verified bytes in one filesystem replacement."""
    destination=Path(destination)
    fd,temporary=tempfile.mkstemp(prefix='.malemod-install-',dir=destination.parent)
    os.close(fd); temporary=Path(temporary)
    try:
        shutil.copy2(source,temporary)
        if digest(temporary)!=digest(source): raise ValueError('Atomic copy verification failed')
        if destination.exists(): destination.chmod(stat.S_IREAD | stat.S_IWRITE)
        os.replace(temporary,destination)
    finally:
        if temporary.exists(): remove_owned(temporary)


def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,temporary=tempfile.mkstemp(prefix='.malemod-receipt-',dir=path.parent)
    os.close(fd);temporary=Path(temporary)
    try:
        write_json(temporary,value);os.replace(temporary,path)
    finally:
        if temporary.exists():remove_owned(temporary)


def remove_owned(path):
    path.chmod(stat.S_IREAD | stat.S_IWRITE)
    path.unlink()


def protected_files(game):
    documents=Path.home()/'Documents/The Witcher 3'
    files=[game/'bin/config/base/audio.ini']
    files += [p for p in documents.iterdir() if p.is_file() and p.suffix.lower() in ('.settings','.xml')]
    files += [p for p in (documents/'gamesaves').iterdir() if p.is_file()]
    return {str(p):digest(p) for p in files if p.is_file()}


def quiet():
    result = subprocess.check_output(['tasklist', '/FI', 'IMAGENAME eq witcher3.exe', '/FO', 'CSV', '/NH'], text=True)
    if 'witcher3.exe' in result.lower():
        raise RuntimeError('Preserve the running game; installation needs a closed process')


def payload_path(relative):
    return (relative == 'bin/x64_dx12/dinput8.dll'
            or relative.startswith('bin/x64_dx12/malemod-native/')
            or relative.startswith('Mods/mod000000WitcherV2/')
            or relative.startswith('Mods/modMaleModClinical/')
            or relative.startswith('Mods/modMaleModNative/'))


def payload_inventory(rows, contract, private_assets=None):
    """Use an explicit reviewed inventory; never ship a directory wildcard."""
    required=list(contract.get('requiredFiles',[]))
    if contract.get('localAssetManifest'):
        if private_assets is None:raise ValueError('Exact local private asset inventory required')
        required += [r['path']for r in private_assets['files']]
    if contract.get('schema')!='malemod.witcher-v2-payload/1' or not required or len({p.casefold()for p in required})!=len(required):
        raise ValueError('Invalid standalone payload contract')
    for path in required:
        target(Path('payload'),path)
        lowered=path.lower()
        if (not payload_path(path) or any(s in lowered for s in ('iteration','continuetest','checkpoint','capture','diagnostic'))
                or Path(path).suffix.lower() in ('.json','.jsonl','.log','.png','.pdb','.ilk','.exp','.lib')):
            raise ValueError('Development file cannot enter standalone payload: '+path)
    selected=[dict(path=r['path'],sha256=r['sha256'])for r in rows if payload_path(r['path'])]
    if len(selected)!=len({r['path']for r in selected}) or {r['path']for r in selected}!=set(required):
        raise ValueError('Standalone payload differs from exact reviewed inventory')
    if private_assets:
        hashes={r['path']:r['sha256']for r in selected}
        if any(hashes[r['path']]!=r['sha256']for r in private_assets['files']):raise ValueError('Private asset bytes differ from local source inventory')
    return sorted(selected,key=lambda r:r['path'])


def private_sources():
    # Audio approval is explicit. Never refill rejected Geralt assets from
    # Wolverine's pools merely because those local source files still exist.
    profile=read_json(ROOT/'v2/voice-profile.json')
    if profile.get('schema')!='malemod.witcher-voice-profile/1' or profile.get('character_id')!='geralt':
        raise ValueError('Expected explicit Geralt voice policy')
    if profile.get('state')=='needs_recording':
        source=Path('C:/Games/X-Men Origins Wolverine/Binaries')
        return source,[source/'TeachingFluid.ini']
    if profile.get('state')!='approved':raise ValueError('Unknown voice approval state; no legacy fallback')
    pointer=read_json(ROOT/'local/v2-voice-pack.json');manifest=Path(pointer['manifest']).resolve()
    if not manifest.is_relative_to((ROOT/'v2/build/voice-packs').resolve())or digest(manifest)!=pointer['sha256']:
        raise ValueError('Expected owned reviewed voice pack')
    pack=read_json(manifest);source=Path(pack['root']).resolve()
    expected={'TeachingFluid.ini',*profile['bindings'].values()}
    if (pack.get('schema')!='malemod.witcher-voice-pack/1'or pack.get('character_id')!='geralt'
            or source!=manifest.parent or len(pack['files'])!=len(expected)
            or {r['path']for r in pack['files']}!=expected):raise ValueError('Voice pack changes the ID binding contract')
    paths=[]
    for row in pack['files']:
        path=target(source,row['path'])
        if path.is_symlink()or digest(path)!=row['sha256']:raise ValueError('Approved private voice recording changed')
        paths.append(path)
    return source,paths


def prepare_private_assets():
    """Inventory local user-owned inputs without copying them into the repo."""
    source,paths=private_sources()
    rows=[]
    for path in paths:
        if path.is_symlink()or not path.resolve().is_relative_to(source.resolve()):raise ValueError('Private source redirects outside original game')
        row=dict(path='bin/x64_dx12/malemod-native/'+path.relative_to(source).as_posix(),source=str(path),bytes=path.stat().st_size,sha256=digest(path))
        if path.suffix=='.wav':
            with wave.open(str(path),'rb')as clip:
                if clip.getcomptype()!='NONE' or clip.getnframes()==0:raise ValueError('Expected original uncompressed PCM clip')
                row.update(channels=clip.getnchannels(),sampleRate=clip.getframerate(),sampleBytes=clip.getsampwidth(),frames=clip.getnframes())
        rows.append(row)
    manifest=ROOT/'local/v2-private-assets.json'
    atomic_json(manifest,dict(schema='malemod.witcher-v2-private-assets/1',localOnly=True,publicRedistribution=False,sourceRoot=str(source),files=rows))
    return dict(manifest=str(manifest),files=len(rows),sha256=digest(manifest),publicRedistribution=False)


def load_private_assets(contract):
    relative=contract.get('localAssetManifest')
    if relative!='local/v2-private-assets.json':raise ValueError('Expected the private local inventory')
    path=ROOT/relative;data=read_json(path)
    if data.get('schema')!='malemod.witcher-v2-private-assets/1'or data.get('localOnly')is not True or data.get('publicRedistribution')is not False:
        raise ValueError('Private assets must remain local user inputs')
    source_root,sources=private_sources()
    if (Path(data['sourceRoot']).resolve()!=source_root.resolve()
            or len(data['files'])!=len(sources)
            or {str(Path(row['source']).resolve())for row in data['files']}!={str(p.resolve())for p in sources}):
        raise ValueError('Private manifest omits or changes the original local source inventory')
    for row in data['files']:
        source=Path(row['source'])
        if not source.resolve().is_relative_to(Path(data['sourceRoot']).resolve())or digest(source)!=row['sha256']:
            raise ValueError('Private source asset changed')
        if row['path']!='bin/x64_dx12/malemod-native/'+source.relative_to(data['sourceRoot']).as_posix():
            raise ValueError('Unexpected private asset destination')
    return path,data


def prepare(preview):
    source, data = load_preview(preview)
    contract=ROOT/'v2/payload.json'
    contract_data=read_json(contract);private_path,private=load_private_assets(contract_data)
    rows=payload_inventory(data['files'],contract_data,private)
    if data.get('testOnlyLODMetadata'): raise ValueError('The LOD probe is excluded from installation')
    verify(source, rows)
    job = ROOT/'v2/build/installation'/('prepared-'+str(time.time_ns()))
    for row in rows:
        dest = target(job/'payload', row['path']); dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target(source, row['path']), dest)
    verify(job/'payload', rows)
    record = dict(schema='malemod.witcher-v2-install/2', game=data['sourceGame'],
                  preview=str(Path(preview).resolve()), previewSHA256=digest(preview),
                  payloadContractSHA256=digest(contract),
                  privateAssetManifestSHA256=digest(private_path),localPrivateAssetsIncluded=True,publicRedistribution=False,
                  baselineReceipts={name:digest(ROOT/'local'/name)for name in ('native-installation.json','installation.json')}, files=rows,
                  installed=False, includesDevelopmentRoom=False)
    write_json(job/'manifest.json', record)
    return job/'manifest.json'


def managed_baseline(game):
    native = read_json(ROOT/'local/native-installation.json')
    fallback = read_json(ROOT/'local/installation.json')
    if Path(native['game']).resolve() != game.resolve():
        raise ValueError('Installation game identity differs')
    rows = {r['path']:r for r in native['files']}
    base = Path(fallback['target']).resolve().relative_to(game.resolve()).as_posix()
    for r in fallback['files']:
        row = dict(path=base+'/'+r['path'], sha256=r['sha256'])
        if row['path'] in rows and rows[row['path']]['sha256'] != row['sha256']:
            raise ValueError('Conflicting ownership receipts')
        rows[row['path']] = row
    return list(rows.values())


def replace_transaction(game, payload, old, new, backup, on_prepared=None):
    """Replace only verified owned files, restoring all bytes after any failure."""
    verify(game, old); verify(payload, new)
    oldpaths = {r['path'] for r in old}; newpaths = {r['path'] for r in new}
    for rel in newpaths-oldpaths:
        if target(game, rel).exists(): raise ValueError('Preserve unmanaged target: '+rel)
    backup.mkdir(parents=True, exist_ok=False)
    for row in old:
        dest = target(backup, row['path']); dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target(game, row['path']), dest)
    verify(backup, old)
    if on_prepared is not None:on_prepared(backup)
    changed = []
    try:
        for rel in sorted(oldpaths-newpaths):
            changed.append(rel); remove_owned(target(game, rel))
        for row in new:
            rel = row['path']; changed.append(rel); dest=target(game, rel)
            dest.parent.mkdir(parents=True, exist_ok=True); copy_owned(target(payload, rel), dest)
        verify(game, new)
    except BaseException:
        for rel in reversed(changed):
            dest = target(game, rel)
            if rel in oldpaths:
                dest.parent.mkdir(parents=True, exist_ok=True); copy_owned(target(backup, rel), dest)
            elif dest.exists(): remove_owned(dest)
        verify(game, old)
        raise


def install(manifest, acceptance):
    quiet(); manifest=Path(manifest).resolve(); data=read_json(manifest)
    if (data.get('schema')!='malemod.witcher-v2-install/2'
            or not manifest.is_relative_to((ROOT/'v2/build/installation').resolve())
            or data.get('installed')
            or digest(ROOT/'v2/payload.json')!=data.get('payloadContractSHA256')):
        raise ValueError('Expected an unchanged prepared standalone package')
    contract=read_json(ROOT/'v2/payload.json')
    private_path,private=load_private_assets(contract)
    if digest(private_path)!=data.get('privateAssetManifestSHA256')or data.get('publicRedistribution')is not False:
        raise ValueError('Prepared private asset inventory changed')
    if set(data.get('baselineReceipts',{}))!={'native-installation.json','installation.json'}:
        raise ValueError('Both installed ownership receipts must be bound')
    if digest(Path(data['preview']))!=data['previewSHA256']:raise ValueError('Prepared preview changed')
    _,preview_data=load_preview(Path(data['preview']))
    if (preview_data.get('testOnlyLODMetadata') or payload_inventory(data['files'],contract,private)!=data['files']
            or payload_inventory(preview_data['files'],contract,private)!=data['files']):
        raise ValueError('Prepared bytes differ from exact reviewed preview')
    review=read_json(acceptance); session=read_json(Path(review['receipt']))
    module=next(r['sha256']for r in data['files']if r['path']=='bin/x64_dx12/malemod-native/malemod_witcher.dll')
    worker=next(r['sha256']for r in data['files']if r['path']=='bin/x64_dx12/malemod-native/canonical_worker.exe')
    from aggregate_v2_acceptance import verify_aggregate
    verify_aggregate(review,module,worker,data['previewSHA256'],data['files'])
    if (not review.get('attachmentVisualAccepted') or not review.get('campaignPassed')
            or not review.get('featureParityPassed')or not review.get('clinicalPassed')or not review.get('privateAudioVerified')
            or not review.get('everyVisibleSDKTickServiced')
            or review.get('runtimeFailures') or not review.get('allPhysicsRequestsCompleted')
            or review.get('lodMask') != 15 or not review.get('panelPassed')
            or not session.get('closed') or not session.get('audioRestored')
            or not session.get('iterationWorldFilesRemoved')
            or review.get('runtimeSHA256')!=module or session.get('moduleSHA256')!=module
            or session.get('nativePreviewSHA256') != data['previewSHA256']):
        raise ValueError('Preserve installed runtime: exact native acceptance is incomplete')
    if any(digest(ROOT/'local'/name)!=sha for name,sha in data['baselineReceipts'].items()):
        raise ValueError('Installed baseline changed since package preparation')
    game=settings()['game']; old=managed_baseline(game); payload=manifest.parent/'payload'
    if str(game) != data['game']: raise ValueError('Package game identity differs')
    protected=protected_files(game)
    receipts={name:(ROOT/'local'/name).read_bytes() for name in ['native-installation.json','installation.json']}
    backup=manifest.parent/'rollback'
    def journal(directory):
        for name,contents in receipts.items(): (directory/name).write_bytes(contents)
        atomic_json(directory/'rollback.json',dict(schema='malemod.witcher-v2-rollback/1',game=str(game),
            old=old,new=data['files'],receipts={name:digest(directory/name)for name in receipts},state='prepared'))
    replace_transaction(game,payload,old,data['files'],backup,on_prepared=journal)
    try:
        if any(digest(Path(p))!=sha for p,sha in protected.items()):
            raise RuntimeError('Protected saves/settings changed during installation')
        atomic_json(ROOT/'local/native-installation.json',dict(game=str(game),baseCommit='47023a7f53d794cff84f2f423ba6a7d1fb98ec0f',
            normalStartup=True,files=data['files'],v2=True,rollback=str(backup),acceptance=str(acceptance),acceptanceSHA256=digest(acceptance)))
        atomic_json(ROOT/'local/installation.json',dict(target=str(game/'Mods/mod000000WitcherV2'),project='mod000000WitcherV2',version='2.0-development',files=[]))
        data.update(installed=True,rollback=str(backup),acceptance=str(acceptance),acceptanceSHA256=digest(acceptance),protectedFilesVerified=len(protected));atomic_json(manifest,data)
        rollback_data=read_json(backup/'rollback.json');rollback_data['state']='installed';atomic_json(backup/'rollback.json',rollback_data)
    except BaseException:
        for r in data['files']:
            if r['path'] not in {x['path'] for x in old} and target(game,r['path']).exists(): remove_owned(target(game,r['path']))
        for r in old:
            dest=target(game,r['path']);dest.parent.mkdir(parents=True,exist_ok=True);copy_owned(target(backup,r['path']),dest)
        for name in receipts:copy_owned(backup/name,ROOT/'local'/name)
        raise
    return data


def rollback(backup):
    quiet(); backup=Path(backup).resolve(); data=read_json(backup/'rollback.json');game=settings()['game']
    if str(game) != data['game']: raise ValueError('Rollback game identity differs')
    for name,sha in data.get('receipts',{}).items():
        if digest(backup/name)!=sha:raise ValueError('Rollback receipt changed')
    # A failed rollback itself restores the complete current version.
    undo=backup/('rollback-attempt-'+str(time.time_ns()))
    receipts={name:(ROOT/'local'/name).read_bytes()for name in ('native-installation.json','installation.json')}
    replace_transaction(game,backup,data['new'],data['old'],undo)
    try:
        for name in receipts:copy_owned(backup/name,ROOT/'local'/name)
    except BaseException:
        oldpaths={r['path']for r in data['old']};newpaths={r['path']for r in data['new']}
        for rel in oldpaths-newpaths:remove_owned(target(game,rel))
        for row in data['new']:
            dest=target(game,row['path']);dest.parent.mkdir(parents=True,exist_ok=True);copy_owned(target(undo,row['path']),dest)
        for name,contents in receipts.items():(ROOT/'local'/name).write_bytes(contents)
        raise
    data['state']='restored';atomic_json(backup/'rollback.json',data)
    return dict(restored=True,files=len(data['old']))


def recover(backup):
    """Restore an interrupted transaction, refusing unknown edited target bytes."""
    quiet();backup=Path(backup).resolve();data=read_json(backup/'rollback.json');game=settings()['game']
    if data.get('schema')!='malemod.witcher-v2-rollback/1' or str(game)!=data['game']:
        raise ValueError('Expected exact interrupted transaction identity')
    verify(backup,data['old'])
    allowed={}
    for row in data['old']+data['new']:allowed.setdefault(row['path'],set()).add(row['sha256'])
    for rel,hashes in allowed.items():
        path=target(game,rel)
        if path.exists() and digest(path)not in hashes:raise ValueError('Preserve unknown edited file: '+rel)
    for name,sha in data['receipts'].items():
        if digest(backup/name)!=sha:raise ValueError('Rollback receipt changed')
    oldpaths={r['path']for r in data['old']}
    for rel in allowed.keys()-oldpaths:
        if target(game,rel).exists():remove_owned(target(game,rel))
    for row in data['old']:
        dest=target(game,row['path']);dest.parent.mkdir(parents=True,exist_ok=True);copy_owned(target(backup,row['path']),dest)
    verify(game,data['old'])
    for name in data['receipts']:copy_owned(backup/name,ROOT/'local'/name)
    data['state']='recovered';atomic_json(backup/'rollback.json',data)
    return dict(recovered=True,files=len(data['old']))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('prepare');a.add_argument('preview',type=Path)
    a=s.add_parser('private-assets')
    a=s.add_parser('install');a.add_argument('manifest',type=Path);a.add_argument('acceptance',type=Path)
    a=s.add_parser('rollback');a.add_argument('backup',type=Path)
    a=s.add_parser('recover');a.add_argument('backup',type=Path)
    a=p.parse_args()
    result=prepare_private_assets() if a.action=='private-assets' else prepare(a.preview) if a.action=='prepare' else install(a.manifest,a.acceptance) if a.action=='install' else rollback(a.backup) if a.action=='rollback' else recover(a.backup)
    print(json.dumps(result,indent=2,default=str))
