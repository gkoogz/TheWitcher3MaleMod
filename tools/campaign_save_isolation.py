"""Receipt-bound ordinary-save preservation for the fresh campaign probe."""
import re
import shutil
import subprocess
import time
from pathlib import Path
from mod import ROOT, read_json, write_json, digest
from install_v2 import atomic_json


def quiet():
    if 'witcher3.exe' in subprocess.check_output(['tasklist','/FI','IMAGENAME eq witcher3.exe','/FO','CSV','/NH'],text=True).lower():
        raise RuntimeError('Preserve the running game before save isolation')


def named(root,name):
    path=root/name
    if Path(name).name!=name or path.resolve().parent!=root.resolve()or path.is_symlink():
        raise ValueError('Save name leaves exact owned directory')
    return path


def isolate(root,holding):
    quiet();files=sorted(root.iterdir())
    for pending in holding.parent.glob('ordinary-save-holding-*/isolation.json'):
        if not read_json(pending).get('restored'):raise ValueError('Recover pending ordinary-save transaction first: '+str(pending))
    if any(not p.is_file()or p.is_symlink()for p in files):raise ValueError('Preserve unexpected save directory entry')
    holding.mkdir(parents=True,exist_ok=False)
    rows=[dict(name=p.name,sha256=digest(p))for p in files];receipt=holding/'isolation.json'
    atomic_json(receipt,dict(schema='malemod.v2-campaign-isolation/1',root=str(root),files=rows,restored=False,startedUnixSeconds=time.time()))
    try:
        for row in rows:
            source=named(root,row['name']);dest=named(holding,row['name']);shutil.copy2(source,dest)
            if digest(source)!=row['sha256']or digest(dest)!=row['sha256']:raise ValueError('Ordinary save isolation copy differs')
        for row in rows:
            path=named(root,row['name'])
            if digest(path)!=row['sha256']:raise ValueError('Ordinary save changed before private isolation')
            path.unlink()
        if any(root.iterdir()):raise ValueError('Preserve unexpected save files before private game launch')
    except BaseException:
        restore_originals(receipt,allow_missing_backups=True)
        raise
    return receipt


def restore_originals(receipt,allow_missing_backups=False):
    data=read_json(receipt);holding=Path(receipt).parent;root=Path(data['root']);rows=data['files']
    for row in rows:
        source=named(holding,row['name']);dest=named(root,row['name'])
        if source.exists()and digest(source)!=row['sha256']:raise ValueError('Ordinary save isolation backup changed')
        if dest.exists()and digest(dest)!=row['sha256']:raise ValueError('Preserve externally changed ordinary save')
        if not source.exists()and not (allow_missing_backups and dest.exists())and not data.get('restored'):
            raise ValueError('Missing ordinary save backup')
    for row in rows:
        source=named(holding,row['name']);dest=named(root,row['name'])
        if not dest.exists():
            shutil.copy2(source,dest)
            if digest(dest)!=row['sha256']:raise ValueError('Ordinary restoration copy differs')
    if any(digest(named(root,r['name']))!=r['sha256']for r in rows):raise ValueError('Ordinary restoration differs')
    data.update(restored=True,restoredUnixSeconds=time.time(),originalsVerified=len(rows));atomic_json(receipt,data)
    for row in rows:
        source=named(holding,row['name'])
        if source.exists():source.unlink()
    return len(rows)


def recovery_probe():
    path=ROOT/'build/live-controls/Release/launch_sealed.exe'
    if not path.is_file()or '--audio-session-count'.encode('utf-16-le')not in path.read_bytes():
        raise ValueError('Supported receipt-bound orphan audio inspector is unavailable')
    return path


def archive_manual_saves(session,job):
    root=Path.home()/'Documents/The Witcher 3/gamesaves';rows=[]
    for path in sorted(root.iterdir()):
        if not re.fullmatch(r'(QuickSave|ManualSave)_[a-zA-Z0-9_]+',path.stem):continue
        metadata=path.with_suffix('.json')
        if (not path.is_file()or path.is_symlink()or path.suffix not in ('.sav','.json','.png')
                or path.stat().st_mtime<session['launchedUnixSeconds']or not metadata.is_file()
                or not re.search(r'"modName"\s*:\s*"modmalemodcontinuetest"',metadata.read_text(),re.I)):
            raise ValueError('Unknown private manual-save provenance')
        rows.append(dict(name=path.name,sha256=digest(path)))
    archive=job/'private-manual-saves';archive.mkdir(exist_ok=True)
    for row in rows:
        shutil.copy2(root/row['name'],archive/row['name'])
        if digest(archive/row['name'])!=row['sha256']:raise ValueError('Private save archive differs')
    for row in rows:
        if digest(root/row['name'])!=row['sha256']:raise ValueError('Private save changed before cleanup')
        (root/row['name']).unlink()


def cleanup(isolation):
    data=read_json(isolation);session_path=data.get('session')
    if session_path:
        from close_sealed_session import close
        from run_iteration_world import finish
        session=read_json(session_path);close(session_path,recovery_audio_probe=recovery_probe())
        if not read_json(session_path).get('iterationWorldFilesRemoved'):
            archive_manual_saves(session,Path(isolation).parent)
            root=Path(data['root']);originals={r['name']:r for r in data['files']}
            already_originals=({p.name for p in root.iterdir()}==set(originals)
                and all(digest(root/n)==r['sha256']for n,r in originals.items()))
            transaction=Path(session['iterationSaveTransaction']);inner=read_json(transaction)
            if already_originals and not inner['files']and not inner.get('finishedUnixSeconds'):
                # Older interrupted runner restored outer originals before inner cleanup.
                # Reconcile only a complete, byte-identical original set, never extras.
                inner.update(finishedUnixSeconds=time.time(),originalsVerified=0,outerOrdinaryRestorationVerified=len(originals),
                    outerIsolationReceipt=str(isolation),recoveryReason='Exact ordinary originals already restored; no private additions remain')
                write_json(transaction,inner)
                from native_preview import session_game
                owned=(session_game(session)/'Mods/modMaleModIteration').resolve()
                for row in session.get('iterationWorldFiles',[]):
                    path=Path(row['path'])
                    if not path.resolve().is_relative_to(owned)or (path.exists()and digest(path)!=row['sha256']):
                        raise ValueError('Preserve changed temporary room file')
                for row in session.get('iterationWorldFiles',[]):
                    path=Path(row['path'])
                    if path.exists():path.unlink()
                session=read_json(session_path);session.update(iterationWorldFilesRemoved=True,iterationSaveOriginalsVerified=0,outerOrdinarySavesVerified=len(originals));write_json(session_path,session)
            else:finish(session_path,recovery_audio_probe=recovery_probe())
        # finish persists world removal before restoring the photo quarantine.
        # An interrupted photo restore must still be retried on --recover.
        latest=read_json(session_path)
        if latest.get('iterationWorldFilesRemoved')and latest.get('iterationScreenshotTransaction')and not latest.get('iterationScreenshotFilesRestored'):
            finish(session_path,recovery_audio_probe=recovery_probe())
    else:quiet()
    count=restore_originals(isolation)
    print('Ordinary saves restored and verified:',count,flush=True)
    return count
