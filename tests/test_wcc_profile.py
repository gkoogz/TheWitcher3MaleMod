import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from mod import ROOT,read_json,settings
from verify_wcc_profile import verify


class CompilerProfileTest(unittest.TestCase):
    """Read-only ABI acceptance must reject identity and call-site drift."""
    @classmethod
    def setUpClass(cls):
        cls.executable=settings()['wcc']
        if not cls.executable.exists():raise unittest.SkipTest('Official compiler not installed')
        cls.profile=read_json(ROOT/'characters/compiler-native-profile.json')

    def test_current_observed_call_chain(self):
        self.assertTrue(verify(self.executable,self.profile)['callChainVerified'])

    def test_unknown_identity_rejected(self):
        profile=copy.deepcopy(self.profile);profile['executableSHA256']='0'*64
        with self.assertRaisesRegex(ValueError,'identity'):verify(self.executable,profile)

    def test_instruction_prefix_drift_rejected(self):
        profile=copy.deepcopy(self.profile);profile['functions']['construct']['prefix']='00'*16
        with self.assertRaisesRegex(ValueError,'prefix'):verify(self.executable,profile)

    def test_registration_reference_drift_rejected(self):
        profile=copy.deepcopy(self.profile);profile['registrationReferenceRVA']+=1
        with self.assertRaisesRegex(ValueError,'instruction'):verify(self.executable,profile)


if __name__=='__main__':unittest.main()
