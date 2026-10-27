import copy
from pathlib import Path
import sys
import struct
import zlib
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_v2_detail_package as package


class DetailPackageGuardTests(unittest.TestCase):
    def setUp(self):
        self.job=ROOT/'v2/build/materials/target-uv1-03'
        self.baseline=ROOT/'v2/build/materials/seam-native-07/package-with-shaders.json'
        self.graph=ROOT/'v2/build/materials/stock-detail-01/graph-compiled.json'
        if not (self.job/'native-uv1-audit.json').exists()or(self.job/'package.json').exists():
            self.skipTest('Fresh closed, not-yet-packaged UV1 audit fixture unavailable')

    def no_native_on(self,relative,change):
        original=package.read_json
        target=(self.graph if relative=='graph-receipt'else self.job/relative).resolve()
        def changed(path):
            value=copy.deepcopy(original(path))
            if Path(path).resolve()==target:change(value)
            return value
        with patch.object(package,'read_json',side_effect=changed), \
             patch.object(package.mod,'settings',side_effect=AssertionError('Bad proof reached settings')) as settings, \
             patch.object(package,'complete_depot',side_effect=AssertionError('Bad proof reached depot')) as depot, \
             patch.object(package.mod,'build',side_effect=AssertionError('Bad proof launched native build')) as native:
            with self.assertRaises(ValueError):package.build(self.job,self.baseline,self.graph)
            settings.assert_not_called();depot.assert_not_called();native.assert_not_called()

    def test_actual_closed_native03_preflight_is_read_only(self):
        with patch.object(package.mod,'build',side_effect=AssertionError('Preflight invoked build')) as native:
            job,_,_,audit=package.preflight(self.job,self.baseline,self.graph)
            self.assertEqual(job,self.job.resolve())
            self.assertTrue(audit['nativeRoundtripVerified'])
            native.assert_not_called()

    def test_failed_native_attribute_audit_cannot_start_build(self):
        self.no_native_on('native-uv1-audit.json',lambda d:d.update(nativeRoundtripVerified=False))

    def test_different_baseline_geometry_cannot_start_build(self):
        self.no_native_on('native-uv1-audit.json',lambda d:d.update(baselineBufferSHA256='0'*64))

    def test_sdk_or_other_unowned_compiler_cannot_start_build(self):
        self.no_native_on('graph-receipt',lambda d:d['command']['args'].__setitem__(0,str(Path(ROOT.anchor)/'not-owned/wcc_lite.exe')))

    def test_stale_native_field_cannot_start_build(self):
        self.no_native_on('native-uv1-audit.json',lambda d:next(x for x in d['sections']if x['nativeMaterial']!=0).update(targetFieldSHA256='0'*64))

    def test_missing_inventory_entry_cannot_start_build(self):
        self.no_native_on('official-roundtrip.json',lambda d:d['sourceInventory'].pop('characters/malemod/garments/fabric.w2mg'))

    def test_stale_authoring_fbx_cannot_start_build(self):
        self.no_native_on('uv1-candidate.json',lambda d:d.update(outputFBXSHA256='0'*64))


class RelativeInputGuardTests(unittest.TestCase):
    def test_intake_traversal_and_absolute_paths_rejected(self):
        intake=ROOT/'v2/build/materials/unused/build/intake'
        for name in ['../outside.xbm','characters/../../outside.xbm',str(ROOT/'outside.xbm')]:
            with self.assertRaises(ValueError):package.intake_path(intake,name)


class StockUpperEquivalenceTests(unittest.TestCase):
    def setUp(self):
        info=ROOT/'v2/build/materials/seam-native-07/package-with-shaders.json'
        if not info.exists():self.skipTest('Stock upper fixture unavailable')
        self.raw=(Path(package.read_json(info)['cooked'])/package.UPPER).read_bytes()
        self.reader=package.CookedMesh(self.raw,allow_stock_torso_mapping=True,allow_multi_section=True)

    def changed(self,offset):
        raw=bytearray(self.raw);raw[offset]^=1
        table,count,_=struct.unpack_from('<III',raw,88)
        for i in range(count):
            kind,_,_,length,start,_,_=struct.unpack_from('<HHIIIII',raw,table+i*24)
            if self.reader.names[kind]=='CMesh':struct.pack_into('<I',raw,table+i*24+20,zlib.crc32(raw[start:start+length]))
        struct.pack_into('<I',raw,96,zlib.crc32(raw[table:table+count*24]))
        struct.pack_into('<I',raw,32,package.header_crc(raw,0))
        return bytes(raw)

    def nested(self,vector,component):
        table,count,_=struct.unpack_from('<III',self.raw,88)
        entries=list(struct.iter_unpack('<HHIIIII',self.raw[table:table+count*24]))
        mesh=next(e for e in entries if self.reader.names[e[0]]=='CMesh')
        box,n=package.property_span(self.raw,self.reader,mesh[4],mesh[3],'boundingBox','Box')
        value,n=package.property_span(self.raw,self.reader,box,n,vector,'Vector')
        return package.property_span(self.raw,self.reader,value,n,component,'Float')[0]

    def test_only_min_w_and_derived_valid_crcs_allowed(self):
        proof=package.upper_bytes_equivalence(self.raw,self.changed(self.nested('Min','W')))
        self.assertTrue(proof['allOtherFileBytesIdentical'])
        self.assertTrue(proof['headerAndExportCRCsVerified'])

    def test_spatial_x_and_max_w_changes_rejected_even_with_valid_crcs(self):
        for vector,component in [('Min','X'),('Min','Y'),('Min','Z'),('Max','W')]:
            with self.assertRaises(ValueError):package.upper_bytes_equivalence(self.raw,self.changed(self.nested(vector,component)))

    def test_material_handle_change_rejected_even_with_valid_crcs(self):
        table,count,_=struct.unpack_from('<III',self.raw,88)
        entries=list(struct.iter_unpack('<HHIIIII',self.raw[table:table+count*24]))
        mesh=next(e for e in entries if self.reader.names[e[0]]=='CMesh')
        at,_=package.property_span(self.raw,self.reader,mesh[4],mesh[3],'materials',self.reader.properties['materials'][0])
        with self.assertRaises(ValueError):package.upper_bytes_equivalence(self.raw,self.changed(at+4))


class ExistingPublishGuards(unittest.TestCase):
    def test_wrong_manifest_hash_stops_before_postchecks_or_native_calls(self):
        job=ROOT/'v2/build/materials/target-uv1-03';pub=job/'publish/20261026-194205-72e968'
        if not pub.exists()or(job/'package.json').exists():self.skipTest('Unfinalized published fixture unavailable')
        with patch.object(package.mod,'build',side_effect=AssertionError('Native rerun')) as native, \
             patch.object(package.mod,'settings',side_effect=AssertionError('Native setup')) as setup, \
             patch.object(package,'audit',side_effect=AssertionError('Bad manifest reached postchecks')) as audit:
            with self.assertRaises(ValueError):package.finalize_existing(job,ROOT/'v2/build/materials/seam-native-07/package-with-shaders.json',ROOT/'v2/build/materials/stock-detail-01/graph-compiled.json',pub,'0'*64)
            native.assert_not_called();setup.assert_not_called();audit.assert_not_called()


if __name__=='__main__':unittest.main()
