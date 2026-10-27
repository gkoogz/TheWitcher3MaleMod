"""Explicit native stock-waist lineage and measured cooker-tangent calibration.

No runtime law: the new top rows copy the frozen upper body's existing source
CSR, skin weight bytes and packed lighting. Existing rows only recover their
original packed tangent when the official retessellation changed that word.
"""
import collections,hashlib,struct
from pathlib import Path
import numpy as np
from mod import ROOT,digest,read_json,write_json
from wcc_fbx import Document
from v2_native_binding import read_binding
from v2_source_precision import parse_b04
from audit_v2_waist_join import sections

def load(receipt):
    receipt=Path(receipt);r=read_json(receipt);job=receipt.parent
    if r.get('schema')!='malemod.local-stock-LOD1-waist-authoring/1'or not r.get('requiresPostCookUpperDonorAndPackedLightingCalibration'):raise ValueError('Explicit waist authoring receipt required')
    fbx=Path(r['outputFBX']);fbx=fbx if fbx.is_absolute()else ROOT/fbx
    if digest(fbx)!=r['outputFBXSHA256']or digest(job/'upper-row-lineage.npz')!=r['upperLineageSHA256']:raise ValueError('Waist authoring/lineage changed')
    reference=ROOT/'v2/build/materials/physical-skin-cook-01/bindings'
    if digest(reference/'geralt-source-binding.bin')!=r['bindingSHA256']:raise ValueError('Frozen upper reference binding differs')
    scope=read_json(job/'authoring-scope.json')
    if not scope.get('passed')or scope.get('candidateSHA256')!=digest(fbx):raise ValueError('Closed original-attribute scope proof required')
    lineage=np.load(job/'upper-row-lineage.npz');points=Document(fbx).meshes[1].array('Vertices').reshape(-1,3)[lineage['newAuthorRows']]
    if len(points)!=34 or not np.array_equal(lineage['newAuthorRows'],np.arange(r['oldVertices'],r['oldVertices']+34)):raise ValueError('Declared appended stock rows differ')
    return dict(receipt=receipt,report=r,lineage=lineage,points=points,reference=reference)

def extend_points(waist,points):
    if len(points)!=waist['report']['oldVertices']:raise ValueError('Original fitted row indexing changed')
    return np.vstack([points,waist['points']])

def new_top_rows(section):
    # Native open edges are position-welded only to recover geometry topology;
    # UV/corner variants remain distinct below and are matched explicitly.
    p=section['rows'][:,:6].copy().view('<u2');unique,inverse=np.unique(p,axis=0,return_inverse=True);f=inverse[section['faces']]
    count=collections.Counter(tuple(sorted((int(a),int(b))))for t in f for a,b in zip(t,np.roll(t,-1)))
    graph=collections.defaultdict(set)
    for (a,b),n in count.items():
        if n==1:graph[a].add(b);graph[b].add(a)
    groups=[];remaining=set(graph)
    while remaining:
        todo=[remaining.pop()];seen=set(todo)
        while todo:
            for v in graph[todo.pop()]-seen:seen.add(v);remaining.discard(v);todo.append(v)
        groups.append(seen)
    candidates=[]
    for group in groups:
        rows=np.flatnonzero(np.isin(inverse,list(group)));mean=section['points'][rows].mean(0)
        if 1.04<mean[2]<1.10:candidates.append((group,rows))
    if len(candidates)!=1 or len(candidates[0][0])!=33 or len(candidates[0][1])!=34:raise ValueError('Actual native repaired waist must be33 geometric/34 attribute rows')
    return candidates[0][1]

def calibrate(binding,cooked,waist,receipt_output):
    binding=Path(binding);cooked=Path(cooked);original=binding.read_bytes();data=bytearray(original);parsed=parse_b04(data);old=read_binding(waist['reference']/'geralt-source-binding.bin');new=read_binding(binding);lineage=waist['lineage']
    reference_manifest=read_json(waist['reference']/'manifest.json');old_paths=[Path(r['cookedPath'])for r in reference_manifest['resources']]
    lower_name='l_01_mg__body.w2mesh';newmesh,parts=sections(cooked/lower_name);_,oldparts=sections(old_paths[0]);upper=old['resources'][1]
    if len(parts)!=6 or len(oldparts)!=6:raise ValueError('Exact six section layout required')
    raw_changes=[];top_changes=[];allowed=np.zeros(len(data),bool);top_part=next(p for p in parts if(p['info']['lod'],p['info']['material'])==(1,0));top=set(new_top_rows(top_part).tolist())
    old_upper_mesh,old_upper_parts=sections(old_paths[1]);old_up_section=old_upper_parts[1];old_up_first=upper['firstVertex']+old_up_section['info']['firstVertex']
    expected_uv=old_up_section['rows'][lineage['upperGlobalRows']-old_up_first,16:20]
    expected_positions=lineage['upperBaseline'][:,:12].copy().view('<f4').reshape(-1,3)*lineage['upperScale']+lineage['upperBias']
    rig=read_json(ROOT/'v2/build/geralt-base/player-rig.json')['_chunks']['CSkeleton #0']['_vars'];names=[x['_vars']['name']['_value']for x in rig['bones']['_elements']];new_palette={names[i]:slot for slot,(i,_)in enumerate(new['resources'][0]['palette'])}
    expected_used=[]
    for oldpart,part in zip(oldparts,parts):
        info=part['info'];oldinfo=oldpart['info']
        if(info['lod'],info['material'])!=(oldinfo['lod'],oldinfo['material']):raise ValueError('Native section semantics changed')
        table=collections.defaultdict(list)
        for i,row in enumerate(oldpart['rows']):table[bytes(np.r_[row[:24],row[28:]])].append(i)
        for i,row in enumerate(part['rows']):
            target=info['firstVertex']+i;offset=parsed[0]['rowoffset']+target*52
            if part is top_part and i in top:
                distance=np.linalg.norm(expected_positions-part['points'][i],axis=1);matches=[k for k in np.flatnonzero(distance<=3e-5)if np.array_equal(expected_uv[k],row[16:20])]
                if len(matches)!=1:raise ValueError('New native top row does not uniquely match actual upper position/halfUV')
                k=matches[0];expected_used.append(k);baseline=bytearray(lineage['upperBaseline'][k].tobytes());physical=expected_positions[k];normalised=(physical-np.asarray(new['resources'][0]['bias']))/np.asarray(new['resources'][0]['scale']);struct.pack_into('<3f',baseline,0,*normalised)
                ids=[]
                for local in baseline[12:16]:
                    name=names[upper['palette'][local][0]]
                    if name not in new_palette:raise ValueError('Upper row requires an absent named lower bone')
                    ids.append(new_palette[name])
                baseline[12:16]=bytes(ids);record=bytes(baseline)+struct.pack('<3I3f',*lineage['donors'][k],*lineage['weights'][k]);before=bytes(data[offset:offset+52]);data[offset:offset+52]=record;allowed[offset:offset+52]=True
                top_changes.append(dict(nativeRow=target,upperGlobalRow=int(lineage['upperGlobalRows'][k]),authorRow=int(lineage['newAuthorRows'][k]),nativeCookPositionErrorMeters=float(distance[k]),rawCookLightingHex=before[20:28].hex(),calibratedUpperLightingHex=record[20:28].hex(),skinWeightBytes=list(record[16:20]),donors=lineage['donors'][k].tolist(),weights=lineage['weights'][k].tolist()))
                continue
            candidates=table.get(bytes(np.r_[row[:24],row[28:]]),[])
            if not candidates:raise ValueError('Old active native row changed outside measured packedT')
            words={bytes(oldpart['rows'][h,24:28])for h in candidates}
            if len(words)!=1:raise ValueError('Ambiguous original tangent variants share all other native attributes')
            oldword=next(iter(words))
            if oldword!=bytes(row[24:28]):
                source=oldinfo['firstVertex']+candidates[0];word=old['resources'][0]['rows'][source]['baseline'][24:28].tobytes()
                data[offset+24:offset+28]=word;allowed[offset+24:offset+28]=True
                raw_changes.append(dict(lod=info['lod'],nativeMaterial=info['material'],nativeRow=target,oldNativeRow=source,oldCookTangentHex=oldword.hex(),newCookTangentHex=bytes(row[24:28]).hex(),restoredB04TangentHex=word.hex()))
    if sorted(expected_used)!=list(range(34)):raise ValueError('Not every upper attribute row has exactly one new lower top row')
    if np.any((np.frombuffer(original,'u1')!=np.frombuffer(data,'u1'))&~allowed):raise ValueError('Waist calibration touched an undeclared row/word')
    result=bytes(data);binding.write_bytes(result)
    report=dict(schema='malemod.stock-waist-B04-baseline-calibration/1',inputBindingSHA256=hashlib.sha256(original).hexdigest(),bindingSHA256=digest(binding),authoringReceiptSHA256=digest(waist['receipt']),originalUpperBindingSHA256=digest(waist['reference']/'geralt-source-binding.bin'),nativeCookBufferSHA256=digest(Path(str(cooked/lower_name)+'.1.buffer')),newTopRows=top_changes,oldCookTangentExceptions=raw_changes,onlyDeclaredNewRowsAndOldPackedTChanged=True,sourceNumericsModified=False,nativeObserved=False)
    write_json(receipt_output,report);return report
