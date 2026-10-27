import sys,unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from wcc_fbx import Node,Property
from prepare_v2_target_uv1 import edit_uv1,signature,target_chart,material_sidecar,runtime_half
from audit_v2_target_uv1 import triangle_keys


def layer(name,index,values):
    return Node(name,[Property('I',index)],[Node('MappingInformationType',[Property('S','ByVertice')]),
        Node('ReferenceInformationType',[Property('S','Direct')]),Node('UV',[Property('d',np.asarray(values,dtype=float).reshape(-1).copy())])])


class TargetUV1Tests(unittest.TestCase):
    def test_observed_truncation_and_exact_dyadic_weld_seeds(self):
        native=np.array([[0x3925,0x3ac0],[0x3800,0x3a7f]],dtype='<u2')
        fbx=native.view('<f2').astype(float);fbx[:,1]=1-fbx[:,1]
        np.testing.assert_array_equal(runtime_half(fbx),native)
        sample=np.array([[.6539,.1876]])
        self.assertEqual(float(runtime_half(sample).view('<f2')[0,1]),.81201171875)
        self.assertEqual(float(np.float16(1-sample[0,1])),.8125)

    def test_native_corner_audit_ignores_row_order_but_rejects_winding_or_attributes(self):
        a=triangle_keys([b'a',b'b',b'c'],np.array([[0,1,2]]))
        self.assertEqual(a,triangle_keys([b'c',b'a',b'b'],np.array([[1,2,0]])))
        self.assertNotEqual(a,triangle_keys([b'a',b'b',b'c'],np.array([[0,2,1]])))
        self.assertNotEqual(a,triangle_keys([b'a',b'changed-normal',b'c'],np.array([[0,1,2]])))

    def mesh(self):
        values=np.arange(10,dtype=float).reshape(5,2)/10
        return Node('Geometry',[],[Node('Vertices',[Property('d',np.arange(15,dtype=float))]),
            Node('PolygonVertexIndex',[Property('i',np.array([0,1,-3]))]),layer('LayerElementUV',0,values),
            layer('LayerElementUV',1,values),layer('LayerElementReflectionUV',0,values)])

    def test_only_module_uv1_changes_and_all_other_properties_stay_exact(self):
        mesh=self.mesh();document=SimpleNamespace(nodes=[mesh]);before=signature(document)
        stock=mesh.children[-1].array('UV').copy()[:4];uv0=mesh.children[2].array('UV').copy()
        edit_uv1(mesh,2,np.full((3,2),.375))
        self.assertEqual(signature(document),before)
        np.testing.assert_array_equal(mesh.children[2].array('UV'),uv0)
        np.testing.assert_array_equal(mesh.children[-1].array('UV')[:4],stock)
        np.testing.assert_array_equal(mesh.children[-1].array('UV'),mesh.children[-2].array('UV'))
        mesh.array('Vertices')[0]=99
        self.assertNotEqual(signature(document),before)

    def test_contradictory_shared_chart_and_alias_mismatch_fail(self):
        with self.assertRaisesRegex(ValueError,'contradictory'):
            target_chart(np.zeros((2,3)),np.array([[0,1,0]]),np.array([0,0]),np.array([[0,0],[1,0]]),None)
        mesh=self.mesh();mesh.children[-1].array('UV')[0]=99
        with self.assertRaisesRegex(ValueError,'aliases disagree'):edit_uv1(mesh,2,np.zeros((3,2)))

    def test_exact_four_float_sidecar_delta_with_stock_material_untouched(self):
        names=['Material0','NaturalLOD0','ErectLOD0','NaturalLOD1','ErectLOD1']
        source=('<mesh><materials>'+''.join('<material name="'+name+'">'+(''if name=='Material0'else'<param name="DetailPower" type="Float" value="0" />')+'</material>'for name in names)+'</materials></mesh>').encode()
        changed=material_sidecar(source)
        self.assertEqual(changed.count(b'value="0.5"'),4)
        self.assertEqual(changed.replace(b'value="0.5"',b'value="0"'),source)


if __name__=='__main__':unittest.main()
