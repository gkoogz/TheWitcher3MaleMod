import sys
from pathlib import Path
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from mod import write_json
from build_v2_skin_cache import calibrated_range_diagnostics


class ShaderDiagnosticCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.database=self.root/'empty.db';write_json(self.database,{'files':[]})
        self.baseline=self.root/'baseline.json'
        write_json(self.baseline,dict(args=['-db='+str(self.database)],exitCode=0))
        self.error='[Error][WCC] Min cannot be larger than max 1.000000 < -1.000000\n'
        self.baseline.with_suffix('.log').write_text(self.error+'Found 0 files to process\n')
        self.command=dict(logPath='target.log',exitCode=0)
        (self.root/'target.log').write_text(self.error+'Found 1 files to process\nProcessing [0/1]\n')

    def tearDown(self):self.temp.cleanup()

    def test_exact_empty_database_baseline_accepted(self):
        proof=calibrated_range_diagnostics(self.root,self.command,self.baseline)
        self.assertEqual(proof['identicalPreProcessingDiagnostics'],1)
        self.assertEqual(proof['materialProcessingErrors'],0)

    def test_new_diagnostic_rejected(self):
        with (self.root/'target.log').open('a')as stream:stream.write('[Error][WCC] Different material error\n')
        with self.assertRaises(ValueError):calibrated_range_diagnostics(self.root,self.command,self.baseline)

    def test_same_diagnostic_during_material_processing_rejected(self):
        (self.root/'target.log').write_text('Found 1 files to process\n'+self.error)
        with self.assertRaises(ValueError):calibrated_range_diagnostics(self.root,self.command,self.baseline)

    def test_nonempty_control_or_failed_command_rejected(self):
        self.command['exitCode']=1
        with self.assertRaises(ValueError):calibrated_range_diagnostics(self.root,self.command,self.baseline)
        self.command['exitCode']=0;write_json(self.database,{'files':[{'path':'other.w2mg'}]})
        with self.assertRaises(ValueError):calibrated_range_diagnostics(self.root,self.command,self.baseline)

    def test_two_explicit_graphs_keep_same_preprocessing_calibration(self):
        (self.root/'target.log').write_text(self.error+'Found 2 files to process\nProcessing [0/2]\nProcessing [1/2]\n')
        proof=calibrated_range_diagnostics(self.root,self.command,self.baseline,2)
        self.assertEqual(proof['materialProcessingErrors'],0)
        with self.assertRaises(ValueError):calibrated_range_diagnostics(self.root,self.command,self.baseline,1)


if __name__=='__main__':unittest.main()
