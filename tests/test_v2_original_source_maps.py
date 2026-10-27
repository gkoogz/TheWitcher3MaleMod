import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from prepare_v2_original_source_maps import converted_normal


class OriginalNormalTests(unittest.TestCase):
    def test_original_positive_z_decode_and_native_encoding_without_grade(self):
        pixels=np.array([[128,128,255],[255,128,0],[0,255,0]],dtype=np.uint8);before=pixels.copy()
        actual=converted_normal(pixels)
        np.testing.assert_array_equal(actual,np.array([[128,128,255],[255,128,128],[37,218,128]],dtype=np.uint8))
        np.testing.assert_array_equal(pixels,before)


if __name__=='__main__':unittest.main()
