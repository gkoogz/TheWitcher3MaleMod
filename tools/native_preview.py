"""Private native runtime copies; never replace the managed game installation."""
import argparse
import json
import os
import re
from pathlib import Path
import shutil
import stat
import subprocess
import time
from mod import ROOT, settings, digest, read_json, write_json, relative_resource


def preview_owners():
    owners = [(ROOT/'build/native-preview').resolve()]
    config = ROOT/'local/preview-storage.json'
    if config.is_file():
        data = read_json(config)
        external = Path(data['root'])
        if data.get('repository') != str(ROOT.resolve()) or not external.is_absolute() or external.resolve() != external:
            raise ValueError('Preview storage must be an explicit nonredirected repository-owned directory')
        owners.append(external)
    return owners


def load_preview(path, expected_hash=None, verify_files=True):
    path = Path(path).resolve()
    owner = next((p for p in preview_owners() if path.is_relative_to(p)), None)
    if owner is None or not re.fullmatch(r'preview(?:-[0-9]+)?\.json', path.name):
        raise ValueError('Expected repository-owned preview manifest')
    if expected_hash and digest(path) != expected_hash:
        raise ValueError('Preview manifest changed')
    data = read_json(path)
    game = path.parent/'game'
    if data.get('schema') != 'malemod.native-preview/1' or Path(data['game']) != game:
        raise ValueError('Preview game identity differs')
    if game.resolve() != game or not game.is_relative_to(owner):
        raise ValueError('Preview root may not redirect outside its owner')
    stock = settings()['game']
    if Path(data['sourceGame']) != stock or (game/'content').resolve() != (stock/'content').resolve():
        raise ValueError('Preview licensed content identity differs')
    if verify_files:
        installed = read_json(ROOT/'local/native-installation.json')
        if digest(ROOT/'local/native-installation.json') != data['installationReceiptSHA256']:
            raise ValueError('Managed installation receipt changed')
        for item in installed['files']:
            if digest(stock/relative_resource(item['path'])) != item['sha256']:
                raise ValueError('Managed runtime changed: '+item['path'])
        for item in data['files']:
            target = game/relative_resource(item['path'])
            if not target.resolve().is_relative_to(game) or digest(target) != item['sha256']:
                raise ValueError('Preview file changed: '+item['path'])
        executable = 'bin/x64_dx12/witcher3.exe'
        if digest(game/executable) != digest(stock/executable):
            raise ValueError('Preview executable differs from licensed game')
    return game, data


def session_game(receipt):
    if 'nativePreview' not in receipt:
        return settings()['game']
    return load_preview(receipt['nativePreview'], receipt['nativePreviewSHA256'], False)[0]


def _rebased_manifest_data(data, manifest, manifest_hash, receipt, installation_hash):
    return dict(data, installationReceiptSHA256=installation_hash, candidateAccepted=False,
                previousManifest=str(manifest), previousManifestSHA256=manifest_hash,
                previousClosedSession=str(receipt), previousClosedSessionSHA256=digest(receipt),
                rebaseReason='Closed candidate matches every currently managed installed file')


def _closed_refresh_binding(manifest, receipt, session):
    """Accept the original room receipt once for an unchanged rebased manifest."""
    bound = Path(session.get('nativePreview', '')).resolve()
    if bound == manifest:
        return True
    _, data = load_preview(manifest, verify_files=False)
    origin = Path(data.get('previousManifest', '')).resolve()
    if (bound != origin or data.get('previousClosedSession') != str(receipt)
            or data.get('previousClosedSessionSHA256') != digest(receipt)
            or data.get('previousManifestSHA256') != session.get('nativePreviewSHA256')):
        return False
    _, original = load_preview(origin, session.get('nativePreviewSHA256'), verify_files=False)
    expected = _rebased_manifest_data(original, origin, session['nativePreviewSHA256'],
                                      receipt, digest(ROOT/'local/native-installation.json'))
    # Exact reconstructed equality forbids reusing this inherited receipt after
    # any candidate refresh or manifest edit. Historical files remain immutable.
    return data == expected


def rebase_installed_preview(manifest, receipt):
    """Reuse a closed, now-installed preview via a new immutable-history manifest.

    This only advances the installation baseline when every managed installed
    file is already identical to the private candidate. It copies no game data
    and never changes the original manifest, its proofs, or either game tree.
    """
    manifest, receipt = Path(manifest).resolve(), Path(receipt).resolve()
    session = read_json(receipt)
    original_hash = digest(manifest)
    if (not session.get('closed')
            or not (session.get('audioRestored') or session.get('audioSessionsGone'))
            or not session.get('iterationWorldFilesRemoved')
            or Path(session.get('nativePreview', '')).resolve() != manifest
            or session.get('nativePreviewSHA256') != original_hash):
        raise ValueError('Preview rebase needs its exact verified closed room receipt')
    running = subprocess.check_output(
        ['tasklist', '/FI', 'IMAGENAME eq witcher3.exe', '/FO', 'CSV', '/NH'],
        creationflags=subprocess.CREATE_NO_WINDOW, text=True)
    if 'witcher3.exe' in running.lower():
        raise ValueError('Close the game before rebasing the private preview')
    # Retain ownership, manifest/game, source-game and licensed-content checks.
    # The historical receipt hash is expected to differ after installation.
    game, data = load_preview(manifest, original_hash, verify_files=False)
    stock = settings()['game']
    if game == stock.resolve():
        raise ValueError('Preview must remain separate from the installed game')
    installation = ROOT/'local/native-installation.json'
    installed_hash = digest(installation)
    installed = read_json(installation)
    if Path(installed['game']) != stock:
        raise ValueError('Managed game path differs')
    preview_rows = {}
    for item in data['files']:
        relative = relative_resource(item['path'])
        key = relative.as_posix().casefold()
        if key in preview_rows:
            raise ValueError('Duplicate preview file: '+item['path'])
        target = game/relative
        if (target.resolve() != target or not target.is_file()
                or target.is_symlink() or target.stat().st_nlink != 1):
            raise ValueError('Preview file is not an owned regular copy: '+item['path'])
        if digest(target) != item['sha256']:
            raise ValueError('Preview file changed: '+item['path'])
        preview_rows[key] = item['sha256']
    managed = set()
    for item in installed['files']:
        relative = relative_resource(item['path'])
        key = relative.as_posix().casefold()
        if key in managed:
            raise ValueError('Duplicate managed file: '+item['path'])
        managed.add(key)
        if preview_rows.get(key) != item['sha256']:
            raise ValueError('Installed runtime differs from preview: '+item['path'])
        if digest(stock/relative) != item['sha256']:
            raise ValueError('Managed runtime changed: '+item['path'])
    if not managed:
        raise ValueError('Cannot rebase an empty managed installation')
    executable = 'bin/x64_dx12/witcher3.exe'
    if executable not in preview_rows or digest(game/executable) != digest(stock/executable):
        raise ValueError('Preview executable differs from licensed game')
    if digest(manifest) != original_hash or digest(installation) != installed_hash:
        raise ValueError('Preview or installation identity changed during rebase')
    data = _rebased_manifest_data(data, manifest, original_hash, receipt, installed_hash)
    result = manifest.parent/('preview-'+str(time.time_ns())+'.json')
    # Exclusive creation also prevents a clock collision from replacing history.
    with result.open('x', encoding='utf-8', newline='\n') as handle:
        handle.write(json.dumps(data, indent=2)+'\n')
    load_preview(result)
    return result


def refresh_closed(manifest, receipt, dll, worker=None, material_package=None):
    """Refresh binaries and an existing bounded material package in place."""
    manifest, receipt = Path(manifest).resolve(), Path(receipt).resolve()
    session = read_json(receipt)
    if (not session.get('closed') or not (session.get('audioRestored') or session.get('audioSessionsGone'))
            or not session.get('iterationWorldFilesRemoved')
            or not _closed_refresh_binding(manifest, receipt, session)):
        raise ValueError('Preview refresh needs its verified closed room receipt')
    running = subprocess.check_output(
        ['tasklist', '/FI', 'IMAGENAME eq witcher3.exe', '/FO', 'CSV', '/NH'],
        creationflags=subprocess.CREATE_NO_WINDOW, text=True)
    if 'witcher3.exe' in running.lower():
        raise ValueError('Close the game before refreshing the private preview')
    game, data = load_preview(manifest)
    original_manifest = manifest.read_bytes()
    prefix = 'bin/x64_dx12/malemod-native/'
    replacements = {prefix+'malemod_witcher.dll': Path(dll).read_bytes()}
    material_descriptor = None
    if material_package is not None:
        from modular_material_package import describe, identities
        material_descriptor = describe(material_package)
        if set(identities(material_descriptor)) != set(identities(data.get('materialPackage'))):
            raise ValueError('In-place material refresh requires the same owned package paths')
        for relative in identities(material_descriptor):
            replacements[relative] = (Path(material_package)/relative).read_bytes()
    if worker:
        replacements[prefix+'surface_worker.exe'] = Path(worker).read_bytes()
        profile = game/(prefix+'malemod-runtime.profile')
        raw = profile.read_bytes()
        if raw[:8] != b'MMRUN001' or raw[48:112] != digest(game/(prefix+'surface_worker.exe')).encode('ascii'):
            raise ValueError('Existing private worker binding differs')
        replacements[prefix+'malemod-runtime.profile'] = raw[:48]+digest(Path(worker)).encode('ascii')+raw[112:]
    original = {}
    try:
        for relative, payload in replacements.items():
            target = game/relative
            if target.resolve() != target or target.is_symlink() or target.stat().st_nlink != 1:
                raise ValueError('Preview binary is not an owned regular copy')
            original[relative] = target.read_bytes()
            target.write_bytes(payload)
            row = next(item for item in data['files'] if item['path'] == relative)
            row.update(sha256=digest(target), derived='Closed private runtime refresh')
            if relative.endswith('malemod_witcher.dll'):
                row['source'] = str(Path(dll).resolve())
            elif relative.endswith('surface_worker.exe'):
                row['source'] = str(Path(worker).resolve())
            elif relative.endswith('malemod-runtime.profile'):
                row['workerSHA256'] = digest(Path(worker))
            else:
                row['source'] = str((Path(material_package)/relative).resolve())
        if material_descriptor is not None:
            data['materialPackage'] = material_descriptor
        data['candidateAccepted'] = False
        data['previousClosedSession'] = str(receipt)
        write_json(manifest, data)
        load_preview(manifest)
    except Exception:
        for relative, payload in original.items():
            (game/relative).write_bytes(payload)
        manifest.write_bytes(original_manifest)
        raise
    return manifest


def prepare(dll=None, worker=None, sewn_corrective=None, recruitment=None, modular_geometry=None, modular_native=None, modular_dynamic=None, modular_materials=None, modular_transfer=None, material_package=None):
    stock = settings()['game']
    installed = read_json(ROOT/'local/native-installation.json')
    if Path(installed['game']) != stock:
        raise ValueError('Managed game path differs')
    for item in installed['files']:
        if digest(stock/relative_resource(item['path'])) != item['sha256']:
            raise ValueError('Managed installation changed: '+item['path'])
    replacements = {}
    additions = {}
    from modular_material_package import describe, identities
    material_descriptor = installed.get('materialPackage')
    if material_package is not None:
        material_descriptor = describe(material_package)
        for relative in identities(material_descriptor):
            additions[relative] = Path(material_package).resolve()/relative
    else:
        managed_hashes = {r['path']: r['sha256'] for r in installed['files']}
        for relative, expected in identities(material_descriptor).items():
            if managed_hashes.get(relative) != expected:
                raise ValueError('Installed material package identity differs')
    if bool(modular_geometry) != bool(modular_native):
        raise ValueError('Modular geometry and observed native bindings must be staged together')
    if bool(modular_dynamic)!=bool(modular_materials) or (modular_dynamic and not modular_geometry):
        raise ValueError('Dynamic mount and material donors require the complete modular geometry pair')
    if modular_geometry is not None:
        for name,source,magic in [('geralt.modular',modular_geometry,b'MMMOD002'),('geralt.modular-native',modular_native,b'MMMODW01')]:
            source=Path(source).resolve()
            if not source.is_file() or source.read_bytes()[:8]!=magic:raise ValueError('Modular artifact version differs: '+name)
            additions['bin/x64_dx12/malemod-native/'+name]=source
        native_data=Path(modular_native).read_bytes()
        if native_data[8:72].decode('ascii')!=digest(Path(modular_geometry)) or native_data[72:136].decode('ascii')!=digest(stock/'bin/x64_dx12/malemod-native/geralt.render'):
            raise ValueError('Modular bindings differ from geometry or installed carrier')
    if modular_dynamic is not None:
        for name,source,magic in [('geralt.modular-dynamic',modular_dynamic,b'MMMDYN01'),('geralt.modular-materials',modular_materials,b'MMMAT001')]:
            source=Path(source).resolve()
            versions=(b'MMMDYN01',b'MMMDYN02') if name=='geralt.modular-dynamic' else (magic,)
            if not source.is_file() or source.read_bytes()[:8] not in versions:raise ValueError('Dynamic artifact version differs: '+name)
            additions['bin/x64_dx12/malemod-native/'+name]=source
        data=Path(modular_materials).read_bytes()
        if data[8:200]!=(digest(Path(modular_geometry))+digest(Path(modular_dynamic))+digest(Path(modular_native))).encode():raise ValueError('Dynamic material dependency hashes differ')
    if modular_transfer is not None:
        source=Path(modular_transfer).resolve();data=source.read_bytes()
        if not modular_geometry or data[:8]!=b'MMXFER02' or data[8:72]!=digest(Path(modular_geometry)).encode():raise ValueError('Modular transfer geometry identity differs')
        additions['bin/x64_dx12/malemod-native/geralt.modular-transfer']=source
    if recruitment is not None:
        source = Path(recruitment).resolve()
        if not source.is_file() or source.read_bytes()[:8] not in (b'MMPREC02',b'MMPREC03'):
            raise ValueError('Expected a versioned material-region artifact')
        additions['bin/x64_dx12/malemod-native/geralt.recruitment'] = source
    if sewn_corrective is not None:
        source = Path(sewn_corrective).resolve()
        if not source.is_file() or source.read_bytes()[:8] != b'MMSEWN02':
            raise ValueError('Expected a versioned sewn corrective artifact')
        additions['bin/x64_dx12/malemod-native/geralt.sewn-corrective'] = source
    for name, source in [('malemod_witcher.dll', dll), ('surface_worker.exe', worker)]:
        if source is not None:
            source = Path(source).resolve()
            if not source.is_file():
                raise ValueError('Missing preview runtime: '+str(source))
            replacements['bin/x64_dx12/malemod-native/'+name] = source
    job = preview_owners()[-1]/('preview-'+str(time.time_ns()))
    game = job/'game'
    game.mkdir(parents=True)
    if modular_transfer is not None:
        sidecar=job/'geralt.modular-transfer.sha256';sidecar.write_text(digest(Path(modular_transfer))+'\n');additions['bin/x64_dx12/malemod-native/geralt.modular-transfer.sha256']=sidecar
    if modular_geometry is not None:
        for name,source in [('geralt.modular',modular_geometry),('geralt.modular-native',modular_native)]:
            sidecar=job/(name+'.sha256');sidecar.write_text(digest(Path(source))+'\n')
            additions['bin/x64_dx12/malemod-native/'+name+'.sha256']=sidecar
    if modular_dynamic is not None:
        for name,source in [('geralt.modular-dynamic',modular_dynamic),('geralt.modular-materials',modular_materials)]:
            sidecar=job/(name+'.sha256');sidecar.write_text(digest(Path(source))+'\n');additions['bin/x64_dx12/malemod-native/'+name+'.sha256']=sidecar
    # Every writable file is a real copy. Only the licensed content depot is
    # shared; never recursively remove or modify that junction's contents.
    sources = []
    for folder in ['bin/config', 'bin/initialdata', 'bin/ddi', 'bin/x64_dx12', 'dlc-tombstones', 'Mods']:
        directory = stock/folder
        if not directory.exists():
            continue
        for root, dirs, files in os.walk(directory):
            if Path(root) == stock/'bin/x64_dx12':
                dirs[:] = [x for x in dirs if x != 'malemod-native']
            for name in dirs+files:
                p = Path(root)/name
                if p.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                    raise ValueError('Unexpected redirect in copied game input: '+str(p))
            for name in files:
                if name.lower().endswith(('.log', '.dmp')):
                    continue
                sources.append(Path(root)/name)
    sources.extend(p for p in stock.iterdir() if p.is_file() and
                   (p.suffix.lower() == '.dll' or p.name == 'launcher-configuration.json'))
    # The engine bootstrap reads gameconf.cfg and redscripts.ini above its
    # executable directory, before any gameplay or diagnostic script can run.
    sources.extend(p for p in (stock/'bin').iterdir() if p.is_file())
    for item in installed['files']:
        sources.append(stock/relative_resource(item['path']))
    # Preferences are copied, never shared with the accepted runtime.
    native = stock/'bin/x64_dx12/malemod-native'
    for name in ['malemod-controls.bin', 'malemod-preferences.ini']:
        if (native/name).is_file():
            sources.append(native/name)
    # Validated coupled artifacts may replace their managed counterparts in
    # this private copy. The accepted installation and its hashes stay intact.
    managed = {item['path'].replace('\\', '/') for item in installed['files']}
    for relative in list(additions):
        if relative in managed:
            replacements[relative] = additions.pop(relative)
    rows = []
    for source in sorted(set(sources)):
        relative = source.relative_to(stock).as_posix()
        actual = replacements.get(relative, source)
        target = game/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(actual, target)
        original_hash = digest(actual)
        if digest(target) != original_hash:
            raise RuntimeError('Preview copy differs: '+relative)
        rows.append(dict(path=relative, sha256=original_hash, source=str(actual)))
    for relative, source in additions.items():
        if any(row['path'] == relative for row in rows):
            raise ValueError('Preview addition would replace a managed file: '+relative)
        target = game/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if digest(target) != digest(source):
            raise RuntimeError('Preview addition differs: '+relative)
        rows.append(dict(path=relative, sha256=digest(target), source=str(source)))
    # Literal paths are passed as arguments, not interpolated shell commands.
    script = 'New-Item -ItemType Junction -Path $args[0] -Target $args[1] | Out-Null'
    command = job/'link-content.ps1'
    command.write_text(script, encoding='utf-8')
    subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                    '-File', str(command), str(game/'content'), str(stock/'content')], check=True,
                   creationflags=subprocess.CREATE_NO_WINDOW)
    manifest = job/'preview.json'
    # A replaced worker needs a profile bound to that exact private binary.
    # Preserve revision, bindings, calibration and contacts; never weaken the
    # runtime's identity check or modify the installed profile.
    worker_path = 'bin/x64_dx12/malemod-native/surface_worker.exe'
    if worker_path in replacements:
        profile_path = 'bin/x64_dx12/malemod-native/malemod-runtime.profile'
        target = game/profile_path
        raw = target.read_bytes()
        original_worker_hash = digest(stock/worker_path)
        if (raw[:8] != b'MMRUN001' or len(raw) < 180
                or raw[48:112] != original_worker_hash.encode('ascii')):
            raise ValueError('Preview profile is not bound to the managed source worker')
        candidate_hash = digest(game/worker_path)
        target.write_bytes(raw[:48]+candidate_hash.encode('ascii')+raw[112:])
        row = next(item for item in rows if item['path'] == profile_path)
        row.update(sha256=digest(target), sourceSHA256=row['sha256'],
                   derived='Private worker hash binding only', workerSHA256=candidate_hash)
    write_json(manifest, dict(schema='malemod.native-preview/1', game=str(game), sourceGame=str(stock),
        installationReceiptSHA256=digest(ROOT/'local/native-installation.json'), files=rows,
        contentAccess='Licensed content junction; never delete recursively through it',
        candidateAccepted=False, materialPackage=material_descriptor))
    load_preview(manifest)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dll', type=Path)
    parser.add_argument('--worker', type=Path)
    parser.add_argument('--sewn-corrective', type=Path)
    parser.add_argument('--recruitment', type=Path)
    parser.add_argument('--modular-geometry', type=Path)
    parser.add_argument('--modular-native', type=Path)
    parser.add_argument('--modular-dynamic', type=Path)
    parser.add_argument('--modular-materials', type=Path)
    parser.add_argument('--modular-transfer', type=Path)
    parser.add_argument('--material-package', type=Path)
    args = parser.parse_args()
    print(prepare(args.dll, args.worker, args.sewn_corrective, args.recruitment,args.modular_geometry,args.modular_native,args.modular_dynamic,args.modular_materials,args.modular_transfer,args.material_package))
