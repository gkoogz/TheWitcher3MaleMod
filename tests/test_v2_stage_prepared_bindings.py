import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from mod import digest
from adopt_v2_skin_bindings import FILES
from stage_v2_standalone import verify_prepared_bindings


def write(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n')


class PreparedStagingGuard(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.job=self.root/'job';self.job.mkdir()
        self.source=self.job/'bindings';self.source.mkdir();self.runtime=self.root/'runtime';self.runtime.mkdir()
        package=self.job/'publish';package.mkdir();write(package/'build-manifest.json',{'files':[]})
        self.info=self.job/'package-with-shaders.json';write(self.info,{'directory':str(package),'cooked':str(self.job/'cooked')})
        self.binding={'schema':'malemod.witcher-v2-native-binding/4','sourceLighting':{},
                      'bodyPackageInfo':str(self.info),'bodyPackageInfoSHA256':digest(self.info),
                      'bodyPackageManifestSHA256':digest(package/'build-manifest.json')}
        names=FILES+('source-lighting.json',)
        for name in names:
            for directory in (self.source,self.runtime):
                if name=='manifest.json':write(directory/name,self.binding)
                else:(directory/name).write_bytes(('sealed original '+name).encode())
        self.prepared={'bindings':str(self.source),'bodyPackageInfo':str(self.info),
                       'bodyPackageInfoSHA256':digest(self.info),'adopted':False,
                       'files':[{'path':n,'sha256':digest(self.source/n)}for n in names]}
        write(self.source/'prepared.json',self.prepared);write(self.source/'adopted.json',{**self.prepared,'adopted':True})

    def guard(self):return verify_prepared_bindings(self.info,self.runtime,self.binding)

    def test_complete_seventeen_file_inventory_is_read_only(self):
        before={str(p):digest(p)for p in self.root.rglob('*')if p.is_file()}
        result=self.guard();self.assertEqual(result['fileCount'],17)
        self.assertEqual(before,{str(p):digest(p)for p in self.root.rglob('*')if p.is_file()})

    def test_reordered_fingerprints_rejected_even_if_manifest_changed_to_match(self):
        (self.runtime/'graphics-owned-fingerprints.bin').write_bytes(b'reordered')
        self.binding['fingerprintsSHA256']=digest(self.runtime/'graphics-owned-fingerprints.bin')
        write(self.runtime/'manifest.json',self.binding)
        with self.assertRaisesRegex(ValueError,'Preserve adopted'):self.guard()

    def test_changed_package_manifest_rejected(self):
        package=Path(json.loads(self.info.read_text())['directory'])
        write(package/'build-manifest.json',{'files':['different']})
        with self.assertRaisesRegex(ValueError,'package manifest'):self.guard()

    def test_different_package_descriptor_rejected(self):
        write(self.info,{'directory':'different'})
        with self.assertRaisesRegex(ValueError,'different body package'):self.guard()

    def test_missing_file_and_duplicate_inventory_rejected(self):
        self.prepared['files'][-1]=self.prepared['files'][0]
        write(self.source/'prepared.json',self.prepared)
        with self.assertRaisesRegex(ValueError,'incomplete or duplicated'):self.guard()

    def test_unadopted_preparation_rejected(self):
        write(self.source/'adopted.json',self.prepared)
        with self.assertRaisesRegex(ValueError,'was not adopted'):self.guard()

    def test_modified_original_preparation_rejected(self):
        (self.source/'carrier-binding.json').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'Preserve adopted'):self.guard()

    def test_only_unprepared_legacy_b03_can_fall_back(self):
        elsewhere=self.root/'legacy-package.json';write(elsewhere,{})
        self.assertIsNone(verify_prepared_bindings(elsewhere,self.runtime,{'schema':'binding/3'}))
        with self.assertRaisesRegex(ValueError,'complete adoption provenance'):
            verify_prepared_bindings(elsewhere,self.runtime,{'schema':'binding/4'})


if __name__=='__main__':unittest.main()
