"""Locate actual-game native registration references, without process access."""
import argparse,json,re,struct,uuid
from pathlib import Path
import numpy as np
import pefile,capstone
from mod import ROOT,settings,write_json,digest

def probe(names, executable=None):
    executable=Path(executable).resolve() if executable else settings()['game']/'bin/x64_dx12/witcher3.exe'
    raw=executable.read_bytes();pe=pefile.PE(data=raw)
    section=next(s for s in pe.sections if s.Name.rstrip(b'\0')==b'.text');code=section.get_data();base=pe.OPTIONAL_HEADER.ImageBase+section.VirtualAddress
    functions=[(f.struct.BeginAddress,f.struct.EndAddress) for f in pe.DIRECTORY_ENTRY_EXCEPTION];functions.sort();starts=np.array([a for a,b in functions],dtype=np.uint32)
    decoder=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64);decoder.detail=True
    job=ROOT/'build/probe'/('game-names-'+uuid.uuid4().hex[:12]);job.mkdir(parents=True);rows=[]
    for name in names:
        needles=[name.encode()+b'\0',name.encode('utf-16-le')+b'\0\0'];targets=[]
        for needle in needles:
            at=0
            while True:
                at=raw.find(needle,at)
                if at<0:break
                try:targets.append(pe.OPTIONAL_HEADER.ImageBase+pe.get_rva_from_offset(at))
                except pefile.PEFormatError:pass
                at+=1
        refs=[]
        for alignment in range(4):
            count=(len(code)-alignment)//4
            displacement=np.frombuffer(code,dtype='<i4',count=count,offset=alignment).astype(np.int64)
            location=base+alignment+np.arange(count,dtype=np.int64)*4
            absolute=location+4+displacement
            for target in targets:
                hits=np.flatnonzero(absolute==target)
                for hit in hits:
                    ref=int(location[hit]);rva=ref-pe.OPTIONAL_HEADER.ImageBase
                    index=int(np.searchsorted(starts,rva,side='right'))-1
                    if index<0:continue
                    a,b=functions[index]
                    if not a<=rva<b:continue
                    off=pe.get_offset_from_rva(a);instructions=list(decoder.disasm(raw[off:off+b-a],pe.OPTIONAL_HEADER.ImageBase+a))
                    matched=[i for i in instructions if i.address<=ref<i.address+i.size and any(op.type==capstone.x86.X86_OP_MEM and op.mem.base==capstone.x86.X86_REG_RIP and i.address+i.size+op.mem.disp==target for op in i.operands)]
                    if not matched:continue
                    address=hex(pe.OPTIONAL_HEADER.ImageBase+a);output=job/(name+'-'+hex(a)+'.txt')
                    output.write_text('\n'.join('%x: %s %s'%(i.address,i.mnemonic,i.op_str) for i in instructions))
                    refs.append(dict(stringAddress=hex(target),reference=hex(matched[0].address),function=address,disassembly=output.name))
        rows.append(dict(name=name,strings=[hex(x) for x in targets],references=refs));print(name,refs[:10],flush=True)
    write_json(job/'evidence.json',dict(executable=str(executable),executableSHA256=digest(executable),gameSHA256=digest(executable),names=rows,method='actual executable string/RIP xrefs with unwind function bounds; ABI not yet verified',observedGameplay=False));print(job)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('names',nargs='+');p.add_argument('--executable',type=Path)
    a=p.parse_args();probe(a.names,a.executable)
