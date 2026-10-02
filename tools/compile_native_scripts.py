"""Register the spoke's native imports in an owned official compiler process.

WCC and the game have separate, observed ABIs. No SDK/game file is patched.
This supplies real compiler RTTI instead of replacing imports with script stubs.
"""
import argparse, hashlib, struct, time, uuid
from pathlib import Path
import pefile
from mod import ROOT, settings, base_checkout, digest, copy_tree, readthrough_depot, native_args, write_json, native_failure
from wcc_scripted import Session, ABI_PROFILES, alloc, checked, terminate, close, q, put

# Actual wcc_lite.exe disassembly: LogChannel registration at RVA 0x2ab75a0.
# These are not editor.map or game addresses. Prefix checks precede execution.
WCC_SHA = '37ac28519adc8bc234653fcf973ba76935096aea50003b0f3a03af4007788f7d'
WCC_RVAS = dict(allocate=0x463fa0, intern=0x294a8e0, construct=0x29deeb0,
                registry=0x45b890, register=0x294ff60)


def compile_native(workspace, imports=('MaleModNativeReady',)):
    cfg=settings();base_checkout(cfg);workspace=Path(workspace).resolve()
    if not workspace.is_relative_to(ROOT/'build'):
        raise ValueError('Native compiler inputs must stay in an owned build workspace')
    if digest(cfg['wcc'])!=WCC_SHA:
        raise RuntimeError('Unsupported native compiler; reobserve its ABI before use')
    # Require the reviewed profile generated from this executable, not an offset
    # borrowed from REDkit's different editor binary or from the game.
    profile=__import__('json').loads((ROOT/'characters/compiler-native-profile.json').read_text())
    if profile['executableSHA256']!=WCC_SHA or profile['functions'].keys()!=WCC_RVAS.keys():
        raise ValueError('Native compiler profile differs')
    pe=pefile.PE(str(cfg['wcc']),fast_load=True)
    for name,rva in WCC_RVAS.items():
        row=profile['functions'][name]
        if row['rva']!=rva or pe.get_data(rva,16).hex()!=row['prefix']:
            raise ValueError('Compiler native prefix mismatch: '+name)
    pe.close()
    if not imports or len(set(imports))!=len(imports) or any(not n.startswith('MaleMod') or not n.isidentifier() for n in imports):
        raise ValueError('Expected unique owned native import names')
    combined=ROOT/'build/jobs'/('native-scripts-'+uuid.uuid4().hex[:12]);combined.mkdir(parents=True)
    copy_tree(cfg['redkit']/'r4data/scripts',combined);copy_tree(workspace/'scripts',combined)
    signature=hashlib.sha256()
    for p in sorted(combined.rglob('*.ws')):
        signature.update(p.relative_to(combined).as_posix().encode());signature.update(p.read_bytes())
    out=combined.with_name(combined.name+'-compiled');out.mkdir()
    args=native_args(cfg,'compilescripts',[str(combined),'-out='+str(out)],workspace,readthrough_depot(cfg['depot'],workspace))
    log=ROOT/'build/logs'/(time.strftime('%Y%m%d-%H%M%S')+'-native-scripts-'+uuid.uuid4().hex[:6]+'.log')
    log.parent.mkdir(parents=True,exist_ok=True)
    print('Official native-aware script compiler | log:',log,flush=True)
    s=Session(args,cfg['wcc'].parent,log,ABI_PROFILES[WCC_SHA]);started=time.monotonic()
    try:
        kind,entry=s.event()
        if kind!='break' or entry!=s.base+s.abi['dispatcher']:
            raise RuntimeError('Unexpected compiler dispatch entry')
        mem=alloc(s.pi.process,None,0x10000,0x3000,0x40);checked(mem)
        s.trap=mem;s.bp(mem)
        # WCC never calls gameplay imports. Use a callable no-op only for the
        # RTTI callback table; script parsing/type checking remains unchanged.
        callback=mem+0x100;s.write(callback,b'\xc3')
        for name in imports:
            s.write(mem+0x400,name.encode('ascii')+b'\0')
            obj=s.invoke(s.base+WCC_RVAS['allocate'],0xf8,0x10,0x18)
            if not obj:raise RuntimeError('Compiler function allocation failed')
            s.write(obj,b'\0'*0xf8)
            s.invoke(s.base+WCC_RVAS['intern'],mem+0x200,mem+0x400)
            result=s.invoke(s.base+WCC_RVAS['construct'],obj,mem+0x200,callback)
            if result!=obj:raise RuntimeError('Compiler native constructor returned a different object')
            registry=s.invoke(s.base+WCC_RVAS['registry'])
            if not registry:raise RuntimeError('Compiler native registry unavailable')
            s.invoke(s.base+WCC_RVAS['register'],registry,obj)
        s.unbp(s.trap);s.unbp(entry)
        context=s.ctx();put(context,0xf8,entry);s.setctx(context);s.resume()
        kind,exit_code=s.event(timeout=cfg['timeoutSeconds'])
        if kind!='exit' or exit_code:raise RuntimeError('Official native-aware compilation failed; inspect '+str(log))
    finally:
        if not s.dead:terminate(s.pi.process,1)
        close(s.pi.thread);close(s.pi.process);s.log.close();s.input.close()
    outputs=list(out.glob('*.redscripts'))
    if len(outputs)!=1 or not outputs[0].stat().st_size or native_failure(log.read_text(errors='replace'),exit_code):
        raise RuntimeError('Compiler did not produce a verified script output; inspect '+str(log))
    record=dict(command='native-compilescripts',exitCode=exit_code,seconds=time.monotonic()-started,
        ownedSourceHashes={p.relative_to(workspace/'scripts').as_posix():digest(p) for p in sorted((workspace/'scripts').rglob('*.ws'))},
        imports=list(imports),compilerSHA256=WCC_SHA,profileSHA256=digest(ROOT/'characters/compiler-native-profile.json'),
        wrapperSHA256=digest(Path(__file__)),sourceSignature=signature.hexdigest(),
        logPath=log.relative_to(ROOT).as_posix(),logSHA256=digest(log),
        artifact=outputs[0].relative_to(ROOT).as_posix(),artifactSHA256=digest(outputs[0]),
        sdkModified=False,gameModified=False,scriptImportsStubbed=False,observedGameInvocation=False)
    write_json(log.with_suffix('.json'),record)
    print('Native imports compiled with the official compiler.',flush=True)
    return record


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--imports',nargs='+',default=['MaleModNativeReady']);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();write_json(a.output,compile_native(a.workspace,a.imports))
