"""Read a hash-verified owned save copy; never load or change an original save.

The facts layout is independently measured from the REDkit CFactsDB::StreamSave
and IFile/TString operators. Results are reference data, not bootstrap fixes.
Raw native UTF16 code units are preserved, including nontext keys; only ordinary
printable names may be considered named facts. No facts are applied to a game.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct


def take(data, offset, size):
    if size < 0 or offset < 0 or offset + size > len(data):
        raise ValueError('Truncated native facts stream')
    return data[offset:offset+size], offset+size


def signed_vlq(data, offset):
    raw, offset = take(data, offset, 1)
    first = raw[0]
    value, shift, more = first & 63, 6, first & 64
    while more:
        raw, offset = take(data, offset, 1)
        value |= (raw[0] & 127) << shift
        shift += 7
        more = raw[0] & 128
        if shift > 34 or value > 0x7fffffff:
            raise ValueError('Invalid signed native string length')
    return (-value if first & 128 else value), offset


def facts(data):
    if len(data) < 12 or data[:4] != b'SBDF':
        raise ValueError('Missing native facts header')
    count = struct.unpack_from('<I', data, 4)[0]
    if count > (len(data)-12)//5:
        raise ValueError('Impossible native facts count')
    offset, rows = 8, []
    for _ in range(count):
        start = offset
        length, offset = signed_vlq(data, offset)
        ascii_string = length < 0
        raw, offset = take(data, offset, abs(length)*(1 if ascii_string else 2))
        name = raw.decode('latin1' if ascii_string else 'utf-16-le', errors='surrogatepass')
        counts, offset = take(data, offset, 4)
        expiring, entries = struct.unpack('<HH', counts)
        if expiring > entries:
            raise ValueError('Native expiring fact count exceeds entries')
        values = []
        for _ in range(entries):
            raw_value, offset = take(data, offset, 10)
            value, added, expires = struct.unpack('<hff', raw_value)
            if not math.isfinite(added) or not math.isfinite(expires):
                raise ValueError('Nonfinite native fact time')
            values.append(dict(value=value, addedSeconds=added, expiresSeconds=expires))
        printable = bool(name) and all(32 <= ord(c) < 127 for c in name)
        rows.append(dict(name=name, namedFact=printable, nativeStringEncoding=
                         'ASCII' if ascii_string else 'UTF16-codeunits',
                         offset=start, expiringCount=expiring, entries=values))
    if data[offset:] != b'EBDF':
        raise ValueError('Native facts count/terminator/trailing bytes differ')
    return rows


def extract(save):
    import lz4.block
    if len(save) < 28 or save[:8] != b'SNFHFZLC':
        raise ValueError('Unsupported save container')
    count, header = struct.unpack_from('<II', save, 8)
    if count != 1:
        raise ValueError('This reference reader supports one native LZ4 chunk only')
    compressed, expanded, end = struct.unpack_from('<III', save, 16)
    if header < 28 or header+compressed != len(save) or expanded > 64*1024*1024 or end != 0:
        raise ValueError('Native save chunk boundaries differ')
    payload = lz4.block.decompress(save[header:], uncompressed_size=expanded)
    if len(payload) != expanded or payload.count(b'SBDF') != 1 or payload.count(b'EBDF') != 1:
        raise ValueError('Native facts block is absent or ambiguous')
    start, end = payload.index(b'SBDF'), payload.index(b'EBDF')+4
    return payload[start:end]


def inspect(copy, receipt, output):
    copy, receipt, output = map(lambda p: Path(p).resolve(), (copy, receipt, output))
    if copy.parent != receipt.parent or output.parent != receipt.parent:
        raise ValueError('Use only the existing owned reference-copy directory')
    proof = json.loads(receipt.read_text(encoding='utf-8'))
    matches = [r for r in proof['files'] if Path(r['copy']).resolve() == copy]
    source = copy.read_bytes()
    sha = hashlib.sha256(source).hexdigest()
    if len(matches) != 1 or matches[0]['sha256'] != sha or Path(matches[0]['original']).resolve() == copy:
        raise ValueError('Reference copy hash or original/copy identity differs')
    raw = extract(source)
    rows = facts(raw)
    result = dict(schema='malemod.native-save-facts-reference/1', sourceCopy=str(copy),
                  sourceSHA256=sha, readerSHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  factsSHA256=hashlib.sha256(raw).hexdigest(), recordCount=len(rows),
                  completeStructureVerified=True, nativeTerminatorVerified=True,
                  nontextNames=sum(not r['namedFact'] for r in rows),
                  originalsLoaded=False, originalsModified=False, factsApplied=[], facts=rows)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=True)+'\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k != 'facts'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--copy', required=True, type=Path)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    inspect(args.copy, args.receipt, args.output)
