"""Reject a requested-but-unobserved load and scripted-but-unmoved campaign."""
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from campaign_observations import analyze


def encoded(value):
    chars=[ord(c)for c in value[:9].ljust(9,'\0')]
    return[len(value)]+[sum(chars[i+j]*(128**j)for j in range(3))for i in (0,3,6)]


class CampaignObservationsTests(unittest.TestCase):
    def evidence(self):
        rows=[]
        for stage in (301,302,303,304,305,306,307,309,310,311,312,313):
            paused=stage==306;tick=260 if stage==305 else 300 if stage in(306,312)else stage
            v=[[1,0,0,-291],[0,1,0,-292],[0,0,1,-293],[0 if stage==301 else 2,0,1,1],
               [stage,stage!=310,int(paused),int(paused)],encoded('Starting Armor'if stage==304 else''),encoded('Pants 02'if stage==304 else''),[0,1,int(stage==309),tick]]
            rows.append(dict(iterationReadback=True,seconds=stage,paused=paused,vectors=v))
        rows.append(dict(iterationReadback=True,seconds=308,paused=False,vectors=[[1,0,0,-231],[0,1,0,-232],[0,0,1,-233],[0]*4,[16,1,0,0],[0]*4,[0]*4,[0]*4]))
        return rows,[dict(stage=stage,sequence=seq)for stage,seq in [(305,100),(306,100),(307,110),(309,150)]]

    def test_observed_actions_and_restored_callback_pass(self):
        rows,cps=self.evidence();result=analyze(rows,cps)
        self.assertTrue(result['campaignActionsObserved']);self.assertEqual(result['walkDistanceMeters'],2)

    def test_load_request_without_actual_restored_callback_fails(self):
        rows,cps=self.evidence();rows.pop()
        self.assertFalse(analyze(rows,cps)['campaignActionsObserved'])

    def test_walk_command_with_stationary_actor_fails(self):
        rows,cps=self.evidence();rows[1]['vectors'][3][0]=0
        self.assertFalse(analyze(rows,cps)['campaignActionsObserved'])

    def test_physics_advancing_during_pause_fails(self):
        rows,cps=self.evidence();cps[1]['sequence']=101
        self.assertFalse(analyze(rows,cps)['campaignActionsObserved'])

    def test_rejected_armor_or_malformed_item_readback_fails(self):
        rows,cps=self.evidence();rows[3]['vectors'][5]=encoded('')
        self.assertFalse(analyze(rows,cps)['clothingChangeObserved'])
        rows,cps=self.evidence();rows[3]['vectors'][6]=encoded('Pants\0'+'02')
        self.assertFalse(analyze(rows,cps)['clothingChangeObserved'])


if __name__=='__main__':unittest.main()
