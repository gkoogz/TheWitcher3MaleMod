"""Narrow observed stock torso cook comparison; never changes resource bytes."""
import struct
from pathlib import Path
from build_v2_detail_package import property_span
from packed_mesh_format import CookedMesh
from mod import digest


def typed_layout(raw):
    reader = CookedMesh(raw, allow_stock_torso_mapping=True, allow_multi_section=True)
    offset, count, _ = struct.unpack_from('<III', raw, 88)
    entries = list(struct.iter_unpack('<HHIIIII', raw[offset:offset + count * 24]))
    found = [i for i, entry in enumerate(entries) if reader.names[entry[0]] == 'CMesh']
    if len(found) != 1:
        raise ValueError('Expected one CRC-checked stock torso CMesh')
    index = found[0]
    entry = entries[index]
    box, length = property_span(raw, reader, entry[4], entry[3], 'boundingBox', 'Box')
    words, spatial = {}, {}
    for label in ('Min', 'Max'):
        vector, size = property_span(raw, reader, box, length, label, 'Vector')
        for axis in ('X', 'Y', 'Z', 'W'):
            word, size_word = property_span(raw, reader, vector, size, axis, 'Float')
            if size_word != 4:
                raise ValueError('Expected one typed Vector float word')
            (words if axis == 'W' else spatial)[label + '.' + axis] = word
    return words, dict(headerCRC=32, exportTableCRC=96, meshExportCRC=offset + index * 24 + 20), spatial


def compare_bytes(before, after, before_gpu, after_gpu):
    if len(before) != len(after) or before_gpu != after_gpu:
        raise ValueError('Stock torso size or GPU buffer changed')
    old, new = typed_layout(before), typed_layout(after)
    if old != new:
        raise ValueError('Stock torso typed layout changed')
    words, crcs, _ = old
    allowed = {offset + byte for offset in [*words.values(), *crcs.values()] for byte in range(4)}
    changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    if any(i not in allowed for i in changed):
        raise ValueError('Stock torso changed outside exact Min.W/Max.W and derived CRC words')
    return dict(schema='malemod.stock-upper-two-vector-W-equivalence/1',
        onlyAllowedSerializedFields=['CMesh.boundingBox:Box.Min:Vector.W:Float', 'CMesh.boundingBox:Box.Max:Vector.W:Float'],
        typedWordOffsets=words, derivedCRCOffsets=crcs, changedByteOffsets=changed,
        beforeAndAfterWordHex={key: [before[at:at + 4].hex(), after[at:at + 4].hex()] for key, at in words.items()},
        GPUBufferByteIdentical=True, allSpatialXYZBytesIdentical=True, allOtherFileBytesIdentical=True,
        headerAndExportCRCsVerified=True, noFileBytesPatched=True, epsilonUsed=False,
        scope='Observed official cook W-lane metadata differences only. Universal engine W usage is unobserved; native visibility/LOD gates remain required.')


def audit_upper(before, after):
    before, after = Path(before), Path(after)
    a, b = Path(str(before) + '.1.buffer'), Path(str(after) + '.1.buffer')
    return dict(compare_bytes(before.read_bytes(), after.read_bytes(), a.read_bytes(), b.read_bytes()),
        baselineSHA256=digest(before), candidateSHA256=digest(after), GPUBufferSHA256=digest(b))
