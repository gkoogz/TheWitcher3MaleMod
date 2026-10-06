"""Manual desktop entry to the verified transient Witcher test platform.

Run through its shortcut. Temporary assets and bootstrap are removed after the
owned game process exits; normal game input and audio remain active.
"""
import argparse
import ctypes
import os
from pathlib import Path
import shutil
import subprocess
import time
from mod import ROOT, digest, read_json, settings, verify_package, write_json
from iteration_save_transaction import begin, restore


def play(package, acceptance, *, check_only=False, preview=False):
    package = Path(package).resolve()
    acceptance = Path(acceptance).resolve()
    if not package.is_relative_to((ROOT/'publish').resolve()) or not acceptance.is_relative_to((ROOT/'build').resolve()):
        raise ValueError('Expected owned sandbox package and gameplay acceptance')
    manifest = verify_package(package)
    accepted = read_json(acceptance)
    source = ROOT/'probes/native/iteration_platform_human.ws'
    proof = read_json(ROOT/'build/iteration-human-script/compile.json')
    if manifest['project'] != 'modMaleModIteration' or accepted.get('schema') != 'malemod.iteration-platform-acceptance/1':
        raise ValueError('This launcher only accepts the tested platform')
    if accepted.get('packageManifestSHA256') != digest(package/'build-manifest.json') or accepted.get('driverSHA256') != digest(ROOT/'probes/native/iteration_platform.ws'):
        raise ValueError('Platform changed since its gameplay test')
    if not all(accepted.get(k) for k in ('groundedPlayer','movementObserved','nativeModObserved','f6IntegrationUnchanged')):
        raise ValueError('Platform gameplay verification remains incomplete')
    if not accepted.get('visualReviewPassed'):
        if not (preview and accepted.get('visualReviewPerformed') and accepted.get('knownIssues')==['native-motion-floor-artifact']):
            raise ValueError('Final visual acceptance remains incomplete; this reviewed preview requires --preview')
    if proof['exitCode'] or proof.get('manualPlatformSourceSHA256') != accepted['driverSHA256'] or proof['ownedSourceHashes'].get('local/malemod/'+source.name) != digest(source):
        raise ValueError('Manual bootstrap needs a fresh official compile')
    if proof.get('automaticWalk') is not False or proof.get('automaticNativeCheckpoints') is not False:
        raise ValueError('Manual play must use ordinary controls')
    game = settings()['game']
    installed = read_json(ROOT/'local/native-installation.json')
    fallback = read_json(ROOT/'local/installation.json')
    if installed['game'] != str(game):
        raise ValueError('Installed game path changed')
    if accepted.get('installationReceiptSHA256') != digest(ROOT/'local/native-installation.json'):
        raise ValueError('Installed runtime differs from the platform gameplay test')
    if accepted.get('fallbackReceiptSHA256') != digest(ROOT/'local/installation.json'):
        raise ValueError('Installed rig fallback differs from the platform gameplay test')
    image = Path(accepted['renderedFrame']).resolve()
    if not image.is_relative_to((ROOT/'build').resolve()) or digest(image) != accepted['renderedFrameSHA256']:
        raise ValueError('Accepted native frame is missing or changed')
    for row in installed['files']:
        if digest(game/row['path']) != row['sha256']:
            raise ValueError('Installed mod changed: '+row['path'])
    fallback_root=Path(fallback['target']).resolve()
    if fallback_root != (game/'Mods/modMaleMod').resolve():
        raise ValueError('Fallback installation path changed')
    for row in fallback['files']:
        if digest(fallback_root/row['path']) != row['sha256']:
            raise ValueError('Installed rig fallback changed: '+row['path'])
    existing = subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',
        'Get-Process witcher3 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id'],
        capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    if existing.stdout.strip():
        raise ValueError('Close Witcher before opening its sandbox')
    addon = game/'Mods/modMaleModContinueTest/content/scripts/local/malemod/autocontinue.ws'
    if addon.exists():
        raise ValueError('Another sandbox bootstrap is present; preserve it')
    rows = []
    for item in manifest['files']:
        target = (game/item['path']).resolve()
        if not target.is_relative_to((game/'Mods/modMaleModIteration').resolve()) or target.exists():
            raise ValueError('Existing or invalid sandbox target: '+str(target))
        rows.append(dict(path=str(target),source=str(package/item['path']),sha256=item['sha256']))
    if check_only:
        print('PASS '+('playable preview' if preview else 'manual launch')+' preflight: package, native compile, observed movement, reviewed frame and all 40 installed files')
        return
    job = ROOT/'build/iteration-storage'/('human-platform-'+str(time.time_ns()))
    transaction = begin(Path.home()/'Documents/The Witcher 3/gamesaves',job)
    staged = []
    child = None
    result = dict(package=str(package),acceptanceSHA256=digest(acceptance),
                  physicalInputAutomation=False,privateEnvironment=False,audioChanged=False,
                  playablePreview=preview,knownIssues=accepted.get('knownIssues',[]))
    try:
        for row in rows:
            target = Path(row['path']);target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(row['source'],target)
            if digest(target) != row['sha256']:
                raise ValueError('Staged sandbox bytes differ')
            staged.append(row)
        addon.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,addon)
        staged.append(dict(path=str(addon),sha256=digest(source)))
        env = dict(os.environ)
        env.pop('MALEMOD_SEALED_SESSION',None)
        env.update(SteamAppId='292030',SteamGameId='292030')
        executable = game/'bin/x64_dx12/witcher3.exe'
        child = subprocess.Popen([str(executable)],cwd=executable.parent,env=env)
        result['processID'] = child.pid
        write_json(job/'manual-session.json',result)
        result['exitCode'] = child.wait()
    finally:
        if child is not None and child.poll() is None:
            raise RuntimeError('Preserve sandbox files while its game remains open')
        for row in staged:
            if not Path(row['path']).is_file() or digest(Path(row['path'])) != row['sha256']:
                raise RuntimeError('Preserve changed sandbox file: '+row['path'])
        restored = restore(transaction,closed_private_session=True)
        for row in staged:
            Path(row['path']).unlink()
        for row in installed['files']:
            if digest(game/row['path']) != row['sha256']:
                raise RuntimeError('Installed mod changed during manual play')
        for row in fallback['files']:
            if digest(fallback_root/row['path']) != row['sha256']:
                raise RuntimeError('Installed rig fallback changed during manual play')
        result.update(cleanupComplete=True,originalSavesVerified=restored['originalsVerified'])
        write_json(job/'manual-session.json',result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--acceptance',type=Path,required=True)
    parser.add_argument('--check',action='store_true',help='Verify all launch inputs without changing files or launching')
    parser.add_argument('--preview',action='store_true',help='Allow only the reviewed playable room with its recorded native floor artifact')
    args = parser.parse_args()
    try:
        play(args.package,args.acceptance,check_only=args.check,preview=args.preview)
    except Exception as error:
        if not args.check:
            ctypes.windll.user32.MessageBoxW(None,str(error),'Witcher Grey Sandbox',0x10)
        raise
