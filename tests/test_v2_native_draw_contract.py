import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

_spec = importlib.util.spec_from_file_location(
    'v2_native_draw_contract', Path(__file__).resolve().parents[1] / 'tools/v2_native_draw_contract.py')
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)


class NativeDrawContractTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.binding, self.metadata, self.topology, self.output = [
            root / name for name in ['binding.bin', 'metadata.json', 'topology.bin', 'contract.inc']]
        blob = bytearray(76)
        blob[:8] = b'MMV2B03\0'
        struct.pack_into('<I', blob, 8, 2)
        for _ in range(2):
            blob.extend(struct.pack('<5I6f8II', 6, 12, 0, 0, 0,
                                    1, 1, 1, 0, 0, 0,
                                    0, 3, 3, 3, 48, 120, 84, 156, 0))
            blob.extend(bytes(6 * 52))
        self.binding.write_bytes(blob)
        self.topology.write_bytes(b'MMV2T01\0' + struct.pack('<II10I', 12, 2, 0, 1, 2, 0, 0, 6, 7, 8, 1, 0))
        self.report = {'sourceBindingSHA256': self.hash(self.binding),
                       'topologySHA256': self.hash(self.topology),
                       'resources': [{'vertices': 3, 'triangles': 1}, {'vertices': 3, 'triangles': 1}]}
        self.save_report()

    @staticmethod
    def hash(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def save_report(self):
        self.metadata.write_text(json.dumps(self.report))

    def generate(self):
        return _module.generate(self.binding, self.metadata, self.topology, self.output)

    def test_emission_and_determinism(self):
        self.assertEqual(self.generate(), [(6, 12, (0, 3), (3, 3), (0, 3), (3, 3))] * 2)
        emitted = self.output.read_text()
        self.assertIn(self.hash(self.metadata), emitted)
        self.generate()
        self.assertEqual(self.output.read_text(), emitted)

    def test_binding_hash_rejected_before_emission(self):
        self.binding.write_bytes(self.binding.read_bytes() + b'x')
        with self.assertRaisesRegex(ValueError, 'hash/schema'):
            self.generate()
        self.assertFalse(self.output.exists())

    def test_topology_hash_rejected(self):
        self.topology.write_bytes(self.topology.read_bytes() + b'x')
        with self.assertRaisesRegex(ValueError, 'hash/schema'):
            self.generate()

    def test_rehashed_inconsistent_vertex_metadata_rejected(self):
        self.report['resources'][0]['vertices'] = 4
        self.save_report()
        with self.assertRaisesRegex(ValueError, 'LOD draw metadata'):
            self.generate()

    def test_rehashed_cross_resource_face_rejected(self):
        blob = bytearray(self.topology.read_bytes())
        struct.pack_into('<I', blob, 16, 6)
        self.topology.write_bytes(blob)
        self.report['topologySHA256'] = self.hash(self.topology)
        self.save_report()
        with self.assertRaisesRegex(ValueError, 'resource lineage'):
            self.generate()

    def sectioned_fixture(self):
        blob=bytearray(76)
        blob[:8]=b'MMV2B04\0'
        struct.pack_into('<I',blob,8,2)
        struct.pack_into('<I',blob,72,1)
        blob.extend(bytes(36))  # positions + normals + B04 source tangents
        sections=[]
        for part,n in [(0,6),(1,2)]:
            per_lod=n//2;vertices=n*3;lod_vertices=vertices//2
            blob.extend(struct.pack('<5I6f8I',vertices,n*6,n*108,0,0,1,1,1,0,0,0,
                                    0,lod_vertices,lod_vertices,lod_vertices,48,per_lod*108+48,84,per_lod*108+84))
            blob.extend(struct.pack('<I',n));rows=[]
            fields=_module.SECTION_FIELDS if hasattr(_module,'SECTION_FIELDS') else ['lod','material','firstVertex','vertexCount','positionOffset','uvOffset','lightingOffset','extraOffset','indexFirst','indexCount']
            for i in range(n):
                values=[i//per_lod,i%3 if not part else 0,i*3,3,i*108,i*108+48,i*108+60,i*108+84,i*3,3]
                blob.extend(struct.pack('<10I',*values));rows.append(dict(zip(fields,values)))
            blob.extend(struct.pack('<I',0)+bytes(vertices*52));sections.append(rows)
        self.binding.write_bytes(blob)
        faces=[(0,1,2,0,0),(3,4,5,0,1),(18,19,20,1,0)]
        self.topology.write_bytes(b'MMV2T01\0'+struct.pack('<II',24,3)+b''.join(struct.pack('<5I',*f)for f in faces))
        self.report={'sourceBindingSHA256':self.hash(self.binding),'topologySHA256':self.hash(self.topology),
                     'resources':[{'vertices':6,'triangles':2,'physicalSections':sections[0][:2]},
                                  {'vertices':3,'triangles':1,'physicalSections':sections[1][:1]}]}
        self.save_report()
        return sections

    def test_b04_tangents_and_material_sections(self):
        self.sectioned_fixture()
        result=self.generate()
        self.assertEqual(result[0],(18,36,(0,9),(9,9),(0,9),(9,9)))
        self.assertEqual(result[1],(6,12,(0,3),(3,3),(0,3),(3,3)))

    def test_b04_receiver_material_alias_rejected(self):
        sections=self.sectioned_fixture()
        self.report['resources'][0]['physicalSections'][1]=sections[0][2]
        self.save_report()
        with self.assertRaisesRegex(ValueError,'physical material section'):
            self.generate()


if __name__ == '__main__':
    unittest.main()
