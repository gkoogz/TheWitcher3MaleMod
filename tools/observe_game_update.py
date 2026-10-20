"""Observe a new retail ABI from the exact previously supported executable.

No process access or game writes. Relocations are masked only for comparison;
new function starts, prefixes and opcode-table references are recorded exactly.
"""
import argparse
import bisect
import hashlib
import json
from pathlib import Path
import re
import struct

import capstone
import numpy as np
import pefile


class Image:
    def __init__(self, path):
        self.path = Path(path)
        self.raw = self.path.read_bytes()
        self.sha = hashlib.sha256(self.raw).hexdigest()
        self.pe = pefile.PE(data=self.raw, fast_load=True)
        section = next(s for s in self.pe.sections if s.Name.rstrip(b'\0') == b'.text')
        self.text, self.text_rva = section.get_data(), section.VirtualAddress
        directory = self.pe.OPTIONAL_HEADER.DATA_DIRECTORY[3]
        self.bounds = {a: b for a, b, _ in struct.iter_unpack(
            '<III', self.pe.get_data(directory.VirtualAddress, directory.Size))}
        self.starts = sorted(self.bounds)
        self.decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        self.decoder.detail = True

    def instructions(self, rva):
        return list(self.decoder.disasm(self.pe.get_data(rva, self.bounds[rva] - rva), rva))

    def masked(self, rva, limit=None):
        result = []
        for ins in self.instructions(rva):
            if limit is not None and len(result) + ins.size > limit:
                break
            data = list(ins.bytes)
            if any(o.type == capstone.x86.X86_OP_MEM and o.mem.base == capstone.x86.X86_REG_RIP
                   for o in ins.operands):
                data[ins.disp_offset:ins.disp_offset + ins.disp_size] = [None] * ins.disp_size
            if ins.group(capstone.CS_GRP_CALL) or ins.group(capstone.CS_GRP_JUMP):
                data[ins.imm_offset:ins.imm_offset + ins.imm_size] = [None] * ins.imm_size
            result.extend(data)
        return result

    def matches(self, signature):
        pattern = b''.join(b'.' if v is None else re.escape(bytes([v])) for v in signature)
        return [self.text_rva + m.start() for m in re.finditer(pattern, self.text, re.DOTALL)
                if self.text_rva + m.start() in self.bounds]

    def rip_refs(self, target):
        refs = []
        for alignment in range(4):
            count = (len(self.text) - alignment) // 4
            values = np.frombuffer(self.text, dtype='<i4', count=count, offset=alignment).astype(np.int64)
            locations = self.text_rva + alignment + np.arange(count, dtype=np.int64) * 4
            for hit in np.flatnonzero(locations + 4 + values == target):
                rva = int(locations[hit])
                index = bisect.bisect_right(self.starts, rva) - 1
                if index < 0:
                    continue
                start = self.starts[index]
                if rva >= self.bounds[start]:
                    continue
                for ins in self.instructions(start):
                    if ins.address <= rva < ins.address + ins.size and any(
                        o.type == capstone.x86.X86_OP_MEM and o.mem.base == capstone.x86.X86_REG_RIP
                        and ins.address + ins.size + o.mem.disp == target for o in ins.operands):
                        refs.append((start, ins.address - start))
        return sorted(set(refs))


def observe(old_path, new_path, profile_path):
    old, new = Image(old_path), Image(new_path)
    profile = json.loads(Path(profile_path).read_text())
    if old.sha != profile['gameSHA256']:
        raise ValueError('Reference executable differs from the observed old ABI')
    old_register = int(profile['functions']['registerGlobals']['rva'], 0)
    matches = new.matches(old.masked(old_register, 256))
    if len(matches) != 1:
        raise ValueError('Global registration is missing or ambiguous')
    new_register = matches[0]
    if old.masked(old_register) != new.masked(new_register):
        raise ValueError('Global registration instruction/layout changed')
    calls = {}
    for a, b in zip(old.instructions(old_register), new.instructions(new_register)):
        if a.mnemonic == 'call' and a.operands[0].type == capstone.x86.X86_OP_IMM:
            calls.setdefault(a.operands[0].imm, set()).add(b.operands[0].imm)
    rows = {}
    for name, item in profile['functions'].items():
        before = int(item['rva'], 0)
        candidates = {new_register} if name == 'registerGlobals' else calls.get(before, set())
        if len(candidates) != 1:
            raise ValueError('Call-context mapping is missing or ambiguous: ' + name)
        after = next(iter(candidates))
        if after not in new.bounds or old.masked(before) != new.masked(after):
            raise ValueError('Function instruction/layout changed: ' + name)
        rows[name] = dict(rva=hex(after), prefix=new.pe.get_data(after, 16).hex(),
                          previousRVA=hex(before), normalizedCompleteFunctionEqual=True,
                          length=new.bounds[after] - after)
    table_refs = []
    table_targets = set()
    for before, offset in old.rip_refs(profile['opcodeTableRVA']):
        candidates = new.matches(old.masked(before, 256))
        if len(candidates) != 1:
            continue
        after = candidates[0]
        if old.masked(before) != new.masked(after):
            continue
        ins = next(i for i in new.instructions(after) if i.address == after + offset)
        operands = [o for o in ins.operands if o.type == capstone.x86.X86_OP_MEM
                    and o.mem.base == capstone.x86.X86_REG_RIP]
        if len(operands) != 1:
            raise ValueError('Opcode reference instruction changed')
        target = ins.address + ins.size + operands[0].mem.disp
        table_targets.add(target)
        table_refs.append(dict(previousFunction=hex(before), function=hex(after),
                               instruction=hex(ins.address), target=hex(target),
                               normalizedCompleteFunctionEqual=True))
    if len(table_targets) != 1 or len(table_refs) < 2:
        raise ValueError('Opcode table needs independent consistent observed references')
    return dict(schema='malemod.retail-abi-update/1', previousGameSHA256=old.sha,
                gameSHA256=new.sha, imageSize=new.pe.OPTIONAL_HEADER.SizeOfImage,
                entryPointRVA=new.pe.OPTIONAL_HEADER.AddressOfEntryPoint,
                entryPointPrefix=new.pe.get_data(new.pe.OPTIONAL_HEADER.AddressOfEntryPoint, 14).hex(),
                opcodeTableRVA=next(iter(table_targets)), functions=rows,
                opcodeReferences=table_refs, runtimeVerified=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous', required=True, type=Path)
    parser.add_argument('--current', required=True, type=Path)
    parser.add_argument('--profile', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = observe(args.previous, args.current, args.profile)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(gameSHA256=result['gameSHA256'],
                          functions=len(result['functions']),
                          opcodeReferences=len(result['opcodeReferences']),
                          output=str(args.output))))
