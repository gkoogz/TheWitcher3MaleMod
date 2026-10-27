import importlib.util
from pathlib import Path
import copy,sys,unittest,tempfile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import run_v2_performance as runner
from run_v2_performance import analyze_case,distribution

class PerformanceAnalysisTest(unittest.TestCase):
    def test_added_native_import_rejects_stale_compile_without_a_count_assumption(self):
        imports=['MaleModNativeCoreStep','MaleModNativeRefreshRenderPose']
        runner.native_import_context(dict(imports=imports),dict(imports=imports))
        with self.assertRaisesRegex(ValueError,'native imports'):
            runner.native_import_context(dict(imports=imports[:1]),dict(imports=imports))

    def test_exact_pose_script_is_required_before_any_native_launch(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);scripts=root/'v2/scripts';scripts.mkdir(parents=True)
            for name in ('runtime','clinical','garment','idle'):(scripts/(name+'.ws')).write_text('// '+name)
            pose=root/'v2/build/runtime-binding/render_bones.ws';pose.parent.mkdir(parents=True);pose.write_text('// exact pose')
            expected={'local/malemod/'+p.name:runner.digest(p)for p in list(scripts.glob('*.ws'))+[pose]}
            compiled=dict(ownedSourceHashes=dict(expected,**{'local/malemod/v2_performance.ws':'probe-sha'}))
            preview=dict(files=[dict(path='Mods/modMaleModNative/content/scripts/'+p,sha256=sha)for p,sha in expected.items()])
            with patch.object(runner,'ROOT',root):
                runner.production_script_context(compiled,preview)
                old_four=copy.deepcopy(compiled);old_four['ownedSourceHashes'].pop('local/malemod/render_bones.ws')
                with self.assertRaisesRegex(ValueError,'render_bones'):runner.production_script_context(old_four,preview)
                stale=copy.deepcopy(preview);stale['files'][-1]['sha256']='stale-pose'
                with self.assertRaisesRegex(ValueError,'preview'):runner.production_script_context(compiled,stale)
                pose.write_text('// changed pose')
                with self.assertRaisesRegex(ValueError,'render_bones'):runner.production_script_context(compiled,preview)

    def fixture(self,case=0):
        state,style=case%3,case//3
        rows=[]
        for i in range(301):
            rows.append(dict(frame=i+1,request=i+1,completed=i+1,input=[state]+[50]*17+[.06,0,0,1]+[0]*12+[style],dt=.06,garmentStyle=style,resourceMask=3,nativeRendererFailed=False,visiblePhysicsServices=i,visibleSDKTicks=i,physicsServices=i+1,surfaceServices=(i+1)//2 if style else i+1,hiddenSkippedTicks=0,seconds=i*.06,features=dict(throb=0,active=0,milliseconds=1000+i*60),clinical=dict(active=False),physicsMs=2,surfaceMs=4 if not style or i%2==0 else 0,callbackMs=7,sourceWaitMs=6,bindingMs=1,visibility=dict(present=i)))
        def cp(stage,sequence):return dict(stage=stage,sequence=sequence,controls=[state]+[50]*17,garment=style,throb=0,idleChatter=False,clinicalActive=False)
        return rows,cp(650+case,1),cp(600+case,301)
    def test_observed_cadence_and_statistics(self):
        for case in range(6):
            rows,start,end=self.fixture(case);result=analyze_case(case,start,end,rows)
            self.assertEqual(result['acceptedFrames'],300)
            self.assertEqual(result['surfaceServiceRatio'],.5 if case>=3 else 1)
            self.assertEqual(result['cpuMilliseconds']['physicsMs']['mean'],2)
            self.assertAlmostEqual(result['sdkEngineFrameIntervalMs']['median'],60)
            self.assertEqual(result['sdkWallFrameIntervalMs']['p95'],60)
            self.assertEqual(result['workerDeltaSeconds']['mean'],.06)
            self.assertEqual(result['sourceFixedStepBudget']['maximumSubstepsPerCallback'],12 if case>=3 else 24)
            self.assertAlmostEqual(result['boundedInputStepEquivalent']['mean'],7.2 if case>=3 else 14.4)
    def test_visible_tick_not_serviced_rejected(self):
        rows,start,end=self.fixture();rows[100]['visiblePhysicsServices']-=1
        with self.assertRaisesRegex(ValueError,'Visible SDK'):analyze_case(0,start,end,rows)
    def test_stale_controls_and_renderer_rejected(self):
        for field,value in [('garmentStyle',1),('nativeRendererFailed',True),('resourceMask',1)]:
            rows,start,end=self.fixture();rows[10][field]=value
            with self.assertRaises(ValueError):analyze_case(0,start,end,rows)
    def test_clinical_work_and_short_window_rejected(self):
        rows,start,end=self.fixture();rows[2]['clinical']['active']=True
        with self.assertRaisesRegex(ValueError,'clinical'):analyze_case(0,start,end,rows)
        rows,start,end=self.fixture();end['sequence']=300
        with self.assertRaisesRegex(ValueError,'fewer than300'):analyze_case(0,start,end,rows)
    def test_percentile_and_invalid_samples(self):
        self.assertEqual(distribution(range(1,101))['p95'],95)
        for sample in [[],[-1],[float('nan')]]:
            with self.assertRaises(ValueError):distribution(sample)
if __name__=='__main__':unittest.main()
