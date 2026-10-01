"""Regression gates for the fixed shape build and Base generated controller."""
import json,sys,tempfile,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from fixed_physics import ROOT,generate,independent_rig
from prepare_motion import rig_world

class FixedPhysicsTests(unittest.TestCase):
    def test_observed_neutral_delivery_and_no_controls(self):
        path=ROOT/'build/motion/player-stack-b2060381bc21/player-rig.json'
        if not path.exists():self.skipTest('Local observed rig fixture unavailable')
        rig=json.loads(path.read_text());updated,receipt=independent_rig(rig)
        names,parents,worlds=rig_world(updated['_chunks']['CSkeleton #0']['_vars'])
        _,_,before=rig_world(rig['_chunks']['CSkeleton #0']['_vars'])
        np.testing.assert_allclose(worlds,before,atol=1e-10)
        self.assertEqual(parents[94:],[9]*10)
        with tempfile.TemporaryDirectory() as folder:
            s,r=generate(ROOT.parent/'MaleMod',updated,Path(folder))
        for forbidden in ['RegisterListener','GetUserSettings','SaveUserSettings','MaleModSlider','SetTuning','IK_F12','@shaft','// PHYSICS_METHODS']:
            self.assertNotIn(forbidden,s)
        self.assertEqual(s.count('SetBehaviorVectorVariable('),10)
        self.assertEqual(s.count('SetBehaviorVariable('),60)
        self.assertTrue(r['numericalCodeGeneratedFromBase']);self.assertFalse(r['runtimeParity'])
        self.assertEqual(r['fixedScale'],1)
        self.assertEqual(r['thighBones'],['r_thigh','r_shin','l_thigh','l_shin'])
        self.assertIn("GotoState('MaleModPhysicsStartup')",s)
        self.assertIn("DetachBehavior('MaleModAnatomyLayer')",s)
        self.assertLess(max(r['thighRadii']),.15)
        self.assertLess(max(x[2] for x in r['jointRadii'][8:]),.08)
