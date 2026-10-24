"""Install a hash-bound modular candidate only after its recorded native gate."""
import json
import shutil
import stat
import subprocess
import time
from pathlib import Path
from mod import ROOT, digest, read_json, required_file
from native_preview import load_preview
from modular_material_package import identities as material_identities
from install_native_runtime import write_receipt, verify_native_compatibility

PREFIX = 'bin/x64_dx12/malemod-native/'
ARTIFACTS = {
    'geralt.modular': b'MMMOD002',
    'geralt.modular-native': b'MMMODW01',
    'geralt.modular-dynamic': b'MMMDYN01',
    'geralt.modular-materials': b'MMMAT001',
    'geralt.modular-transfer': b'MMXFER02',
}


def coupled_identity(preview):
    names = ['malemod_witcher.dll', 'surface_worker.exe', 'geralt.render',
             'geralt.bindings', 'malemod-runtime.profile'] + list(ARTIFACTS)
    names += [name+'.sha256' for name in ARTIFACTS]
    files = {row['path']: row['sha256'] for row in preview['files']}
    result = {PREFIX+name: files[PREFIX+name] for name in names}
    for path, expected in material_identities(preview.get('materialPackage')).items():
        if files.get(path) != expected:
            raise ValueError('Material package differs from coupled preview')
        result[path] = expected
    return result


def validate_gate(proof_path, preview_path):
    proof = read_json(proof_path)
    if proof.get('schema') != 'malemod.modular-native-acceptance/1':
        raise ValueError('Expected modular attachment acceptance proof')
    if proof.get('previewSHA256') != digest(preview_path):
        raise ValueError('Acceptance describes a different preview')
    _, candidate = load_preview(preview_path, verify_files=False)
    bundle = coupled_identity(candidate)
    if proof.get('nativeDLLSHA256') != bundle[PREFIX+'malemod_witcher.dll']:
        raise ValueError('Acceptance DLL differs from its coupled preview')
    required = ['originalPelvis', 'collarTopology', 'nativeAppearance',
                'independentMotion', 'shapeControls', 'supportedLODs', 'campaign']
    if any(proof.get('gate', {}).get(k) is not True for k in required):
        raise ValueError('The complete modular attachment gate has not passed')
    if not proof.get('sharedSourceRevision') or not proof.get('sourceManifestSHA256') or not proof.get('sourceManifest'):
        raise ValueError('Missing pinned shared source provenance')
    source_path = required_file(Path(proof['sourceManifest']))
    if digest(source_path) != proof['sourceManifestSHA256']:
        raise ValueError('Build source manifest changed')
    source = read_json(source_path)
    if (source.get('schema') != 'malemod.modular-build-source/1'
            or source.get('sharedSourceRevision') != proof['sharedSourceRevision']
            or source.get('coupledArtifacts') != bundle):
        raise ValueError('Build source manifest describes different runtime artifacts')
    adoption = proof.get('workerAdoption')
    if adoption:
        from ordered_worker_adoption import validate
        path = required_file(Path(adoption['path']))
        if digest(path) != adoption['sha256']:
            raise ValueError('Worker adoption proof changed')
        game, _ = load_preview(preview_path, verify_files=False)
        validated = validate(path, game/PREFIX/'surface_worker.exe')
        if validated['revision'] != source.get('numericalWorkerRevision'):
            raise ValueError('Worker and native build pins differ')
    if not proof.get('evidence') or not proof.get('sessions'):
        raise ValueError('Native acceptance evidence is empty')
    evidence = set()
    for item in proof['evidence']:
        if digest(required_file(Path(item['path']))) != item['sha256']:
            raise ValueError('Acceptance evidence changed: '+item['path'])
        evidence.add(Path(item['path']).resolve())
    scenes = set()
    lod_mask = 0
    for row in proof['sessions']:
        receipt_path = Path(row['receipt']).resolve()
        if receipt_path not in evidence:
            raise ValueError('Native receipt is not hash-bound evidence')
        receipt = read_json(receipt_path)
        if (not receipt.get('closed') or not receipt.get('audioRestored')
                or receipt['moduleSHA256'] != proof['nativeDLLSHA256']
                or receipt['observations']['physicalInputUsed']):
            raise ValueError('Native session identity or cleanup differs')
        _, observed = load_preview(receipt['nativePreview'], receipt['nativePreviewSHA256'], False)
        if coupled_identity(observed) != bundle:
            raise ValueError('Native session used different coupled artifacts')
        save_prefix={'grey':'iteration','campaign':'campaign'}.get(row['scene'])
        if save_prefix is None:raise ValueError('Unknown native acceptance scene')
        transaction=Path(receipt.get(save_prefix+'SaveTransaction','')).resolve()
        if transaction not in evidence:
            raise ValueError('Save restoration transaction is not hash-bound evidence')
        saved=read_json(transaction);verified=saved.get('originalsVerified')
        if (saved.get('schema')!='malemod.private-save-transaction/1'
                or not saved.get('finishedUnixSeconds') or type(verified) is not int
                or verified!=len(saved.get('files',[]))
                or receipt.get(save_prefix+'SaveOriginalsVerified')!=verified):
            raise ValueError('Native session save restoration is unverified')
        trace = Path(receipt['modulePath']).parent / (
            'verification-'+str(receipt['observations']['processID'])+'.jsonl')
        if trace.resolve() not in evidence:
            raise ValueError('Native trace is not hash-bound evidence')
        if not row['stages'] or len(set(row['stages'])) != len(row['stages']):
            raise ValueError('Native acceptance stages must be nonempty and unique')
        records = [json.loads(line) for line in trace.read_text().splitlines()]
        records = [r for r in records if r['stage'] in row['stages']]
        if [r['stage'] for r in records] != row['stages']:
            raise ValueError('Incomplete native acceptance sequence')
        if any(not r.get('modular') or r.get('bodyResourceMask') != 3
               or r['renderFlags'] & 128 for r in records):
            raise ValueError('Native acceptance contains a rendering failure')
        for record in records:
            lod_mask |= record.get('modularCompletedLODMask', 0)
        scenes.add(row['scene'])
    if scenes != {'grey', 'campaign'}:
        raise ValueError('Both grey-room and campaign observations are required')
    if lod_mask & 15 != 15:
        raise ValueError('Both resources and both native LODs must complete GPU draws')
    return proof


def verified_existing_rollback(preview_path, previous, game, candidate_game):
    """Reuse an owned, exact accepted preview without copying another runtime."""
    path = Path(preview_path).resolve()
    # load_preview validates the manifest's declared owned storage and paths.
    root, data = load_preview(path, verify_files=False)
    if root.resolve() in (game.resolve(), candidate_game.resolve()):
        raise ValueError('Rollback must be separate from installed and candidate files')
    declared = {r['path']: r['sha256'] for r in data['files']}
    for row in previous['files']:
        target = root/row['path']
        if (declared.get(row['path']) != row['sha256'] or
                not target.resolve().is_relative_to(root.resolve()) or
                digest(target) != row['sha256']):
            raise ValueError('Existing rollback differs from accepted runtime: '+row['path'])
    receipt = root/'receipt.json'
    if receipt.resolve() != receipt:
        raise ValueError('Rollback receipt may not redirect outside its directory')
    if receipt.exists() and read_json(receipt) != previous:
        raise ValueError('Existing rollback receipt describes another runtime')
    return root


def fresh_backup_directory(path, game, candidate_game):
    """Only accept a new, nonredirected managed-file backup inside consolidated Work."""
    target = Path(path)
    owner = (ROOT/'build').resolve().parent
    if (not target.is_absolute() or target.resolve() != target
            or not target.is_relative_to(owner) or target == owner
            or target.exists() or target.is_symlink() or not target.parent.is_dir()):
        raise ValueError('Backup directory must be fresh, absolute and nonredirected under consolidated Work')
    for root in (game.resolve(), candidate_game.resolve()):
        if target.is_relative_to(root) or root.is_relative_to(target):
            raise ValueError('Backup directory must not overlap either game')
    for parent in target.parents:
        if parent == owner:break
        attributes = getattr(parent.lstat(), 'st_file_attributes', 0)
        if parent.is_symlink() or attributes & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400):
            raise ValueError('Backup directory may not traverse redirected storage')
    return target


def install_modular_native(cfg, preview_path, proof_path, validate_only=False, rollback_preview=None, backup_directory=None):
    if rollback_preview is not None and backup_directory is not None:
        raise ValueError('Choose an existing rollback preview or a fresh backup directory, not both')
    preview_path, proof_path = Path(preview_path).resolve(), Path(proof_path).resolve()
    source_game, preview = load_preview(preview_path)
    proof = validate_gate(proof_path, preview_path)
    game = cfg['game'].resolve()
    receipt_path = ROOT/'local/native-installation.json'
    previous = read_json(receipt_path)
    old = {r['path']: r for r in previous['files']}
    names = ['malemod_witcher.dll'] + list(ARTIFACTS)
    if proof.get('workerAdoption'):
        names += ['surface_worker.exe', 'malemod-runtime.profile']
    names += [n+'.sha256' for n in ARTIFACTS]
    candidate = {r['path']: r for r in preview['files']}
    replacements = {PREFIX+n: candidate[PREFIX+n] for n in names}
    for path in material_identities(preview.get('materialPackage')):
        replacements[path] = candidate[path]
    for rel, row in replacements.items():
        target = (game/rel).resolve()
        if not target.is_relative_to(game):
            raise ValueError('Installation path leaves the managed game')
        if target.exists() and rel not in old:
            raise ValueError('Preserve unmanaged target: '+rel)
        if digest(source_game/rel) != row['sha256']:
            raise ValueError('Candidate changed: '+rel)
    native = source_game/PREFIX
    for name, magic in ARTIFACTS.items():
        versions=(b'MMMDYN01',b'MMMDYN02') if name=='geralt.modular-dynamic' else (magic,)
        if (native/name).read_bytes()[:8] not in versions:
            raise ValueError('Unsupported coupled artifact: '+name)
        if (native/(name+'.sha256')).read_text().strip() != digest(native/name):
            raise ValueError('Coupled artifact hash differs: '+name)
    geometry, binding, dynamic = [digest(native/n) for n in
                                 ['geralt.modular', 'geralt.modular-native', 'geralt.modular-dynamic']]
    if ((native/'geralt.modular-native').read_bytes()[8:136] !=
            (geometry+digest(native/'geralt.render')).encode()
            or (native/'geralt.modular-dynamic').read_bytes()[8:72] != geometry.encode()
            or (native/'geralt.modular-transfer').read_bytes()[8:72] != geometry.encode()
            or (native/'geralt.modular-materials').read_bytes()[8:200] !=
            (geometry+dynamic+binding).encode()):
        raise ValueError('Coupled modular artifact dependencies differ')
    if digest(native/'malemod_witcher.dll') != proof['nativeDLLSHA256']:
        raise ValueError('Reviewed DLL identity differs')
    fixed_dependencies = ['geralt.bindings', 'geralt.render']
    if proof.get('workerAdoption'):
        from ordered_worker_adoption import validate
        validate(Path(proof['workerAdoption']['path']), native/'surface_worker.exe',
                 game/PREFIX/'surface_worker.exe')
        before = (game/PREFIX/'malemod-runtime.profile').read_bytes()
        after = (native/'malemod-runtime.profile').read_bytes()
        if (before[:8] != b'MMRUN001' or after[:48] != before[:48]
                or after[112:] != before[112:]
                or after[48:112] != digest(native/'surface_worker.exe').encode()):
            raise ValueError('Worker adoption changed character calibration or bindings')
    else:
        fixed_dependencies += ['surface_worker.exe', 'malemod-runtime.profile']
    for name in fixed_dependencies:
        if digest(native/name) != digest(game/PREFIX/name):
            raise ValueError('Unreviewed numerical/native dependency changed: '+name)
    verify_native_compatibility(game, native)
    existing_backup = verified_existing_rollback(rollback_preview, previous, game, source_game) if rollback_preview else None
    custom_backup = fresh_backup_directory(backup_directory, game, source_game) if backup_directory is not None else None
    if validate_only:
        return {'validated': True, 'replacements': list(replacements)}
    query = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command',
        'Get-Process witcher3 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id'],
        capture_output=True, text=True)
    if query.stdout.strip():
        raise RuntimeError('Close Witcher before installing the accepted candidate')
    documents = Path.home()/'Documents/The Witcher 3'
    protected = [game/'bin/config/base/audio.ini', game/PREFIX/'malemod-controls.bin',
                 game/PREFIX/'malemod-preferences.ini']
    protected += [p for p in documents.glob('*') if p.suffix in ('.settings', '.xml')]
    protected += list((documents/'gamesaves').glob('*'))
    protected = {p: digest(p) for p in protected if p.is_file()}
    # One accepted managed runtime, not another dated game/restore-image bank.
    # Never overwrite it implicitly; source backups belong in GitHub.
    backup = existing_backup or custom_backup or ROOT/'local/native-rollback-current'
    if not existing_backup:
        if custom_backup is not None:
            fresh_backup_directory(custom_backup, game, source_game)
        backup.mkdir()
        for rel, row in old.items():
            target = backup/rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(game/rel, target)
            if digest(target) != row['sha256']:
                raise RuntimeError('Exact rollback differs: '+rel)
    shutil.copy2(receipt_path, backup/'receipt.json')
    updated = json.loads(json.dumps(previous))
    updated['materialPackage'] = preview.get('materialPackage')
    updated['files'] = [r for r in previous['files'] if r['path'] not in replacements]
    updated['files'] += [dict(path=rel, sha256=row['sha256']) for rel, row in replacements.items()]
    updated.update(backup=str(backup), modularAcceptance={
        'proof': str(proof_path), 'proofSHA256': digest(proof_path),
        'sharedSourceRevision': proof['sharedSourceRevision'],
        'nativeDLLSHA256': proof['nativeDLLSHA256'], 'fullAttachmentGatePassed': True},
        observedNormalStartup=False)
    if proof.get('workerAdoption'):
        updated['numericalWorkerAdoption'] = proof['workerAdoption']
    changed = []
    try:
        for rel, row in replacements.items():
            changed.append(rel)
            (game/rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_game/rel, game/rel)
            if digest(game/rel) != row['sha256']:
                raise RuntimeError('Installed hash differs: '+rel)
        if any(digest(p) != h for p, h in protected.items()):
            raise RuntimeError('Protected user data changed during installation')
        for rel, row in old.items():
            if rel not in replacements and digest(game/rel) != row['sha256']:
                raise RuntimeError('Unrelated managed file changed: '+rel)
        write_receipt(receipt_path, updated)
    except BaseException:
        for rel in reversed(changed):
            if rel in old:
                shutil.copy2(backup/rel, game/rel)
            elif (game/rel).is_file():
                (game/rel).unlink()
        shutil.copy2(backup/'receipt.json', receipt_path)
        raise
    result = dict(installed=True, backup=str(backup), changedFiles=list(replacements),
                  protectedFilesVerified=len(protected), fullAttachmentGatePassed=True)
    write_receipt(backup/'install-result.json', result)
    print(json.dumps(result, indent=2))
    return result
