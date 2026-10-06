"""Native ownership tail validation; these fixtures do not prove gameplay."""
from pathlib import Path
import struct
import sys
import unittest
import zlib
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from iteration_layer_ownership import inspect_layers
from player_rig_redirect import header_crc


def fixture(owner=1, parent=0, info_parent=2, floor='levels/own/floor.w2l', extra=b'', root=2):
    names = ['', 'CGameWorld', 'CLayerGroup', 'CLayerInfo', 'hasEmbeddedLayerInfos',
             'hasEmbeddedLayerInfo', 'Bool', 'String', 'depotFilePath']
    strings = b''; offsets = []
    for name in names:
        offsets.append(len(strings)); strings += name.encode() + b'\0'
    def prop(name, kind, value):
        return struct.pack('<HHI', names.index(name), names.index(kind), 4 + len(value)) + value
    world = b'\0' + prop('hasEmbeddedLayerInfos', 'Bool', b'\1') + b'\0\0' + struct.pack('<i', root)
    group = b'\0' + prop('hasEmbeddedLayerInfos', 'Bool', b'\1') + b'\0\0' + struct.pack('<ii', owner, parent) + b'\0\1' + struct.pack('<i', 3) + extra
    text = bytes([128 + len(floor)]) + floor.encode()
    info = b'\0' + prop('hasEmbeddedLayerInfo', 'Bool', b'\1') + prop('depotFilePath', 'String', text) + b'\0\0' + struct.pack('<i', info_parent)
    name_table = b''.join(struct.pack('<II', at, 0) for at in offsets)
    at = 160 + len(strings) + len(name_table) + 3 * 24
    exports = b''
    for kind, data in [('CGameWorld', world), ('CLayerGroup', group), ('CLayerInfo', info)]:
        exports += struct.pack('<HHIIIII', names.index(kind), 0, 0, len(data), at, 0, zlib.crc32(data)); at += len(data)
    raw = bytearray(160) + strings + name_table + exports + world + group + info
    raw[:4] = b'CR2W'; struct.pack_into('<I', raw, 4, 164)
    at = 160
    for index, data, stride in [(0, strings, 1), (1, name_table, 8), (4, exports, 24)]:
        struct.pack_into('<III', raw, 40 + 12 * index, at, len(data) // stride, zlib.crc32(data)); at += len(data)
    struct.pack_into('<I', raw, 32, header_crc(raw, 0))
    return raw


class OwnershipTests(unittest.TestCase):
    def test_actual_root_world_floor_parent_chain(self):
        result = inspect_layers(fixture(), 'levels/own/floor.w2l')
        self.assertEqual((result['worldExport'], result['rootExport'], result['floorInfoExport']), (1, 2, 3))

    def test_null_wrong_class_and_inconsistent_parent_rejected(self):
        for args in (dict(root=0), dict(root=3), dict(owner=0), dict(parent=1), dict(info_parent=1)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                inspect_layers(fixture(**args), 'levels/own/floor.w2l')

    def test_missing_floor_and_duplicate_tail_rejected(self):
        for args in (dict(floor='levels/other/floor.w2l'), dict(extra=b'\0')):
            with self.subTest(args=args), self.assertRaises(ValueError):
                inspect_layers(fixture(**args), 'levels/own/floor.w2l')

    def test_crc_and_bounds_rejected(self):
        damaged = fixture(); damaged[-1] ^= 1
        for data in (damaged, fixture()[:-1]):
            with self.assertRaises(ValueError):
                inspect_layers(data, 'levels/own/floor.w2l')


if __name__ == '__main__':
    unittest.main()
