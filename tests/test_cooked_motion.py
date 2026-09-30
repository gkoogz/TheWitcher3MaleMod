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
    def check(self,text):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'native.xml';p.write_text(text);return verify_binding(p)
    def test_same_constraint_is_required_and_gameplay_is_separate(self):
        result=self.check(FIXTURE)
        self.assertTrue(result['cookedControllerBindingVerified'])
        self.assertFalse(result['runtimeHandleBindingVerified'])
        with self.assertRaises(ValueError):self.check(FIXTURE.replace('name="constraint"><reference id="5"','name="constraint"><reference id="6"'))
    def test_missing_script_property_or_mesh_link_fails(self):
        with self.assertRaises(ValueError):self.check(FIXTURE.replace('scripted="1"','scripted="0"'))
        with self.assertRaises(ValueError):self.check(FIXTURE.replace('name="child"><reference id="2"','name="child"><reference id="9"'))
