"""Bind native captures to one completed private modular scenario.

Run before starting the next private session. This records observations, never
grants visual approval or installation permission.
"""
import argparse
import json
import statistics
from pathlib import Path
from mod import ROOT, digest, read_json, write_json
from native_preview import load_preview
from install_modular_native import coupled_identity


def record(receipt, first, count, output):
    receipt, output = Path(receipt).resolve(), Path(output).resolve()
    if not receipt.is_relative_to((ROOT/'build/probe').resolve()) or output.exists():
        raise ValueError('Use an owned session and fresh evidence output')
    r=read_json(receipt);pid=r['observations']['processID']
    if r['observations']['physicalInputUsed'] or r['physicalDesktopSwitch']:
        raise ValueError('Private noninteractive session required')
    _,preview=load_preview(r['nativePreview'],r['nativePreviewSHA256'],False)
    trace=Path(r['modulePath']).parent/f'verification-{pid}.jsonl'
    rows=[json.loads(line) for line in trace.read_text().splitlines()]
    cases=[x for x in rows if first<=x['stage']<first+count]
    if [x['stage'] for x in cases]!=list(range(first,first+count)):
        raise ValueError('Incomplete or repeated native stages')
    if any(not x.get('modular') or x['bodyResourceMask']!=3 or
           x['renderFlags']&128 for x in cases):
        raise ValueError('Native modular draw failure')
    expected=[x for x in rows if x['stage']==200]+cases
    shots=sorted((p for p in (Path.home()/'Documents/The Witcher 3/screenshots').glob('*.png')
                  if p.stat().st_mtime>=r['launchedUnixSeconds']),key=lambda p:p.stat().st_mtime)
    if len(shots)!=len(expected):raise ValueError('Native capture count differs')
    mask=0
    for x in cases:mask|=x['modularCompletedLODMask']
    frames=[]
    for row,shot in zip(expected,shots):
        with shot.open('rb') as stream:
            if stream.read(8)!=b'\x89PNG\r\n\x1a\n':raise ValueError('Invalid native PNG')
        frames.append(dict(stage=row['stage'],path=str(shot),sha256=digest(shot),
                           controls=row.get('controls'),lodMask=row['modularCompletedLODMask']))
    value=dict(schema='malemod.modular-native-session/1',receipt=str(receipt),
        receiptSHA256=digest(receipt),trace=str(trace),traceSHA256=digest(trace),
        coupledArtifacts=coupled_identity(preview),stages=list(range(first,first+count)),
        completedLODMask=mask,frames=frames,
        medianModularMilliseconds=statistics.median(x['modularMs'] for x in cases),
        nativeDrawPass=True,visualAcceptance=False,fullAttachmentGatePassed=False)
    write_json(output,value)
    print(f'{output}: {count} stages, completed LOD mask {mask}')
    return value


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('receipt',type=Path);p.add_argument('--first',type=int,required=True)
    p.add_argument('--count',type=int,required=True);p.add_argument('--output',type=Path,required=True)
    record(**vars(p.parse_args()))
