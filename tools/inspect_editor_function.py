"""Read-only offline inspection of a named REDkit editor function.

Never attaches to a process or writes to the SDK. Disassembly is diagnostic,
not evidence of gameplay support. Output stays in the ignored build tree.
"""
import argparse
import mmap
import re
import uuid
import pefile
import capstone
from mod import ROOT, settings, digest, write_json


def inspect(symbol):
    cfg = settings()
    executable = cfg['redkit'] / 'bin/x64_RedKit/editor.exe'
    symbols = executable.with_suffix('.map')
    functions = []
    for line in symbols.read_text(errors='replace').splitlines():
        match = re.match(r'\s+0001:[0-9a-f]+\s+(\S+)\s+([0-9a-f]{16})\s+f\s', line)
        if match:
            functions.append((int(match[2], 16), match[1]))
    matches = [(a, n) for a, n in functions if symbol in n]
    if len(matches) != 1:
        raise ValueError('Expected one symbol: ' + repr(matches))
    address, name = matches[0]
    end = min(a for a, _ in functions if a > address)
    job = ROOT / 'build/probe' / ('disassembly-' + uuid.uuid4().hex[:12])
    job.mkdir(parents=True)
    with executable.open('rb') as source, mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as data:
        pe = pefile.PE(data=data[:4096], fast_load=True)
        offset = pe.get_offset_from_rva(address - pe.OPTIONAL_HEADER.ImageBase)
        decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        result = '\n'.join('%x: %s %s' % (i.address, i.mnemonic, i.op_str)
                           for i in decoder.disasm(data[offset:offset + end-address], address))
    output = job / 'function.txt'
    output.write_text(result, encoding='utf-8')
    write_json(job / 'evidence.json', dict(symbol=name, address=hex(address),
               nextSymbolAddress=hex(end), executableSHA256=digest(executable),
               mapSHA256=digest(symbols), observedGameplay=False))
    print(output)
    print(result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('symbol')
    inspect(parser.parse_args().symbol)
