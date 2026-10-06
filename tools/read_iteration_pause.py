"""Read-only, bounded inspection of the exact private retail process's pause strings."""
import ctypes as C
from ctypes import wintypes as W
import json,struct,sys
from pathlib import Path

r=json.loads(Path(sys.argv[1]).read_text())
k=C.WinDLL('kernel32',use_last_error=True)
def api(name,result,args):
    f=getattr(k,name);f.restype=result;f.argtypes=args;return f
P=C.c_void_p
op=api('OpenProcess',P,[W.DWORD,W.BOOL,W.DWORD])
rpm=api('ReadProcessMemory',W.BOOL,[P,P,P,C.c_size_t,P])
times=api('GetProcessTimes',W.BOOL,[P,*[C.POINTER(W.FILETIME)]*4])
close=api('CloseHandle',W.BOOL,[P])
h=op(0x410,False,r['observations']['processID'])
if not h:raise RuntimeError('Exact private process unavailable')
try:
    ft=[W.FILETIME() for _ in range(4)]
    assert times(h,*[C.byref(t) for t in ft])
    assert str((ft[0].dwHighDateTime<<32)|ft[0].dwLowDateTime)==r['observations']['processCreationTime']
    def read(addr,size):
        buf=C.create_string_buffer(size)
        return buf.raw if rpm(h,addr,buf,size,None) else None
    obj=int(sys.argv[2],0)
    data=read(obj,0x800)
    assert data
    print('pause candidate bytes',data[0x150:0x178].hex())
    for i in range(0x70,0x7e8,8):
        ptr,count=struct.unpack_from('<QI',data,i)
        if not 1<=count<=32 or not 0x100000000<=ptr<0x7fffffffffff:continue
        for stride in (12,16,24):
            arr=read(ptr,count*stride)
            if not arr:continue
            values=[]
            for j in range(count):
                sp,sl=struct.unpack_from('<QI',arr,j*stride)
                if not 1<=sl<=128:break
                raw=read(sp,sl)
                if not raw:break
                s=raw.rstrip(b'\0')
                if not s or any(c<32 or c>126 for c in s):break
                values.append(s.decode('ascii'))
            if len(values)==count:print(json.dumps({'object':hex(obj),'offset':hex(i),'stride':stride,'strings':values}))
finally:close(h)
