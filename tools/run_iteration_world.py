"""Stage and launch an owned native sandbox in the existing private station.

No ordinary save is loaded. Closing removes only unchanged task-owned files.
The installed anatomy runtime is verified and kept byte-identical.
"""
import argparse
import json
from pathlib import Path
import shutil
from mod import ROOT, settings, digest, verify_package, write_json, read_json
from run_sealed_session import run
from close_sealed_session import close
from iteration_save_transaction import begin, restore
from prepare_iteration_world import validate_world_dimensions
from iteration_layer_ownership import inspect_layers
import time


def launch(package, *, driver_source=None, compile_proof=None):
    package = Path(package).resolve()
    if not package.is_relative_to((ROOT/'publish').resolve()):
        raise ValueError('Expected an owned published sandbox package')
    manifest = verify_package(package)
    if manifest['project'] != 'modMaleModIteration':
        raise ValueError('Only the dedicated sandbox mod may be staged')
    native=read_json(package.with_name(package.name+'.iteration-native-proof.json'))
    if native.get('schema') == 'malemod.iteration-transient-platform/1':
        if native.get('buildManifestSHA256') != digest(package/'build-manifest.json'):
            raise ValueError('Transient platform build proof changed')
        proof_path=Path(native['nativeLinksReceipt'])
        if not proof_path.resolve().is_relative_to((ROOT/'build/iteration-storage').resolve()) or digest(proof_path)!=native['nativeLinksReceiptSHA256']:
            raise ValueError('Transient platform native receipt changed')
        links=read_json(proof_path)
        if links.get('label')!='cooked' or not all(links.get(k) for k in ('templateClassVerified','staticMeshVerified','ownMeshHardReferenceVerified')):
            raise ValueError('Transient floor native reference readback failed')
        pack=next(c for c in manifest['nativeCommands'] if c['command']=='pack')
        intake=Path(next(a[5:] for a in pack['args'] if a.startswith('-dir=')))
        for row in links['resources']:
            if digest(intake/row['path'])!=row['sha256']:
                raise ValueError('Transient floor cooked resource changed')
    else:
        if native.get('schema')!='malemod.iteration-native-package/2' or native.get('buildManifestSHA256')!=digest(package/'build-manifest.json'):
            raise ValueError('Dedicated world needs exact native-reference package proof')
        for field in ('authoringReceipt','nativeLinksReceipt'):
            proof_path=Path(native[field]).resolve()
            if not proof_path.is_relative_to((ROOT/'build/iteration-storage').resolve()) or digest(proof_path)!=native[field+'SHA256']:
                raise ValueError('Native iteration receipt missing or stale')
        links=read_json(Path(native['nativeLinksReceipt']))
        if not links.get('nonNullWorldPlayerCameraQuestFloorEnvironment') or not links.get('nonNullTerrainClipMap') or links.get('label')!='cooked':
            raise ValueError('Cooked iteration resources failed reference readback')
        ownership=links.get('nativeLayerOwnership')
        if not ownership or not ownership.get('worldParentRootAndFloorLinksVerified'):
            raise ValueError('Cooked native world must certify root/group/floor ownership')
        # Recheck the exact cooked bytes behind the bound readback before staging.
        authoring=read_json(Path(native['authoringReceipt']))
        world_rows=[r for r in links['resources']
                    if r['path']=='levels/malemod_iteration/malemod_iteration.w2w']
        if len(world_rows)!=1:
            raise ValueError('Native world readback is missing or ambiguous')
        world=Path(authoring['package'])
        commands=manifest['nativeCommands']
        pack=next(c for c in commands if c['command']=='pack')
        intake=Path(next(a[5:] for a in pack['args'] if a.startswith('-dir=')))
        world=intake/world_rows[0]['path']
        if digest(world)!=world_rows[0]['sha256'] or inspect_layers(world.read_bytes(),
                'levels/malemod_iteration/floor.w2l')!=ownership:
            raise ValueError('Native cooked ownership/resource bytes changed')
        resolution=links.get('nativeResolutionDerivation',{})
        coarsest=resolution.get('coarsest',0)
        if coarsest<=0 or links.get('nativeMipSizes')!={'cookedMipStackHeight':coarsest**2*2,
            'cookedMipStackControl':coarsest**2*2,'cookedMipStackColor':(coarsest>>1)**2*2}:
            raise ValueError('Cooked terrain requires matching measured native mip dimensions')
        occlusion=links.get('nativeOcclusionDimensions',{})
        tiles=validate_world_dimensions(occlusion.get('worldDimensions',0))
        if occlusion.get('tileSize')!=256 or occlusion.get('tilesPerEdge')!=tiles:
            raise ValueError('Cooked world requires measured nonzero native occlusion tiles')
    game = settings()['game']; rows = []
    for item in manifest['files']:
        relative = Path(item['path'])
        if not relative.is_relative_to('Mods/modMaleModIteration'):
            raise ValueError('Sandbox package leaves its own mod')
        target = game/relative
        if target.exists(): raise ValueError('Preserve existing sandbox installation: '+str(target))
        rows.append(dict(path=str(target), source=str(package/relative), sha256=item['sha256']))
    save_transaction=begin(Path.home()/'Documents/The Witcher 3/gamesaves',
        ROOT/'build/iteration-storage'/('save-transaction-'+str(time.time_ns())))
    staged=[]
    try:
        for item in rows:
            target=Path(item['path']); target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(item['source'],target); staged.append(item)
            if digest(target)!=item['sha256']: raise RuntimeError('Staged sandbox file hash differs')
        receipt=run(driver_source=driver_source or ROOT/'probes/native/iteration_platform.ws',
            compile_proof=compile_proof or ROOT/'build/iteration-platform-script/compile.json',
            launcher_path=ROOT/'build/iteration-launch/launch_sealed.exe', game_arguments=('-windowed',))
        # run prints the exact private session receipt; record extra ownership.
        receipt['iterationWorldFiles']=rows; receipt['iterationWorldPackage']=str(package)
        receipt['iterationBootstrapMode']=links.get('bootstrapMode','minimal-lifetime')
        receipt['iterationSaveTransaction']=str(save_transaction)
        # Select by this exact process identity, not an unrelated newest game.
        matches=[p for p in (ROOT/'build/probe').glob('sealed-session-*/receipt.json')
            if read_json(p)['observations']==receipt['observations']]
        if len(matches)!=1: raise RuntimeError('Private receipt identity is ambiguous')
        write_json(matches[0],receipt); print(matches[0])
        return matches[0]
    except Exception:
        # Before a successful private launch only, restore our own staged files.
        if 'receipt' not in locals():
            for item in staged:
                path=Path(item['path'])
                if path.is_file() and digest(path)==item['sha256']: path.unlink()
        raise


def finish(receipt):
    path=Path(receipt).resolve(); data=read_json(path)
    root=settings()['game']/'Mods/modMaleModIteration'
    for item in data.get('iterationWorldFiles',[]):
        target=Path(item['path']).resolve()
        if not target.is_relative_to(root.resolve()) or digest(target)!=item['sha256']:
            raise ValueError('Preserve changed sandbox file')
    close(path)
    closed=read_json(path)
    if data.get('iterationSaveTransaction'):
        restored=restore(data['iterationSaveTransaction'],closed_private_session=closed.get('closed') and closed.get('audioRestored'))
        closed['iterationSaveOriginalsVerified']=restored['originalsVerified']
        write_json(path,closed)
    for item in data.get('iterationWorldFiles',[]): Path(item['path']).unlink()
    data=read_json(path); data['iterationWorldFilesRemoved']=True; write_json(path,data)
    print('Sandbox files removed; installed anatomy runtime preserved')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--package',type=Path); group.add_argument('--close',type=Path)
    parser.add_argument('--driver-source',type=Path)
    parser.add_argument('--compile-proof',type=Path)
    args=parser.parse_args()
    if bool(args.driver_source) != bool(args.compile_proof): parser.error('Driver and proof must be supplied together')
    if args.close and args.driver_source: parser.error('Close uses its original bound driver identity')
    if args.package: launch(args.package,driver_source=args.driver_source,compile_proof=args.compile_proof)
    else: finish(args.close)
