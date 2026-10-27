"""Durable same-volume quarantine of photos around an exact private session."""
import os,re,shutil,stat,subprocess,time,uuid
from pathlib import Path
from mod import ROOT,read_json,digest
from install_v2 import atomic_json,copy_owned

ACTIVE=ROOT/'v2/build/screenshot-transactions/active.json'


def quiet():
    if 'witcher3.exe'in subprocess.check_output(['tasklist','/FI','IMAGENAME eq witcher3.exe','/FO','CSV','/NH'],text=True).lower():
        raise ValueError('Close the exact private game before screenshot restoration')


def inventory(root):
    root=Path(root)
    if root.is_symlink()or getattr(root.lstat(),'st_file_attributes',0)&1024:raise ValueError('Preserve redirected screenshot directory')
    rows=[]
    for p in sorted(root.iterdir()):
        info=p.lstat()
        if not p.is_file()or p.is_symlink()or getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',1024):
            raise ValueError('Preserve unexpected screenshot entry: '+p.name)
        sha=digest(p);after=p.stat()
        if (info.st_size,info.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('Screenshot changed during inventory: '+p.name)
        rows.append(dict(name=p.name,sha256=sha,bytes=info.st_size,mtime=info.st_mtime))
    return rows


def verify(root,rows):
    observed=inventory(root)
    if {r['name']:r['sha256']for r in observed}!={r['name']:r['sha256']for r in rows}:
        expected={r['name']:r['sha256']for r in rows};actual={r['name']:r['sha256']for r in observed}
        names=sorted(n for n in set(expected)|set(actual)if expected.get(n)!=actual.get(n))
        raise ValueError('Screenshot originals changed: '+', '.join(names))


def pending():
    if ACTIVE.exists():
        path=Path(read_json(ACTIVE)['receipt'])
        if not read_json(path).get('restored'):raise ValueError('Recover pending screenshot transaction first: '+str(path))


def begin(root,job):
    quiet();pending();root=Path(root).absolute();job=Path(job).resolve()
    root.mkdir(exist_ok=True)
    if root.is_symlink()or getattr(root.lstat(),'st_file_attributes',0)&1024:
        raise ValueError('Preserve redirected screenshot directory')
    root=root.resolve()
    rows=inventory(root);job.mkdir(parents=True,exist_ok=False);receipt=job/'receipt.json'
    holding=root.parent/('.malemod-screenshots-'+uuid.uuid4().hex)
    data=dict(schema='malemod.screenshot-transaction/1',root=str(root),holding=str(holding),files=rows,createdUnixSeconds=time.time(),restored=False,state='prepared')
    atomic_json(receipt,data);atomic_json(ACTIVE,dict(receipt=str(receipt)))
    os.rename(root,holding);root.mkdir();verify(holding,rows)
    data['state']='isolated';atomic_json(receipt,data);return receipt


def bind(receipt,session_path):
    receipt=Path(receipt);data=read_json(receipt);session=read_json(session_path)
    if data.get('session')and Path(data['session']).resolve()!=Path(session_path).resolve():raise ValueError('Screenshot transaction already belongs to another native session')
    data.update(session=str(Path(session_path).resolve()),identity=session['observations'],launchedUnixSeconds=session['launchedUnixSeconds'])
    atomic_json(receipt,data)


def restore(receipt):
    quiet();receipt=Path(receipt).resolve();data=read_json(receipt)
    if data.get('schema')!='malemod.screenshot-transaction/1':raise ValueError('Expected exact screenshot transaction')
    root,holding=Path(data['root']),Path(data['holding'])
    if holding.parent!=root.parent or not re.fullmatch(r'\.malemod-screenshots-[0-9a-f]{32}',holding.name):raise ValueError('Screenshot quarantine ownership differs')
    if data.get('session'):
        session=read_json(data['session'])
        if (session['observations']!=data['identity']or not session.get('closed')or not(session.get('audioRestored')or session.get('audioSessionsGone'))
                or not session.get('iterationWorldFilesRemoved')):raise ValueError('Exact private session closure required before screenshot restoration')
    if not holding.exists():
        verify(root,data['files']);archived=[]
        for row in data.get('sessionFiles',[]):
            photo=receipt.parent/'session-photos'/row['name']
            if not photo.is_file()or digest(photo)!=row['sha256']:raise ValueError('Screenshot archive missing after interrupted restoration: '+row['name'])
            archived.append(dict(path=str(photo),name=row['name'],sha256=row['sha256']))
        data.update(restored=True,state='restored',originalsVerified=len(data['files']),archive=archived)
        atomic_json(receipt,data);return data
    verify(holding,data['files'])
    if not root.exists():root.mkdir()
    observed=inventory(root)
    if 'sessionFiles'not in data:
        for row in observed:
            p=root/row['name']
            if (not data.get('session')or not re.fullmatch(r'screenshot_\d+\.png',row['name'],re.I)
                    or row['mtime']<data['launchedUnixSeconds']or p.read_bytes()[:8]!=b'\x89PNG\r\n\x1a\n'):
                raise ValueError('Preserve unexpected concurrent screenshot: '+row['name'])
        data.update(sessionFiles=observed,state='archiving');atomic_json(receipt,data)
    expected={r['name']:r for r in data['sessionFiles']}
    for row in observed:
        if row['name']not in expected or row['sha256']!=expected[row['name']]['sha256']:
            raise ValueError('Preserve changed concurrent screenshot: '+row['name'])
    archive=receipt.parent/'session-photos';archive.mkdir(exist_ok=True);archived=[]
    for row in data['sessionFiles']:
        source=root/row['name'];target=archive/row['name']
        if target.exists()and digest(target)!=row['sha256']:raise ValueError('Screenshot archive changed: '+row['name'])
        if not target.exists():
            if not source.exists()or digest(source)!=row['sha256']:raise ValueError('Screenshot missing before archive: '+row['name'])
            copy_owned(source,target)
        if digest(target)!=row['sha256']:raise ValueError('Screenshot archive verification failed: '+row['name'])
        archived.append(dict(path=str(target),name=row['name'],sha256=row['sha256']))
    for row in observed:
        source=root/row['name']
        if digest(source)!=row['sha256']:raise ValueError('Screenshot changed before cleanup: '+row['name'])
        source.unlink()
    if list(root.iterdir()):raise ValueError('Preserve unexpected screenshot before original-directory restore')
    root.rmdir();os.rename(holding,root);verify(root,data['files'])
    data.update(restored=True,state='restored',originalsVerified=len(data['files']),archive=archived,restoredUnixSeconds=time.time())
    atomic_json(receipt,data);return data


if __name__=='__main__':
    import argparse,json
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--restore',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(restore(args.restore),indent=2))
