"""Install an explicitly user-selected root-articulation development candidate."""
import json
import shutil
import subprocess
import time
from pathlib import Path
from mod import ROOT, digest, read_json, required_file
from install_native_runtime import write_receipt, verify_native_compatibility


def install_reviewed_native(cfg, preview_path, proof_path):
    preview_path = Path(preview_path).resolve()
    proof_path = Path(proof_path).resolve()
    if not preview_path.is_relative_to((ROOT/'build/native-preview').resolve()):
        raise ValueError('Expected repository-owned native preview')
    preview, proof = read_json(preview_path), read_json(proof_path)
    candidate = proof['candidate']
    session = read_json(Path(candidate['nativeSession']))
    if (proof.get('schema') != 'malemod.root-articulation-proof/1'
            or not session.get('closed') or not session.get('audioRestored')
            or candidate['nativeDLLSHA256'] != session['moduleSHA256']
            or Path(session['nativePreview']).resolve() != preview_path
            or session['nativePreviewSHA256'] != digest(preview_path)
            or candidate['nativeViews'] not in (57,81)
            or candidate['allCapturedAngleGains'] != [1, 1]):
        raise ValueError('Reviewed native candidate identity differs')
    game = cfg['game'].resolve()
    source_game = Path(preview['game']).resolve()
    if (preview.get('schema') != 'malemod.native-preview/1'
            or source_game != preview_path.parent/'game'
            or Path(preview['sourceGame']).resolve() != game):
        raise ValueError('Preview game ownership differs')
    receipt_path = ROOT/'local/native-installation.json'
    previous = read_json(receipt_path)
    if (Path(previous['game']).resolve() != game
            or digest(receipt_path) != preview['installationReceiptSHA256']):
        raise ValueError('Managed installation changed since preview')
    query = subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',
        'Get-Process witcher3 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id'],
        capture_output=True, text=True)
    if query.stdout.strip():
        raise RuntimeError('Close Witcher before installing the reviewed candidate')
    prefix = 'bin/x64_dx12/malemod-native/'
    names = ['malemod_witcher.dll','geralt.sewn-corrective','geralt.recruitment']
    replacements = {prefix+n: next(r for r in preview['files'] if r['path']==prefix+n) for n in names}
    old = {r['path']:r for r in previous['files']}
    for rel,row in old.items():
        target = (game/rel).resolve()
        if not target.is_relative_to(game) or digest(required_file(target)) != row['sha256']:
            raise ValueError('Preserve changed managed file: '+rel)
    for rel,row in replacements.items():
        source, target = (source_game/rel).resolve(), (game/rel).resolve()
        if not source.is_relative_to(source_game) or not target.is_relative_to(game):
            raise ValueError('Candidate path redirects outside owned root')
        if digest(required_file(source)) != row['sha256']:
            raise ValueError('Reviewed candidate changed: '+rel)
        if target.exists() and rel not in old:
            raise ValueError('Preserve unmanaged target: '+rel)
    if replacements[prefix+names[0]]['sha256'] != candidate['nativeDLLSHA256']:
        raise ValueError('Reviewed DLL differs')
    if replacements[prefix+names[2]]['sha256'] != candidate['ownershipArtifactSHA256']:
        raise ValueError('Reviewed material ownership differs')
    for name,magic in [('geralt.sewn-corrective',b'MMSEWN02'),('geralt.recruitment',b'MMPREC03')]:
        if (source_game/prefix/name).read_bytes()[:8] != magic:
            raise ValueError('Unexpected collar data contract')
    # The reviewed candidate retains the existing worker, binding, render and profile.
    for name in ['surface_worker.exe','geralt.bindings','geralt.render','malemod-runtime.profile']:
        if digest(source_game/prefix/name) != digest(game/prefix/name):
            raise ValueError('Additional dependency changed: '+name)
    verify_native_compatibility(game, source_game/prefix)
    protected = [game/'bin/config/base/audio.ini', game/prefix/'malemod-controls.bin',
                 game/prefix/'malemod-preferences.ini']
    documents = Path.home()/'Documents/The Witcher 3'
    protected += [p for p in documents.glob('*') if p.is_file() and p.suffix in ('.settings','.xml')]
    protected += list((documents/'gamesaves').glob('*'))
    protected = {str(p):digest(p) for p in protected if p.is_file()}
    backup = ROOT/'local'/('native-backup-root-'+time.strftime('%Y%m%d-%H%M%S'))
    backup.mkdir()
    for rel,row in old.items():
        target = backup/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(game/rel,target)
        if digest(target) != row['sha256']:
            raise RuntimeError('Rollback backup differs: '+rel)
    shutil.copy2(receipt_path,backup/'receipt.json')
    updated = json.loads(json.dumps(previous))
    updated['files'] = [r for r in updated['files'] if r['path'] not in replacements]
    updated['files'] += [{'path':rel,'sha256':row['sha256']} for rel,row in replacements.items()]
    updated.update(backup=str(backup),reviewedRootArticulation={
        'proof':str(proof_path),'proofSHA256':digest(proof_path),
        'preview':str(preview_path),'previewSHA256':digest(preview_path),
        'userSelectedDevelopmentInstall':True,'fullAttachmentGatePassed':False,
        'sourceCommit':proof['sourceCommit'],'sourceIsDirty':proof['sourceIsDirty'],
        'nativeDLLSHA256':candidate['nativeDLLSHA256']},observedNormalStartup=False)
    changed=[]
    try:
        for rel,row in replacements.items():
            changed.append(rel)
            shutil.copy2(source_game/rel,game/rel)
            if digest(game/rel) != row['sha256']:
                raise RuntimeError('Installed candidate differs: '+rel)
        for rel,row in old.items():
            if rel not in replacements and digest(game/rel) != row['sha256']:
                raise RuntimeError('Unrelated managed file changed: '+rel)
        if any(digest(Path(p)) != h for p,h in protected.items()):
            raise RuntimeError('Protected user file changed during installation')
        write_receipt(receipt_path,updated)
    except BaseException:
        for rel in reversed(changed):
            if rel in old: shutil.copy2(backup/rel,game/rel)
            elif (game/rel).is_file(): (game/rel).unlink()
        shutil.copy2(backup/'receipt.json',receipt_path)
        raise
    result = {'installed':True,'changedFiles':list(replacements),'backup':str(backup),
        'nativeDLLSHA256':candidate['nativeDLLSHA256'],'protectedFilesVerified':len(protected),
        'rollbackFilesVerified':len(old),'fullAttachmentGatePassed':False,
        'normalStartupObserved':False,'userSelectedDevelopmentInstall':True}
    write_receipt(backup/'install-result.json',result)
    print(json.dumps(result,indent=2))
    return result
