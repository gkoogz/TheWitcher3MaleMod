"""Installation ownership and rollback boundaries, using disposable files only."""
import sys
import tempfile
import unittest
import shutil
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import install_v2 as installer


class TransactionTests(unittest.TestCase):
    def setup_tree(self, root):
        game=root/'game';payload=root/'payload';game.mkdir();payload.mkdir()
        (game/'old.bin').write_bytes(b'old');(game/'shared.bin').write_bytes(b'before')
        (game/'unrelated.bin').write_bytes(b'user')
        (payload/'shared.bin').write_bytes(b'after');(payload/'new.bin').write_bytes(b'new')
        rows=lambda r,names:[dict(path=n,sha256=installer.digest(r/n))for n in names]
        return game,payload,rows(game,['old.bin','shared.bin']),rows(payload,['shared.bin','new.bin'])

    def test_upgrade_and_exact_old_backup(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);game,payload,old,new=self.setup_tree(root)
            installer.replace_transaction(game,payload,old,new,root/'rollback')
            installer.verify(game,new);installer.verify(root/'rollback',old)
            self.assertFalse((game/'old.bin').exists())
            self.assertEqual((game/'unrelated.bin').read_bytes(),b'user')

    def test_failure_restores_removed_and_replaced_files(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);game,payload,old,new=self.setup_tree(root);copy=installer.shutil.copy2
            def interrupted(source,destination,*a,**kw):
                if source==payload/'new.bin':raise OSError('simulated write failure')
                return copy(source,destination,*a,**kw)
            with patch.object(installer.shutil,'copy2',interrupted):
                with self.assertRaises(OSError):installer.replace_transaction(game,payload,old,new,root/'rollback')
            installer.verify(game,old)
            self.assertFalse((game/'new.bin').exists())
            self.assertEqual((game/'unrelated.bin').read_bytes(),b'user')

    def test_changed_owned_file_and_unmanaged_collision_are_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);game,payload,old,new=self.setup_tree(root)
            (game/'shared.bin').write_bytes(b'user edit')
            with self.assertRaises(ValueError):installer.replace_transaction(game,payload,old,new,root/'rollback')
            self.assertFalse((root/'rollback').exists())
            (game/'shared.bin').write_bytes(b'before');(game/'new.bin').write_bytes(b'user file')
            with self.assertRaises(ValueError):installer.replace_transaction(game,payload,old,new,root/'rollback')
            self.assertEqual((game/'new.bin').read_bytes(),b'user file')

    def test_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ['../escape','/absolute','sub\\escape','','.','sub//escape']:
                with self.assertRaises(ValueError):installer.target(Path(d),name)

    def test_partial_atomic_copy_never_replaces_existing_bytes(self):
        with tempfile.TemporaryDirectory()as d:
            root=Path(d);source=root/'source';dest=root/'dest';source.write_bytes(b'new');dest.write_bytes(b'original')
            def interrupted(source,temporary):
                temporary.write_bytes(b'partial');raise OSError('power interruption')
            with patch.object(installer.shutil,'copy2',interrupted):
                with self.assertRaises(OSError):installer.copy_owned(source,dest)
            self.assertEqual(dest.read_bytes(),b'original')
            self.assertEqual({p.name for p in root.iterdir()},{'source','dest'})

    def test_durable_journal_callback_precedes_first_mutation(self):
        with tempfile.TemporaryDirectory()as d:
            root=Path(d);game,payload,old,new=self.setup_tree(root)
            def journal(backup):
                installer.verify(game,old);installer.verify(backup,old)
                raise OSError('cannot persist ownership receipt')
            with self.assertRaises(OSError):installer.replace_transaction(game,payload,old,new,root/'rollback',on_prepared=journal)
            installer.verify(game,old);self.assertFalse((game/'new.bin').exists())

    def test_inventory_requires_exact_allowlist_and_rejects_development_files(self):
        path='bin/x64_dx12/malemod-native/a.bin';rows=[dict(path=path,sha256='a'*64)]
        contract=dict(schema='malemod.witcher-v2-payload/1',requiredFiles=[path])
        self.assertEqual(installer.payload_inventory(rows,contract),rows)
        for invalid in [rows+rows,[],rows+[dict(path='bin/x64_dx12/malemod-native/extra.bin',sha256='b'*64)]]:
            with self.assertRaises(ValueError):installer.payload_inventory(invalid,contract)
        for suffix in ['v2-checkpoint-1.bin','trace.jsonl','debug.pdb','iteration.bin']:
            bad='bin/x64_dx12/malemod-native/'+suffix
            with self.assertRaises(ValueError):installer.payload_inventory([dict(path=bad,sha256='a'*64)],dict(contract,requiredFiles=[bad]))

    def test_private_inventory_requires_exact_original_hashes(self):
        path='bin/x64_dx12/malemod-native/TeachingAudio/Phase1/clip-01.wav'
        row=dict(path=path,sha256='a'*64);private=dict(files=[row]);contract=dict(schema='malemod.witcher-v2-payload/1',requiredFiles=[],localAssetManifest='local/v2-private-assets.json')
        self.assertEqual(installer.payload_inventory([row],contract,private),[row])
        with self.assertRaises(ValueError):installer.payload_inventory([dict(row,sha256='b'*64)],contract,private)
        with self.assertRaises(ValueError):installer.payload_inventory([row],contract)

    def test_body_inventory_derives_explicit_shader_caches_without_a_file_count(self):
        core=sorted(installer.BODY_CORE_FILES);shader=installer.BODY_PACKAGE_PREFIX+'shaderDx12_0.cache'
        contract=dict(schema='malemod.witcher-v2-payload/1',requiredFiles=core+[shader])
        self.assertEqual(installer.body_package_paths(contract),set(core+[shader]))
        rows=[dict(path=p,sha256='a'*64)for p in contract['requiredFiles']]
        old={r['path']:r for r in rows};changed={p:dict(r)for p,r in old.items()}
        for p in installer.LOD_MUTABLE_FILES:changed[p]['sha256']='b'*64
        self.assertEqual(installer.lod_body_inventory(old,changed,contract),set(old))
        changed[shader]['sha256']='b'*64
        with self.assertRaises(ValueError):installer.lod_body_inventory(old,changed,contract)
        self.assertEqual(len(installer.payload_inventory(rows,contract)),len(contract['requiredFiles']))
        with self.assertRaises(ValueError):installer.payload_inventory(rows[:-1],contract)
        extra=installer.BODY_PACKAGE_PREFIX+'shaderDx12_1.cache'
        with self.assertRaises(ValueError):installer.payload_inventory(rows+[dict(path=extra,sha256='a'*64)],contract)
        contract['requiredFiles'].append(extra)
        self.assertEqual(installer.body_package_paths(contract),set(core+[shader,extra]))
        self.assertEqual(len(installer.payload_inventory(rows+[dict(path=extra,sha256='a'*64)],contract)),len(core)+2)

    def rollback_tree(self,root):
        game,payload,old,new=self.setup_tree(root);backup=root/'rollback';local=root/'local';local.mkdir()
        installer.replace_transaction(game,payload,old,new,backup)
        for name in ('native-installation.json','installation.json'):
            (backup/name).write_bytes(b'old receipt');(local/name).write_bytes(b'new receipt')
        installer.write_json(backup/'rollback.json',dict(schema='malemod.witcher-v2-rollback/1',game=str(game),old=old,new=new,
            receipts={name:installer.digest(backup/name)for name in ('native-installation.json','installation.json')}))
        return game,payload,old,new,backup,local

    def test_rollback_failure_restores_entire_current_version(self):
        with tempfile.TemporaryDirectory()as d:
            root=Path(d);game,payload,old,new,backup,local=self.rollback_tree(root);copy=shutil.copy2
            def interrupted(source,destination,*a,**kw):
                if Path(source).resolve()==(backup/'shared.bin').resolve():raise OSError('simulated rollback failure')
                return copy(source,destination,*a,**kw)
            with patch.object(installer,'ROOT',root),patch.object(installer,'settings',return_value={'game':game}),patch.object(installer,'quiet'),patch.object(installer.shutil,'copy2',interrupted):
                with self.assertRaises(OSError):installer.rollback(backup)
            installer.verify(game,new);self.assertFalse((game/'old.bin').exists())
            self.assertEqual((local/'native-installation.json').read_bytes(),b'new receipt')

    def test_rollback_restores_receipts_and_original_file_union(self):
        with tempfile.TemporaryDirectory()as d:
            root=Path(d);game,payload,old,new,backup,local=self.rollback_tree(root)
            with patch.object(installer,'ROOT',root),patch.object(installer,'settings',return_value={'game':game}),patch.object(installer,'quiet'):
                self.assertTrue(installer.rollback(backup)['restored'])
            installer.verify(game,old);self.assertFalse((game/'new.bin').exists())
            self.assertEqual((local/'native-installation.json').read_bytes(),b'old receipt')

    def test_interrupted_recovery_preserves_unknown_edits_then_restores_known_mixture(self):
        with tempfile.TemporaryDirectory()as d:
            root=Path(d);game,payload,old,new,backup,local=self.rollback_tree(root)
            (game/'shared.bin').write_bytes(b'user edit')
            with patch.object(installer,'ROOT',root),patch.object(installer,'settings',return_value={'game':game}),patch.object(installer,'quiet'):
                with self.assertRaises(ValueError):installer.recover(backup)
                self.assertEqual((game/'shared.bin').read_bytes(),b'user edit')
                (game/'shared.bin').write_bytes(b'before')
                self.assertTrue(installer.recover(backup)['recovered'])
            installer.verify(game,old);self.assertFalse((game/'new.bin').exists())


if __name__=='__main__':unittest.main()
