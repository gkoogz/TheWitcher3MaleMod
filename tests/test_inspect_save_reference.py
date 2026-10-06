import math
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from inspect_save_reference import facts, signed_vlq


def string(raw, ascii_string=True):
    n = len(raw) if ascii_string else len(raw)//2
    head = (n & 63) | (128 if ascii_string else 0) | (64 if n > 63 else 0)
    out = bytearray([head]); n >>= 6
    while n:
        out.append((n & 127) | (128 if n > 127 else 0)); n >>= 7
    return bytes(out)+raw


def record(raw, ascii_string=True, value=1, expires=-1):
    return string(raw, ascii_string)+struct.pack('<HHhff', 0, 1, value, 123.5, expires)


def stream(records):
    return b'SBDF'+struct.pack('<I', len(records))+b''.join(records)+b'EBDF'


class NativeSaveFactsTests(unittest.TestCase):
    def test_long_ascii_names_use_six_then_seven_bit_groups(self):
        raw=b'tutorial_'+b'a'*327
        rows=facts(stream([record(raw),record(b'started_new_game')]))
        self.assertEqual(rows[0]['name'],raw.decode())
        self.assertEqual(rows[1]['entries'][0]['value'],1)
        self.assertTrue(all(r['namedFact'] for r in rows))

    def test_nontext_native_codeunits_preserved_without_named_fact(self):
        raw=b'\x00\xd8'+b'\x00\x00'*326
        rows=facts(stream([record(raw,False),record(b'tut_stash_fresh_playthrough')]))
        self.assertFalse(rows[0]['namedFact'])
        self.assertEqual(rows[0]['name'].encode('utf-16-le','surrogatepass'),raw)
        self.assertTrue(rows[1]['namedFact'])

    def test_truncation_count_and_terminator_rejected(self):
        valid=stream([record(b'example')])
        for invalid in [valid[:-1],valid+b'x',valid[:4]+struct.pack('<I',2)+valid[8:],b'XXXX'+valid[4:]]:
            with self.assertRaises(ValueError):facts(invalid)

    def test_time_and_expiring_count_rejected(self):
        with self.assertRaises(ValueError):facts(stream([record(b'example',expires=math.nan)]))
        with self.assertRaises(ValueError):facts(stream([string(b'x')+struct.pack('<HH',2,1)+struct.pack('<hff',1,1,-1)]))

    def test_compact_integer_truncation_and_overflow_rejected(self):
        for invalid in [b'\x40',b'\x40\x80',b'\x7f\xff\xff\xff\xff']:
            with self.assertRaises(ValueError):signed_vlq(invalid,0)


if __name__=='__main__':unittest.main()
