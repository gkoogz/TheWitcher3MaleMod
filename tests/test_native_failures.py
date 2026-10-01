import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from mod import native_failure,native_assert_key


class NativeFailureTests(unittest.TestCase):
    def test_stock_baseline_diagnostic_is_specific_to_the_observed_pair(self):
        message="[Error][Assert] namesPool.cpp:221] CName collision detected 'isChainAttack' vs 'man_swimming_jump_dive_stop' with hash '2873949622'"
        self.assertEqual(native_assert_key(message),'stock-player-name-collision-2873949622')
        self.assertIsNone(native_assert_key(message.replace('2873949622','2873949623')))
        self.assertIsNone(native_assert_key(message.replace('isChainAttack','anotherName')))
        self.assertIsNone(native_assert_key('component.cpp:208] ( anotherCondition ).'))

    def test_rejects_observed_zero_exit_resource_failures(self):
        for message in ('[Error][Engine] !!! TEMPLATE COOKING FAILED !!!',
                        '[Error][Engine] Unable to create uncached entity',
                        '[Error][Core] Invalid name index 32768 (of 71)',
                        '[resource load failed] resource.w2ent',
                        '[Error][Assert] CName collision detected',
                        '[Error][Assert] component.cpp:208] ( m_transformParent == 0 ).'):
            self.assertTrue(native_failure(message, 0), message)

    def test_startup_configuration_warning_is_not_resource_failure(self):
        self.assertFalse(native_failure('[Error][Core] CreateFile failed: mods.settings', 0))
        self.assertTrue(native_failure('', 1))
