"""Acceptance gates must reject invented grounding, idle-only and stalled output."""
import copy
import sys
import unittest,tempfile
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import accept_v2_room as room
from accept_v2_room import observations,archived_frame,room_closure
from mod import digest


class RoomAcceptanceTests(unittest.TestCase):
    def closure_fixture(self,root):
        receipt=root/'build/probe/session/receipt.json';receipt.parent.mkdir(parents=True)
        photos=root/'v2/build/screenshot-transactions/test/receipt.json';photos.parent.mkdir(parents=True)
        session=dict(closed=True,exitCode=0,audioRestored=True,iterationWorldFilesRemoved=True,
            observations=dict(processID=7,processCreationTime='123'),iterationScreenshotTransaction=str(photos),
            iterationScreenshotFilesRestored=True,iterationScreenshotOriginalsVerified=1,iterationScreenshotArchive=[])
        transaction=dict(schema='malemod.screenshot-transaction/1',restored=True,files=[dict(name='ordinary.png',sha256='original')],
            originalsVerified=1,archive=[],session=str(receipt),identity=session['observations'])
        room.write_json(photos,transaction);return receipt,photos,session,transaction

    def test_normal_installed_finish_and_restoration_receipt_without_duplicate_fields_pass(self):
        with tempfile.TemporaryDirectory()as directory,patch.object(room,'ROOT',Path(directory)):
            receipt,photos,session,transaction=self.closure_fixture(Path(directory))
            room_closure(session,receipt)
            # Installed sessions do not carry nativePreview; the durable photo
            # receipt also supports snapshots without duplicated summary flags.
            for key in('iterationScreenshotFilesRestored','iterationScreenshotOriginalsVerified','iterationScreenshotArchive'):session.pop(key)
            room_closure(session,receipt)

    def test_crash_after_views_or_gone_audio_cannot_accept_installed_room(self):
        with tempfile.TemporaryDirectory()as directory,patch.object(room,'ROOT',Path(directory)):
            receipt,photos,session,transaction=self.closure_fixture(Path(directory))
            for delta in(dict(exitCode=1296891907),dict(audioRestored=False,audioSessionsGone=True),dict(iterationWorldFilesRemoved=False)):
                changed=dict(session,**delta)
                with self.assertRaisesRegex(ValueError,'normal exit'):room_closure(changed,receipt)

    def test_pending_mismatched_or_unverified_photo_transaction_rejected(self):
        with tempfile.TemporaryDirectory()as directory,patch.object(room,'ROOT',Path(directory)):
            receipt,photos,session,transaction=self.closure_fixture(Path(directory))
            for delta in(dict(restored=False),dict(originalsVerified=0),dict(session=str(receipt.parent/'another.json')),dict(identity=dict(processID=8))):
                room.write_json(photos,dict(transaction,**delta))
                with self.assertRaisesRegex(ValueError,'restoration proof'):room_closure(session,receipt)
            room.write_json(photos,transaction)
            with self.assertRaisesRegex(ValueError,'summary'):room_closure(dict(session,iterationScreenshotFilesRestored=False),receipt)

    def test_closed_room_frame_resolves_archived_native_photo(self):
        with tempfile.TemporaryDirectory()as directory:
            archived=Path(directory)/'screenshot_1.png';archived.write_bytes(b'owned native image')
            requested=Path.home()/'Documents/The Witcher 3/screenshots/screenshot_1.png'
            session=dict(iterationScreenshotArchive=[dict(name=requested.name,path=str(archived),sha256=digest(archived))])
            self.assertEqual(archived_frame(session,requested),archived.resolve())
            archived.write_bytes(b'changed')
            with self.assertRaises(ValueError):archived_frame(session,requested)
    def rows(self):
        rows=[dict(frame=i,request=i,completed=i,resourceMask=3,coverageDraws=1,visibleSDKTicks=i,visiblePhysicsServices=i)for i in range(1,102)]
        for seconds,x in [(1,0),(5,2)]:
            rows.append(dict(iterationReadback=True,seconds=seconds,paused=False,vectors=[
                [1,0,0,-251],[0,1,0,-252],[0,0,1,-253],[x,0,1,1],[1,1,1,1],[0,0,1,1],[0,0,1,1],[0,0,1,0]]))
        return rows

    def test_measured_grounded_movement_and_complete_frames(self):
        value=observations(self.rows());self.assertEqual(value['movementDistance'],2);self.assertEqual(value['sourceFrames'],101)

    def lifecycle_rows(self):
        rows=self.rows();rows[-1]['vectors'][3][0]=0
        sample=copy.deepcopy(rows[-1]);sample['seconds']=8
        for i,marker in enumerate((-201,-202,-203)):sample['vectors'][i][3]=marker
        sample['vectors'][3][0]=2
        rows.append(sample);return rows

    def test_actual_lifecycle_walk_on_verified_static_floor(self):
        value=observations(self.lifecycle_rows())
        self.assertEqual(value['movementDistance'],2)
        self.assertEqual(value['floorReadbacks'],2)
        self.assertEqual(value['groundedLifecycleReadbacks'],1)

    def test_lifecycle_cannot_invent_floor_or_grounding(self):
        for change in ('no_floor','one_floor','moving_floor','tilted_floor','airborne','before_floor','wrong_marker','no_player'):
            rows=self.lifecycle_rows()
            if change=='no_floor':rows=[r for r in rows if not r.get('iterationReadback')or r['vectors'][0][3]==-201]
            elif change=='one_floor':rows.pop(-2)
            elif change=='moving_floor':rows[-2]['vectors'][5][0]=1
            elif change=='tilted_floor':rows[-2]['vectors'][7][0]=1
            elif change=='airborne':rows[-1]['vectors'][3][2]=3
            elif change=='before_floor':rows[-1]['seconds']=0
            elif change=='wrong_marker':rows[-1]['vectors'][0][3]=-202
            elif change=='no_player':rows[-1]['vectors'][4][2]=0
            with self.subTest(change=change),self.assertRaises(ValueError):observations(rows)

    def test_idle_motion_wrong_floor_and_airborne_are_rejected(self):
        for mutate in [lambda v:v[3].__setitem__(0,0),lambda v:v[4].__setitem__(2,0),lambda v:v[3].__setitem__(2,3)]:
            rows=copy.deepcopy(self.rows());mutate(rows[-1]['vectors'])
            with self.assertRaises(ValueError):observations(rows)

    def test_incomplete_physics_and_no_surface_publication_are_rejected(self):
        rows=self.rows();rows[20]['completed']-=1
        with self.assertRaises(ValueError):observations(rows)
        rows=self.rows()
        for row in rows:
            if 'frame'in row:row['coverageDraws']=0
        with self.assertRaises(ValueError):observations(rows)

    def test_native_renderer_fault_or_unserviced_visible_tick_is_rejected(self):
        rows=self.rows();rows[20]['nativeRendererFailed']=True
        with self.assertRaises(ValueError):observations(rows)
        rows=self.rows();rows[20]['visibleSDKTicks']+=1
        with self.assertRaises(ValueError):observations(rows)


if __name__=='__main__':unittest.main()
