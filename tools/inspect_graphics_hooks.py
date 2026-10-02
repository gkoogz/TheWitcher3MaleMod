"""Read bounded SDK method prologues recorded by an owned live observer.

Verifies process lifetime/module identity; no injection, execution or writes.
Only logged SDK code addresses and their detour jump stubs are read.
"""
import argparse,ctypes as C,json,struct
from ctypes import wintypes as W
from pathlib import Path
from mod import ROOT,digest,read_json,write_json,settings


def inspect(receipt_path):
    receipt_path=Path(receipt_path).resolve()
    if not receipt_path.is_relative_to(ROOT/'build/probe'):raise ValueError('Expected owned receipt')
    receipt=read_json(receipt_path);observations=receipt['observations'];pid=observations['processID']
    owned=(ROOT/receipt['modulePath']).resolve()
    if not owned.is_relative_to(ROOT/'build') or digest(owned)!=receipt['moduleSHA256']:raise ValueError('Owned observer changed')
    k=C.WinDLL('kernel32',use_last_error=True);p=C.WinDLL('psapi',use_last_error=True);P=C.c_void_p;U=C.c_uint32
    def api(lib,name,result,args):
        fn=getattr(lib,name);fn.restype=result;fn.argtypes=args;return fn
    open_process=api(k,'OpenProcess',P,[U,W.BOOL,U]);close=api(k,'CloseHandle',W.BOOL,[P])
    read=api(k,'ReadProcessMemory',W.BOOL,[P,P,P,C.c_size_t,C.POINTER(C.c_size_t)])
    enum=api(p,'EnumProcessModulesEx',W.BOOL,[P,P,U,C.POINTER(U),U])
    filename=api(p,'GetModuleFileNameExW',U,[P,P,W.LPWSTR,U])
    class Info(C.Structure):_fields_=[('base',P),('size',U),('entry',P)]
    info=api(p,'GetModuleInformation',W.BOOL,[P,P,C.POINTER(Info),U])
    times=api(k,'GetProcessTimes',W.BOOL,[P,C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME)])
    process=open_process(0x0410,False,pid)
    if not process:raise C.WinError(C.get_last_error())
    try:
        created,exited,kernel,user=W.FILETIME(),W.FILETIME(),W.FILETIME(),W.FILETIME()
        if not times(process,C.byref(created),C.byref(exited),C.byref(kernel),C.byref(user)):raise C.WinError(C.get_last_error())
        if str((created.dwHighDateTime<<32)|created.dwLowDateTime)!=observations['processCreationTime']:raise ValueError('Process lifetime differs')
        modules=(P*1024)();needed=U()
        if not enum(process,modules,C.sizeof(modules),C.byref(needed),3) or needed.value>C.sizeof(modules):raise C.WinError(C.get_last_error())
        ranges=[]
        for address in modules[:needed.value//C.sizeof(P)]:
            name=C.create_unicode_buffer(32768);record=Info()
            if filename(process,address,name,32768) and info(process,address,C.byref(record),C.sizeof(record)):
                ranges.append((record.base,record.base+record.size,Path(name.value).resolve()))
        if owned not in [row[2] for row in ranges] or (settings()['game']/'bin/x64_dx12/witcher3.exe').resolve() not in [row[2] for row in ranges]:raise ValueError('Owned game/module identities differ')
        def owner(address):return next((path for lo,hi,path in ranges if lo<=address<hi),None)
        def bytes_at(address,size):
            data=C.create_string_buffer(size);got=C.c_size_t()
            if not read(process,address,data,size,C.byref(got)) or got.value!=size:raise C.WinError(C.get_last_error())
            return data.raw
        def jump(address):
            code=bytes_at(address,16)
            if code[0]==0xe9:return address+5+struct.unpack_from('<i',code,1)[0]
            if code[:2]==b'\xff\x25':return struct.unpack('<Q',bytes_at(address+6+struct.unpack_from('<i',code,2)[0],8))[0]
            return None
        log=owned.parent/f'graphics-probe-{pid}.jsonl'
        rows=[json.loads(line) for line in log.read_text().splitlines()]
        methods=sorted({int(row[key],16) for row in rows if row['event']=='listImplementation' for key in ['vertexMethod','indexedMethod']})
        if not methods or len(methods)>128:raise ValueError('Missing/bounded SDK method inventory')
        result=[]
        for address in methods:
            path=owner(address)
            if not path or path.name.lower() not in {'d3d12core.dll','d3d12.dll','sl.interposer.dll'}:raise ValueError('Recorded method is outside observed SDK modules')
            target=jump(address);relay=target
            if target and owner(target)!=owned:target=jump(target)
            result.append(dict(sdkModule=path.name,methodAddress=hex(address),relayAddress=hex(relay) if relay else None,
                callbackAddress=hex(target) if target else None,detourStillTargetsOwnedObserver=bool(target and owner(target)==owned)))
        report=dict(readOnly=True,processLifetimeVerified=True,observerSHA256=receipt['moduleSHA256'],recipeSHA256=digest(Path(__file__)),methods=result)
        write_json(receipt_path.parent/'hook-integrity.json',report);print(json.dumps(report,indent=2));return report
    finally:close(process)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('receipt',type=Path);inspect(p.parse_args().receipt)
