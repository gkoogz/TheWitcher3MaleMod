from pathlib import Path
import math
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from prepare_iteration_world import validate_world_dimensions,author


class NativeWorldDimensionsTests(unittest.TestCase):
    def test_minimum_world_keeps_independent_studio_extent(self):
        self.assertEqual(validate_world_dimensions(256),1)
        self.assertEqual(validate_world_dimensions(8192),32)
        authored=author({'floor':{'extentMeters':32,'thicknessMeters':.5},'spawnMeters':[0,0,.03]})
        world=authored['levels/malemod_iteration/malemod_iteration.w2w']['_chunks']['CGameWorld #0']['_vars']
        self.assertEqual(world['worldDimensions']['_value'],256)

    def test_inconsistent_zero_tile_and_misaligned_extents_rejected(self):
        for value in [0,-256,128,255,257,256.5,math.inf,math.nan]:
            with self.assertRaises(ValueError):validate_world_dimensions(value)


if __name__=='__main__':unittest.main()
