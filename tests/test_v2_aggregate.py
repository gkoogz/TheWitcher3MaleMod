"""Reject incomplete feature receipts and stale or Boolean-only release claims."""
import copy,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from aggregate_v2_acceptance import panel_gates,frame_gates,verify_aggregate,inventory_hash,script_proof_gates,private_save_gates,screenshot_gates,Evidence
from mod import digest,write_json


class AggregateTests(unittest.TestCase):
    def test_screenshot_proof_binds_exact_closed_session_and_archived_pixels(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);archive=root/'session-photos';archive.mkdir();image=archive/'screenshot_1.png';image.write_bytes(b'\x89PNG\r\n\x1a\nactual capture fixture')
            session_path=root/'session.json';receipt=root/'receipt.json';identity=dict(processID=1,processCreationTime='owned')
            rows=[dict(name=image.name,path=str(image),sha256=digest(image))]
            session=dict(observations=identity,iterationScreenshotFilesRestored=True,iterationScreenshotTransaction=str(receipt),iterationScreenshotArchive=rows)
            write_json(receipt,dict(schema='malemod.screenshot-transaction/1',restored=True,originalsVerified=0,files=[],session=str(session_path),identity=identity,archive=rows))
            screenshot_gates(session,session_path,Evidence())
            session['observations']=dict(processID=2,processCreationTime='different')
            with self.assertRaisesRegex(ValueError,'another native session'):screenshot_gates(session,session_path,Evidence())
            session['observations']=identity;image.write_bytes(b'changed')
            with self.assertRaises(ValueError):screenshot_gates(session,session_path,Evidence())

    def test_actual_private_save_archive_is_required_and_hash_bound(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);archive=root/'private-created';archive.mkdir()
            save=archive/'CheckPoint_owned.sav';save.write_bytes(b'private save fixture')
            metadata=archive/'CheckPoint_owned.json';write_json(metadata,dict(modName='modmalemodcontinuetest'))
            rows=[dict(name=p.name,sha256=digest(p))for p in(save,metadata)]
            transaction=root/'save-transaction.json';write_json(transaction,dict(finishedUnixSeconds=1,originalsVerified=0,archivedPrivateCreated=rows))
            session=dict(iterationSaveTransaction=str(transaction));report=dict(generatedSaves=rows)
            private_save_gates(session,report,Evidence())
            save.write_bytes(b'changed private save')
            with self.assertRaises(ValueError):private_save_gates(session,report,Evidence())

    def test_archived_official_probe_proof_binds_exact_runtime_scripts(self):
        with tempfile.TemporaryDirectory()as directory:
            bank=Path(directory);driver=bank/'driver-source.ws';driver.write_text('// owned probe')
            proof=bank/'compile.json';write_json(proof,dict(command='native-compilescripts',exitCode=0,imports=['NativeEntry'],
                ownedSourceHashes={'local/malemod/v2_campaign.ws':digest(driver),'local/malemod/runtime.ws':'runtime-sha'}))
            session=dict(driver='D:/owned/v2_campaign.ws',driverCompileProofSHA256=digest(proof),temporaryContinueSHA256=digest(driver))
            preview=dict(files=[dict(path='Mods/modMaleModNative/content/scripts/local/malemod/runtime.ws',sha256='runtime-sha')])
            script_proof_gates('campaign',bank/'review.json',session,preview,Evidence())
            with self.assertRaisesRegex(ValueError,'Native import surface'):
                script_proof_gates('campaign',bank/'review.json',session,preview,Evidence(),['NativeEntry','NativeRefresh'])
            preview['files'][0]['sha256']='different-runtime'
            with self.assertRaises(ValueError):script_proof_gates('campaign',bank/'review.json',session,preview,Evidence())
            preview['files'][0]['sha256']='runtime-sha';driver.write_text('// changed probe')
            with self.assertRaises(ValueError):script_proof_gates('campaign',bank/'review.json',session,preview,Evidence())

    def panel(self):
        controls=[2]+[50]*17;clinical=[0,0,0];panel=dict(passed=True)
        for i in range(21):
            if i==0:controls[0]=0
            elif i==1:clinical[0]=1
            elif i==2:clinical[1]=1
            elif i==20:clinical[2]=1
            else:controls[i-2]=51
            panel[str(i)]=dict(selected=i,controls=list(controls),clinical=list(clinical),token='owned',physicalInputUsed=False,hostFocusUsed=False)
        panel.update(shiftStep=dict(controls=[2,55]+[50]*16),lighting=dict(passed=True,before=True,switched=False,restored=True),
            teachingShortcut=dict(passed=True,startFrame=10,cancelFrame=11),windowJ=dict(windowMessagePosted=True,messagesBefore=0,messagesAfter=1),
            idlePlayback=dict(nativeAutomaticEvent=True,playedBefore=4,playedAfter=5),final=dict(controls=[2]+[50]*17,clinical=[0,0,0]))
        return panel

    def test_all21_alone_does_not_replace_actual_idle_or_shortcut_proof(self):
        panel=self.panel();panel_gates(panel)
        for name in('idlePlayback','teachingShortcut','lighting','shiftStep','windowJ'):
            incomplete=copy.deepcopy(panel);incomplete.pop(name)
            with self.assertRaises(ValueError):panel_gates(incomplete)

    def test_unrelated_panel_change_is_rejected(self):
        panel=self.panel();panel['9']['controls'][17]=99
        with self.assertRaises(ValueError):panel_gates(panel)

    def test_zero_visible_or_unserviced_visible_ticks_are_rejected(self):
        row=dict(frame=1,request=1,completed=1,physicsServices=1,visibleSDKTicks=1,visiblePhysicsServices=1)
        self.assertEqual(len(frame_gates([row])),1)
        for changed in(dict(row,visibleSDKTicks=0,visiblePhysicsServices=0),dict(row,visibleSDKTicks=2),dict(row,nativeRendererFailed=True)):
            with self.assertRaises(ValueError):frame_gates([changed])

    def test_legacy_booleans_cannot_authorize_install(self):
        with self.assertRaises(ValueError):verify_aggregate(dict(schema='malemod.witcher-v2-native-acceptance/1',attachmentVisualAccepted=True,campaignPassed=True),'m','w','p',[])

    def test_changed_lower_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'evidence';path.write_bytes(b'original');row=dict(path=str(path),sha256=digest(path))
            review=dict(schema='malemod.witcher-v2-aggregate-acceptance/1',runtimeSHA256='m',workerSHA256='w',nativePreviewSHA256='p',
                payloadInventorySHA256=inventory_hash([]),performanceComparisonReviewed=True,nativeFPSParityClaimed=False,evidenceFiles=[row])
            path.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'Lower evidence changed'):verify_aggregate(review,'m','w','p',[])


if __name__=='__main__':unittest.main()
