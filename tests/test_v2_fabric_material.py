"""Guard exact source-facing equivalence and native fabric graph connectivity."""
import sys
import unittest
import os
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import v2_fabric_material as fabric


class FabricMaterialTests(unittest.TestCase):
    def test_native_output_reflection_matches_source_facing_before_rib(self):
        rng=np.random.default_rng(763)
        normal=rng.normal(size=(2000,3));normal/=np.linalg.norm(normal,axis=1)[:,None]
        tangent=rng.normal(size=(2000,3));tangent-=normal*np.sum(tangent*normal,axis=1)[:,None];tangent/=np.linalg.norm(tangent,axis=1)[:,None]
        bump=rng.uniform(-.16,.16,(2000,1))
        pre=normal+tangent*bump;pre/=np.linalg.norm(pre,axis=1)[:,None]
        native_back=pre-2*np.sum(normal*pre,axis=1)[:,None]*normal
        source_back=-normal+tangent*bump;source_back/=np.linalg.norm(source_back,axis=1)[:,None]
        np.testing.assert_allclose(native_back,source_back,atol=2e-15,rtol=0)

    def test_actual_hlsl_parser_accepts_raster_and_fallback(self):
        if os.name!='nt':self.skipTest('Native HLSL parser requires Windows')
        self.assertTrue(fabric.validate_hlsl()['passed'])

    def graph(self):
        root=Path(__file__).resolve().parents[1]/'v2/build/materials'
        path=root/'carriers-09/build/intake/characters/malemod/garments/fabric.w2mg'
        if not path.exists():self.skipTest('Owned officially resaved fabric fixture not present')
        return path

    def test_official_graph_connects_typed_inputs_and_no_specular_term(self):
        proof=fabric.inspect(self.graph())
        self.assertTrue(proof['allDeclaredInputsBound'])
        self.assertTrue(proof['reciprocalConnections'])
        self.assertFalse(proof['explicitCustomFaceFlip'])

    def test_disconnected_derivative_uv_is_rejected(self):
        path=self.graph();values=list(fabric.state(path));objects=values[2]
        normal=next(i for i,o in enumerate(objects)if b'sourceFabricNormal('in o[2].get('customCode',('',b''))[1])
        uv=next(s for s in values[4](normal,'sockets')if values[3](s)=='UV')
        objects[uv][2]['connections']=('array:2,0,ptr:CGraphConnection',bytes(4))
        with patch.object(fabric,'state',return_value=values),self.assertRaisesRegex(ValueError,'Disconnected'):
            fabric.inspect(path)


if __name__=='__main__':unittest.main()
