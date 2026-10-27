"""Compare closed quiet native reports while keeping CPU scopes and FPS apart."""
import argparse,json,struct,hashlib
from pathlib import Path
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def size(p):
 b=p.read_bytes()
 if b[:8]!=b'\x89PNG\r\n\x1a\n':raise ValueError('Missing actual native PNG dimensions')
 return list(struct.unpack_from('>II',b,16))
def compare(source,target):
 s=json.loads(source.read_text());t=json.loads(target.read_text())
 if not s.get('complete')or not s.get('close',{}).get('audioRestored'):raise ValueError('Canonical reference did not close/restore')
 if not t.get('passed')or not t.get('closed',{}).get('closed')or not t.get('settingsOriginalsVerified'):raise ValueError('Target native run did not pass/close/restore')
 if len(s['cases'])!=6 or len(t['cases'])!=6:raise ValueError('Six controlled cases required in each engine')
 rows=[]
 for w,v in zip(s['cases'],t['cases']):
  style=int(w['garment']=='Jockstrap');state=w['physicsState']
  if v['state']!=state or v['garment']!=style or w['overall']!=50 or w['shapeControls']!=50 or w['throbMode']or w['menuOpen']:raise ValueError('Control identity differs')
  p=w['cpuPhases']['physics'];surface=w['cpuPhases']['gameplay surface']
  if p['count']<300 or v['acceptedFrames']<300:raise ValueError('Fewer than300 controlled source physics frames')
  source_size=w.get('nativeDimensions')or size(Path(w['capture']));target_size=v['captureSize']
  source_surface_mean=surface['meanMs']*surface['count']/p['count'];target_surface_mean=v['cpuMilliseconds']['surfaceMs']['mean']
  rows.append(dict(state=state,garment=style,sourcePhysicsFrames=p['count'],targetPhysicsFrames=v['acceptedFrames'],
   nativeDimensions=dict(wolverine=source_size,witcher=target_size,matched=source_size==target_size),
   physicsMeanCPUms=dict(wolverine=p['meanMs'],witcher=v['cpuMilliseconds']['physicsMs']['mean']),
   surfaceMeanCPUmsPerCallback=dict(wolverine=source_surface_mean,witcher=target_surface_mean),
   surfaceMeanCPUmsPerService=dict(wolverine=surface['meanMs'],witcher=v['surfaceMillisecondsPerService']),
   sourceSurfaceServiceRatio=surface['count']/p['count'],targetSurfaceServiceRatio=v['surfaceServiceRatio'],
   nativeFrameMeanMs=dict(wolverine=w['nativePresentWeightedMeanMs'],witcherRendererCounter=v['rendererCounterMeanIntervalMs']),
   targetSDKDeltaSeconds=v.get('sdkDeltaSeconds'),targetWorkerDeltaSeconds=v.get('workerDeltaSeconds'),
   sourceFixedStepBudget=v.get('sourceFixedStepBudget'),sourceActualSolverSubstepsObserved=False,targetActualSolverSubstepsObserved=False,
   sourceSDKdtAvailable=False,targetBoundedInputStepEquivalent=v.get('boundedInputStepEquivalent')))
 return dict(schema='malemod.witcher-v2-native-performance-comparison/1',sourceReportSHA256=h(source),targetReportSHA256=h(target),cases=rows,
  parityPassed=None,notes=['CPU scopes are independently comparable; inclusive scopes must not be added together',
   'Physics per callback varies with dt and therefore number of original fixed steps; actual substeps are not exported',
   'Native FPS is reported separately from kernel CPU and depends on engine, scene and observed resolution',
   'Source frame means come from native Present intervals; target mean uses actual renderer Present counter over wall interval',
   'No source/target per-Present timestamp median/P95 equivalence or unobserved performance parity is claimed'])
if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--wolverine',type=Path,required=True);ap.add_argument('--witcher',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 if a.output.exists():raise ValueError('Choose fresh comparison output')
 result=compare(a.wolverine,a.witcher);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
