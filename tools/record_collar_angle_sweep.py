"""Record full-slider native coverage without mistaking it for visual acceptance."""
import argparse
import json
from pathlib import Path
import shutil
from mod import ROOT, digest, read_json, write_json

ANGLES = [1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100]
VIEWS = ['front', 'side', 'oblique', 'low-oblique']


def validate(rows):
    selected = [r for r in rows if 300 <= r['stage'] < 492]
    if [r['stage'] for r in selected] != list(range(300, 492)):
        raise ValueError('Expected all 192 ordered angle/view checkpoints')
    previous = -1
    cases = []
    for i, row in enumerate(selected):
        case = i // 4
        expected = [case // 16, 100, 100, 100, 35, 100, 95,
                    ANGLES[case % 16], 100, 50, 50, 50, 50, 50, 50, 50, 50, 51]
        if row['controls'] != expected:
            raise ValueError('Unexpected controls at stage '+str(row['stage']))
        if row['completedSequence'] != row['sequence'] or row['sequence'] <= previous:
            raise ValueError('Stale or incomplete surface at stage '+str(row['stage']))
        if row['bodyResourceMask'] != 3 or row['vertices'] <= 0:
            raise ValueError('Both body resources were not observed')
        previous = row['sequence']
        cases.append(dict(stage=row['stage'], state=case // 16,
                          angle=ANGLES[case % 16], view=VIEWS[i % 4],
                          uploadFNV64=row['uploadFNV64']))
    return cases


def record(receipt):
    receipt = Path(receipt).resolve()
    if not receipt.is_relative_to((ROOT/'build/probe').resolve()):
        raise ValueError('Expected repository-owned session')
    session = read_json(receipt)
    child = session['observations']
    if not child['noninteractiveWindowStation'] or child['physicalInputUsed']:
        raise ValueError('Expected private native session')
    trace = Path(session['modulePath']).parent/f"verification-{child['processID']}.jsonl"
    if trace.stat().st_mtime < session['launchedUnixSeconds']:
        raise ValueError('Stale verification trace')
    raw = trace.read_bytes()
    rows = [json.loads(line) for line in raw.splitlines()]
    cases = validate(rows)
    frames = sorted((Path.home()/'Documents/The Witcher 3/screenshots').glob('*.png'),
                    key=lambda p: p.stat().st_mtime_ns)
    frames = [p for p in frames if p.stat().st_mtime >= session['launchedUnixSeconds']]
    # The maintained bootstrap takes one frame immediately after checkpoint
    # 200. Its early return then hands every later frame to the sweep driver.
    if len(frames) != len(cases)+1:
        raise ValueError('Screenshot count differs; preserve files for manual association')
    folder = receipt.parent/'frames'; folder.mkdir(exist_ok=True)
    for case, frame in zip(cases, frames[1:]):
        target = folder/f"{case['stage']}-s{case['state']}-angle{case['angle']}-{case['view']}.png"
        shutil.copy2(frame, target)
        case.update(frame=str(target), frameSHA256=digest(target),
                    association='Ordered screenshot calls after checkpoint 200 bootstrap')
    (receipt.parent/'checkpoints.jsonl').write_bytes(raw)
    result = dict(nativeCoverageComplete=True, attachmentGatePassed=False,
                  visualAcceptance=False, cases=cases,
                  moduleSHA256=session['moduleSHA256'],
                  traceSHA256=digest(receipt.parent/'checkpoints.jsonl'))
    write_json(receipt.parent/'angle-sweep.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('receipt', type=Path)
    result = record(parser.parse_args().receipt)
    print('Recorded', len(result['cases']), 'native views; visual acceptance remains separate')
