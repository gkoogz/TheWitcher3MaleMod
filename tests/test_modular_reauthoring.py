"""Guard measured-name restoration and storage-neutral rollback reuse."""
from pathlib import Path
import hashlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from prepare_modular_render import measured_rig_names
from install_modular_native import verified_existing_rollback


class Reauthoring(unittest.TestCase):
    def test_stock_name_order_and_recorded_extension(self):
        profile={'skeleton': {'stockPrefixCount':2, 'totalJoints':3,
            'pelvis':{'index':1,'name':'pelvis'},
            'addedJoints':[{'index':2,'name':'recorded_extension'}]}}
        rig={'_chunks':{'CSkeleton #0':{'_vars':{'bones':{'_elements':[
            {'_vars':{'name':{'_value':n}}} for n in ['root','pelvis']]}}}}}
        with patch('prepare_modular_render.read_json',return_value=rig):
            self.assertEqual(measured_rig_names(profile,Path('stock.json')),
                             ['root','pelvis','recorded_extension'])
            profile['skeleton']['addedJoints'][0]['index']=3
            with self.assertRaisesRegex(ValueError,'order'):
                measured_rig_names(profile,Path('stock.json'))

    def test_rollback_reuse_requires_exact_accepted_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve(); backup=root/'old';backup.mkdir()
            payload=backup/'owned.bin';payload.write_bytes(b'accepted')
            previous={'files':[{'path':'owned.bin','sha256':hashlib.sha256(b'accepted').hexdigest()}]}
            with patch('install_modular_native.load_preview',return_value=(backup,previous)):
                self.assertEqual(verified_existing_rollback(root/'preview.json',previous,root/'game',root/'candidate'),backup)
                with self.assertRaisesRegex(ValueError,'separate'):
                    verified_existing_rollback(root/'preview.json',previous,backup,root/'candidate')
                payload.write_bytes(b'different')
                with self.assertRaisesRegex(ValueError,'differs'):
                    verified_existing_rollback(root/'preview.json',previous,root/'game',root/'candidate')


if __name__=='__main__':unittest.main()
