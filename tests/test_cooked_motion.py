import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from verify_cooked_motion import verify_binding

FIXTURE='''<dump><objects>
<object class="MaleModMotionComponent" id="1"><properties><prop name="dynamicConstraint" scripted="1"><reference id="5"/></prop></properties></object>
<object class="CAnimDangleComponent" id="4"><properties><prop name="constraint"><reference id="5"/></prop></properties></object>
<object class="CAnimDangleConstraint_Dyng" id="5"/>
<object class="CMeshComponent" id="2"/>
<object class="CMeshSkinningAttachment" id="3"><properties><prop name="parent"><reference id="4"/></prop><prop name="child"><reference id="2"/></prop></properties></object>
</objects></dump>'''

class CookedBindingTests(unittest.TestCase):
    def check(self,text,**kwargs):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'native.xml';p.write_text(text);return verify_binding(p,**kwargs)
    def test_same_constraint_is_required_and_gameplay_is_separate(self):
        result=self.check(FIXTURE)
        self.assertTrue(result['cookedControllerBindingVerified'])
        self.assertFalse(result['runtimeHandleBindingVerified'])
        with self.assertRaises(ValueError):self.check(FIXTURE.replace('name="constraint"><reference id="5"','name="constraint"><reference id="6"'))
    def test_missing_script_property_or_mesh_link_fails(self):
        with self.assertRaises(ValueError):self.check(FIXTURE.replace('scripted="1"','scripted="0"'))
        with self.assertRaises(ValueError):self.check(FIXTURE.replace('name="child"><reference id="2"','name="child"><reference id="9"'))

    def test_deformation_gate_rejects_null_resources_and_disconnected_output(self):
        helper=r'''<object class="CAnimatedComponent" id="7"><properties>
        <prop name="name">MaleModDeformation</prop>
        <prop name="skeleton"><resource path="characters\malemod\physics\deformation.w2rig"/></prop>
        <prop name="behaviorInstanceSlots"><array><prop name="graph"><resource path="characters\malemod\behavior\deformation.w2beh"/></prop></array></prop>
        </properties></object>
        <object class="CAnimatedAttachment" id="8"><properties>
        <prop name="parent"><reference id="7"/></prop><prop name="child"><reference id="4"/></prop>
        </properties></object>'''
        text=FIXTURE.replace('</objects>',helper+'</objects>').replace(
            '<prop name="constraint">','<prop name="transformParent"><reference id="8"/></prop><prop name="constraint">')
        result=self.check(text)
        self.assertTrue(result['cookedDeformationBindingVerified'])
        self.assertFalse(result['liveScaleObserved'])
        with self.assertRaises(ValueError):
            self.check(text.replace('<resource path="characters\\malemod\\behavior\\deformation.w2beh"/>','NULL'))
        with self.assertRaises(ValueError):
            self.check(text.replace('name="parent"><reference id="7"','name="parent"><reference id="4"'))

    def test_late_graph_requires_both_ordered_native_slots(self):
        slots=''.join(r'''<element><object class="SBehaviorGraphInstanceSlot"><properties>
            <prop name="instanceName">%s</prop><prop name="alwaysOnTopOfStack">false</prop>
            <prop name="graph"><resource path="characters\malemod\behavior\deformation.w2beh"/></prop>
            </properties></object></element>''' % name for name in ('MaleModDeformation','MaleModDeformationLate'))
        helper=r'''<object class="CAnimatedComponent" id="7"><properties>
            <prop name="name">MaleModDeformation</prop>
            <prop name="skeleton"><resource path="characters\malemod\physics\deformation.w2rig"/></prop>
            <prop name="behaviorInstanceSlots"><array>''' + slots + '''</array></prop></properties></object>'''
        text=FIXTURE.replace('</objects>',helper+'</objects>').replace(
            'name="parent"><reference id="4"','name="parent"><reference id="7"')
        result=self.check(text,output='direct',require_late=True)
        self.assertTrue(result['cookedLateGraphSlotsVerified'])
        for broken in (text.replace('MaleModDeformationLate','WrongSlot'),
                       text.replace('>false</prop>','>true</prop>'),
                       text.replace('behavior\\deformation.w2beh','behavior\\missing.w2beh')):
            with self.assertRaises(ValueError):self.check(broken,output='direct',require_late=True)
