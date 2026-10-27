import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from prepare_v2_waist_join import replace_faces,face_key
from adopt_v2_skin_bindings import validate_waist_manifest

class LocalStockWaistTests(unittest.TestCase):
    def test_preserves_every_outside_face_in_order(self):
        old=np.arange(300).reshape(-1,3);remove=np.arange(13,65);new=np.arange(189).reshape(-1,3)+400
        actual,keep=replace_faces(old,remove,new)
        np.testing.assert_array_equal(actual[:48],old[keep]);np.testing.assert_array_equal(actual[48:],new)
        self.assertEqual(len(actual),len(old)+11)

    def test_rejects_duplicate_or_out_of_scope_removal(self):
        old=np.arange(300).reshape(-1,3);new=np.arange(189).reshape(-1,3)
        for remove in [np.r_[np.arange(51),50],np.arange(51),np.arange(49,101)]:
            with self.assertRaises(ValueError):replace_faces(old,remove,new)

    def test_rejects_unreviewed_triangle_budget(self):
        old=np.arange(300).reshape(-1,3)
        for new in [np.zeros((64,3),int),np.zeros((62,3),int),np.full((63,3),-1)]:
            with self.assertRaises(ValueError):replace_faces(old,np.arange(52),new)

    def test_oriented_face_keys_do_not_accept_winding_flip(self):
        self.assertEqual(face_key([2,3,1]),face_key([1,2,3]));self.assertNotEqual(face_key([1,3,2]),face_key([1,2,3]))

    def test_optional_calibration_chain_and_legacy(self):
        validate_waist_manifest({})
        waist=dict(schema='malemod.stock-waist-B04-baseline-calibration/1',bindingSHA256='before-precision',onlyDeclaredNewRowsAndOldPackedTChanged=True,sourceNumericsModified=False,newTopRows=[{}]*34)
        good=dict(sourceWaist=waist,sourcePrecision=dict(rawBindingSHA256='before-precision'));validate_waist_manifest(good)
        with self.assertRaises(ValueError):validate_waist_manifest(dict(sourceWaist=waist,sourcePrecision=dict(rawBindingSHA256='unrelated-stage')))
        with self.assertRaises(ValueError):validate_waist_manifest(dict(good,sourceWaist=dict(waist,newTopRows=[{}]*35)))

if __name__=='__main__':unittest.main()
