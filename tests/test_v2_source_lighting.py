import inspect
from pathlib import Path
import sys,tempfile,unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import v2_source_lighting as lighting
from bind_wolverine_v2 import bind


class SourceLightingTests(unittest.TestCase):
    def test_binder_default_remains_off(self):
        self.assertIs(inspect.signature(bind).parameters['source_lighting'].default,False)

    def test_native_encoding_keeps_raw_vector_not_unit_or_gram(self):
        raw=np.asarray([[.25,.2,.25],[.2,.2,.2]])
        words=lighting.direction_words(raw,np.asarray([0xc0000000,0x80000000],np.uint32))
        decoded=lighting.decode(words)
        np.testing.assert_allclose(decoded,raw,atol=1/1023,rtol=0)
        self.assertLess(np.linalg.norm(decoded[0]),.5)
        np.testing.assert_array_equal(words>>30,[3,2])

    def test_alias_diagnostic_is_separate_and_cannot_bypass_rest_or_missing_cases(self):
        self.assertFalse(lighting.allow_alias(13e-6,70e-6,67e-6,True))
        self.assertTrue(lighting.allow_alias(13e-6,70e-6,67e-6,True,True))
        self.assertFalse(lighting.allow_alias(31e-6,70e-6,67e-6,True,True))
        self.assertFalse(lighting.allow_alias(13e-6,70e-6,67e-6,False,True))

    def test_legacy_binding_cannot_receive_experimental_lighting(self):
        with self.assertRaisesRegex(ValueError,'B04'):
            lighting.restore_payload(b'MMV2B03\0'+bytes(100),'.','unused','unused')

    def test_wrong_reference_does_not_replace_generated_binding(self):
        binding=ROOT/'v2/build/runtime-binding/geralt-source-binding.bin';ref=ROOT/'v2/build/wolverine-reference/state-2/anatomy.packed'
        if not binding.exists()or not ref.exists():self.skipTest('Owned actual reference fixture absent')
        with tempfile.TemporaryDirectory()as folder:
            folder=Path(folder);data=binding.read_bytes();target=folder/'binding.bin';target.write_bytes(data)
            wrong=bytearray(ref.read_bytes());wrong[0]^=1;reference=folder/'reference.packed';reference.write_bytes(wrong)
            with self.assertRaisesRegex(ValueError,'reference differs'):
                lighting.restore_binding(target,folder,folder/'unused.w2mesh',reference,folder/'receipt.json')
            self.assertEqual(target.read_bytes(),data)
            self.assertFalse((folder/'receipt.json').exists())


if __name__=='__main__':unittest.main()
