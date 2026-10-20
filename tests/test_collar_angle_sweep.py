"""Coverage must reject skipped angles, stale geometry and partial body output."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from record_collar_angle_sweep import ANGLES, validate


class SweepEvidence(unittest.TestCase):
    def rows(self):
        return [dict(stage=300+i, sequence=i+1, completedSequence=i+1,
                     controls=[i//64,100,100,100,35,100,95,ANGLES[(i//4)%16],
                               100,50,50,50,50,50,50,50,50,51],
                     bodyResourceMask=3, vertices=49884, uploadFNV64=str(i))
                for i in range(192)]

    def test_complete_range(self):
        cases=validate(self.rows())
        self.assertEqual(len(cases),192)
        self.assertEqual({(c['state'],c['angle']) for c in cases},
                         {(s,a) for s in range(3) for a in ANGLES})

    def test_missing_view(self):
        with self.assertRaisesRegex(ValueError,'192 ordered'):
            validate(self.rows()[:-1])

    def test_stale_controls(self):
        rows=self.rows();rows[20]['controls'][7]=15
        with self.assertRaisesRegex(ValueError,'controls'):
            validate(rows)

    def test_incomplete_surface(self):
        rows=self.rows();rows[20]['completedSequence']-=1
        with self.assertRaisesRegex(ValueError,'incomplete surface'):
            validate(rows)

    def test_missing_upper_body(self):
        rows=self.rows();rows[20]['bodyResourceMask']=1
        with self.assertRaisesRegex(ValueError,'Both body resources'):
            validate(rows)


if __name__=='__main__':
    unittest.main()
