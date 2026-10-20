"""Close only the exact child recorded by an owned private verification receipt."""
import argparse,ctypes as C,json,time
from ctypes import wintypes as W
from pathlib import Path
from mod import ROOT,read_json,write_json,digest,settings
from native_preview import session_game

def close(receipt):
    path=Path(receipt).resolve()
    if not path.is_relative_to(ROOT/'build/probe'):raise ValueError('Expected owned private receipt')
    r=read_json(path);identity=r['observations']
    game=session_game(r)
    if not identity['noninteractiveWindowStation'] or identity['physicalInputUsed'] or r['physicalDesktopSwitch']:raise ValueError('Not an isolated child')
    if r.get('closed'):return r
    k=C.WinDLL('kernel32',use_last_error=True)
    k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
    k.GetProcessTimes.argtypes=[W.HANDLE,*[C.POINTER(W.FILETIME)]*4];k.GetProcessTimes.restype=W.BOOL
    k.QueryFullProcessImageNameW.argtypes=[W.HANDLE,W.DWORD,W.LPWSTR,C.POINTER(W.DWORD)];k.QueryFullProcessImageNameW.restype=W.BOOL
    k.TerminateProcess.argtypes=[W.HANDLE,W.UINT];k.TerminateProcess.restype=W.BOOL
    k.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD];k.WaitForSingleObject.restype=W.DWORD
    k.CloseHandle.argtypes=[W.HANDLE]
    def cleanup_exited():
        events=[json.loads(line) for line in (path.parent/'launcher.txt').read_bytes().splitlines(keepends=True) if line.endswith(b'\n')]
        starts=[e for e in events if 'processID' in e]
        exits=[e for e in events if 'exitCode' in e]
        source=Path(r['temporaryContinueSource'])
        # An exited child can no longer supply GetProcessTimes. Require its own
        # launcher-recorded identity/exit/audio lifecycle before removing files.
        if len(starts)!=1 or starts[0]!=identity or len(exits)!=1 or not any('restoredAudioSessions' in e for e in events):
            raise ValueError('Cannot certify recorded private child exit')
        if not source.resolve().is_relative_to(game/'Mods/modMaleModContinueTest') or digest(source)!=r['temporaryContinueSHA256']:
            raise ValueError('Temporary driver identity changed')
        source.unlink()
        r.update(closed=True,audioRestored=True,alreadyExited=True,exitCode=exits[0]['exitCode'],closeVerifiedCreationTime=identity['processCreationTime'])
        write_json(path,r)
        print('Recorded private child had exited; scoped audio restored; temporary driver removed')
        return r
    handle=k.OpenProcess(0x101001,False,identity['processID'])
    if not handle:
        error=C.get_last_error()
        if error!=87: raise OSError(error,'Cannot open recorded private child')
        return cleanup_exited()
    try:
        times=[W.FILETIME() for _ in range(4)]
        if not k.GetProcessTimes(handle,*[C.byref(t) for t in times]):raise OSError(C.get_last_error(),'Cannot identify private child')
        creation=str((times[0].dwHighDateTime<<32)|times[0].dwLowDateTime)
        if creation!=identity['processCreationTime']:raise ValueError('PID has been reused; preserve that process')
        if k.WaitForSingleObject(handle,0)==0: return cleanup_exited()
        name=C.create_unicode_buffer(32768);length=W.DWORD(len(name))
        if not k.QueryFullProcessImageNameW(handle,0,name,C.byref(length)):raise OSError(C.get_last_error(),'Cannot identify game executable')
        if Path(name.value).resolve()!=(game/'bin/x64_dx12/witcher3.exe').resolve():raise ValueError('Recorded child executable differs')
        source=Path(r['temporaryContinueSource'])
        if not source.resolve().is_relative_to(game/'Mods/modMaleModContinueTest') or digest(source)!=r['temporaryContinueSHA256']:raise ValueError('Temporary driver identity changed')
        if not k.TerminateProcess(handle,0):raise OSError(C.get_last_error(),'Cannot close private child')
        if k.WaitForSingleObject(handle,10000)!=0:raise TimeoutError('Private child has not exited')
    finally:k.CloseHandle(handle)
    source.unlink()
    deadline=time.monotonic()+10;events=[]
    while time.monotonic()<deadline:
        lines=(path.parent/'launcher.txt').read_bytes().splitlines(keepends=True)
        events=[json.loads(line) for line in lines if line.endswith(b'\n')]
        if any('exitCode' in e for e in events):break
        time.sleep(.1)
    restored=any('restoredAudioSessions' in e for e in events)
    r.update(closed=True,audioRestored=restored,closeVerifiedCreationTime=creation)
    write_json(path,r)
    if not restored or not any('exitCode' in e for e in events):raise RuntimeError('Child closed; private audio restoration is not confirmed')
    print('Closed exact private child; scoped audio restored; temporary driver removed')
    return r

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('receipt',type=Path);a=p.parse_args();close(a.receipt)
