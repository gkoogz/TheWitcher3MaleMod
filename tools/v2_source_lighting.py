"""Optional experimental source-interior raw TBN restoration for B04.

Canonical positions/solver and native skinning/UV/cook remain unchanged. Restore
raw source N/T through the actual placement, preserving stock/shared seam bytes.
Only proven close-position frame-donor aliases may change their existing donor.
"""
import hashlib
import json
from pathlib import Path
import struct

import numpy as np
from scipy.sparse import csr_matrix
from scipy.spatial import cKDTree

from packed_mesh_format import CookedMesh
from v2_source_precision import parse_b04,match_source_rows


def digest(data):return hashlib.sha256(data).hexdigest()
def decode(word):return np.stack([((word>>(10*k))&1023).astype(float)/511.5-1 for k in range(3)],axis=1)
def direction_words(v,top):
    # Native IA representation only. Do not Gram-orthogonalize, smooth or
    # normalize the source reference vectors before encoding them.
    q=np.floor(np.clip(v*.5+.5,0,1)*1023+.5).astype(np.uint32)
    return q[:,0]|(q[:,1]<<10)|(q[:,2]<<20)|top


def allow_alias(rest,maximum,maximum_delta,has_cases,diagnostic_all=False):
    return bool(has_cases)and rest<=3e-5 and(max(rest,maximum,maximum_delta)<=3e-5 or diagnostic_all)


def restore_payload(original,fit_directory,cooked_path,reference_anatomy,case_directory=None,diagnostic_all_aliases=False):
    fit_directory,cooked_path,reference_anatomy=map(Path,(fit_directory,cooked_path,reference_anatomy))
    resources=parse_b04(original);resource=resources[0];data=bytearray(original)
    rotation=np.asarray(struct.unpack_from('<9f',original,12)).reshape(3,3);det=float(np.linalg.det(rotation))
    if abs(abs(det)-1)>1e-5 or abs(rotation@rotation.T-np.eye(3)).max()>1e-5:raise ValueError('Lighting placement is not an observed orthogonal frame')
    source_count=struct.unpack_from('<I',data,72)[0]
    ref=reference_anatomy.read_bytes()
    if len(ref)!=17528*32:raise ValueError('Unexpected canonical reference anatomy bounds')
    packed=np.frombuffer(ref,'u1').reshape(-1,32)
    source_positions=packed[:,:12].copy().view('<f4').reshape(-1,3)
    source_n=packed[:,16:19].astype(np.float32)/np.float32(127.5)-np.float32(1)
    source_t=packed[:,12:15].astype(np.float32)/np.float32(127.5)-np.float32(1)
    source_h=packed[:,19].astype(float)/127.5-1
    bound_p=np.frombuffer(original,'<f4',source_count*3,76).reshape(-1,3)[:17528]
    bound_n=np.frombuffer(original,'<f4',source_count*3,76+source_count*12).reshape(-1,3)[:17528]
    bound_t=np.frombuffer(original,'<f4',source_count*3,76+source_count*24).reshape(-1,3)[:17528]
    if not(np.array_equal(source_positions,bound_p)and np.array_equal(source_n,bound_n)and np.array_equal(source_t,bound_t)):
        raise ValueError('Source lighting reference differs from the binding source banks')
    if not set(np.unique(source_h))<={-1.,1.}:raise ValueError('Unobserved source handedness')
    cases=[];case_report=[]
    if case_directory is not None:
        for path in sorted(Path(case_directory).glob('v2-checkpoint-*.source')):
            raw=path.read_bytes()
            if len(raw)!=source_count*32:raise ValueError('Captured source case bounds differ')
            p=np.frombuffer(raw,'u1').reshape(-1,32)[:17528]
            if not np.array_equal(p[:,19],packed[:,19]):raise ValueError('Captured source handedness changes; static restoration is insufficient')
            positions=p[:,:12].copy().view('<f4').reshape(-1,3)
            if not np.isfinite(positions).all():raise ValueError('Captured source positions are nonfinite')
            cases.append(positions);case_report.append(dict(path=str(path.resolve()),sha256=digest(raw)))
        if not cases:raise ValueError('Alias proof directory has no actual source checkpoints')
    cooked_bytes=cooked_path.read_bytes();buffer=Path(str(cooked_path)+'.1.buffer').read_bytes();mesh=CookedMesh(cooked_bytes,allow_multi_section=True)
    sections=mesh.skin_sections(buffer)
    if len(sections)!=len(resource['sections']):raise ValueError('Lighting material section count differs')
    index_offset=struct.unpack('<I',mesh.get(mesh.cooked,'indexBufferOffset','Uint32'))[0]
    words=np.frombuffer(data,'<u4',resource['count']*13,resource['rowoffset']).reshape(-1,13)
    weights=np.frombuffer(data,'<f4',resource['count']*13,resource['rowoffset']).reshape(-1,13)[:,10:13]
    allowed=np.zeros(len(data),bool);reports=[];protected=sum(r['count']for r in resources);changes=0
    for section_index,(native,s)in enumerate(zip(sections,resource['sections'])):
        lod,material,first,count=map(int,s[:4])
        keys=('positionOffset','uvOffset','lightingOffset','extraOffset','indexFirst','indexCount')
        if tuple(map(int,s[4:]))!=tuple(native[k]for k in keys)or(lod,first,count)!=(native['lod'],native['firstVertex'],native['vertexCount']):raise ValueError('Lighting/native section streams differ')
        if not material:continue
        if material not in(1,2)or lod not in(0,1):raise ValueError('Unobserved source lighting section semantic')
        with np.load(fit_directory/('lod%d.npz'%lod))as archive:a={k:archive[k]for k in archive.files}
        body=int(a['bodyCount']);authored=a['points'][body:]*.01
        lineage=csr_matrix((a['module_data'],a['module_indices'],a['module_indptr']),shape=a['module_shape'])
        uv=lineage@a['moduleOriginalUV'];faces=a['faces'][np.all(a['faces']>=body,axis=1)]-body
        quant=np.frombuffer(buffer,'<u2',count*8,native['positionOffset']).reshape(-1,8)[:,:3]
        points=quant.astype(float)/65535*np.asarray(mesh.scale[:3])+np.asarray(mesh.offset[:3])
        native_uv=np.frombuffer(buffer,'<f2',count*2,native['uvOffset']).reshape(-1,2)
        native_faces=np.frombuffer(buffer,'<u2',native['indexCount'],index_offset+native['indexFirst']*2).reshape(-1,3)[:,[0,2,1]]
        ids,mapping=match_source_rows(points,native_uv,native_faces,authored,uv,faces)
        if mapping['extraIdenticalTriangles']!=int(material==2):raise ValueError('Unobserved source material transport duplicate')
        seam=cKDTree(a['points'][a['seamBody']]*.01).query(authored[ids])[0]<=1e-8;selected=np.flatnonzero(~seam);native_ids=first+selected
        n=(lineage@source_n)[ids];t=(lineage@source_t)[ids];h=(lineage@source_h)[ids]
        if np.any(abs(abs(h)-1)>1e-6):raise ValueError('Source handedness is mixed across a fitted lineage row')
        desired_n=n@rotation.T;desired_t=t@rotation.T;native_h=np.sign(h)*np.sign(det)
        before=words[native_ids,5:7].copy()
        words[native_ids,5]=direction_words(desired_n[selected],words[native_ids,5]&0xc0000000)
        words[native_ids,6]=direction_words(desired_t[selected],np.where(native_h[selected]>0,0xc0000000,0).astype(np.uint32))
        aliases=[];equivalent_aliases=0
        for local in selected:
            row=first+int(local);lr=lineage.getrow(ids[local]);expected_ids=np.zeros(3,np.uint32);expected_weights=np.zeros(3,np.float32)
            if lr.nnz>3:raise ValueError('Source lighting lineage exceeds triangle support')
            expected_ids[:lr.nnz]=lr.indices;expected_weights[:lr.nnz]=lr.data
            actual_ids=words[row,7:10].copy();actual_weights=weights[row].copy()
            if np.array_equal(actual_ids,expected_ids)and np.array_equal(actual_weights,expected_weights):continue
            expected_n=np.sum(source_n[expected_ids]*expected_weights[:,None],axis=0)
            expected_t=np.sum(source_t[expected_ids]*expected_weights[:,None],axis=0)
            actual_n=np.sum(source_n[actual_ids]*actual_weights[:,None],axis=0)
            actual_t=np.sum(source_t[actual_ids]*actual_weights[:,None],axis=0)
            if max(abs(expected_n-actual_n).max(),abs(expected_t-actual_t).max())<=1e-6:
                equivalent_aliases+=1;continue
            expected_p=np.sum(source_positions[expected_ids]*expected_weights[:,None],axis=0)
            actual_p=np.sum(source_positions[actual_ids]*actual_weights[:,None],axis=0)
            rest=float(np.linalg.norm(expected_p-actual_p)*.01);maximum=rest;maximum_delta=0
            for case in cases:
                ep=np.sum(case[expected_ids]*expected_weights[:,None],axis=0);ap=np.sum(case[actual_ids]*actual_weights[:,None],axis=0)
                maximum=max(maximum,float(np.linalg.norm(ep-ap)*.01));maximum_delta=max(maximum_delta,float(np.linalg.norm((ep-expected_p)-(ap-actual_p))*.01))
            captured_within=max(rest,maximum,maximum_delta)<=3e-5
            accepted=allow_alias(rest,maximum,maximum_delta,cases,diagnostic_all_aliases)
            if accepted:
                words[row,7:10]=expected_ids;weights[row]=expected_weights;start=resource['rowoffset']+row*52;allowed[start+28:start+52]=True
            aliases.append(dict(nativeRow=row,authoredModuleRow=int(ids[local]),oldDonors=actual_ids.tolist(),oldWeights=actual_weights.tolist(),newDonors=expected_ids.tolist(),newWeights=expected_weights.tolist(),
                                restPositionDifferenceMeters=rest,maximumCapturedPositionDifferenceMeters=maximum,maximumCapturedDeltaTransferDifferenceMeters=maximum_delta,corrected=accepted,
                                exceedsPrimaryCapturedTolerance=not captured_within,diagnosticAuthoritativeCorrection=bool(accepted and not captured_within and diagnostic_all_aliases),
                                heldReason=None if accepted else('No changing captured cases provided'if not cases else'Exceeded conservative primary captured-case30micrometre policy')))
        for row in native_ids:
            start=resource['rowoffset']+int(row)*52;allowed[start+20:start+28]=True
        protected-=len(selected);changes+=int(np.any(before!=words[native_ids,5:7],axis=1).sum())
        reports.append(dict(section=section_index,lod=lod,semanticMaterial=material,interiorRows=len(selected),protectedSharedSeamRows=int(seam.sum()),fitSHA256=digest((fit_directory/('lod%d.npz'%lod)).read_bytes()),
                            rawSourceVectors=True,GramBaselineApplied=False,normalTopBitsPreserved=True,
                            clippedNormalComponents=int((abs(desired_n[selected])>1).sum()),clippedTangentComponents=int((abs(desired_t[selected])>1).sum()),
                            aliases=aliases,unmodifiedFrameEquivalentAliases=equivalent_aliases,**mapping))
    if len(reports)!=4:raise ValueError('Source lighting requires both states in both LODs')
    if np.any((np.frombuffer(original,'u1')!=np.frombuffer(data,'u1'))&~allowed):raise ValueError('Source lighting changed protected/non-lighting bytes')
    result=bytes(data)
    report=dict(schema='malemod.witcher-v2-experimental-source-lighting/1',experimental=True,defaultEnabled=False,inputBindingSHA256=digest(original),bindingSHA256=digest(result),
                referenceAnatomySHA256=digest(ref),placementDeterminant=det,sourceHandednessCounts={str(float(k)):int(v)for k,v in zip(*np.unique(source_h,return_counts=True))},
                cookedMeshSHA256=digest(cooked_bytes),cookedBufferSHA256=digest(buffer),capturedCases=case_report,sections=reports,
                changedLightingRows=changes,protectedStockAndSharedSeamRows=protected,stockAndSharedSeamBytesIdentical=True,positionBaselineSkinningSourceHeaderAndCookUnchanged=True,
                aliasToleranceMeters=3e-5,aliasPolicy='diagnostic-authoritative-topology'if diagnostic_all_aliases else'primary-captured-tolerance',canonicalWorkerChanged=False,sourceFrameRotationChanged=False,nativeObserved=False,attachmentGatePassed=False,
                limitations=['Native10bit direction encoding clips components outside[-1,1] and quantizes the raw source frame',
                             'SourceFrameRotation remains existing Gram rotation extraction; changing raw source nonorthogonality is not another shader law',
                             'Held frame aliases still use existing geometry-donor rotation until separately proven safe',
                             'Native visual and all-triangle changing-case validation required before adoption'])
    return result,report


def restore_binding(binding_path,fit_directory,cooked_path,reference_anatomy,receipt_path,case_directory=None,diagnostic_all_aliases=False):
    binding_path,receipt_path=Path(binding_path),Path(receipt_path)
    result,report=restore_payload(binding_path.read_bytes(),fit_directory,cooked_path,reference_anatomy,case_directory,diagnostic_all_aliases)
    binding_path.write_bytes(result);receipt_path.write_text(json.dumps(report,indent=2)+'\n');return report
