"""Read only the status exports already loaded by an owned launcher receipt.

Does not load/inject a DLL, write memory, press a key or end the game process.
"""
import argparse,ctypes as C,json
from pathlib import Path
from ctypes import wintypes as W
from mod import ROOT,read_json,write_json,digest,settings


def read(receipt_path):
    receipt_path=Path(receipt_path).resolve()
    if not receipt_path.is_relative_to(ROOT/'build/probe'):raise ValueError('Expected an owned launch receipt')
    receipt=read_json(receipt_path);pid=receipt['observations']['processID']
    module=(ROOT/receipt.get('modulePath','build/native-x64/Release/malemod_witcher.dll')).resolve()
    if not module.is_relative_to(ROOT/'build'):raise ValueError('Expected an owned native build')
    if digest(module)!=receipt['moduleSHA256']:raise ValueError('Loaded module provenance differs; preserve its build before reading')
    k=C.WinDLL('kernel32',use_last_error=True);p=C.WinDLL('psapi',use_last_error=True)
    def api(lib,name,result,args):
        fn=getattr(lib,name);fn.restype=result;fn.argtypes=args;return fn
    P=C.c_void_p;U=C.c_uint32
    open_process=api(k,'OpenProcess',P,[U,W.BOOL,U]);close=api(k,'CloseHandle',W.BOOL,[P])
    enum=api(p,'EnumProcessModulesEx',W.BOOL,[P,P,U,C.POINTER(U),U])
    filename=api(p,'GetModuleFileNameExW',U,[P,P,W.LPWSTR,U])
    load=api(k,'LoadLibraryExW',P,[W.LPCWSTR,P,U]);free=api(k,'FreeLibrary',W.BOOL,[P])
    get=api(k,'GetProcAddress',P,[P,C.c_char_p])
    thread=api(k,'CreateRemoteThread',P,[P,P,C.c_size_t,P,P,U,P])
    wait=api(k,'WaitForSingleObject',U,[P,U]);exit_code=api(k,'GetExitCodeThread',W.BOOL,[P,C.POINTER(U)])
    process=open_process(0x043a,False,pid)
    if not process:raise C.WinError(C.get_last_error())
    local=None
    try:
        # New receipts identify the lifetime as well as PID, which Windows reuses.
        creation=receipt['observations'].get('processCreationTime')
        if creation is not None:
            times=api(k,'GetProcessTimes',W.BOOL,[P,C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME)])
            created,exited,kernel,user=W.FILETIME(),W.FILETIME(),W.FILETIME(),W.FILETIME()
            if not times(process,C.byref(created),C.byref(exited),C.byref(kernel),C.byref(user)):raise C.WinError(C.get_last_error())
            if str((created.dwHighDateTime<<32)|created.dwLowDateTime)!=creation:raise ValueError('Owned process lifetime differs')
        modules=(P*1024)();needed=U()
        if not enum(process,modules,C.sizeof(modules),C.byref(needed),3) or needed.value>C.sizeof(modules):raise C.WinError(C.get_last_error())
        found={}
        for address in modules[:needed.value//C.sizeof(P)]:
            name=C.create_unicode_buffer(32768)
            if filename(process,address,name,32768):found[Path(name.value).resolve()]=address
        executable=(settings()['game']/'bin/x64_dx12/witcher3.exe').resolve()
        if executable not in found or module.resolve() not in found:raise ValueError('Owned game/module identities differ')
        local=load(str(module),None,1) # DONT_RESOLVE_DLL_REFERENCES; no local hooks run.
        if not local:raise C.WinError(C.get_last_error())
        values={}
        for name in ['MaleModProbeStatus','MaleModGraphicsProbeStatus']:
            entry=get(local,name.encode())
            if not entry:raise ValueError('Missing owned status export')
            handle=thread(process,None,0,found[module.resolve()]+entry-local,None,0,None)
            if not handle:raise C.WinError(C.get_last_error())
            try:
                code=U()
                if wait(handle,5000)!=0 or not exit_code(handle,C.byref(code)):raise RuntimeError('Status read did not finish')
                values[name]=code.value
            finally:close(handle)
        flags=values['MaleModProbeStatus']
        record=dict(processID=pid,scriptInvocationObserved=bool(flags&8),typedArgumentsObserved=bool(flags&16),
            typedRoundtripObserved=bool(flags&64),typedProbeFailed=bool(flags&32),registrationFailed=bool(flags&2),
            graphicsFlags=values['MaleModGraphicsProbeStatus'],rawFlags=flags,readOnlyStatus=True)
        write_json(receipt_path.parent/'status.json',record);print(json.dumps(record,indent=2));return record
    finally:
        if local:free(local)
        close(process)


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('receipt',type=Path);read(a.parse_args().receipt)
