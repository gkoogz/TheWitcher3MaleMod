"""Independent geometric witnesses for the offline ramp intersection gate."""
import sys
from pathlib import Path
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from verify_radial_progressivity import segment_triangle,crossings


class RadialQualityWitnesses(unittest.TestCase):
    def test_strict_plane_crossing_and_parallel_segment(self):
        t=np.array([[[0.,0,0],[1,0,0],[0,1,0]]])
        self.assertTrue(segment_triangle(np.array([[.25,.25,-1]]),np.array([[.25,.25,1]]),t)[0])
        self.assertFalse(segment_triangle(np.array([[.25,.25,1]]),np.array([[.5,.25,1]]),t)[0])

    def test_existing_edge_touch_is_not_an_intersection(self):
        t=np.array([[[0.,0,0],[1,0,0],[0,1,0]]])
        self.assertFalse(segment_triangle(np.array([[.5,0,-1]]),np.array([[.5,0,1]]),t)[0])

    def test_nonadjacent_crossing_is_found_and_disjoint_faces_are_clear(self):
        p=np.array([[-.03,.02,1],[.03,.02,1],[0,.08,1],[0,.03,.98],[0,.03,1.02],[0,.06,1.]])
        faces=np.array([[0,1,2],[3,4,5]])
        self.assertEqual(crossings(p,p,faces)['strictNonadjacentIntersections'],1)
        disjoint=p.copy();disjoint[3:,0]+=.1
        self.assertEqual(crossings(disjoint,disjoint,faces)['strictNonadjacentIntersections'],0)

    def test_shared_vertex_aliases_are_excluded(self):
        p=np.array([[-.03,.02,1],[.03,.02,1],[0,.08,1],[-.03,.02,1],[0,.03,1.02],[0,.06,1.]])
        self.assertEqual(crossings(p,p,np.array([[0,1,2],[3,4,5]]))['strictNonadjacentIntersections'],0)


if __name__=='__main__':unittest.main()
