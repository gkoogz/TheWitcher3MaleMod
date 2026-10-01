import re
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from mod import ROOT,settings
from player_stack import player_script
from size_controls import add_size_controls


class SizeControlTests(unittest.TestCase):
    def test_source_mapping_tables_survive_script_generation_at_every_ui_step(self):
        cfg=settings();sys.path.insert(0,str(cfg['base']))
        from malemod_base.control_transport import normalized_samples,SIZE_CONTROLS
        source=player_script((ROOT/'probes/runtime/maleModPhysics.ws').read_text(),['observed_%d'%i for i in range(104)])
        names=['mm_shaft_'+str(i).zfill(2) for i in range(8)]+['mm_scrotum_l','mm_scrotum_r']
        script,contract=add_size_controls(source,cfg['base'],names)
        self.assertEqual(contract['supportedControls'],list(SIZE_CONTROLS))
        for key in SIZE_CONTROLS:
            actual=[float(v) for v in re.findall(r'size_'+key+r'_ratios\.PushBack\(([^)]+)\)',script)]
            expected=normalized_samples(key)
            self.assertEqual(len(actual),len(expected))
            self.assertLess(max(abs(a-b) for a,b in zip(actual,expected)),1e-9)
            self.assertIn('"MaleModPortable", "'+key+'"',script)
        self.assertEqual(script.count('SetBehaviorVectorVariable('),10)
        self.assertNotIn('Vector(bridgeScale, bridgeScale, bridgeScale)',script)
        self.assertFalse(contract['sourceSurfaceParity'])

    def test_unknown_native_cage_cannot_receive_assumed_anatomical_roles(self):
        with self.assertRaisesRegex(ValueError,'Recalibrate'):
            add_size_controls('',settings()['base'],['unknown']*10)
