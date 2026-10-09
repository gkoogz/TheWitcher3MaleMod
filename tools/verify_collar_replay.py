"""Compare complete actual LOD and native vertex buffers; no visual acceptance."""
import argparse,json
from pathlib import Path
from mod import ROOT,digest,write_json

def verify(reference,candidate):
    reference=Path(reference);candidate=Path(candidate)
    a=json.loads((reference/'cases.json').read_text());b=json.loads((candidate/'cases.json').read_text())
    fields=lambda rows:[(x['label'],x['controls'],x.get('characterContactsCalibrated',False)) for x in rows]
    if not a or fields(a)!=fields(b) or len({x['label'] for x in a})!=len(a):
        raise ValueError('Replay controls, calibrated-contact status or ordering differs')
    artifacts=[]
    for row in a:
        for suffix in ('-lod0.bin','-lod1.bin','-render.bin'):
            name=row['label']+suffix;p=reference/name;q=candidate/name
            if not p.is_file() or not q.is_file() or not p.stat().st_size:
                raise ValueError('Missing complete replay artifact: '+name)
            original=digest(p);result=digest(q)
            if original!=result:raise ValueError('Native buffer differs: '+name)
            artifacts.append(dict(name=name,bytes=p.stat().st_size,sha256=result))
    return dict(schema='malemod.complete-target-buffer-replay/1',cases=len(a),artifacts=artifacts,
        byteIdentical=True,controls=fields(a),referenceCasesSHA256=digest(reference/'cases.json'),
        candidateCasesSHA256=digest(candidate/'cases.json'),nativeGameplay=False,
        visualAcceptance=False,fullAttachmentGate=False)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to((ROOT/'build').resolve()) or output.exists():
        raise ValueError('Use a fresh owned proof path')
    proof=verify(args.reference,args.candidate);write_json(output,proof)
    print('PASS',proof['cases'],'cases:',len(proof['artifacts']),'byte-identical complete native buffers')
