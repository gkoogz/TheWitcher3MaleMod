from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import validate_v2_material_techniques as gate


class ExplicitTechniqueGateTests(unittest.TestCase):
    def setUp(self):
        self.job=ROOT/'v2/build/materials/stock-detail-01'
        if not (self.job/'graph-compiled.json').exists():
            self.skipTest('Official stock-detail graph fixture unavailable')
        self.output=self.job/'build/unittest-technique-preflight'

    def test_default_never_invokes_native_compiler(self):
        with patch.object(gate.native,'compile_one',side_effect=AssertionError('Unexpected compiler')) as native:
            proof=gate.validate(self.job,self.output)
            self.assertTrue(proof['preflightPassed'])
            self.assertFalse(proof['nativeCommandExecuted'])
            native.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_existing_or_unowned_output_rejected(self):
        for path in [self.job/'build/intake',ROOT/'build/wrong-technique-output']:
            with self.assertRaises(ValueError):gate.preflight(self.job,path)

    def test_uncompiled_graph_rejected(self):
        with patch.object(gate,'read_json',return_value={'nativeCompiled':False}):
            with self.assertRaises(ValueError):gate.preflight(self.job,self.output)

    def test_native_failure_restores_exact_job_selector(self):
        old=gate.native.JOB
        with patch.object(gate.native,'compile_one',side_effect=RuntimeError('fixture')):
            with self.assertRaises(RuntimeError):gate.validate(self.job,self.output,True)
        self.assertEqual(gate.native.JOB,old)

    def test_incomplete_technique_inventory_rejected(self):
        with patch.object(gate.native,'compile_one',return_value={'techniqueCount':1211}):
            with self.assertRaises(ValueError):gate.validate(self.job,self.output,True)
        self.assertFalse(self.output.exists())


if __name__=='__main__':unittest.main()
