"""Read an existing owned diagnostic dump; never attach to or alter a process.

Reports the exception record's AMD64 context rather than a dumper-thread context.
Stack addresses are candidates, explicitly not an unwound call stack.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from minidump.minidumpfile import MinidumpFile


def inspect(path):
    path = Path(path)
    dump = MinidumpFile.parse(str(path))
    if not dump.exception or len(dump.exception.exception_records) != 1:
        raise ValueError('Expected exactly one exception context')
    exception = dump.exception.exception_records[0]
    if dump.sysinfo.ProcessorArchitecture.name != 'AMD64':
        raise ValueError('Only measured AMD64 context layout is supported')
    dump.file_handle.seek(exception.ThreadContext.Rva)
    context = dump.file_handle.read(exception.ThreadContext.DataSize)
    if len(context) < 256:
        raise ValueError('Truncated AMD64 context')
    names = ('rax rcx rdx rbx rsp rbp rsi rdi r8 r9 r10 r11 r12 r13 r14 r15 rip').split()
    registers = {name: struct.unpack_from('<Q', context, offset)[0]
                 for name, offset in zip(names, range(120, 249, 8))}
    if registers['rip'] != exception.ExceptionRecord.ExceptionAddress:
        raise ValueError('Exception/context addresses disagree')
    def module(address):
        matches = [item for item in dump.modules.modules
                   if item.baseaddress <= address < item.endaddress]
        if len(matches) != 1:
            return None
        item = matches[0]
        return dict(path=item.name, base=hex(item.baseaddress), rva=hex(address-item.baseaddress))
    thread = next(item for item in dump.threads.threads if item.ThreadId == exception.ThreadId)
    stack_end = thread.Stack.StartOfMemoryRange + thread.Stack.DataSize
    if not thread.Stack.StartOfMemoryRange <= registers['rsp'] <= stack_end:
        raise ValueError('Exception stack pointer outside captured thread stack')
    data = dump.get_reader().read(registers['rsp'], min(4096, stack_end-registers['rsp']))
    candidates = []
    for offset in range(0, len(data)-7, 8):
        address = struct.unpack_from('<Q', data, offset)[0]
        owner = module(address)
        if owner:
            candidates.append(dict(stackOffset=hex(offset), address=hex(address), **owner))
    return dict(schema='malemod.private-exception/1', dump=str(path.resolve()),
                dumpSHA256=hashlib.sha256(path.read_bytes()).hexdigest(),
                thread=exception.ThreadId, code=hex(exception.ExceptionRecord.ExceptionCode_raw),
                information=exception.ExceptionRecord.ExceptionInformation,
                registers={key: hex(value) for key, value in registers.items()},
                exceptionModule=module(registers['rip']),
                stackCandidates=candidates, unwound=False, processModified=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dump', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.dump)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in ('thread', 'code', 'exceptionModule', 'registers')}, indent=2))
