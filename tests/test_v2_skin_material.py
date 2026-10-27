import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
import v2_skin_material as skin


class NativeSkinGraphTests(unittest.TestCase):
    def setUp(self):
        self.graph = TOOLS.parent / 'v2/build/materials/anatomy-01/build/intake' / skin.GRAPH
        if not self.graph.is_file():
            self.skipTest('Prepared official native skin graph fixture is unavailable')

    def test_actual_official_compiled_graph_connectivity(self):
        proof = skin.inspect(self.graph)
        self.assertTrue(proof['sourceSpecularIsTexture'])
        self.assertTrue(proof['sourceSpecularSRGBDecoded'])
        self.assertTrue(proof['sourceSubsurfaceSRGBDecoded'])

    @unittest.skipUnless(sys.platform=='win32','Native D3DCompile requires Windows')
    def test_source_custom_functions_compile_with_actual_hlsl_compiler(self):
        self.assertTrue(skin.validate_custom_functions(self.graph)['passed'])

    def altered(self, change):
        state = skin.state(self.graph)
        change(state)
        with patch.object(skin, 'state', return_value=state):
            with self.assertRaises(ValueError):
                skin.inspect(self.graph)

    def test_flattened_source_specular_rejected(self):
        def change(state):
            _, _, objects, name, _, _ = state
            i = next(i for i, o in enumerate(objects) if 'parameterName' in o[2] and name(i, 'parameterName') == 'SpecularColor')
            kind, flags, props, tail = objects[i]
            objects[i] = ('CMaterialParameterColor', flags, props, tail)
        self.altered(change)

    def test_disconnected_source_map_rejected(self):
        def change(state):
            _, _, objects, name, array, _ = state
            i = next(i for i, o in enumerate(objects) if 'parameterName' in o[2] and name(i, 'parameterName') == 'SpecularColor')
            for s in array(i, 'sockets'):
                objects[s][2]['connections'] = ('array:2,0,ptr:CGraphConnection', bytes(4))
        self.altered(change)

    def test_changed_authored_source_strength_rejected(self):
        def change(state):
            _, _, objects, _, _, _ = state
            node = next(o for o in objects if b'sourceSpecular(' in o[2].get('customCode', ('', b''))[1])
            ty, code = node[2]['customCode']
            node[2]['customCode'] = (ty, code.replace(b'1.0,1.5,2.0', b'1.0,1.0,1.0'))
        self.altered(change)

    def test_debug_detail_normal_rejected_even_at_zero_weight(self):
        def change(state):
            _, _, objects, name, _, _ = state
            detail=next(i for i,o in enumerate(objects)if o[0]=='CMaterialParameterTexture'and name(i,'parameterName')=='DetailNormal')
            diffuse=next(o for i,o in enumerate(objects)if o[0]=='CMaterialParameterTexture'and name(i,'parameterName')=='Diffuse')
            objects[detail][2]['texture']=diffuse[2]['texture']
        self.altered(change)

    def test_unused_custom_vector_argument_must_be_typed(self):
        def change(state):
            _, _, objects, name, array, _ = state
            i=next(i for i,o in enumerate(objects)if b'sourceSpecular(' in o[2].get('customCode',('',b''))[1])
            s=next(s for s in array(i,'sockets')if name(s)=='blendColor')
            objects[s][2]['connections']=('array:2,0,ptr:CGraphConnection',bytes(4))
        self.altered(change)

    def test_missing_specular_srgb_decode_rejected(self):
        def change(state):
            node=next(o for o in state[2]if b'sourceSpecular('in o[2].get('customCode',('',b''))[1])
            ty,code=node[2]['customCode'];node[2]['customCode']=(ty,code.replace(b'2.4',b'1.0'))
        self.altered(change)

    def test_missing_subsurface_srgb_decode_rejected(self):
        def change(state):
            node=next(o for o in state[2]if b'sourceSubsurface('in o[2].get('customCode',('',b''))[1])
            ty,code=node[2]['customCode'];node[2]['customCode']=(ty,code.replace(b'2.4',b'1.0'))
        self.altered(change)


if __name__ == '__main__':
    unittest.main()
