"""Guard the calibrated native encodings against silent pose corruption."""
import struct
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from audit_animation_skinning import track_frame


def track(compression,address=0,frames=1):
    node=ET.Element('object');props=ET.SubElement(node,'properties')
    for name,value in dict(compression=compression,dataAddr=address,
                           dataAddrFallback=address,numFrames=frames).items():
        ET.SubElement(props,'prop',name=name).text=str(value)
    return node


class AnimationDecodingTests(unittest.TestCase):
    def test_truncated_float_bits_are_not_half_floats_or_normalized_ints(self):
        for compression in (0,1,2):
            bits=[struct.unpack('<I',struct.pack('<f',v))[0] for v in (1.,-2.,.5)]
            width=4-compression
            data=b''.join((b>>(8*compression)).to_bytes(width,'little') for b in bits)
            np.testing.assert_array_equal(track_frame(track(compression),data,0,1),[1.,-2.,.5])

    def test_quaternion_sign_uses_stored_z_bit(self):
        positive=struct.pack('<fff',0.,0.,0.)
        negative=positive[:8]+bytes([1])+positive[9:]
        self.assertEqual(track_frame(track(0),positive,0,1,True)[3],1.)
        self.assertEqual(track_frame(track(0),negative,0,1,True)[3],-1.)

    def test_absent_stream_and_unknown_compression_fail(self):
        for node,data in [(track(3),b'\0'*12),(track(0,100),b'\0'*12),
                          (track(0,frames=2),b'\0'*24)]:
            with self.assertRaises(ValueError):track_frame(node,data,0,3)

    def test_streamed_tail_uses_explicit_native_fallback(self):
        node=track(0,12,31)
        data=struct.pack('<fff',1.,2.,3.)
        fallback=struct.pack('<fff',4.,5.,6.)
        np.testing.assert_array_equal(track_frame(node,data,30,31,fallback=fallback),[4.,5.,6.])
