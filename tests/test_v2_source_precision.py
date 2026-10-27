"""Precision restoration guards against altering stock/seam or other attributes."""
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import v2_source_precision as precision


class Fixture:
    def __init__(self, root):
        self.root = Path(root)
        self.authored = np.asarray([[.1, .1, .1], [.200001, .1, .1], [.2, .300001, .1], [.1, .3, .200001]])
        uv = np.asarray([[.1, .2], [.3, .4], [.5, .6], [.7, .8]])
        faces = np.asarray([[0, 1, 2], [0, 2, 3]], np.int64)
        for lod in (0, 1):
            np.savez(self.root / ('lod%d.npz' % lod), bodyCount=1,
                     points=np.vstack([self.authored[0], self.authored]) * 100,
                     module_data=np.ones(4), module_indices=np.arange(4), module_indptr=np.arange(5), module_shape=[4, 4],
                     moduleOriginalUV=uv, faces=faces + 1, seamBody=np.asarray([0]))
        self.sections = []
        raw = bytearray()
        rows = []
        index_blocks = []
        first = 0
        indexfirst = 0
        for lod in (0, 1):
            for material in (0, 1, 2):
                points = self.authored if material else self.authored[:1]
                n = len(points)
                quant = np.rint(points * 65535).astype('<u2')
                position = len(raw)
                qwords = np.zeros((n, 8), '<u2')
                qwords[:, :3] = quant
                raw += qwords.tobytes()
                uv_offset = len(raw)
                raw += np.asarray(uv if material else uv[:1], '<f2').tobytes()
                tris = faces[:, [0, 2, 1]] if material else np.zeros((1, 3), int)
                if material == 2:
                    tris = np.vstack([tris, tris[:1]])
                self.sections.append(dict(lod=lod, material=material, firstVertex=first, vertexCount=n,
                                          positionOffset=position, uvOffset=uv_offset, lightingOffset=0, extraOffset=0,
                                          indexFirst=indexfirst, indexCount=tris.size))
                index_blocks.append(np.asarray(tris, '<u2').tobytes())
                for q in quant:
                    # Distinct opaque attributes make accidental rewrites visible.
                    rows.append(struct.pack('<3f', *(q.astype(float) / 65535)) + bytes(range(12, 52)))
                first += n
                indexfirst += tris.size
        self.index_offset = len(raw)
        raw += b''.join(index_blocks)
        self.cooked = self.root / 'fixture.w2mesh'
        self.cooked.write_bytes(b'fixture native metadata')
        Path(str(self.cooked) + '.1.buffer').write_bytes(raw)
        self.scale = (1, 1, 1)
        self.offset = (0, 0, 0)
        self.mesh = self
        self.payload = b'MMV2B04\0' + struct.pack('<I15fI', 2, *([0.] * 15), 1) + bytes(36)
        self.payload += self.resource(rows, self.sections)
        dummy = [dict(lod=lod, material=0, firstVertex=lod, vertexCount=1, positionOffset=0, uvOffset=0,
                      lightingOffset=0, extraOffset=0, indexFirst=lod * 3, indexCount=3) for lod in (0, 1)]
        self.payload += self.resource([rows[0], rows[0]], dummy)

    def resource(self, rows, sections):
        data = struct.pack('<5I6f8I', len(rows), 6, 100, 0, 0, 1, 1, 1, 0, 0, 0, *([0] * 8))
        data += struct.pack('<I', len(sections))
        for s in sections:
            data += struct.pack('<10I', *(s[k] for k in ('lod', 'material', 'firstVertex', 'vertexCount', 'positionOffset', 'uvOffset', 'lightingOffset', 'extraOffset', 'indexFirst', 'indexCount')))
        return data + struct.pack('<I', 0) + b''.join(rows)

    def get(self, *unused):
        return struct.pack('<I', self.index_offset)

    @property
    def cooked(self):
        return self._cooked

    @cooked.setter
    def cooked(self, value):
        self._cooked = value

    def skin_sections(self, unused):
        return self.sections


class SourcePrecisionTests(unittest.TestCase):
    def test_stock_seam_and_all_nonposition_bytes_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            f = Fixture(folder)
            with patch.object(precision, 'CookedMesh', return_value=f):
                result, report = precision.restore_payload(f.payload, folder, f.cooked)
            self.assertNotEqual(result, f.payload)
            rr = precision.parse_b04(f.payload)
            allowed = np.zeros(len(result), bool)
            for s in f.sections:
                if not s['material']:
                    continue
                # First module vertex is the seam and must stay exact.
                for row in range(s['firstVertex'] + 1, s['firstVertex'] + 4):
                    start = rr[0]['rowoffset'] + row * 52
                    allowed[start:start + 12] = True
            a, b = np.frombuffer(f.payload, 'u1'), np.frombuffer(result, 'u1')
            self.assertFalse(np.any((a != b) & ~allowed))
            self.assertEqual(report['protectedRows'], 8)
            self.assertTrue(report['stockBodyAndSharedSeamRowsByteIdentical'])
            self.assertTrue(all(x['maximumCorrectionMeters'] < 3e-5 for x in report['sections']))

    def test_legacy_b03_is_rejected_before_replacement(self):
        with self.assertRaisesRegex(ValueError, 'B04'):
            precision.parse_b04(b'MMV2B03\0' + bytes(100))

    def test_wrong_topology_is_rejected(self):
        authored = np.asarray([[0, 0, 0], [1, 0, 0], [0, 1, 0.]])
        uv = np.asarray([[.1, .2], [.3, .4], [.5, .6]])
        with self.assertRaisesRegex(ValueError, 'topology'):
            precision.match_source_rows(authored, uv, [[0, 2, 1]], authored, uv, [[0, 1, 2]])

    def test_close_uv_alias_is_resolved_by_oriented_topology(self):
        authored = np.asarray([[0, 0, 0], [1e-6, 0, 0], [0, 1, 0], [0, 0, 1.]])
        uv = np.asarray([[.1, .2], [.1, .2], [.3, .4], [.5, .6]])
        ids, report = precision.match_source_rows(authored[[1, 2, 3]], uv[[1, 2, 3]], [[0, 1, 2]], authored, uv, [[1, 2, 3]])
        np.testing.assert_array_equal(ids, [1, 2, 3])
        self.assertEqual(report['topologyResolvedRows'], 1)

    def test_distant_geometry_rejected_without_touching_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            f = Fixture(folder)
            with np.load(Path(folder) / 'lod0.npz') as fit:
                data = {k: fit[k] for k in fit.files}
            data['points'] = data['points'].copy()
            data['points'][2] += 1
            np.savez(Path(folder) / 'lod0.npz', **data)
            binding = Path(folder) / 'binding.bin'
            binding.write_bytes(f.payload)
            with patch.object(precision, 'CookedMesh', return_value=f), self.assertRaisesRegex(ValueError, 'donor'):
                precision.restore_binding(binding, folder, f.cooked, Path(folder) / 'proof.json')
            self.assertEqual(binding.read_bytes(), f.payload)

    def test_excessive_baseline_correction_rejected_without_write(self):
        with tempfile.TemporaryDirectory() as folder:
            f = Fixture(folder)
            raw = bytearray(f.payload)
            start = precision.parse_b04(raw)[0]['rowoffset'] + 2 * 52
            struct.pack_into('<f', raw, start, .21)
            binding = Path(folder) / 'binding.bin'
            binding.write_bytes(raw)
            with patch.object(precision, 'CookedMesh', return_value=f), self.assertRaisesRegex(ValueError, 'correction exceeds'):
                precision.restore_binding(binding, folder, f.cooked, Path(folder) / 'proof.json')
            self.assertEqual(binding.read_bytes(), bytes(raw))


if __name__ == '__main__':
    unittest.main()
