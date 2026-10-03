"""Managed normal-startup native adapter; verify every source and owned target."""
import json,shutil,subprocess,time
from pathlib import Path
from mod import ROOT,settings,base_checkout,read_json,write_json,digest,required_file

def write_receipt(path,data):
    temporary=path.with_suffix('.pending.json')
    write_json(temporary,data);temporary.replace(path)

def restore_native_runtime(cfg,backup):
    backup=Path(backup).resolve();owned_root=(ROOT/'local').resolve()
    if not backup.is_relative_to(owned_root):raise ValueError('Backup must be a managed local snapshot')
    source=read_json(backup/'receipt.json');current=read_json(ROOT/'local/native-installation.json')
    game=cfg['game'].resolve()
    if Path(source['game']).resolve()!=game or Path(current['game']).resolve()!=game:raise ValueError('Backup game path differs')
    query=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',
        'Get-Process witcher3 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id'],capture_output=True,text=True)
    if query.stdout.strip():raise RuntimeError('Close Witcher before restoring a native module')
    old={r['path']:r for r in current['files']};restore={r['path']:r for r in source['files']}
    for rel,row in old.items():
        target=(game/rel).resolve()
        if not target.is_relative_to(game) or not target.is_file() or digest(target)!=row['sha256']:raise ValueError('Managed target changed; preserve it: '+rel)
    for rel,row in restore.items():
        target=(game/rel).resolve();saved=(backup/rel).resolve()
        if not target.is_relative_to(game) or not saved.is_relative_to(backup) or digest(required_file(saved))!=row['sha256']:raise ValueError('Backup file differs: '+rel)
        if target.exists() and rel not in old:raise ValueError('Preserve unmanaged restore target: '+rel)
    rollback=ROOT/'local'/('native-restore-backup-'+time.strftime('%Y%m%d-%H%M%S'));rollback.mkdir()
    for rel in old:
        target=rollback/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(game/rel,target)
    write_json(rollback/'receipt.json',current);changed=[]
    try:
        for rel,row in restore.items():
            target=game/rel;target.parent.mkdir(parents=True,exist_ok=True);changed.append(rel);shutil.copy2(backup/rel,target)
            if digest(target)!=row['sha256']:raise RuntimeError('Restored hash differs: '+rel)
        for rel in old.keys()-restore.keys():(game/rel).unlink();changed.append(rel)
        source['restoredFrom']=str(backup);source['backup']=str(rollback)
        write_receipt(ROOT/'local/native-installation.json',source)
    except BaseException:
        for rel in reversed(changed):
            if rel in old:shutil.copy2(rollback/rel,game/rel)
            elif (game/rel).exists():(game/rel).unlink()
        raise
    print('Restored exact native-owned snapshot; preferences and .31 resources preserved.');return source

def install_native_runtime(cfg,remove=False):
    query=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',
        "Get-Process witcher3 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id"],capture_output=True,text=True)
    if query.stdout.strip():raise RuntimeError('Close Witcher before replacing its native module')
    game=cfg['game'].resolve();receipt_path=ROOT/'local/native-installation.json'
    previous=read_json(receipt_path) if receipt_path.exists() else None
    if previous and previous['game']!=str(game):raise ValueError('Managed installation belongs to another game path')
    old={r['path']:r for r in previous['files']} if previous else {}
    for rel,row in old.items():
        target=(game/rel).resolve()
        if not target.is_relative_to(game) or not target.is_file() or digest(target)!=row['sha256']:
            raise ValueError('Managed target changed; preserve it: '+rel)
    if remove:
        if not previous:raise ValueError('No managed native installation')
        for rel in old:(game/rel).unlink()
        receipt_path.replace(ROOT/'local'/('native-removed-'+time.strftime('%Y%m%d-%H%M%S')+'.json'))
        print('Removed only verified native-owned files; .31 baseline preserved.');return
    pin=base_checkout(cfg)['commit'];release=ROOT/'build/native-runtime-controller/Release'
    selection_path=ROOT/'build/full-runtime/current-install.json'
    selection=read_json(selection_path) if selection_path.exists() else dict(profile='build/full-runtime/runtime-profile-166cb02-contacts',render='build/full-runtime/render-contract-166cb02-v4')
    profile_dir=ROOT/selection['profile'];render_dir=ROOT/selection['render']
    profile=read_json(profile_dir/'manifest.json')
    render=read_json(render_dir/'manifest.json')
    if profile['baseCommit']!=pin or render['baseCommit']!=pin or render['bindingsSHA256']!=profile['bindingsSHA256']:
        raise ValueError('Native profile/render contract differs from committed Base pin')
    files={
      'bin/x64_dx12/dinput8.dll':release/'dinput8.dll',
      **{'bin/x64_dx12/malemod-native/'+n:release/n for n in ['malemod_witcher.dll','surface_worker.exe','malemod-runtime.profile',
          'geralt.bindings','geralt.render','geralt.render.sha256','graphics-owned-fingerprints.bin','malemod-overlay.enable']},
      'Mods/modMaleModNative/content/scripts/local/malemod/runtime.ws':ROOT/'probes/native/runtime.ws',
      'Mods/modMaleModNative/content/scripts/local/malemod/render_bones.ws':render_dir/'render_bones.ws'}
    if selection.get('clinical'):
        clinical_dir=ROOT/selection['clinical'];clinical=read_json(clinical_dir/'manifest.json')
        if clinical['baseCommit']!=pin or digest(clinical_dir/'clinical.render')!=clinical['packetSHA256']:
            raise ValueError('Clinical rendering pin/hash differs')
        if digest(cfg['base']/'legacy/wolverine/src/runtime/splat_bakes.bin')!=clinical['bakeSHA256']:
            raise ValueError('Clinical bake differs from Base source')
        from mod import verify_package
        package=ROOT/clinical['package'];patch=verify_package(package)
        if patch['baseCommit']!=pin or patch['project']!='modMaleModClinical':raise ValueError('Clinical native package differs')
        for row in patch['files']:files[row['path']]=package/row['path']
        for name in ['clinical.render','clinical.render.sha256']:files['bin/x64_dx12/malemod-native/'+name]=release/name
        files['bin/x64_dx12/malemod-native/splat_bakes.bin']=cfg['base']/'legacy/wolverine/src/runtime/splat_bakes.bin'
        files['Mods/modMaleModNative/content/scripts/local/malemod/clinical.ws']=ROOT/'probes/native/clinical.ws'
    if selection.get('bodyPackage'):
        from mod import verify_package
        package=ROOT/selection['bodyPackage'];patch=verify_package(package)
        if patch['baseCommit']!=pin or patch['project']!='mod0000MaleModBodyBoundary':raise ValueError('Body patch pin/priority package differs')
        for row in patch['files']:
            source=package/row['path']
            if digest(source)!=row['sha256']:raise ValueError('Body patch file differs')
            files[row['path']]=source
    for name,expected in [('surface_worker.exe',profile['workerSHA256']),('malemod-runtime.profile',profile['packetSHA256']),
                          ('geralt.bindings',profile['bindingsSHA256']),('geralt.render',render['packetSHA256'])]:
        if digest(required_file(release/name))!=expected:raise ValueError('Native input hash differs: '+name)
    proof=read_json(ROOT/'build/probe/native-bootstrap-compile.json')
    if proof['exitCode'] or proof['scriptImportsStubbed'] or digest(ROOT/proof['artifact'])!=proof['artifactSHA256']:
        raise ValueError('Official native startup compilation proof failed')
    for name in ['runtime','render_bones']+(['clinical'] if selection.get('clinical') else []):
        rel='local/malemod/'+name+'.ws';source=files['Mods/modMaleModNative/content/scripts/'+rel]
        if proof['ownedSourceHashes'].get(rel)!=digest(source):raise ValueError('Native script differs from compiler proof')
    baseline=read_json(ROOT/'local/installation.json')
    if not all(digest(Path(baseline['target'])/f['path'])==f['sha256'] for f in baseline['files']):
        raise ValueError('Installed .31 baseline differs')
    for rel,source in files.items():
        if source.name=='malemod-overlay.enable':
            if not source.is_file():raise ValueError('Missing overlay enable marker')
        else:required_file(source)
        target=(game/rel).resolve()
        if not target.is_relative_to(game):raise ValueError('Target escapes game directory')
        if target.exists() and rel not in old:raise ValueError('Unmanaged target exists; preserve it: '+rel)
    backup=ROOT/'local'/('native-backup-'+time.strftime('%Y%m%d-%H%M%S'));backup.mkdir()
    for rel in old:
        out=backup/rel;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(game/rel,out)
    if previous:write_json(backup/'receipt.json',previous)
    changed=[]
    try:
        for rel,source in files.items():
            target=game/rel;target.parent.mkdir(parents=True,exist_ok=True);changed.append(rel);shutil.copy2(source,target)
            if digest(target)!=digest(source):raise RuntimeError('Installed hash mismatch: '+rel)
        receipt=dict(game=str(game),baseCommit=pin,normalStartup=True,diagnosticSourceContacts=profile['diagnosticSourceContacts'],
            files=[dict(path=rel,sha256=digest(source)) for rel,source in files.items()],compilerProofSHA256=digest(ROOT/'build/probe/native-bootstrap-compile.json'),
            baselinePreserved=True,backup=str(backup),observedNormalStartup=False,observedMenu=False,observedMeshReplacement=False)
        write_receipt(receipt_path,receipt)
    except BaseException:
        for rel in reversed(changed):
            if rel in old:shutil.copy2(backup/rel,game/rel)
            elif (game/rel).exists():(game/rel).unlink()
        raise
    print(json.dumps(receipt,indent=2));return receipt
