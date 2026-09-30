"""Run script-aware cooking in a version-pinned official WCC process.
Never attaches to the game, changes SDK files, or installs an output.
"""
import ctypes as C
from ctypes import wintypes as W
import struct, subprocess, time, sys, hashlib, os, msvcrt, uuid
from pathlib import Path
from mod import *

K=C.WinDLL('kernel32',use_last_error=True)
P=C.c_void_p; U=C.c_uint32; Q=C.c_uint64
class SI(C.Structure):
    _fields_=[('cb',U),('reserved',P),('desktop',P),('title',P),('x',U),('y',U),('xs',U),('ys',U),('xc',U),('yc',U),('fill',U),('flags',U),('show',C.c_uint16),('res2',C.c_uint16),('reserved2',P),('stdin',P),('stdout',P),('stderr',P)]
class PI(C.Structure):
    _fields_=[('process',P),('thread',P),('pid',U),('tid',U)]
class DE(C.Structure):
    _fields_=[('code',U),('pid',U),('tid',U),('pad',U),('data',C.c_ubyte*160)]
def api(name,restype,args):
    f=getattr(K,name);f.restype=restype;f.argtypes=args;return f
create=api('CreateProcessW',W.BOOL,[W.LPCWSTR,W.LPWSTR,P,P,W.BOOL,U,P,W.LPCWSTR,C.POINTER(SI),C.POINTER(PI)])
wait=api('WaitForDebugEvent',W.BOOL,[C.POINTER(DE),U]);cont=api('ContinueDebugEvent',W.BOOL,[U,U,U])
read=api('ReadProcessMemory',W.BOOL,[P,P,P,C.c_size_t,P]);write=api('WriteProcessMemory',W.BOOL,[P,P,P,C.c_size_t,P])
getctx=api('GetThreadContext',W.BOOL,[P,P]);setctx=api('SetThreadContext',W.BOOL,[P,P])
alloc=api('VirtualAllocEx',P,[P,P,C.c_size_t,U,U]);free=api('VirtualFreeEx',W.BOOL,[P,P,C.c_size_t,U])
flush=api('FlushInstructionCache',W.BOOL,[P,P,C.c_size_t]);close=api('CloseHandle',W.BOOL,[P])
terminate=api('TerminateProcess',W.BOOL,[P,U])
def checked(ok):
    if not ok:raise C.WinError(C.get_last_error())
def q(b,off=0):return struct.unpack_from('<Q',b,off)[0]
def put(b,off,v):struct.pack_into('<Q',b,off,v)
class Session:
    def __init__(self,args,cwd,log):
        self.pi=PI();s=SI();s.cb=C.sizeof(s)
        self.log=log.open('wb'); self.input=open(os.devnull,'rb')
        s.flags=0x100
        s.stdout=s.stderr=msvcrt.get_osfhandle(self.log.fileno())
        s.stdin=msvcrt.get_osfhandle(self.input.fileno())
        os.set_handle_inheritable(s.stdout,True);os.set_handle_inheritable(s.stdin,True)
        checked(create(None,C.create_unicode_buffer(subprocess.list2cmdline(args)),None,None,True,2|0x08000000,None,str(cwd),C.byref(s),C.byref(self.pi)))
        self.pending=None;self.base=None;self.breakpoints={};self.initial=False;self.dead=False
    def read(self,a,n):
        b=C.create_string_buffer(n);checked(read(self.pi.process,a,b,n,None));return b.raw
    def write(self,a,b):checked(write(self.pi.process,a,b,len(b),None));checked(flush(self.pi.process,a,len(b)))
    def ctx(self):
        b=C.create_string_buffer(1248);a=(C.addressof(b)+15)&~15;C.c_uint32.from_address(a+0x30).value=0x10001f;checked(getctx(self.pi.thread,a));return bytearray(C.string_at(a,1232))
    def setctx(self,v):
        b=C.create_string_buffer(1248);a=(C.addressof(b)+15)&~15;C.memmove(a,bytes(v),len(v));checked(setctx(self.pi.thread,a))
    def bp(self,a):
        if a not in self.breakpoints:self.breakpoints[a]=self.read(a,1);self.write(a,b'\xcc')
    def unbp(self,a):self.write(a,self.breakpoints.pop(a))
    def resume(self,status=0x10002):
        checked(cont(self.pending.pid,self.pending.tid,status));self.pending=None
    def event(self,timeout=180):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            e=DE()
            if not wait(C.byref(e),1000):
                if C.get_last_error()==121:continue
                raise C.WinError(C.get_last_error())
            self.pending=e;b=bytes(e.data)
            if e.code==3:
                self.base=q(b,24)
                if q(b):close(q(b))
                self.bp(self.base+0x5214f0)
            elif e.code==6:
                if q(b):close(q(b))
            elif e.code==5:
                self.dead=True;code=struct.unpack_from('<I',b)[0];self.resume();return ('exit',code)
            elif e.code==1:
                code=struct.unpack_from('<I',b)[0];address=q(b,16)
                if code==0x80000003:
                    if address in self.breakpoints:return ('break',address)
                    if not self.initial:self.initial=True
                    else:raise RuntimeError('Unexpected native breakpoint '+hex(address))
                elif code==0x406d1388:pass
                else:
                    first=struct.unpack_from('<I',b,152)[0]
                    if first:self.resume(0x80010001);continue
                    raise RuntimeError('Unhandled native exception '+hex(code)+' at '+hex(address))
            self.resume()
        raise TimeoutError('WCC debugger probe timeout')
    def invoke(self,address,rcx=0,rdx=0,r8=0,r9=0,skip_cleanup=False):
        saved=self.ctx();ctx=bytearray(saved);sp=(q(ctx,0x98)-0x100)&~15;sp-=8
        self.write(sp,struct.pack('<Q',self.trap));put(ctx,0x98,sp);put(ctx,0xf8,address)
        for off,v in [(0x80,rcx),(0x88,rdx),(0xb8,r8),(0xc0,r9)]:put(ctx,off,v)
        if skip_cleanup:self.bp(self.base+0x521d45)
        self.setctx(ctx);self.resume()
        while True:
            kind,a=self.event()
            if kind!='break':raise RuntimeError('WCC exited during invocation: '+str(a))
            if skip_cleanup and a==self.base+0x521d45:
                self.unbp(a);x=self.ctx()
                if q(x,0x80)!=rdx:raise RuntimeError('Unexpected argument destructor')
                put(x,0xf8,a+5);self.setctx(x);self.resume();continue
            if a!=self.trap:raise RuntimeError('Unexpected invocation stop '+hex(a))
            value=q(self.ctx(),0x78);self.setctx(saved);return value

def run_scripted_cook(cfg, options, workspace, label, inspect_entities=()):
    """Keep compiler RTTI alive for native cooking; debug only the owned child.

    REDkit 5.0's standalone cooker has no custom script classes. This wrapper
    invokes its unchanged dispatcher twice in one process. The SDK and game
    binaries are never patched on disk. Exact executable hash is mandatory.
    Temporary breakpoints only control the child tool's command dispatch; they
    do not bypass compiler, resource, cooker, or output validation.
    """
    expected='56503cf15e29062579ca26531ec8aa387d056590030bf534a878411ad9c5417e'
    if digest(cfg['wcc'])!=expected:raise RuntimeError('Unsupported WCC executable; session addresses require revalidation')
    workspace=Path(workspace).resolve()
    if not workspace.is_relative_to(ROOT/'build'):raise ValueError('Expected an owned build workspace')
    combined=ROOT/'build/jobs'/('session-scripts-'+uuid.uuid4().hex[:12]);combined.mkdir(parents=True)
    copy_tree(cfg['redkit']/'r4data/scripts',combined);copy_tree(workspace/'scripts',combined)
    signature=hashlib.sha256()
    for p in sorted(combined.rglob('*.ws')):
        signature.update(p.relative_to(combined).as_posix().encode());signature.update(p.read_bytes())
    out=combined.with_name(combined.name+'-compiled');out.mkdir()
    depot=readthrough_depot(cfg['depot'],workspace)
    args=native_args(cfg,'compilescripts',[str(combined),'-out='+str(out)],workspace,depot)
    log=ROOT/'build/logs'/(time.strftime('%Y%m%d-%H%M%S')+'-'+label+'-'+uuid.uuid4().hex[:6]+'.log')
    log.parent.mkdir(parents=True,exist_ok=True)
    print('REDkit script-aware cook | log:',log,flush=True)
    commands=[['cook',*options]]
    for p in inspect_entities:
        p=Path(p).resolve()
        if not p.is_relative_to(ROOT/'build'):raise ValueError('Inspection must stay in build')
        commands.append(['dumpfile','-file='+str(p),'-out=\\\\?\\'])
    s=Session(args,cfg['wcc'].parent,log);started=time.monotonic();results=[]
    try:
        kind,entry=s.event()
        if kind!='break' or entry!=s.base+0x5214f0:raise RuntimeError('Unexpected WCC dispatcher entry')
        x=s.ctx();engine=q(x,0x80);ret=q(s.read(q(x,0x98),8));s.unbp(entry);s.bp(ret);put(x,0xf8,entry);s.setctx(x);s.resume()
        kind,a=s.event()
        if kind!='break' or a!=ret:raise RuntimeError('Unexpected WCC compilation return')
        x=s.ctx()
        if not q(x,0x78)&255:raise RuntimeError('Script compilation failed; inspect '+str(log))
        s.unbp(ret);put(x,0xf8,ret);s.setctx(x)
        mem=alloc(s.pi.process,None,0x10000,0x3000,0x40);checked(mem);s.trap=mem;s.bp(mem)
        for command in commands:
            argv=[str(cfg['wcc']),*command]
            table=mem+0x100;arr=mem+0x200;raw=mem+0x1000
            if len(argv)>200 or sum(len(a.encode())+1 for a in argv)>0xe000:raise ValueError('Command exceeds native session argument bounds')
            for i,arg in enumerate(argv):
                b=arg.encode()+b'\x00';s.write(raw,b);s.write(arr+i*12,b'\x00'*12)
                s.invoke(s.base+0x293e240,arr+i*12,raw);raw+=len(b)
            s.write(table,struct.pack('<QII',arr,len(argv),len(argv)))
            result=s.invoke(s.base+0x5214f0,engine,table,skip_cleanup=True)&255
            results.append({'command':command[0],'args':command[1:],'returnedSuccess':bool(result)})
            for i in range(len(argv)):s.invoke(s.base+0x293e5f0,arr+i*12)
            if not result:raise RuntimeError('Native '+command[0]+' failed; inspect '+str(log))
        s.unbp(s.trap);checked(free(s.pi.process,mem,0,0x8000));s.resume()
        kind,exit_code=s.event()
        if kind!='exit' or exit_code:raise RuntimeError('WCC failed at shutdown')
    finally:
        if not s.dead:terminate(s.pi.process,1)
        close(s.pi.thread);close(s.pi.process);s.log.close();s.input.close()
    compiled=list(out.glob('*.redscripts'))
    if len(compiled)!=1:raise RuntimeError('Missing compiled script artifact')
    text=log.read_text(errors='replace')
    if native_failure(text,exit_code):raise RuntimeError('Native command errors; inspect '+str(log))
    # These two diagnostics also occur during the unchanged standalone SDK
    # compilation. New asserts, including debugger/argument ABI errors, fail.
    known_asserts=('scriptCompiledCode.cpp:56] ( !m_sourceFile.Empty() )',
                   'soundFileLoader.cpp:101] ( soundBank != nullptr )')
    if any('[Error][Assert]' in line and not any(message in line for message in known_asserts)
           for line in text.splitlines()):
        raise RuntimeError('Unexpected native assertion; inspect '+str(log))
    record={'command':'scripted-cook','commands':results,'exitCode':exit_code,
            'seconds':round(time.monotonic()-started,3),'logPath':log.relative_to(ROOT).as_posix(),
            'logSHA256':digest(log),'wccSHA256':expected,'wrapperSHA256':digest(Path(__file__)),
            'sourceSignature':signature.hexdigest(),'compiledSHA256':digest(compiled[0]),
            'sdkModified':False,'runtimeHookRequired':False}
    write_json(log.with_suffix('.json'),record)
    print('Native script-aware commands succeeded.',flush=True)
    return record
