"""Version-aware numerical worker adoption; no cleanliness or runtime waivers."""
import struct
from pathlib import Path
from mod import read_json,digest

def validate_process_library(base,library,current,require_clean=False,pin=None):
    base,library=Path(base).resolve(),Path(library).resolve()
    owned_build=(base/'build').resolve()
    if not library.is_relative_to(owned_build) or digest(library)!=current['librarySHA256'] or current['serialGeometry']:
        raise ValueError('Current parallel Base library differs')
    wire=current['wireVersion']
    if wire==5:
        if not current.get('sessionWireFrameGarmentTestsPassed'):raise ValueError('Historical wire5 verification missing')
        return
    if wire!=6:raise ValueError('Unsupported source wire version')
    if require_clean:
        if not pin or len(pin)!=40:raise ValueError('Clean source adoption requires exact Base pin')
        path=(base/('build/physical-reaction-source-proof-'+pin[:7]+'/proof.json')).resolve()
    else:
        path=(base/current['sourceConsumptionProofPath']).resolve()
        if digest(path)!=current['sourceConsumptionProofSHA256']:raise ValueError('Wire6 source-consumption receipt changed')
    if not path.is_relative_to(owned_build):raise ValueError('Source receipt leaves owned builds')
    proof=read_json(path)
    if require_clean and (proof.get('sourceDirty')!='' or proof.get('sourceCommit')!=pin):raise ValueError('Source consumption proof is dirty or pinned to another revision')
    if proof.get('schema')!=2 or proof.get('wire')!=6 or proof.get('sourceProcessIsolated') is not True or proof['library']['sha256']!=digest(library):
        raise ValueError('Wire6 source-consumption recipe differs')
    for name in ('library','executable'):
        row=proof[name];binary=(base/row['path']).resolve()
        if not binary.is_relative_to(owned_build) or digest(binary)!=row['sha256']:raise ValueError('Source proof binary changed')
    required={'src/surface/runtime.cpp','include/malemod/surface/runtime.hpp','include/malemod/surface/wire.hpp','include/malemod/surface/garment_impulse.hpp','include/malemod/garments/reaction_support.hpp','tools/verify_garment_source_reactions.py'}
    if not required<=set(proof.get('sourceHashes',{})):raise ValueError('Source proof omits required implementation hashes')
    for relative,expected in proof['sourceHashes'].items():
        source=(base/relative).resolve()
        if not source.is_relative_to(base) or digest(source)!=expected:raise ValueError('Source consumption source changed: '+relative)
    cases=proof.get('cases',[])
    if len(cases)!=3 or {c.get('state') for c in cases}!={0,1,2}:raise ValueError('Source proof omits mechanical states')
    for case in cases:
        keys=('disabledExactParity','cdfRetryExactParity','physicalImpulseChangesSource','pendingNoSubstepExactParity','pendingCoalescingExactParity')
        if not all(case.get(k) is True for k in keys):raise ValueError('Source consumption behavior failed')
        records=case.get('records',{});data={}
        if not {'0','2','3','4','5','6'}<=set(records):raise ValueError('Source consumption modes missing')
        for mode,row in records.items():
            binary=(path.parent/row['file']).resolve()
            if not binary.is_relative_to(path.parent):raise ValueError('Source output escapes receipt directory')
            raw=binary.read_bytes()
            if len(raw)<8 or struct.unpack_from('<I',raw)[0]!=6 or len(raw)!=row['bytes'] or digest(binary)!=row['sha256']:raise ValueError('Source output changed or is not wire6')
            data[mode]=raw
        if data['0']!=data['2'] or data['0']==data['3'] or not data['3']==data['4']==data['5']==data['6']:raise ValueError('Source impulse disabled/retry/queue conservation failed')
    return dict(path=(Path('build')/path.relative_to(owned_build)).as_posix(),sha256=digest(path))
