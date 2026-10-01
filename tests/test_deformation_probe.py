"""Guard native probe diagnostics needed to distinguish UI and pose failures."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from build_deformation_probe import probe_script


class DeformationProbeTests(unittest.TestCase):
    def test_delayed_instance_and_callback_readback_are_kept(self):
        source=(Path(__file__).resolve().parents[1]/'probes/runtime/maleModPhysics.ws').read_text()
        script=probe_script(source,direct=True,late=True)
        self.assertIn("GotoState('MaleModGraphStartup')",script)
        self.assertIn('Sleep(0.25)',script)
        self.assertIn("graphs.PushBack('MaleModDeformationLate')",script)
        self.assertIn('deformationRoot.ActivateBehaviors(graphs)',script)
        self.assertIn("bridgeChanges += 1",script)
        self.assertIn("GetBehaviorVectorVariable('mm_shaft_00_scale')",script)
        self.assertIn("controller.SetTuning('MaleModBridgeScale',value)",script)
        # Important receiver direction: schedule helper after player, never
        # make the player's animation depend on our diagnostic component.
        self.assertIn('deformationRoot.UpdateByOtherAnimatedComponent(thePlayer.GetRootAnimatedComponent())',script)
        self.assertNotIn('thePlayer.GetRootAnimatedComponent().UpdateByOther',script)
