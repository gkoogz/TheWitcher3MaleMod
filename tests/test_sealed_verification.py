"""The private observer must fail partial/out-of-order runs without game input."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import run_sealed_session as sealed

class SealedVerification(unittest.TestCase):
    def fixture(self, root, stages, trailing=b''):
        receipt=root/'build/probe/session/receipt.json';receipt.parent.mkdir(parents=True)
        module=root/'private/malemod_witcher.dll';module.parent.mkdir()
        receipt.write_text(json.dumps(dict(modulePath=str(module),observations=dict(
            processID=123,noninteractiveWindowStation=True,physicalInputUsed=False))))
        rows=b''.join((json.dumps(dict(stage=s,runtimeFlags=135))+'\n').encode() for s in stages)
        (module.parent/'verification-123.jsonl').write_bytes(rows+trailing)
        return receipt

    def test_full_run_ignores_partial_inflight_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);receipt=self.fixture(root,sealed.VERIFICATION_STAGES,b'{"stage":')
            with patch.object(sealed,'ROOT',root):
                result=sealed.wait_for_verification(receipt,1)
            self.assertTrue(result['complete']);self.assertEqual(result['observedStages'][-1],116)

    def test_partial_run_records_last_fault_then_times_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);receipt=self.fixture(root,[64,65])
            with patch.object(sealed,'ROOT',root),patch.object(sealed.time,'sleep'):
                with self.assertRaises(TimeoutError):sealed.wait_for_verification(receipt,.002)
            status=json.loads((receipt.parent/'wait-status.json').read_text())
            self.assertFalse(status['complete']);self.assertEqual(status['lastTelemetry']['stage'],65)

    def test_ordered_gap_is_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);receipt=self.fixture(root,[64,66])
            with patch.object(sealed,'ROOT',root):
                with self.assertRaisesRegex(ValueError,'order'):sealed.wait_for_verification(receipt,1)

    def test_reused_pid_old_trace_cannot_pass_new_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);receipt=self.fixture(root,sealed.VERIFICATION_STAGES)
            record=json.loads(receipt.read_text());record['launchedUnixSeconds']=sealed.time.time()+1
            receipt.write_text(json.dumps(record))
            with patch.object(sealed,'ROOT',root),patch.object(sealed.time,'sleep'):
                with self.assertRaises(TimeoutError):sealed.wait_for_verification(receipt,.002)
            self.assertEqual(json.loads((receipt.parent/'wait-status.json').read_text())['observedStages'],[])

if __name__=='__main__':unittest.main()
