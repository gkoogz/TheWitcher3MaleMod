import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from bind_wolverine_v2 import complete_body_domain


class ComplementaryBodyTests(unittest.TestCase):
    def test_missing_side_is_present_and_retains_its_bank_indices(self):
        right=np.array([[1.,0,0],[2,0,0],[1,1,0]])
        left=np.array([[-1.,0,0],[-2,0,0],[-1,1,0]])
        vertices,faces=complete_body_domain([right,left],[np.array([[0,1,2]]),np.array([[0,1,2]])])
        np.testing.assert_array_equal(vertices,np.vstack([right,left]))
        np.testing.assert_array_equal(faces,[[0,1,2],[3,4,5]])
        self.assertTrue(np.all(vertices[faces[1],0]<0))

    def test_zero_area_donor_is_removed_without_welding_distinct_rows(self):
        p=np.array([[0.,0,0],[1,0,0],[0,1,0],[0,0,0]])
        vertices,faces=complete_body_domain([p,p],[np.array([[0,1,2],[0,3,1]]),np.array([[0,1,2]])])
        self.assertEqual(len(vertices),8)
        np.testing.assert_array_equal(faces,[[0,1,2],[4,5,6]])

    def test_missing_or_invalid_second_part_fails_closed(self):
        p=np.eye(3)
        with self.assertRaisesRegex(ValueError,'Both'):complete_body_domain([p],[np.array([[0,1,2]])])
        with self.assertRaisesRegex(ValueError,'topology'):complete_body_domain([p,p],[np.array([[0,1,2]]),np.array([[0,1,3]])])


if __name__=='__main__':unittest.main()
