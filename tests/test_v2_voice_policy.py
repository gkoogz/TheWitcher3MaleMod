import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import install_v2

class VoicePolicyTests(unittest.TestCase):
    def test_needs_recording_never_reimports_wolverine_audio(self):
        with tempfile.TemporaryDirectory()as d:
            root=Path(d);(root/'v2').mkdir();(root/'v2/voice-profile.json').write_text(json.dumps(dict(schema='malemod.witcher-voice-profile/1',character_id='geralt',state='needs_recording')))
            with patch.object(install_v2,'ROOT',root):
                source,paths=install_v2.private_sources()
                self.assertEqual([p.name for p in paths],['TeachingFluid.ini'])
                self.assertFalse(any(p.suffix=='.wav'for p in paths))
    def test_missing_or_unknown_voice_policy_fails_closed(self):
        with tempfile.TemporaryDirectory()as d:
            root=Path(d);(root/'v2').mkdir()
            with patch.object(install_v2,'ROOT',root):
                with self.assertRaises(FileNotFoundError):install_v2.private_sources()
                (root/'v2/voice-profile.json').write_text(json.dumps(dict(schema='malemod.witcher-voice-profile/1',character_id='geralt',state='legacy')))
                with self.assertRaises(ValueError):install_v2.private_sources()
if __name__=='__main__':unittest.main()
