"""Match relocation-masked REDkit functions in the actual game, offline only.

Matches are candidates, never callable ABI proof. Writes no engine files and
does not attach to a process. Installed executable hashes are part of evidence.
"""
import argparse,hashlib,json,re,uuid
from pathlib import Path
import pefile,capstone
from mod import ROOT,settings,write_json,digest

def probe(selectors):
    cfg=settings();editor=cfg['redkit']/'bin/x64_RedKit/editor.exe';mapping=editor.with_suffix('.map')
    game=cfg['game']/'bin/x64_dx12/witcher3.exe'
    symbols=[]
    for line in mapping.read_text(errors='replace').splitlines():
        m=re.match(r'\s+0001:[0-9a-f]+\s+(\S+)\s+([0-9a-f]{16})\s+f\s',line)
        if m:symbols.append((int(m[2],16),m[1]))
    editor_bytes=editor.read_bytes();game_bytes=game.read_bytes();ep=pefile.PE(data=editor_bytes,fast_load=True);gp=pefile.PE(data=game_bytes,fast_load=True)
    section=next(s for s in gp.sections if s.Name.rstrip(b'\0')==b'.text');text=section.get_data();base=gp.OPTIONAL_HEADER.ImageBase+section.VirtualAddress
    decoder=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64);decoder.detail=True
    rows=[]
    for selector in selectors:
        matches=[(a,n) for a,n in symbols if selector in n]
        if len(matches)!=1:raise ValueError('Expected unique symbol '+selector+': '+str(matches[:8]))
        address,name=matches[0];end=min(a for a,n in symbols if a>address);offset=ep.get_offset_from_rva(address-ep.OPTIONAL_HEADER.ImageBase)
        instructions=list(decoder.disasm(editor_bytes[offset:offset+min(end-address,112)],address))
        code=bytearray();mask=[];signature=[]
        for ins in instructions:
            start=len(code);code.extend(ins.bytes);mask.extend([True]*ins.size);signature.append(ins.mnemonic)
            if ins.mnemonic=='call' or ins.group(capstone.CS_GRP_JUMP):
                for i in range(ins.imm_offset,ins.imm_offset+ins.imm_size):mask[start+i]=False
            if any(op.type==capstone.x86.X86_OP_MEM and op.mem.base==capstone.x86.X86_REG_RIP for op in ins.operands):
                for i in range(ins.disp_offset,ins.disp_offset+ins.disp_size):mask[start+i]=False
            if ins.mnemonic=='ret':break
        runs=[];start=0
        while start<len(code):
            if not mask[start]:start+=1;continue
            end=start
            while end<len(code) and mask[end]:end+=1
            runs.append((end-start,start));start=end
        _,anchor=max(runs);length=min(max(runs)[0],24);needle=bytes(code[anchor:anchor+length]);found=[];position=0
        while True:
            at=text.find(needle,position)
            if at<0:break
            position=at+1;candidate=at-anchor
            if candidate>=0 and candidate+len(code)<=len(text) and all(not active or text[candidate+i]==code[i] for i,active in enumerate(mask)):
                found.append(hex(base+candidate))
        rows.append(dict(selector=selector,symbol=name,editorAddress=hex(address),maskedBytes=len(code),knownBytes=sum(mask),gameCandidates=found,unique=len(found)==1,mnemonics=signature,abiVerified=False))
        print(selector,'candidates',found[:8],flush=True)
    job=ROOT/'build/probe'/('game-functions-'+uuid.uuid4().hex[:12]);job.mkdir(parents=True)
    report=dict(editorSHA256=digest(editor),mapSHA256=digest(mapping),gameSHA256=digest(game),method='exact relocation-masked instruction bytes; offline candidates only',functions=rows,observedGameplay=False)
    write_json(job/'evidence.json',report);print(job);return report
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('selectors',nargs='+');probe(p.parse_args().selectors)
