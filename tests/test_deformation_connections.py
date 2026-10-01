"""Reproduce the false-positive graph cook: nodes present, output disconnected."""
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from verify_deformation_graph import verify_graph
from deformation_graph import deformation_graph


class PoseConnectionTests(unittest.TestCase):
    def fixture(self):
        nodes=['<object class="CBehaviorGraphTPoseNode" id="0"><properties/></object>']
        previous='0';index=0
        def append(kind,fields):
            nonlocal previous,index
            index+=1
            nodes.append('<object class="'+kind+'" id="'+str(index)+'"><properties>'+fields+
                '<prop name="cachedInputNode"><reference id="'+previous+'"/></prop></properties></object>')
            previous=str(index)
        for i in range(94):
            name='fixture_'+str(i)
            append('CBehaviorGraphConstraintNodeParentAlign','<prop name="bone">'+name+'</prop><prop name="parentBone">'+name+'</prop><prop name="localSpace">true</prop>')
        for i,bone in enumerate(['mm_shaft_'+str(j).zfill(2) for j in range(8)]+['mm_scrotum_l','mm_scrotum_r']):
            var='v'+str(i)
            nodes.append('<object class="CBehaviorGraphVectorVariableNode" id="'+var+'"><properties><prop name="variableName">'+bone+'_scale</prop></properties></object>')
            append('CBehaviorGraphScaleBoneNode','<prop name="boneName">'+bone+'</prop><prop name="cachedControlVariableNode"><reference id="'+var+'"/></prop>')
        append('CBehaviorGraphOutputNode','')
        return '<dump><objects>'+''.join(nodes)+'</objects></dump>'
    def check(self,text):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'graph.xml';p.write_text(text);return verify_graph(p)
    def test_all_nodes_must_reach_the_native_output(self):
        text=self.fixture()
        self.assertTrue(self.check(text)['cookedPoseConnectionsVerified'])
        for broken in (text.replace('<reference id="104"/>','NULL'),
                       text.replace('<reference id="v0"/>','NULL'),
                       text.replace('<reference id="32"/>','NULL'),
                       text.replace('mm_shaft_00_scale','wrong_variable')):
            with self.assertRaises(ValueError):self.check(broken)
    def test_authored_compiled_graph_is_marked_consistently(self):
        graph=deformation_graph({'_chunks':{'CBehaviorGraph #0':{'_vars':{}}}},['fixture_root'],['fixture_joint'])
        self.assertTrue(graph['_chunks']['CBehaviorGraph #0']['_vars']['sourceDataRemoved']['_value'])

    def test_root_motion_cannot_reenter_an_attached_identity_root(self):
        graph=deformation_graph({'_chunks':{'CBehaviorGraph #0':{'_vars':{}}}},
            ['Root','pelvis'],['fixture_joint'],identity_root='Root')
        align=[c['_vars']['bone']['_value'] for c in graph['_chunks'].values()
            if c['_type']=='CBehaviorGraphConstraintNodeParentAlign']
        self.assertEqual(align,['pelvis'])
        self.assertEqual(len([c for c in graph['_chunks'].values()
            if c['_type']=='CBehaviorGraphTPoseNode']),1)

    def test_identity_root_verification_rejects_copying_bone_zero(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'graph.xml';p.write_text(self.fixture())
            with self.assertRaises(ValueError):
                verify_graph(p,stock_names=['fixture_'+str(i) for i in range(94)],identity_root='fixture_0')
