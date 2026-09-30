"""Deploy/revert the verified motion test with hotkeys and a static-build backup."""
import argparse,csv,io,shutil,subprocess
from mod import *
import input_bindings

def game_closed():
    result=subprocess.run(['tasklist','/FI','IMAGENAME eq witcher3.exe','/FO','CSV','/NH'],capture_output=True,text=True,check=True)
    if any(row and row[0].lower()=='witcher3.exe' for row in csv.reader(io.StringIO(result.stdout))):
        raise RuntimeError('Close Witcher 3 before changing its installed mod or input settings')

def restore_previous(cfg,previous,backup):
    target=Path(previous['target']).resolve();expected=inside(cfg['game']/'Mods',previous['project'])
    if target!=expected or target.exists():raise RuntimeError('Previous mod restoration target is not vacant')
    backup=Path(backup).resolve()
    if not backup.is_relative_to(ROOT/'local/uninstalled'):raise ValueError('Rollback source must be a managed archive')
    reject_reparse_tree(backup)
    for item in previous['files']:
        if digest(required_file(inside(backup,item['path'])))!=item['sha256']:raise RuntimeError('Rollback files changed')
    shutil.copytree(backup,target);write_json(ROOT/'local/installation.json',previous)

def install(directory):
    cfg=settings();game_closed();directory=Path(directory).resolve();manifest=verify_package(directory)
    if not (manifest.get('motionBinding') or {}).get('cookedControllerBindingVerified'):
        raise RuntimeError('Package lacks verified cooked controller binding')
    packed=read_json(ROOT/'local/motion-package-verification.json')
    if packed['package']!=directory.relative_to(ROOT).as_posix():raise RuntimeError('Run native unbundle verification for this exact package first')
    input_path=Path.home()/'Documents/The Witcher 3/input.settings'
    input_bindings.edit_bindings(input_path.read_bytes())
    previous=read_json(ROOT/'local/installation.json')
    rollback_path=ROOT/'local/motion-rollback.json'
    old_rollback=read_json(rollback_path) if rollback_path.exists() else None
    uninstall_package(cfg);backup=read_json(ROOT/'local/installation.json')['uninstalledTo']
    stable_previous,stable_backup=previous,backup
    if old_rollback and old_rollback['newPackage']==previous['package']:
        stable_previous,stable_backup=old_rollback['previous'],old_rollback['backup']
    write_json(rollback_path,{'previous':stable_previous,'backup':stable_backup,
        'replaced':previous,'replacedBackup':backup,'newPackage':packed['package']})
    try:
        install_package(cfg,directory);bindings=input_bindings.install(input_path)
        print('Installed motion test and hotkeys; previous build archived at:',backup)
        print('F6 opens the native pause menu; select MaleMod - motion controls. Escape returns to gameplay.')
        return bindings
    except Exception:
        current=read_json(ROOT/'local/installation.json')
        if current.get('package')==packed['package'] and Path(current['target']).exists():uninstall_package(cfg)
        restore_previous(cfg,previous,backup)
        if old_rollback:write_json(rollback_path,old_rollback)
        raise

def revert():
    cfg=settings();game_closed();record=read_json(ROOT/'local/motion-rollback.json')
    current=read_json(ROOT/'local/installation.json')
    if current['package']!=record['newPackage']:raise RuntimeError('Installed package is no longer this motion test')
    uninstall_package(cfg);restore_previous(cfg,record['previous'],record['backup'])
    input_bindings.uninstall();print('Restored the previous static build; removed only MaleMod hotkeys.')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['install','revert'])
    parser.add_argument('--directory',type=Path);args=parser.parse_args()
    if args.command=='revert':revert()
    else:install(args.directory or ROOT/read_json(ROOT/'publish/latest.json')['directory'])
