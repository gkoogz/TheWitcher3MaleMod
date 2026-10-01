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
    commands=manifest.get('nativeCommands',[])
    if any(r.get('command')=='preserve-native-compiled-entities' for r in commands):
        raise RuntimeError('SDK source-cache package blocked after loading CTD')
    if (manifest.get('deformationBridge') or {}).get('effectiveTemplates') and not any(
        r.get('command')=='stage-shipped-cooked-player-entities' for r in commands):
        raise RuntimeError('Effective player package requires verified shipped cooked caches')
    if not (manifest.get('motionBinding') or {}).get('cookedControllerBindingVerified'):
        raise RuntimeError('Package lacks verified cooked controller binding')
    if (manifest.get('deformationBridge') or {}).get('parentPoseSpace')=='attached' and not (manifest.get('motionBinding') or {}).get('cookedPlayerStackBindingVerified'):
        raise RuntimeError('Attached input in an ordinary helper stack resets the stock pose; held candidate must not be installed')
    if manifest.get('deformationBridge') and not ((manifest.get('motionBinding') or {}).get('poseGraph') or {}).get('cookedPoseConnectionsVerified'):
        raise RuntimeError('Deformation package lacks connected native pose/scale output verification')
    packed=read_json(ROOT/'local/motion-package-verification.json')
    if packed['package']!=directory.relative_to(ROOT).as_posix():raise RuntimeError('Run native unbundle verification for this exact package first')
    if (manifest.get('motionBinding') or {}).get('deformationOutput')=='player':
        native=(manifest['motionBinding'].get('playerRig') or {})
        round_trip=(packed.get('additionalMotionBinding') or {}).get('playerRig') or {}
        if (manifest.get('deformationBridge') or {}).get('executionPhase')!='player-stack' or not native.get('nativePlayerRigVerified') or native!=round_trip:
            raise RuntimeError('Player layer lacks matching native/packed private rig verification')
        if (manifest.get('deformationBridge') or {}).get('effectiveTemplates') and not native.get('nativeEffectivePlayerTemplatesVerified'):
            raise RuntimeError('Player repair lacks verified effective gameplay/UI template roots')
    if (manifest.get('deformationBridge') or {}).get('lateActivation') or manifest['version']=='0.4.8-late-graph-test':
        if not (packed.get('additionalMotionBinding') or {}).get('cookedLateGraphSlotsVerified'):
            raise RuntimeError('Delayed graph package lacks native second-slot verification')
    input_path=Path.home()/'Documents/The Witcher 3/input.settings'
    fixed = bool(manifest.get('fixedPhysics'))
    if not fixed:input_bindings.edit_bindings(input_path.read_bytes())
    previous=read_json(ROOT/'local/installation.json')
    rollback_path=ROOT/'local/motion-rollback.json'
    old_rollback=read_json(rollback_path) if rollback_path.exists() else None
    uninstall_package(cfg);backup=read_json(ROOT/'local/installation.json')['uninstalledTo']
    stable_previous,stable_backup=previous,backup
    if old_rollback and old_rollback['newPackage']==previous['package'] and not previous.get('observedLoadAndPose'):
        stable_previous,stable_backup=old_rollback['previous'],old_rollback['backup']
    write_json(rollback_path,{'previous':stable_previous,'backup':stable_backup,
        'replaced':previous,'replacedBackup':backup,'newPackage':packed['package']})
    try:
        install_package(cfg,directory)
        if fixed:
            bindings=input_bindings.uninstall() if (ROOT/'local/input-bindings.json').exists() else []
            print('Installed fixed-scale physics candidate; removed owned MaleMod hotkeys. Previous build:',backup)
            return bindings
        bindings=input_bindings.install(input_path)
        print('Installed motion test and hotkeys; previous build archived at:',backup)
        category='MaleMod - size controls' if manifest.get('sizeControls') else 'MaleMod - player pose test'
        print('F6 opens the native pause menu; select '+category+'. Escape returns to gameplay.')
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
    prior_manifest=read_json(ROOT/record['previous']['package']/'build-manifest.json')
    if prior_manifest.get('fixedPhysics'):
        if (ROOT/'local/input-bindings.json').exists():input_bindings.uninstall()
    else:input_bindings.install(Path.home()/'Documents/The Witcher 3/input.settings')
    print('Restored the previous verified build; preserved its required hotkeys.')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['install','revert'])
    parser.add_argument('--directory',type=Path);args=parser.parse_args()
    if args.command=='revert':revert()
    else:install(args.directory or ROOT/read_json(ROOT/'publish/latest.json')['directory'])
