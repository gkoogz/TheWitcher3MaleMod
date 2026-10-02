"""Regression gates for the fixed shape build and Base generated controller."""
import json,sys,tempfile,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from fixed_physics import ROOT,generate,independent_rig
from prepare_motion import rig_world

class FixedPhysicsTests(unittest.TestCase):
    def test_observed_neutral_delivery_and_no_controls(self):
        pointer=ROOT/'generated/default-cage.json'
        if not pointer.exists():self.skipTest('Local default cage unavailable')
        cage=ROOT/json.loads(pointer.read_text())['cage'];path=cage/'motion-dyng.json'
        if not path.exists():self.skipTest('Local observed rig fixture unavailable')
        rig=json.loads(path.read_text());rig['_chunks']={'CSkeleton #0':rig['_chunks']['CSkeleton #1']};updated,receipt=independent_rig(rig)
        names,parents,worlds=rig_world(updated['_chunks']['CSkeleton #0']['_vars'])
        _,_,before=rig_world(rig['_chunks']['CSkeleton #0']['_vars'])
        np.testing.assert_allclose(worlds,before,atol=1e-10)
        self.assertEqual(parents[94:],[9]*10)
        with tempfile.TemporaryDirectory() as folder:
            s,r=generate(ROOT.parent/'MaleMod',updated,Path(folder),cage=cage)
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
        self.assertEqual(r['physicsNodes'],14)
        self.assertEqual(r['renderJoints'],10)
        self.assertEqual(r['bendTarget'],'zero curvature')
        self.assertLess(r['neutralGuideToRenderJointError'],1e-5)
        np.testing.assert_allclose(r['restLengths'],r['restLengths'][0])
        self.assertLess(r['restLengths'][0],.03)
        self.assertIn('SampleGuide(12,i/7.0,position,direction)',s)
        self.assertIn('targets = restPoints;',s)
        self.assertIn('localPoint = position;',s)
        self.assertIn('IntegrateRelative(i,localGravity*gravity,linear,omega,alpha,',s)
        self.assertNotIn('physicsVelocity[i].Z -=',s)
        self.assertNotIn('localPoint = Point(worldToPelvis, position)',s)
        self.assertNotIn('return center+VecTransformDir(pelvis,',s)
        self.assertIn('pelvis local',r['solverSpace'])
        self.assertFalse(r['frameMotion']['sourceParity'])

    def test_posed_reference_cannot_be_called_default(self):
        path=ROOT/'build/motion/player-stack-b2060381bc21/player-rig.json'
        if not path.exists():self.skipTest('Historical local fixture unavailable')
        rig,_=independent_rig(json.loads(path.read_text()))
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError,'evaluated Wolverine defaults'):
                generate(ROOT.parent/'MaleMod',rig,Path(folder),cage=ROOT/'build/motion/cage-dec402309e13')
