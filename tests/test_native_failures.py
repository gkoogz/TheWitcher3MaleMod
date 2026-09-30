import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from mod import native_failure


class NativeFailureTests(unittest.TestCase):
    def test_rejects_observed_zero_exit_resource_failures(self):
        for message in ('[Error][Engine] !!! TEMPLATE COOKING FAILED !!!',
                        '[Error][Engine] Unable to create uncached entity',
                        '[Error][Core] Invalid name index 32768 (of 71)',
                        '[resource load failed] resource.w2ent'):
            self.assertTrue(native_failure(message, 0), message)

    def test_startup_configuration_warning_is_not_resource_failure(self):
        self.assertFalse(native_failure('[Error][Core] CreateFile failed: mods.settings', 0))
        self.assertTrue(native_failure('', 1))
