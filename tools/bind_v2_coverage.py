"""Project the actual canonical Meridian uncovered-index list into both LODs."""
import re,struct,sys,argparse
from pathlib import Path
import numpy as np
from mod import ROOT,read_json,write_json,digest
from v2_native_binding import read_binding,cooked_resource
sys.path.insert(0,str(ROOT.parent/'MaleMod'))
from malemod_base.garment_coverage import project_covered_faces


def bind(output=None):
    r=ROOT/'v2/build';out=Path(output)if output is not None else r/'runtime-binding';source=ROOT.parent/'XMenOriginsWolverineMaleMod/src/runtime/meridian_recipe.h'
    text=source.read_text();block=text.split('uncoveredIndices[]={',1)[1].split('};',1)[0]
    uncovered=np.array([int(v)for v in re.findall(r'\d+',block)],dtype=np.int64).reshape(-1,3)
    ref=r/'wolverine-reference/state-2';raw=np.fromfile(ref/'anatomy.packed','u1').reshape(-1,32)
    positions=raw[:,:12].copy().view('<f4').reshape(-1,3);source_faces=np.fromfile(ref/'anatomy.indices','<u2').reshape(-1,3)
    binding=read_binding(out/'geralt-source-binding.bin');description=binding['resources'][0];rows=description['rows']
    path,mesh,buffer,sections=cooked_resource(0,out);offset=struct.unpack('<I',mesh.get(mesh.cooked,'indexBufferOffset','Uint32'))[0]
    original=np.frombuffer(buffer,'<u2',count=description['indexBytes']//2,offset=offset);masked=original.copy();section_reports=[]
    for c in sections:
        start=c['indexFirst'];n=c['indexCount'];faces=original[start:start+n].reshape(-1,3)
        selected=project_covered_faces(positions,source_faces,uncovered,rows['donors'],rows['weights'],faces.astype(np.int64)+c['firstVertex'])
        result=masked[start:start+n].reshape(-1,3);result[selected]=result[selected,:1]
        section_reports.append(dict(lod=c['lod'],material=c['material'],triangles=len(faces),coveredTriangles=int(selected.sum()),retainedTriangles=int((~selected).sum())))
    reports=[dict(lod=lod,**{key:sum(row[key]for row in section_reports if row['lod']==lod)for key in ('triangles','coveredTriangles','retainedTriangles')})for lod in (0,1)]
    if any(x['coveredTriangles']<30000 for x in reports)or any(x['material']and x['coveredTriangles']<30000 for x in section_reports):raise ValueError('Incomplete canonical interior coverage')
    file=out/'geralt-meridian-coverage.bin';file.write_bytes(b'MMV2C01\0'+struct.pack('<I',len(masked))+masked.tobytes())
    report=dict(schema='malemod.witcher-v2-canonical-coverage/1',canonicalRecipeSHA256=digest(source),sourceBindingSHA256=digest(out/'geralt-source-binding.bin'),nativeIndexBufferSHA256=__import__('hashlib').sha256(original.tobytes()).hexdigest(),coverageSHA256=digest(file),lods=reports,sections=section_reports,completeAnatomyRetained=True,sourceUncoveredTriangles=len(uncovered))
    write_json(out/'coverage.json',report);print(report);return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path);args=parser.parse_args();bind(args.output)
