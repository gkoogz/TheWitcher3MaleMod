"""Startup repair must reject drift and recover both native and script files."""
import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import install_native_runtime as native
from mod import digest,write_json
from startup_movies import PATCH,validate_startup_queue

class StartupRepair(unittest.TestCase):
    def fixture(self,root):
        game=root/'game';sdk=root/'sdk';proof_path=root/'build/proof.json'
        exe=game/'bin/x64_dx12/witcher3.exe';exe.parent.mkdir(parents=True);exe.write_bytes(b'current retail')
        replacements=[];files=[]
        for rel in ['bin/x64_dx12/dinput8.dll','bin/x64_dx12/malemod-native/malemod_witcher.dll']:
            target=game/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b'original '+rel.encode())
            candidate=root/'build'/Path(rel).name;candidate.parent.mkdir(parents=True,exist_ok=True);candidate.write_bytes(b'fixed '+rel.encode())
            files.append(dict(path=rel,sha256=digest(target)))
            replacements.append(dict(path=rel,source=str(candidate),sha256=digest(candidate)))
        old='Mods/modLocalSkipStartupMovies/content/scripts/game/r4Game.ws'
        new='Mods/modLocalSkipStartupMovies/content/scripts/local/startup_movies.ws'
        target=game/old;target.parent.mkdir(parents=True);target.write_text('old stock override')
        helper=root/'build/helper.ws';helper.write_text(PATCH,newline='\n')
        stock=sdk/'r4data/scripts/game/r4Game.ws';stock.parent.mkdir(parents=True)
        stock.write_text("public function PopulateMenuQueueStartupOnce(out menus : array<name>) {menus.PushBack('StartupMoviesMenu');}")
        verification=root/'build/helper-verification.json'
        write_json(verification,dict(name='modLocalSkipStartupMovies',sourceSHA256=digest(stock),
            native={'exitCode':0},files={'content/scripts/local/startup_movies.ws':digest(helper)}))
        receipt=dict(game=str(game),baseCommit='retained-pin',files=files)
        write_json(root/'local/native-installation.json',receipt)
        write_json(root/'local/startup-movies-install.json',dict(name='modLocalSkipStartupMovies',files={'content/scripts/game/r4Game.ws':digest(target)}))
        proof=dict(schema='malemod.startup-repair/1',baseCommit='retained-pin',gameSHA256=digest(exe),
            replacements=replacements,evidenceFiles=[dict(path=str(verification),sha256=digest(verification))],attachmentRegression={'fullCertification':False},
            startupMoviesRepair=dict(oldPath=old,newPath=new,source=str(helper),verification=str(verification),oldSHA256=digest(target),sha256=digest(helper)))
        for flag in ['abiObserved','startupGateTestPassed','offlineAttachmentRegressionPassed','nativeRoomRegressionPassed','nativeCampaignRegressionPassed','candidateSessionsClosed']:proof[flag]=True
        write_json(proof_path,proof)
        return dict(game=game,redkit=sdk),proof_path,proof,receipt

    def test_install_changes_only_abi_and_stale_override(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();cfg,path,proof,previous=self.fixture(root)
            with patch.object(native,'ROOT',root),patch.object(native.subprocess,'run') as query:
                query.return_value.stdout='';updated=native.install_startup_repair(cfg,path)
            for row in proof['replacements']:self.assertEqual(digest(cfg['game']/row['path']),row['sha256'])
            helper=proof['startupMoviesRepair'];self.assertFalse((cfg['game']/helper['oldPath']).exists())
            self.assertEqual((cfg['game']/helper['newPath']).read_text(),PATCH)
            self.assertEqual(updated['baseCommit'],previous['baseCommit'])
            backup=Path(updated['backup'])
            for row in previous['files']:self.assertEqual(digest(backup/row['path']),row['sha256'])
            self.assertEqual(digest(backup/helper['oldPath']),helper['oldSHA256'])

    def test_rejects_changed_game_before_copy(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();cfg,path,proof,previous=self.fixture(root)
            (cfg['game']/'bin/x64_dx12/witcher3.exe').write_bytes(b'new patch')
            with patch.object(native,'ROOT',root),patch.object(native.subprocess,'run') as query:
                query.return_value.stdout=''
                with self.assertRaises(ValueError):native.install_startup_repair(cfg,path)
            self.assertEqual(json.loads((root/'local/native-installation.json').read_text()),previous)

    def test_partial_native_copy_restores_originals(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();cfg,path,proof,previous=self.fixture(root);copy=native.shutil.copy2
            failing_row=proof['replacements'][1]
            def failing(source,target):
                if str(source)==failing_row['source'] and Path(target)==cfg['game']/failing_row['path']:
                    Path(target).write_bytes(b'partial');raise OSError('copy failure')
                return copy(source,target)
            with patch.object(native,'ROOT',root),patch.object(native.subprocess,'run') as query,patch.object(native.shutil,'copy2',failing):
                query.return_value.stdout=''
                with self.assertRaises(OSError):native.install_startup_repair(cfg,path)
            for row in previous['files']:self.assertEqual(digest(cfg['game']/row['path']),row['sha256'])
            helper=proof['startupMoviesRepair'];self.assertTrue((cfg['game']/helper['oldPath']).exists())
            self.assertFalse((cfg['game']/helper['newPath']).exists())

    def test_startup_recipe_refuses_additional_stock_behavior(self):
        with self.assertRaises(RuntimeError):validate_startup_queue("public function PopulateMenuQueueStartupOnce(out menus : array<name>) {menus.PushBack('OtherMenu');menus.PushBack('StartupMoviesMenu');}")

    def test_general_reinstall_refuses_old_native_build(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();cfg,_,_,_=self.fixture(root)
            expected=digest(cfg['game']/'bin/x64_dx12/witcher3.exe')
            write_json(root/'characters/game-native-profile.json',{'gameSHA256':expected})
            release=root/'build/old';release.mkdir();module=release/'malemod_witcher.dll'
            module.write_bytes(b'previous executable profile')
            with patch.object(native,'ROOT',root):
                with self.assertRaises(ValueError):native.verify_native_compatibility(cfg['game'],release)
                module.write_bytes(b'compiled profile '+expected.encode())
                native.verify_native_compatibility(cfg['game'],release)

if __name__=='__main__':unittest.main()
