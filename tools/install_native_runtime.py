"""Managed normal-startup native adapter; verify every source and owned target."""
import json,shutil,subprocess,time
from pathlib import Path
from mod import ROOT,settings,base_checkout,read_json,write_json,digest,required_file

def write_receipt(path,data):
    temporary=path.with_suffix('.pending.json')
    write_json(temporary,data);temporary.replace(path)

def startup_snapshot_files(receipt, root):
    """Resolve only the two managed startup-helper recipes, with exact hashes."""
    allowed={'content/scripts/game/r4Game.ws','content/scripts/local/startup_movies.ws'}
    if receipt.get('name')!='modLocalSkipStartupMovies' or len(receipt['files'])!=1:
        raise ValueError('Unexpected startup helper ownership')
    result={}
    for rel,h in receipt['files'].items():
        if rel not in allowed:raise ValueError('Unexpected startup helper path')
        path=root/'Mods/modLocalSkipStartupMovies'/rel
        if not path.resolve().is_relative_to(root.resolve()) or digest(required_file(path))!=h:
            raise ValueError('Startup helper snapshot changed: '+rel)
        result['Mods/modLocalSkipStartupMovies/'+rel]=h
    return result

def verify_native_compatibility(game, release):
    """Keep a stale general build from undoing an executable-specific repair."""
    expected=read_json(ROOT/'characters/game-native-profile.json')['gameSHA256']
    if digest(required_file(game/'bin/x64_dx12/witcher3.exe'))!=expected:
        raise ValueError('Game executable needs a newly observed compatibility profile')
    if expected.encode('ascii') not in required_file(release/'malemod_witcher.dll').read_bytes():
        raise ValueError('Native build targets an older executable; rebuild and validate before installation')

def install_startup_repair(cfg, proof_path):
    """Replace only two ABI adapters, retaining the installed Base/data contract."""
    proof_path=Path(proof_path).resolve()
    if not proof_path.is_relative_to((ROOT/'build').resolve()):
        raise ValueError('Startup repair needs an owned build proof')
    proof=read_json(proof_path)
    if (proof.get('schema')!='malemod.startup-repair/1' or
            not all(proof.get(k) for k in ('abiObserved','startupGateTestPassed',
                'offlineAttachmentRegressionPassed','nativeRoomRegressionPassed',
                'nativeCampaignRegressionPassed','candidateSessionsClosed'))):
        raise ValueError('Startup repair regression evidence is incomplete')
    game=cfg['game'].resolve()
    previous=read_json(ROOT/'local/native-installation.json')
    if Path(previous['game']).resolve()!=game or previous['baseCommit']!=proof['baseCommit']:
        raise ValueError('Repair must retain this installed Base/data revision')
    query=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',
        'Get-Process witcher3 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id'],capture_output=True,text=True)
    if query.stdout.strip():raise RuntimeError('Preserve the existing Witcher session')
    if digest(game/'bin/x64_dx12/witcher3.exe')!=proof['gameSHA256']:
        raise ValueError('Game changed after compatibility validation')
    expected={'bin/x64_dx12/dinput8.dll','bin/x64_dx12/malemod-native/malemod_witcher.dll'}
    replacements={row['path']:row for row in proof['replacements']}
    if set(replacements)!=expected or len(proof['replacements'])!=2:
        raise ValueError('Startup repair may replace only the two native ABI adapters')
    for row in previous['files']:
        target=(game/row['path']).resolve()
        if not target.is_relative_to(game) or digest(required_file(target))!=row['sha256']:
            raise ValueError('Installed file changed; preserve it: '+row['path'])
    for rel,row in replacements.items():
        if rel not in {r['path'] for r in previous['files']}:
            raise ValueError('Repair target is not managed')
        if digest(required_file(Path(row['source'])))!=row['sha256']:
            raise ValueError('Validated replacement changed: '+rel)
    for row in proof['evidenceFiles']:
        if digest(required_file(Path(row['path'])))!=row['sha256']:
            raise ValueError('Regression evidence changed')
    startup=proof.get('startupMoviesRepair')
    startup_previous=None;startup_compiled=None
    if startup:
        startup_previous=read_json(ROOT/'local/startup-movies-install.json')
        original='Mods/modLocalSkipStartupMovies/content/scripts/game/r4Game.ws'
        replacement='Mods/modLocalSkipStartupMovies/content/scripts/local/startup_movies.ws'
        if (startup['oldPath']!=original or startup['newPath']!=replacement or
                startup_previous['files']!={'content/scripts/game/r4Game.ws':startup['oldSHA256']} or
                digest(required_file(game/original))!=startup['oldSHA256'] or (game/replacement).exists()):
            raise ValueError('Startup helper no longer matches its managed original')
        from startup_movies import PATCH,validate_startup_queue
        validate_startup_queue((cfg['redkit']/'r4data/scripts/game/r4Game.ws').read_text(encoding='utf-8-sig'))
        if (required_file(Path(startup['source'])).read_text()!=PATCH or
                digest(Path(startup['source']))!=startup['sha256']):
            raise ValueError('Startup helper differs from the narrow authored replacement')
        verification=Path(startup['verification']).resolve()
        if not verification.is_relative_to((ROOT/'build').resolve()):
            raise ValueError('Startup helper needs an owned compiler receipt')
        startup_compiled=read_json(verification)
        if (startup_compiled['name']!='modLocalSkipStartupMovies' or
                startup_compiled['files']!={'content/scripts/local/startup_movies.ws':startup['sha256']} or
                startup_compiled['native']['exitCode']!=0 or
                startup_compiled['sourceSHA256']!=digest(cfg['redkit']/'r4data/scripts/game/r4Game.ws') or
                not any(Path(r['path']).resolve()==verification and r['sha256']==digest(verification)
                    for r in proof['evidenceFiles'])):
            raise ValueError('Startup helper compiler evidence differs')
    backup=ROOT/'local'/('native-backup-startup-'+time.strftime('%Y%m%d-%H%M%S'))
    backup.mkdir()
    for row in previous['files']:
        target=backup/row['path'];target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(game/row['path'],target)
        if digest(target)!=row['sha256']:raise RuntimeError('Rollback backup differs')
    write_json(backup/'receipt.json',previous)
    if startup:
        target=backup/startup['oldPath'];target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(game/startup['oldPath'],target)
        write_json(backup/'startup-movies-receipt.json',startup_previous)
    updated=json.loads(json.dumps(previous));changed=[]
    try:
        for rel,row in replacements.items():
            changed.append(rel);shutil.copy2(row['source'],game/rel)
            if digest(game/rel)!=row['sha256']:raise RuntimeError('Installed repair hash differs')
        if startup:
            target=game/startup['newPath'];target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(startup['source'],target)
            if digest(target)!=startup['sha256']:raise RuntimeError('Installed startup helper differs')
            (game/startup['oldPath']).unlink()
            startup_updated=dict(startup_compiled)
            startup_updated.update(files={'content/scripts/local/startup_movies.ws':startup['sha256']},
                backup=str(backup),change='Replace only the startup movie queue; retain the current stock CR4Game',
                gameplay='Private room and campaign startup verified',startupRepairProof=str(proof_path),
                installed=True,destination=str(game/'Mods/modLocalSkipStartupMovies'))
            write_receipt(ROOT/'local/startup-movies-install.json',startup_updated)
        for row in updated['files']:
            if row['path'] in replacements:row['sha256']=replacements[row['path']]['sha256']
        updated.update(backup=str(backup),gameExecutableSHA256=proof['gameSHA256'],
            startupRepairProof=str(proof_path),startupRepairProofSHA256=digest(proof_path),
            observedNormalStartup=False,attachmentRegression=proof['attachmentRegression'])
        write_receipt(ROOT/'local/native-installation.json',updated)
    except BaseException:
        for rel in reversed(changed):shutil.copy2(backup/rel,game/rel)
        if startup:
            shutil.copy2(backup/startup['oldPath'],game/startup['oldPath'])
            target=game/startup['newPath']
            if target.exists() and digest(target)==startup['sha256']:target.unlink()
            write_receipt(ROOT/'local/startup-movies-install.json',startup_previous)
        raise
    print(json.dumps(dict(installed=True,changedFiles=sorted(replacements),
                         baseCommit=previous['baseCommit'],startupHelperReplaced=bool(startup),rollback=str(backup))))
    return updated

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
    helper_source=helper_current=None;helper_old={};helper_restore={}
    if (backup/'startup-movies-receipt.json').exists():
        helper_source=read_json(backup/'startup-movies-receipt.json')
        helper_current=read_json(ROOT/'local/startup-movies-install.json')
        helper_old=startup_snapshot_files(helper_current,game)
        helper_restore=startup_snapshot_files(helper_source,backup)
        for rel in helper_restore:
            if (game/rel).exists() and rel not in helper_old:
                raise ValueError('Preserve unmanaged startup restore target: '+rel)
    rollback=ROOT/'local'/('native-restore-backup-'+time.strftime('%Y%m%d-%H%M%S'));rollback.mkdir()
    for rel in old:
        target=rollback/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(game/rel,target)
    write_json(rollback/'receipt.json',current);changed=[]
    if helper_source:
        for rel in helper_old:
            target=rollback/rel;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(game/rel,target)
        write_json(rollback/'startup-movies-receipt.json',helper_current)
    helper_changed=[]
    try:
        for rel,row in restore.items():
            target=game/rel;target.parent.mkdir(parents=True,exist_ok=True);changed.append(rel);shutil.copy2(backup/rel,target)
            if digest(target)!=row['sha256']:raise RuntimeError('Restored hash differs: '+rel)
        for rel in old.keys()-restore.keys():(game/rel).unlink();changed.append(rel)
        for rel,h in helper_restore.items():
            target=game/rel;target.parent.mkdir(parents=True,exist_ok=True)
            helper_changed.append(rel);shutil.copy2(backup/rel,target)
            if digest(target)!=h:raise RuntimeError('Restored startup hash differs')
        for rel in helper_old.keys()-helper_restore.keys():
            helper_changed.append(rel);(game/rel).unlink()
        if helper_source:
            helper_source.update(restoredFrom=str(backup),backup=str(rollback))
            write_receipt(ROOT/'local/startup-movies-install.json',helper_source)
        source['restoredFrom']=str(backup);source['backup']=str(rollback)
        write_receipt(ROOT/'local/native-installation.json',source)
    except BaseException:
        for rel in reversed(changed):
            if rel in old:shutil.copy2(rollback/rel,game/rel)
            elif (game/rel).exists():(game/rel).unlink()
        for rel in reversed(helper_changed):
            if rel in helper_old:shutil.copy2(rollback/rel,game/rel)
            elif (game/rel).exists():(game/rel).unlink()
        if helper_current:write_receipt(ROOT/'local/startup-movies-install.json',helper_current)
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
    verify_native_compatibility(game,release)
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
        if patch['project']!='modMaleModClinical':raise ValueError('Clinical native package differs')
        if patch['baseCommit']!=pin:
            from readopt_carrier_runtime import validate
            validate(clinical_dir,'clinical',pin)
        for row in patch['files']:files[row['path']]=package/row['path']
        for name in ['clinical.render','clinical.render.sha256']:files['bin/x64_dx12/malemod-native/'+name]=release/name
        files['bin/x64_dx12/malemod-native/splat_bakes.bin']=cfg['base']/'legacy/wolverine/src/runtime/splat_bakes.bin'
        files['Mods/modMaleModNative/content/scripts/local/malemod/clinical.ws']=ROOT/'probes/native/clinical.ws'
    if selection.get('garments'):
        garment_dir=ROOT/selection['garments'];garment=read_json(garment_dir/'manifest.json')
        if garment['baseCommit']!=pin or garment['renderSHA256']!=render['packetSHA256'] or digest(garment_dir/'garment.bindings')!=garment['packetSHA256']:
            raise ValueError('Garment binding differs from pinned native surface')
        package_manifest=read_json(ROOT/selection['garmentCarrier']/'package.json')
        from mod import verify_package
        package=ROOT/package_manifest['directory'];patch=verify_package(package)
        if patch['project']!='modMaleModGarments':raise ValueError('Garment native package differs')
        if patch['baseCommit']!=pin:
            from readopt_carrier_runtime import validate
            validate(ROOT/selection['garmentCarrier'],'garment',pin)
        for row in patch['files']:files[row['path']]=package/row['path']
        reaction=garment.get('physicalReactionBinding',{})
        if reaction.get('version')!=1 or reaction.get('generalizedBodies')!=14 or reaction.get('nativeVertices')!=garment.get('anatomySemantics',{}).get('fullAnatomyVertices'):
            raise ValueError('Complete physical garment reaction binding missing')
        for name in ['garment.bindings','garment.bindings.sha256','garment.reactions','garment.reactions.sha256','garment.render','garment.render.sha256']:files['bin/x64_dx12/malemod-native/'+name]=release/name
        for name,expected in [('garment.bindings',garment['packetSHA256']),('garment.reactions',reaction['packetSHA256']),('garment.render',package_manifest['packetSHA256'])]:
            if digest(required_file(release/name))!=expected or required_file(release/(name+'.sha256')).read_text().strip()!=expected:
                raise ValueError('Staged garment input hash differs: '+name)
        files['Mods/modMaleModNative/content/scripts/local/malemod/garment.ws']=ROOT/'probes/native/garment.ws'
    if selection.get('bodyPackage'):
        from mod import verify_package
        package=ROOT/selection['bodyPackage'];patch=verify_package(package)
        if patch['project']!='mod0000MaleModBodyBoundary':raise ValueError('Body priority package differs')
        if patch['baseCommit']!=pin:
            if not selection.get('bodyAdoption'):raise ValueError('Body patch differs from runtime pin and lacks verified adoption')
            from readopt_body_runtime import validate_adoption
            adoption=validate_adoption(ROOT/selection['bodyAdoption'],package,pin,cfg)
            if adoption['bodyJob']!=selection.get('bodyJob'):raise ValueError('Body adoption authoring job differs from selection')
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
    for name in ['runtime','render_bones']+(['clinical'] if selection.get('clinical') else [])+(['garment'] if selection.get('garments') else []):
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
