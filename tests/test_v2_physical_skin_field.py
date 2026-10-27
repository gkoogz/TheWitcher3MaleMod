import sys,unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from wcc_fbx import Node,Property
from prepare_v2_physical_skin_field import quantize,edit_r,preserved_signature,physical_xml,atlas_proof
from audit_v2_physical_skin_field import compare_sections


def colors(values,index):
    return Node('LayerElementColor',[Property('I',index)],[
        Node('MappingInformationType',[Property('S','ByVertice')]),
        Node('ReferenceInformationType',[Property('S','Direct')]),
        Node('Colors',[Property('d',np.asarray(values,dtype=float).reshape(-1).copy())])])


class PhysicalSkinFieldTests(unittest.TestCase):
    def test_quantization_bounds_and_endpoints(self):
        values=np.array([0,1,.5,.00015,.3])
        encoded,error=quantize(values)
        np.testing.assert_array_equal(encoded[:3],[0,255,128])
        self.assertLessEqual(error.max(),.5/255)
        for bad in([float('nan')],[-.01],[1.01]):
            with self.assertRaises(ValueError):quantize(bad)

    def test_only_source_red_changes_in_both_active_color_aliases(self):
        original=np.array([[.1,.2,.3,.4],[.6,.7,.8,1],[.9,.8,.7,1-2e-14]])
        mesh=Node('Geometry',[],[Node('Vertices',[Property('d',np.arange(9,dtype=float))]),colors(original,0),colors(original,1)])
        document=SimpleNamespace(nodes=[mesh],meshes=[mesh]);before=preserved_signature(document,[1])
        edit_r(mesh,1,np.array([255,0],dtype=np.uint8))
        self.assertEqual(preserved_signature(document,[1]),before)
        for layer in mesh.children[1:]:
            changed=layer.array('Colors').reshape(-1,4)
            np.testing.assert_array_equal(changed[0],original[0])
            np.testing.assert_array_equal(changed[:,1:],original[:,1:])
            np.testing.assert_array_equal(changed[1:,0],[1,0])
        mesh.children[1].array('Colors')[7]=.5
        self.assertNotEqual(preserved_signature(document,[1]),before)

    def test_four_ambient_overrides_removed_with_scalars_and_stock_exact(self):
        stock=b'<material name="Material0"><param name="Ambient" value="stock.xbm" /></material>\r\n'
        lines=[b'  <param name="Ambient" type="handle:ITexture" value="characters\\malemod\\anatomy\\lod'+str(lod).encode()+b'-ambient.xbm" />\r\n'for lod in(0,0,1,1)]
        scalars=b'<param name="DetailPower" type="Float" value="0.5" />\r\n'
        original=stock+b''.join(lines)+scalars
        self.assertEqual(physical_xml(original),stock+scalars)
        with self.assertRaises(ValueError):physical_xml(stock+scalars)

    def test_uv0_aliases_keep_distinct_physical_fields(self):
        proof=atlas_proof(np.array([[0,0],[0,0],[1,1]]),np.array([1,.00015,0]),np.array([255,0,0],dtype=np.uint8))
        self.assertEqual(proof['overlappedUVGroupsWithDistinctPhysicalR'],1)
        self.assertFalse(proof['UV0BakingUsed'])

    def test_native_audit_allows_only_source_r_and_rejects_stock_r_or_source_gba(self):
        def section(colors):
            return dict(keys=[b'geometry-uv0-NT'+bytes(c)for c in colors],uv1=[b'uv1']*3,faces=np.array([[0,1,2]]))
        original=section([[1,2,3,255]]*3)
        changed=section([[99,2,3,255]]*3)
        compare_sections({(0,1):original},{(0,1):changed})
        with self.assertRaisesRegex(ValueError,'Protected native'):compare_sections({(0,0):original},{(0,0):changed})
        for color in([99,2,4,255],[99,2,3,254]):
            with self.assertRaisesRegex(ValueError,'Protected native'):compare_sections({(0,1):original},{(0,1):section([color]*3)})


if __name__=='__main__':unittest.main()
