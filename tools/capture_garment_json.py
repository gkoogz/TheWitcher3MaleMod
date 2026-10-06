"""Transfer explicit measured JSON values through the adapter's native capture writer."""
import argparse,json,hashlib,math,subprocess
from pathlib import Path

def capture(source,dest,bridge):
 data=json.loads(Path(source).read_text());capacity=data['donorCapacity']
 if capacity!=16:raise ValueError('Measured JSON must retain the current16-donor contract')
 text=[]
 def put(values):
  for value in values:
   if not isinstance(value,(float,int)) or not math.isfinite(value):raise ValueError('Nonfinite measured value')
  text.append(' '.join(map(repr,values)))
 def point(p):
  if len(p)!=3:raise ValueError('Measured point must have three components')
  put(p)
 def samples(rows):
  put([len(rows)])
  for sample in rows:
   point(sample['position']);point(sample['normal'])
   if len(sample['lineage'])!=16:raise ValueError('Source lineage capacity changed')
   for d in sample['lineage']:put([d['surface'],d['vertex'],d['weight']])
 def triangles(rows):
  put([len(rows)])
  for face in rows:point(face)
 text.append('MMGFTXT1');frame=data['frame']
 for name in ('origin','lateral','forward','up'):point(frame[name])
 put([data['characterEpoch'],data['topologyRevision'],data['restRevision']]);point(data['gravity']);put([data['deltaTime'],data['anatomyMass']])
 for rows in (data['waist'],data['opening'],data['anatomy'],*data['rearStraps']):samples(rows)
 if len(data['rearStraps'])!=2:raise ValueError('Two measured rear routes required')
 triangles(data['anatomyTriangles']);put([len(data['bodyContacts'])])
 for c in data['bodyContacts']:point(c['a']);point(c['b']);put([c['radius']])
 samples(data['bodySurface']);triangles(data['bodyTriangles'])
 if len(data['anatomyRegions'])!=4:raise ValueError('Four complete anatomy semantic regions required')
 for region in data['anatomyRegions']:put([len(region)]);put(region)
 dest=Path(dest);dest.parent.mkdir(parents=True,exist_ok=True);intermediate=dest.with_suffix('.measured.txt');intermediate.write_text('\n'.join(text)+'\n')
 args=[str(Path(bridge).resolve()),str(intermediate.resolve()),str(dest.resolve())];process=subprocess.run(args,text=True,capture_output=True)
 receipt={'sourceJSON':str(Path(source).resolve()),'sourceJSONSHA256':hashlib.sha256(Path(source).read_bytes()).hexdigest(),'bridgeArguments':args,'exitCode':process.returncode,'stdout':process.stdout,'stderr':process.stderr,'anatomyMass':data['anatomyMass'],'donorCapacity':16,'capturesPersistentState':False,'format':'MMGFC006'}
 if process.returncode==0:
  receipt['nativeInputSHA256']=hashlib.sha256(dest.read_bytes()).hexdigest();receipt['nativeWriterReaderByteRoundtrip']=dest.read_bytes()==Path(str(dest)+'.roundtrip').read_bytes()
 dest.with_suffix('.json-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 if process.returncode:raise RuntimeError(process.stderr)
 return receipt
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('dest',type=Path);p.add_argument('--bridge',required=True,type=Path);a=p.parse_args();print(json.dumps(capture(a.source,a.dest,a.bridge),indent=2))
