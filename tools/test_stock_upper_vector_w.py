"""Guard tests against actual private licensed mesh bytes; never writes them."""
import argparse
import struct
import unittest
import zlib
from pathlib import Path
from player_rig_redirect import header_crc
from stock_upper_vector_w import typed_layout, compare_bytes


def valid_crcs(raw):
    data = bytearray(raw)
    offset, count, _ = struct.unpack_from('<III', data, 88)
    for i in range(count):
        entry = offset + i * 24
        size, position = struct.unpack_from('<II', data, entry + 8)
        struct.pack_into('<I', data, entry + 20, zlib.crc32(data[position:position + size]))
    struct.pack_into('<I', data, 96, zlib.crc32(data[offset:offset + count * 24]))
    struct.pack_into('<I', data, 32, header_crc(data, 0))
    return bytes(data)


class Guard(unittest.TestCase):
    def test_actual_observed_pair(self):
        self.assertTrue(compare_bytes(BASE, CANDIDATE, GPU, GPU)['allSpatialXYZBytesIdentical'])

    def test_exact_w_words_with_valid_crcs(self):
        changed = bytearray(BASE)
        for at in typed_layout(BASE)[0].values():
            changed[at:at + 4] = bytes.fromhex('12345678')
        self.assertTrue(compare_bytes(BASE, valid_crcs(changed), GPU, GPU)['headerAndExportCRCsVerified'])

    def test_spatial_xyz_rejected_even_with_valid_crcs(self):
        for at in typed_layout(BASE)[2].values():
            changed = bytearray(BASE)
            changed[at] ^= 1
            with self.assertRaises(ValueError):
                compare_bytes(BASE, valid_crcs(changed), GPU, GPU)

    def test_other_property_rejected_even_with_valid_crcs(self):
        changed = bytearray(BASE)
        # A changed import-table byte remains outside the exact typed exception.
        offset, size, _ = struct.unpack_from('<III', changed, 40)
        changed[offset] ^= 1
        struct.pack_into('<I', changed, 48, zlib.crc32(changed[offset:offset + size]))
        with self.assertRaises(ValueError):
            compare_bytes(BASE, valid_crcs(changed), GPU, GPU)

    def test_invalid_crc_rejected(self):
        changed = bytearray(BASE)
        changed[next(iter(typed_layout(BASE)[0].values()))] ^= 1
        with self.assertRaises(ValueError):
            compare_bytes(BASE, bytes(changed), GPU, GPU)

    def test_gpu_or_length_change_rejected(self):
        with self.assertRaises(ValueError):
            compare_bytes(BASE, BASE, GPU, GPU[:-1])
        with self.assertRaises(ValueError):
            compare_bytes(BASE, BASE[:-1], GPU, GPU)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    args = parser.parse_args()
    BASE, CANDIDATE = args.baseline.read_bytes(), args.candidate.read_bytes()
    GPU = Path(str(args.baseline) + '.1.buffer').read_bytes()
    unittest.main(argv=[__file__])
