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

    def test_calibrated_independent_frames_and_source_table_delivery(self):
        import json
        import tempfile
        import numpy as np
        from shape_size_transport import independent_rig,build_transport
        from prepare_motion import rig_world
        path=ROOT/'build/motion/player-stack-49c3f9716831/player-rig.json'
        if not path.exists():self.skipTest('Local verified native player fixture unavailable')
        original=json.loads(path.read_text())
        rig,receipt=independent_rig(original)
        v=rig['_chunks']['CSkeleton #0']['_vars']
        _,parents,worlds=rig_world(v)
        self.assertEqual(parents[94:],[9]*10)
        np.testing.assert_allclose(worlds,rig_world(original['_chunks']['CSkeleton #0']['_vars'])[2],atol=1e-12)
        for key in ('bones','parentIndices','rigdata'):
            self.assertEqual(v[key]['_elements'][:94],original['_chunks']['CSkeleton #0']['_vars'][key]['_elements'][:94])
        with tempfile.TemporaryDirectory(dir=ROOT/'build/probe') as temp:
            poses,receipt=build_transport(settings()['base'],rig,Path(temp))
        names=['mm_shaft_'+str(i).zfill(2) for i in range(8)]+['mm_scrotum_l','mm_scrotum_r']
        source=player_script((ROOT/'probes/runtime/maleModPhysics.ws').read_text(),['observed_%d'%i for i in range(104)])
        script,_=add_size_controls(source,settings()['base'],names,poses=poses)
        actual=np.array([float(v) for v in re.findall(r'sourcePoses\.PushBack\(([^)]+)\)',script)])
        np.testing.assert_allclose(actual,poses.reshape(-1),atol=1e-10)
        self.assertEqual(script.count('SetBehaviorVariable('),60)
        self.assertIn('index * 120 + field',script)
        # Mapped default coordinates: overall=1,width=2,length=2,scrotum=2.
        neutral=poses[1,2,2,2]
        np.testing.assert_allclose(neutral[:,:3],0,atol=1e-10)
        np.testing.assert_allclose(neutral[:,3:6],1,atol=1e-10)
        np.testing.assert_allclose(neutral[:,6:9],0,atol=1e-10)
        # All crown points receive one identical similarity transform from
        # either joint, including maximum glans. Their skin-weight blend cannot
        # introduce the previous kink or squash the free crown.
        for head in (.82/.9706456,1.,1.56/.9706456):
            offsets=[]
            for i in (6,7):
                q=worlds[94+i][:3,:3];origin=worlds[94+i][:3,3]
                delta=poses[...,i,:3]+(head-1)*poses[...,i,9:]
                factor=poses[...,i,3]*head
                offsets.append(origin+np.einsum('ij,...j->...i',q,delta)-factor[...,None]*origin)
            np.testing.assert_allclose(offsets[0],offsets[1],atol=1e-10)
