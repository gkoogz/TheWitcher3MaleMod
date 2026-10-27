"""Audit an official local-waist cook; no mutation of any native resource."""
import argparse,collections,json,struct
from pathlib import Path
import numpy as np
from mod import ROOT,digest,read_json,write_json
from packed_mesh_format import CookedMesh
from wcc_fbx import Document,triangles
from build_v2_detail_package import audit_upper
from prepare_v2_waist_join import face_key

LOWER='characters/models/geralt/body/model/l_01_mg__body.w2mesh'
UPPER='characters/models/geralt/body/model/t_01_mg__body_hires.w2mesh'
def sections(path):
    path=Path(path);mesh=CookedMesh(path.read_bytes(),allow_multi_section=True,allow_stock_torso_mapping=path.name.startswith('t_01_'));raw=Path(str(path)+'.1.buffer').read_bytes();offset=struct.unpack('<I',mesh.get(mesh.cooked,'indexBufferOffset','Uint32'))[0];result=[]
    for s in mesh.skin_sections(raw):
        n=s['vertexCount'];streams=[np.frombuffer(raw,'u1',n*stride,s[key]).reshape(n,stride)for key,stride in [('positionOffset',16),('uvOffset',4),('lightingOffset',8),('extraOffset',8)]]
        rows=np.hstack(streams);f=np.frombuffer(raw,'<u2',s['indexCount'],offset+s['indexFirst']*2).reshape(-1,3).astype(int)
        p=streams[0][:,:6].copy().view('<u2').astype(float)/65535*np.array(mesh.scale[:3])+np.array(mesh.offset[:3])
        result.append(dict(info=s,rows=rows,faces=f,points=p))
    return mesh,result
def keys(section,lighting=True):
    rows=section['rows']if lighting else np.hstack([section['rows'][:,:24],section['rows'][:,28:]])
    return [face_key([bytes(rows[v])for v in t])for t in section['faces']]

def audit(waist_receipt,baseline,candidate,output,bindings=None):
    waist_receipt,baseline,candidate,output=map(Path,(waist_receipt,baseline,candidate,output));receipt=read_json(waist_receipt);job=waist_receipt.parent
    fbx=Path(receipt['outputFBX']);fbx=fbx if fbx.is_absolute()else ROOT/fbx
    if digest(fbx)!=receipt['outputFBXSHA256']or digest(job/'upper-row-lineage.npz')!=receipt['upperLineageSHA256']:raise ValueError('Frozen waist authoring changed')
    oldmesh,old=sections(baseline/LOWER);newmesh,new=sections(candidate/LOWER)
    if len(old)!=6 or len(new)!=6:raise ValueError('Both native skin states and LODs required')
    if oldmesh.scale!=newmesh.scale or oldmesh.offset!=newmesh.offset:raise ValueError('Local waist repair changed global native position quantization')
    report=[];protected_diff=[]
    proto=np.load(ROOT/'v2/build/acceptance/final-602-lod1/independent-visual-review/one-ring-split.npz');remove=set(proto['removedSectionFaces'].tolist())
    if digest(ROOT/'v2/build/acceptance/final-602-lod1/independent-visual-review/one-ring-split.npz')!=receipt['prototypeSHA256']:raise ValueError('Frozen local face-removal prototype changed')
    for a,z in zip(old,new):
        s=a['info'];t=z['info'];which=(s['lod'],s['material'])
        if which!=(t['lod'],t['material']):raise ValueError('Native semantic section changed')
        if which!=(1,0):
            exact=collections.Counter(keys(a))==collections.Counter(keys(z))
            if not exact:
                if not np.array_equal(a['faces'],z['faces'])or a['rows'].shape!=z['rows'].shape or not np.array_equal(np.hstack([a['rows'][:,:24],a['rows'][:,28:]]),np.hstack([z['rows'][:,:24],z['rows'][:,28:]])):raise ValueError('Protected source/LOD0 changed beyond measured cooker tangents: '+str(which))
                changed=np.flatnonzero(np.any(a['rows'][:,24:28]!=z['rows'][:,24:28],axis=1));protected_diff.append(dict(scope='shared source weld',lod=s['lod'],nativeMaterial=s['material'],changedNativeRows=(changed+s['firstVertex']).tolist(),changedTangentBytes=int(np.sum(a['rows'][:,24:28]!=z['rows'][:,24:28]))))
            report.append(dict(lod=s['lod'],material=s['material'],allOrientedTrianglesExact=True,allNonTangentBytesExact=True,rawNativeTangentBytesExact=exact,faces=len(a['faces'])));continue
        expected=collections.Counter(k for i,k in enumerate(keys(a))if i not in remove);actual=collections.Counter(keys(z));missing=expected-actual
        if missing:
            expected_no=collections.Counter(k for i,k in enumerate(keys(a,False))if i not in remove);actual_no=collections.Counter(keys(z,False));unmatched=expected_no-actual_no
            if unmatched:raise ValueError('Existing nonincident stock corners/skin/UV/color changed beyond lighting: '+str(sum(unmatched.values())))
            protected_diff.append(dict(scope='LOD1 stock nonincident faces',changedTangentTriangleCount=sum(missing.values())))
        # Remove by stable physical/skin/UV/color identity even if WCC regeneratesT.
        expected_no=collections.Counter(k for i,k in enumerate(keys(a,False))if i not in remove);keep=[];extra=[]
        for i,k in enumerate(keys(z,False)):
            if expected_no[k]:expected_no[k]-=1;keep.append(i)
            else:extra.append(i)
        if any(expected_no.values())or len(extra)!=63:raise ValueError('Exactly52 stock faces must be replaced by63')
        # Match every replacement corner against the exact authored63triangle witness.
        lineage=np.load(job/'upper-row-lineage.npz');auth=Document(fbx).meshes[1];points=auth.array('Vertices').reshape(-1,3)*.01;uv=next(n for n in auth.children if n.name=='LayerElementUV'and n.values==[0]).array('UV').reshape(-1,2).copy();uv[:,1]=1-uv[:,1]
        corners=z['faces'][extra];native_uv=z['rows'][:,16:20].copy().view('<f2').astype(float);domains={}
        from scipy.spatial import cKDTree
        needed=np.unique(lineage['replacementAuthorFaces']);tree=cKDTree(points[needed]);maximum=0
        for v in np.unique(corners):
            near=tree.query_ball_point(z['points'][v],3e-5);ids=[int(needed[i])for i in near if np.max(abs(uv[needed[i]]-native_uv[v]))<=.00051]
            if not ids:raise ValueError('Replacement corner has no declared waist witness within30um/UV')
            domains[int(v)]=ids;maximum=max(maximum,min(np.linalg.norm(points[i]-z['points'][v])for i in ids))
        wanted=collections.Counter(face_key(t[::-1])for t in lineage['replacementAuthorFaces']);import itertools
        for tri in corners:
            matches={face_key(p)for p in itertools.product(*(domains[int(v)]for v in tri))if wanted[face_key(p)]}
            if len(matches)!=1:raise ValueError('Replacement triangle not uniquely orientation-preserving authored topology')
            wanted[matches.pop()]-=1
        if any(wanted.values()):raise ValueError('Missing replacement triangle')
        report.append(dict(lod=1,material=0,oldFaces=len(a['faces']),newFaces=len(z['faces']),removedFaces=52,replacementFaces=63,protectedOutsideFaceCount=len(keep),maximumReplacementPositionErrorMeters=maximum,newTopRequiresExplicitUpperCSRAndPackedLightingCalibration=True))
    upper=audit_upper(baseline/UPPER,candidate/UPPER)
    for kind in('ribbed','elastic','red','blue'):
        rel='characters/malemod/garments/'+kind+'.w2mesh.1.buffer'
        if digest(baseline/rel)!=digest(candidate/rel):raise ValueError('Canonical garment carrier changed')
    calibration_proof=None
    if bindings is not None:
        from v2_native_binding import read_binding
        bindings=Path(bindings);calibration=read_json(bindings/'source-waist.json');manifest=read_json(bindings/'manifest.json');old=read_binding(ROOT/'v2/build/materials/physical-skin-cook-01/bindings/geralt-source-binding.bin');new=read_binding(bindings/'geralt-source-binding.bin')
        if(calibration['nativeCookBufferSHA256']!=digest(candidate/(LOWER+'.1.buffer'))or manifest.get('sourceWaist')!=calibration or manifest.get('bindingSHA256')!=digest(bindings/'geralt-source-binding.bin')):raise ValueError('Binding calibration is not closed against this cook')
        for entry in calibration['oldCookTangentExceptions']:
            expected=old['resources'][0]['rows'][entry['oldNativeRow']]['baseline'][24:28];actual=new['resources'][0]['rows'][entry['nativeRow']]['baseline'][24:28]
            if not np.array_equal(expected,actual):raise ValueError('Final binding did not retain the frozen old tangent')
        calibration_proof=dict(bindingSHA256=digest(bindings/'geralt-source-binding.bin'),receiptSHA256=digest(bindings/'source-waist.json'),oldActiveTangentRestorationRows=len(calibration['oldCookTangentExceptions']),finalRestoredWordsByteExact=True,newTopUpperRows=len(calibration['newTopRows']))
    result=dict(schema='malemod.local-stock-waist-native-roundtrip/1',passed=not protected_diff or calibration_proof is not None,geometryAndUVTopologyPassed=True,baselineCookedSHA256=digest(baseline/LOWER),baselineBufferSHA256=digest(baseline/(LOWER+'.1.buffer')),candidateCookedSHA256=digest(candidate/LOWER),candidateBufferSHA256=digest(candidate/(LOWER+'.1.buffer')),waistAuthoringReceiptSHA256=digest(waist_receipt),sections=report,rawCookTangentExceptions=protected_diff,qualifiedBindingCalibration=calibration_proof,upper=upper,carrierBuffersUnchanged=True,nativeObserved=False,globallyAdopted=False)
    write_json(output,result)
    if protected_diff and calibration_proof is None:raise ValueError('WCC changed protected stock lighting; explicit existing-row calibration required')
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--waist-receipt',type=Path,required=True);p.add_argument('--baseline-cooked',type=Path,required=True);p.add_argument('--candidate-cooked',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--bindings',type=Path);a=p.parse_args();print(json.dumps(audit(a.waist_receipt,a.baseline_cooked,a.candidate_cooked,a.output,a.bindings),indent=2))
