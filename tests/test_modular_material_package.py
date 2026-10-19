import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from modular_material_package import PATHS, identities
from install_modular_native import coupled_identity, PREFIX, ARTIFACTS


class MaterialPackageTest(unittest.TestCase):
    def test_texture_bundle_is_part_of_native_acceptance_identity(self):
        names=['malemod_witcher.dll','surface_worker.exe','geralt.render',
               'geralt.bindings','malemod-runtime.profile']+list(ARTIFACTS)
        names += [n+'.sha256' for n in ARTIFACTS]
        package=dict(files=[dict(path=p,sha256='a'*64) for p in sorted(PATHS)])
        preview=dict(files=[dict(path=PREFIX+n,sha256='b'*64) for n in names]+package['files'],materialPackage=package)
        result=coupled_identity(preview)
        self.assertTrue(PATHS.issubset(result))
        preview['files'][-1]=dict(path=preview['files'][-1]['path'],sha256='c'*64)
        with self.assertRaises(ValueError):coupled_identity(preview)

    def test_extra_or_duplicate_paths_are_rejected(self):
        rows=[dict(path=p,sha256='a'*64) for p in PATHS]
        with self.assertRaises(ValueError):identities(dict(files=rows+[rows[0]]))
        rows[0]=dict(path='../outside',sha256='a'*64)
        with self.assertRaises(ValueError):identities(dict(files=rows))

    def test_prior_runtime_without_texture_package_remains_supported(self):
        self.assertEqual(identities(None),{})


if __name__=='__main__':unittest.main()
