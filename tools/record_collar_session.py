"""Record an owned native collar run; numerical checks do not grant visual approval."""
import argparse,json,shutil,statistics,math
from pathlib import Path
from mod import ROOT,digest,read_json,write_json

def record(path, repair_review=False, physics_review=False,physics_motion=False):
    path=Path(path).resolve()
    if not path.is_relative_to((ROOT/'build/probe').resolve()):raise ValueError('Owned session required')
    receipt=read_json(path);child=receipt['observations']
    if not child['noninteractiveWindowStation'] or child['physicalInputUsed'] or receipt['physicalDesktopSwitch']:raise ValueError('Private station required')
    trace=Path(receipt['modulePath']).parent/f"verification-{child['processID']}.jsonl"
    raw=trace.read_bytes();rows=[json.loads(s) for s in raw.splitlines(keepends=True) if s.endswith(b'\n')]
    first,count=(600,81 if physics_review else 57) if repair_review else (300,39)
    if physics_motion:first,count=600,36
    driver_root=ROOT/'build/collar-sessions'/('physics-motion' if physics_motion else 'repair-review')
    if repair_review and not Path(receipt['driver']).is_relative_to(driver_root):
        raise ValueError('Repair review requires its bound measured-camera driver')
    cases=[r for r in rows if first<=r['stage']<first+count]
    if [r['stage'] for r in cases]!=list(range(first,first+count)):raise ValueError('Incomplete ordered collar run')
    if any(r['vertices']!=49884 or r['bodyResourceMask']!=3 or r['runtimeFlags']&(32|256) or r['garmentStyle']!=0 for r in cases):raise ValueError('Incomplete body output or service error')
    images=sorted((Path.home()/'Documents/The Witcher 3/screenshots').glob('*.png'),key=lambda p:p.stat().st_mtime)
    images=[p for p in images if p.stat().st_mtime>=receipt['launchedUnixSeconds']]
    expected=[r for r in rows if r['stage']==200]+cases
    if len(images)!=len(expected):raise ValueError(f'Capture count differs: {len(images)} vs {len(expected)}')
    for image in images:
        with image.open('rb') as stream:
            if stream.read(8)!=b'\x89PNG\r\n\x1a\n':raise ValueError('Native screenshot is empty or invalid: '+str(image))
    out=path.parent/'frames';out.mkdir(exist_ok=True);frames=[]
    for row,source in zip(expected,images):
        target=out/f"stage-{row['stage']}.png"
        if target.exists() and digest(target)!=digest(source):raise ValueError('Preserve existing capture')
        shutil.copy2(source,target);frames.append(dict(stage=row['stage'],path=target.relative_to(ROOT).as_posix(),sha256=digest(target),controls=row.get('controls'),corrective=row.get('attachmentCorrective')))
    copied=path.parent/'checkpoints.jsonl';copied.write_bytes(raw)
    motion=cases[-3:];origins=[r['actorOrigin'] for r in motion]
    movement=sum(math.dist(a,b) for a,b in zip(origins,origins[1:]))
    proof=dict(schema='malemod.collar-native-review/1',baseCommit=read_json(ROOT/'local/native-installation.json')['baseCommit'],
        receiptSHA256=digest(path),moduleSHA256=receipt['moduleSHA256'],driverSHA256=receipt['temporaryContinueSHA256'],
        checkpointSHA256=digest(copied),frames=frames,nativeCases=count,bodyResources=2,lods=2,vertices=49884,
        movementMetres=movement,sourceMedianMs=statistics.median(r['sourceMs'] for r in cases),targetMedianMs=statistics.median(r['targetMs'] for r in cases),
        presentationIntervalMedianMs=statistics.median(r['presentationIntervalMs'] for r in cases),physicalInputUsed=False,
        privateSessionClosed=receipt.get('closed',False),audioRestored=receipt.get('audioRestored',False),
        numericalRuntimePass=True,visualAcceptance=False,performanceParityClaimed=False)
    write_json(path.parent/'collar-review.json',proof);print(json.dumps({k:v for k,v in proof.items() if k!='frames'},indent=2))
    return proof

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('receipt',type=Path);p.add_argument('--repair-review',action='store_true');p.add_argument('--physics-review',action='store_true');p.add_argument('--physics-motion',action='store_true');a=p.parse_args();record(a.receipt,a.repair_review or a.physics_review or a.physics_motion,a.physics_review,a.physics_motion)
