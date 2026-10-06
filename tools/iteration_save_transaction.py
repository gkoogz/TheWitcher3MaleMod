"""Hash-bound preservation of ordinary saves across a private native new game.

The native no-save lock is also used, but engine initialization can reset it.
Only missing originals are restored; changed originals or unrelated new files
abort cleanup. Newly created checkpoints require our private driver's metadata.
"""
import json
from pathlib import Path
import re
import shutil
import time
from mod import digest, read_json, write_json


def begin(save_directory, job):
    root = Path(save_directory).resolve()
    job = Path(job).resolve()
    if not root.is_dir() or job.exists():
        raise ValueError('Existing save directory and new transaction required')
    files = sorted(root.iterdir())
    if any(not p.is_file() or p.is_symlink() for p in files):
        raise ValueError('Save directory must contain only ordinary files')
    job.mkdir(parents=True)
    rows = []
    for path in files:
        target = job/path.name
        h = digest(path)
        shutil.copy2(path, target)
        if digest(target) != h or digest(path) != h:
            raise ValueError('Save changed during backup')
        rows.append(dict(name=path.name, sha256=h))
    value = dict(schema='malemod.private-save-transaction/1', root=str(root),
                 startedUnixSeconds=time.time(), files=rows)
    write_json(job/'receipt.json', value)
    return job/'receipt.json'


def restore(receipt, *, closed_private_session):
    if not closed_private_session:
        raise ValueError('Exact private child must be closed before restoration')
    receipt = Path(receipt).resolve()
    data = read_json(receipt)
    if data.get('schema') != 'malemod.private-save-transaction/1':
        raise ValueError('Invalid save transaction')
    root = Path(data['root']).resolve()
    original = {row['name']: row for row in data['files']}
    if len(original) != len(data['files']) or any(Path(n).name != n for n in original):
        raise ValueError('Invalid original save names')
    for name, row in original.items():
        if digest(receipt.parent/name) != row['sha256']:
            raise ValueError('Original backup changed')
        target = root/name
        if target.exists() and digest(target) != row['sha256']:
            raise ValueError('Preserve changed original save: '+name)
    extras = sorted(p for p in root.iterdir() if p.name not in original)
    extra_names = {p.name for p in extras}
    rows = []
    for path in extras:
        if not path.is_file() or path.is_symlink() or path.suffix not in ('.json', '.png', '.sav'):
            raise ValueError('Preserve unrelated save directory addition')
        if path.stat().st_mtime < data['startedUnixSeconds']:
            raise ValueError('Addition predates private transaction')
        if not re.fullmatch(r'(CheckPoint|AutoSave)_[a-zA-Z0-9_]+', path.stem):
            raise ValueError('Not a private automatic save')
        metadata = path.with_suffix('.json')
        if metadata.name not in extra_names or not re.search(
                r'"modName"\s*:\s*"modmalemodcontinuetest"', metadata.read_text(), re.I):
            raise ValueError('Missing exact private-driver save provenance')
        rows.append(dict(name=path.name, sha256=digest(path)))
    # Validate everything before any mutation. Keep generated checkpoints as
    # diagnostic evidence outside gamesaves, rather than destroy their bytes.
    archive = receipt.parent/'private-created'
    archive.mkdir(exist_ok=True)
    for row in rows:
        shutil.copy2(root/row['name'], archive/row['name'])
        if digest(archive/row['name']) != row['sha256']:
            raise ValueError('Private save archive differs')
    restored = []
    for name, row in original.items():
        if not (root/name).exists():
            shutil.copy2(receipt.parent/name, root/name)
            restored.append(name)
    for row in rows:
        if digest(root/row['name']) != row['sha256']:
            raise ValueError('Private-created save changed before cleanup')
        (root/row['name']).unlink()
    if {p.name for p in root.iterdir()} != set(original) or any(
            digest(root/n) != r['sha256'] for n, r in original.items()):
        raise ValueError('Save transaction final hash check failed')
    data.update(restoredOriginals=restored, archivedPrivateCreated=rows,
                finishedUnixSeconds=time.time(), originalsVerified=len(original))
    write_json(receipt, data)
    return data
