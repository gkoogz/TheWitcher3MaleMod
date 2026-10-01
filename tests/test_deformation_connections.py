"""Reproduce the false-positive graph cook: nodes present, output disconnected."""
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from verify_deformation_graph import verify_graph
from deformation_graph import deformation_graph


class PoseConnectionTests(unittest.TestCase):
    def test_authored_rest_mask_cannot_replace_stock_animation_or_root_motion(self):
        import xml.etree.ElementTree as ET
        names=['fixture_'+str(i) for i in range(94)]
        controlled=['mm_shaft_'+str(i).zfill(2) for i in range(8)]+['mm_scrotum_l','mm_scrotum_r']
        graph=deformation_graph({'_chunks':{'CBehaviorGraph #0':{'_vars':{}}}},names,controlled,
            identity_root=names[0],parent_space='attached',rest_joints=True)
        ids={k:str(i) for i,k in enumerate(graph['_chunks'])}
        root=ET.Element('dump');objects=ET.SubElement(root,'objects')
        def prop(parent,name,data):
            p=ET.SubElement(parent,'prop',name=name)
            if '_value' in data:
                value=data['_value'];p.text=str(value).lower() if isinstance(value,bool) else format(value,'g') if isinstance(value,float) else str(value)
            elif '_reference' in data.get('_vars',{}):
                ET.SubElement(p,'reference',id=ids[data['_vars']['_reference']['_value']])
            elif '_elements' in data:
                arr=ET.SubElement(p,'array')
                for e in data['_elements']:
                    el=ET.SubElement(arr,'element');obj=ET.SubElement(el,'object');props=ET.SubElement(obj,'properties')
                    for k,v in e.get('_vars',{}).items():prop(props,k,v)
        for key,chunk in graph['_chunks'].items():
            o=ET.SubElement(objects,'object',{'id':ids[key],'class':chunk['_type']});p=ET.SubElement(o,'properties')
            for k,v in chunk['_vars'].items():prop(p,k,v)
        text=ET.tostring(root,encoding='unicode')
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'graph.xml';p.write_text(text)
            result=verify_graph(p,stock_names=names,identity_root=names[0],parent_space='attached',rest_joints=True)
            self.assertTrue(result['authoredRestMaskVerified']);self.assertEqual(result['connectedPoseNodes'],23)
            for bad in (text.replace('name="m_boneName">mm_shaft_00','name="m_boneName">fixture_9'),
                        text.replace('name="m_weight">1','name="m_weight">0'),
                        text.replace('name="num">94','name="num">9'),
                        text.replace('name="alwaysActiveOverrideInput">true','name="alwaysActiveOverrideInput">false'),
                        text.replace('name="getDeltaMotionFromOverride">false','name="getDeltaMotionFromOverride">true'),
                        text.replace('name="value">1','name="value">0')):
                p.write_text(bad)
                with self.assertRaises(ValueError):verify_graph(p,stock_names=names,identity_root=names[0],parent_space='attached',rest_joints=True)

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

    def test_local_and_model_pose_policies_cannot_be_confused(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'graph.xml';p.write_text(self.fixture())
            with self.assertRaises(ValueError):verify_graph(p,parent_space='model')
            p.write_text(self.fixture().replace('>true<','>false<'))
            self.assertEqual(verify_graph(p,parent_space='model')['parentPoseSpace'],'model')
            with self.assertRaises(ValueError):verify_graph(p)

    def test_attached_input_preserves_stock_pose_and_resets_only_authored_scale(self):
        names=['fixture_'+str(i) for i in range(94)]
        controls=['mm_shaft_'+str(i).zfill(2) for i in range(8)]+['mm_scrotum_l','mm_scrotum_r']
        graph=deformation_graph({'_chunks':{'CBehaviorGraph #0':{'_vars':{}}}},names,controls,
            identity_root=names[0],parent_space='attached')
        chunks=graph['_chunks'].values()
        self.assertFalse(any(c['_type'] in ('CBehaviorGraphTPoseNode','CBehaviorGraphConstraintNodeParentAlign') for c in chunks))
        self.assertEqual([c['_vars']['bone']['_value'] for c in chunks if c['_type']=='CBehaviorGraphConstraintReset'],controls)
        import re
        text=self.fixture().replace('CBehaviorGraphTPoseNode','CBehaviorGraphInputNode')
        # Retain the original IDs while removing the stock alignment chain.
        text=re.sub(r'<object class="CBehaviorGraphConstraintNodeParentAlign".*?</object>','',text)
        text=text.replace('<reference id="94"/>','<reference id="0"/>')
        for i,bone in enumerate(controls):
            previous=str(94+i) if i else '0'
            reset='reset'+str(i)
            text=text.replace('<reference id="'+previous+'"/>','<reference id="'+reset+'"/>')
            node='<object class="CBehaviorGraphConstraintReset" id="'+reset+'"><properties>'
            node+='<prop name="bone">'+bone+'</prop><prop name="translation">false</prop><prop name="rotation">false</prop><prop name="scale">true</prop>'
            node+='<prop name="cachedInputNode"><reference id="'+previous+'"/></prop></properties></object>'
            text=text.replace('</objects>',node+'</objects>')
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'graph.xml';p.write_text(text)
            result=verify_graph(p,stock_names=names,identity_root=names[0],parent_space='attached')
            self.assertEqual(result['connectedPoseNodes'],21)
            self.assertEqual(result['stockAlignmentNodes'],0)
            for bad in (text.replace('name="rotation">false','name="rotation">true'),
                        text.replace('id="reset0"/>','id="0"/>'),
                        text.replace('name="bone">mm_shaft_00','name="bone">fixture_0')):
                p.write_text(bad)
                with self.assertRaises(ValueError):
                    verify_graph(p,stock_names=names,identity_root=names[0],parent_space='attached')
