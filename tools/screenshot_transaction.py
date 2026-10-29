"""Durable same-volume quarantine of photos around an exact private session."""
import ctypes,os,re,shutil,stat,subprocess,time,uuid
from ctypes import wintypes
from pathlib import Path
from mod import ROOT,read_json,digest
from install_v2 import atomic_json,copy_owned

ACTIVE=ROOT/'v2/build/screenshot-transactions/active.json'
_ORIGINAL_LEASES={}


class _OriginalFileLease:
    """Parent-owned read handles deny writers during inventory and gameplay.

    Windows permits readers and individual-file delete/rename sharing. It still
    refuses renaming a parent directory containing these open handles, so the
    owned directory moves below explicitly close/reacquire leases and retain
    the existing full-hash checks on both sides of the move.
    """
    def __init__(self,root):
        self.root=Path(root).resolve();self.handles=[];self.names=[]
        if os.name!='nt':raise OSError('Original screenshot leases require Windows')
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        self.kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        self.kernel.CreateFileW.restype=wintypes.HANDLE
        self.kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        self.kernel.CloseHandle.restype=wintypes.BOOL
        try:
            for path in _entries(self.root):
                # Noninheritable, GENERIC_READ, FILE_SHARE_READ|DELETE,
                # OPEN_EXISTING. An existing writer causes sharing violation.
                handle=self.kernel.CreateFileW(str(path),0x80000000,0x1|0x4,None,3,0x80,None)
                if handle==ctypes.c_void_p(-1).value:
                    error=ctypes.get_last_error()
                    raise OSError(error,'Cannot protect screenshot original: '+path.name,str(path),error)
                self.handles.append(handle);self.names.append(path.name)
            self.check_names()
        except BaseException:
            self.close();raise

    def check_names(self):
        if [p.name for p in _entries(self.root)]!=self.names:
            raise ValueError('Screenshot entries changed during read-only protection')

    def close(self):
        first_error=None
        while self.handles:
            handle=self.handles.pop()
            if not self.kernel.CloseHandle(handle)and first_error is None:first_error=ctypes.WinError(ctypes.get_last_error())
        if first_error is not None:raise first_error


def _lease_key(receipt):return str(Path(receipt).resolve()).casefold()


def _hold_originals(receipt,root):
    key=_lease_key(receipt);lease=_ORIGINAL_LEASES.get(key)
    if lease is not None:
        if lease.root!=Path(root).resolve():raise ValueError('Original screenshot lease belongs to another directory')
        lease.check_names();return lease
    lease=_OriginalFileLease(root);_ORIGINAL_LEASES[key]=lease;return lease


def _release_originals(receipt):
    key=_lease_key(receipt);lease=_ORIGINAL_LEASES.get(key)
    if lease is not None:
        try:lease.close()
        finally:_ORIGINAL_LEASES.pop(key,None)


def _rename_originals(receipt,source,target):
    # Even FILE_SHARE_DELETE handles prevent a Windows parent-directory move.
    # Only this owned move releases protection; reacquire before the next hash
    # verification, or before propagating a failed rename to the caller.
    _release_originals(receipt)
    try:os.rename(source,target)
    except BaseException:
        _hold_originals(receipt,source);raise
    _hold_originals(receipt,target)


def quiet():
    if 'witcher3.exe'in subprocess.check_output(['tasklist','/FI','IMAGENAME eq witcher3.exe','/FO','CSV','/NH'],text=True).lower():
        raise ValueError('Close the exact private game before screenshot restoration')


def _entries(root):
    root=Path(root)
    if root.is_symlink()or getattr(root.lstat(),'st_file_attributes',0)&1024:raise ValueError('Preserve redirected screenshot directory')
    entries=[]
    for p in sorted(root.iterdir()):
        info=p.lstat()
        if not p.is_file()or p.is_symlink()or getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',1024):
            raise ValueError('Preserve unexpected screenshot entry: '+p.name)
        entries.append(p)
    return entries


def inventory(root):
    rows=[]
    for p in _entries(root):
        info=p.lstat()
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
    lease=_OriginalFileLease(root);receipt=job/'receipt.json';retained=False
    try:
        rows=inventory(root);lease.check_names()
        if [r['name']for r in rows]!=lease.names:raise ValueError('Screenshot inventory differs from protected originals')
        job.mkdir(parents=True,exist_ok=False)
        holding=root.parent/('.malemod-screenshots-'+uuid.uuid4().hex)
        data=dict(schema='malemod.screenshot-transaction/1',root=str(root),holding=str(holding),files=rows,createdUnixSeconds=time.time(),restored=False,state='prepared')
        atomic_json(receipt,data);atomic_json(ACTIVE,dict(receipt=str(receipt)))
        key=_lease_key(receipt)
        if key in _ORIGINAL_LEASES:raise ValueError('Screenshot receipt already owns original-file protection')
        _ORIGINAL_LEASES[key]=lease;retained=True
        _rename_originals(receipt,root,holding);root.mkdir();verify(holding,rows)
        data['state']='isolated';atomic_json(receipt,data);return receipt
    except BaseException:
        if not retained:
            # An atomic journal writer may report failure after committing its
            # rename. Preserve protection if the durable ACTIVE pointer really
            # names this new transaction; otherwise release preflight handles.
            active=False
            try:active=ACTIVE.is_file()and Path(read_json(ACTIVE)['receipt']).resolve()==receipt.resolve()and receipt.is_file()
            except (OSError,ValueError,KeyError):pass
            if active:_ORIGINAL_LEASES[_lease_key(receipt)]=lease
            else:lease.close()
        raise


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
    _hold_originals(receipt,holding if holding.exists()else root)
    if not holding.exists():
        verify(root,data['files']);archived=[]
        for row in data.get('sessionFiles',[]):
            photo=receipt.parent/'session-photos'/row['name']
            if not photo.is_file()or digest(photo)!=row['sha256']:raise ValueError('Screenshot archive missing after interrupted restoration: '+row['name'])
            archived.append(dict(path=str(photo),name=row['name'],sha256=row['sha256']))
        data.update(restored=True,state='restored',originalsVerified=len(data['files']),archive=archived)
        atomic_json(receipt,data);_release_originals(receipt);return data
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
    root.rmdir();_rename_originals(receipt,holding,root);verify(root,data['files'])
    data.update(restored=True,state='restored',originalsVerified=len(data['files']),archive=archived,restoredUnixSeconds=time.time())
    atomic_json(receipt,data);_release_originals(receipt);return data


if __name__=='__main__':
    import argparse,json
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--restore',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(restore(args.restore),indent=2))
