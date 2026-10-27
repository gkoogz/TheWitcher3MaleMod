"""Strict native roundtrip for source COLOR.R only, against the frozen UV1-03 cook."""
import argparse,json
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from mod import digest,read_json,write_json
from wcc_fbx import Document
from audit_v2_target_uv1 import native_sections,triangle_keys
from prepare_v2_target_uv1 import runtime_half


def protected_keys(section,source):
    # Native key ends RGBA; preserve GBA and every other attribute including UV1.
    return [key[:-4]+(b'\0'+key[-3:]if source else key[-4:])+uv1
            for key,uv1 in zip(section['keys'],section['uv1'])]


def compare_sections(old,new):
    if set(old)!=set(new):raise ValueError('Native section identities changed')
    for key in old:
        before,after=old[key],new[key]
        if triangle_keys(protected_keys(before,key[1]!=0),before['faces'])!=triangle_keys(protected_keys(after,key[1]!=0),after['faces']):
            raise ValueError('Protected native geometry/UV0/UV1/skin/N-T/GBA or winding changed: '+str(key))


def audit(receipt,baseline,candidate,output):
    receipt,baseline,candidate,output=map(Path,(receipt,baseline,candidate,output))
    proof=read_json(receipt);fbx=Path(proof['outputFBX'])
    if digest(fbx)!=proof['outputFBXSHA256']:raise ValueError('Physical source FBX changed')
    if digest(proof['reference'])!=proof['referenceSHA256']:raise ValueError('UV1-03 reference changed')
    expected_baseline=Path(proof['reference']).parent/'final-native-uv1-audit.json'
    expected=read_json(expected_baseline)
    if digest(baseline)!=expected['candidateCookedSHA256']or digest(str(baseline)+'.1.buffer')!=expected['candidateBufferSHA256']:
        raise ValueError('Use exact frozen native UV1-03 baseline')
    oldmesh,old=native_sections(baseline);newmesh,new=native_sections(candidate)
    for name in('scale','offset','palette','inverse_binds','bone_mapping'):
        if getattr(oldmesh,name)!=getattr(newmesh,name):raise ValueError('Native bounds or skeleton changed: '+name)
    compare_sections(old,new);document=Document(fbx);reports=[]
    for key in sorted(new):
        lod,material=key;before,after=old[key],new[key]
        report=dict(lod=lod,material=material,baselineRows=len(before['keys']),candidateRows=len(after['keys']),triangles=len(after['faces']),protectedCornersExact=True)
        if material:
            field=proof['lods'][lod];path=Path(field['fieldPath'])
            if digest(path)!=field['fieldSHA256']or digest(field['sourceDonor'])!=field['sourceDonorSHA256']:raise ValueError('Original physical field provenance changed')
            q=np.load(path)['expectedR'];mesh=document.meshes[lod];count=field['bodyCount']
            points=mesh.array('Vertices').reshape(-1,3)[count:]*.01
            uv=next(n for n in mesh.children if n.name=='LayerElementUV'and n.values==[0]).array('UV').reshape(-1,2)[count:]
            uv_words=runtime_half(uv);used=np.unique(after['faces']);dist,choices=cKDTree(points).query(after['positions'][used],k=min(32,len(points)))
            for row,ds,ids in zip(used,dist,choices):
                ids=ids[(ds<=.00005)&np.all(uv_words[ids]==after['uv0Words'][row],axis=1)]
                values=np.unique(q[ids])
                if len(values)!=1:raise ValueError('Ambiguous physicalR mapping; inspect native split/corner provenance: '+str((key,int(row),values.tolist())))
                if after['keys'][row][-4]!=int(values[0]):raise ValueError('Actual native COLOR.R byte differs: '+str((key,int(row),after['keys'][row][-4],int(values[0]))))
            report.update(usedNativeRows=len(used),nativeRByteExact=True,sourceAlpha255=all(k[-1]==255 for k in after['keys']))
            if not report['sourceAlpha255']:raise ValueError('Source native alpha changed')
        else:report['stockRGBAUV1Exact']=True
        reports.append(report)
    result=dict(schema='malemod.physical-source-skin-native-audit/1',fieldReceipt=str(receipt),fieldReceiptSHA256=digest(receipt),
        baselineCookedSHA256=digest(baseline),baselineBufferSHA256=digest(str(baseline)+'.1.buffer'),candidateCookedSHA256=digest(candidate),candidateBufferSHA256=digest(str(candidate)+'.1.buffer'),
        nativeRRoundtripVerified=True,protectedTriangleCornerAttributesExact=True,sections=reports,nativeGameplayObserved=False,globallyAdopted=False)
    write_json(output,result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in('receipt','baseline','candidate','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();print(json.dumps(audit(a.receipt,a.baseline,a.candidate,a.output),indent=2))
