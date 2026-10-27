"""Audit a future official UV1 cook against the frozen native baseline."""
import argparse,collections,json,struct
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from mod import digest,read_json,write_json
from packed_mesh_format import CookedMesh
from wcc_fbx import Document
from prepare_v2_target_uv1 import runtime_half


def triangle_keys(keys,faces):
    result=collections.Counter()
    for a,b,c in faces:
        x,y,z=keys[int(a)],keys[int(b)],keys[int(c)]
        result[min(x+y+z,y+z+x,z+x+y)]+=1
    return result


def native_sections(path):
    path=Path(path);mesh=CookedMesh(path.read_bytes(),allow_multi_section=True)
    data=Path(str(path)+'.1.buffer').read_bytes();index=struct.unpack('<I',mesh.get(mesh.cooked,'indexBufferOffset','Uint32'))[0]
    result={}
    for section in mesh.skin_sections(data):
        n=section['vertexCount'];p=section['positionOffset'];extra=section['extraOffset']
        raw=np.frombuffer(data,'u1',n*16,p).reshape(n,16)
        uv=np.frombuffer(data,'u1',n*4,section['uvOffset']).reshape(n,4)
        light=np.frombuffer(data,'u1',n*8,section['lightingOffset']).reshape(n,8)
        # Observed native input layout: COLOR0 RGBA8 at slot3+0 and
        # TEXCOORD1 R16G16_FLOAT at slot3+4, both in the eight-byte stream.
        color=np.ndarray((n,4),'u1',buffer=data,offset=extra,strides=(8,1)).copy()
        uv1=np.ndarray((n,4),'u1',buffer=data,offset=extra+4,strides=(8,1)).copy()
        quant=raw[:,:8].copy().view('<u2').reshape(n,4)[:,:3]
        positions=quant.astype(float)/65535*np.asarray(mesh.scale[:3])+np.asarray(mesh.offset[:3])
        key=(section['lod'],section['material'])
        if key in result:raise ValueError('Unobserved repeated native material section')
        faces=np.frombuffer(data,'<u2',section['indexCount'],index+section['indexFirst']*2).reshape(-1,3)
        result[key]=dict(keys=[r.tobytes()for r in np.c_[raw,uv,light,color]],uv1=[r.tobytes()for r in uv1],uv0Words=uv.copy().view('<u2').reshape(n,2),
            uv1Words=uv1.copy().view('<u2').reshape(n,2),uv0=uv.copy().view('<f2').reshape(n,2),positions=positions,faces=faces)
    return mesh,result


def audit(candidate_receipt,baseline,candidate,output):
    proof=read_json(candidate_receipt);fbx=Path(proof['outputFBX'])
    if digest(fbx)!=proof['outputFBXSHA256']:raise ValueError('UV1 candidate source changed')
    if proof.get('baselineInfo'):
        if (digest(proof['baselineInfo'])!=proof['baselineInfoSHA256']or digest(baseline)!=proof['baselineCookedSHA256']
                or digest(Path(str(baseline)+'.1.buffer'))!=proof['baselineBufferSHA256']):raise ValueError('Immutable baseline UV0 seed provenance changed')
    document=Document(fbx);oldmesh,old=native_sections(baseline);newmesh,new=native_sections(candidate)
    if (oldmesh.scale!=newmesh.scale or oldmesh.offset!=newmesh.offset or set(old)!=set(new)
            or oldmesh.palette!=newmesh.palette or oldmesh.inverse_binds!=newmesh.inverse_binds or oldmesh.bone_mapping!=newmesh.bone_mapping):
        raise ValueError('Native bounds, skeleton palette/binds or material/LOD identities changed')
    reports=[]
    for key in sorted(new):
        before,after=old[key],new[key];lod,material=key
        if triangle_keys(before['keys'],before['faces'])!=triangle_keys(after['keys'],after['faces']):
            raise ValueError('Native position/topology/UV0/skin/N-T/color corner identity changed: '+str(key))
        if material==0:
            if triangle_keys([a+b for a,b in zip(before['keys'],before['uv1'])],before['faces'])!=triangle_keys([a+b for a,b in zip(after['keys'],after['uv1'])],after['faces']):
                raise ValueError('Original stock native UV1 changed: '+str(key))
            reports.append(dict(lod=lod,nativeMaterial=material,stockNativeUV1Exact=True,baselineRows=len(before['keys']),candidateRows=len(after['keys']),triangles=len(after['faces']),indexOrderUnchanged=np.array_equal(before['faces'],after['faces'])));continue
        mesh=document.meshes[lod];n=proof['lods'][lod]['bodyCount'];points=mesh.array('Vertices').reshape(-1,3)[n:]*.01
        source_uv=next(x for x in mesh.children if x.name=='LayerElementUV'and x.values==[0]).array('UV').reshape(-1,2)[n:]
        expected=next(x for x in mesh.children if x.name=='LayerElementUV'and x.values==[1]).array('UV').reshape(-1,2)[n:]
        source_runtime=runtime_half(source_uv).view('<f2').astype(float);expected=runtime_half(expected)
        used=np.unique(after['faces']);distance,choices=cKDTree(points).query(after['positions'][used],k=min(32,len(points)))
        bad=[];max_error=0
        for native,dist,indices in zip(used,distance,choices):
            valid=(dist<=.00005)&(np.max(abs(source_runtime[indices]-after['uv0'][native].astype(float)),axis=1)<=.0011)
            matches=indices[valid];max_error=max(max_error,float(dist[0]))
            if not len(matches)or not np.any(np.all(expected[matches]==after['uv1Words'][native],axis=1)):
                bad.append(dict(row=int(native),actual=after['uv1Words'][native].view('<f2').astype(float).tolist(),nearestExpected=expected[indices[0]].view('<f2').astype(float).tolist()))
        if bad:raise ValueError('Native slot3 UV1 half2 does not roundtrip: '+str(key)+' '+json.dumps(bad[:5]))
        field_path=Path(candidate_receipt).parent/f'lod{lod}-target-uv1.npz';field=np.load(field_path)
        if proof['lods'][lod].get('targetFieldSHA256')and digest(field_path)!=proof['lods'][lod]['targetFieldSHA256']:raise ValueError('Exact dyadic target field changed')
        stock=new[(lod,0)];body_points=mesh.array('Vertices').reshape(-1,3)[:n]*.01
        module_tree=cKDTree(after['positions']);stock_tree=cKDTree(stock['positions']);samples=0
        for sample,(b,m) in enumerate(zip(field['seamBody'],field['seamModule'])):
            source_rows=module_tree.query_ball_point(points[int(m)],.00005);body_rows=stock_tree.query_ball_point(body_points[int(b)],.00005)
            expected_stock=field['weldNativeUV0Words'][sample]if'weldNativeUV0Words'in field else runtime_half(field['stockUV0FBX'][int(b)])
            source_bits=after['uv1Words'][source_rows]
            stock_bits=stock['uv0Words'][body_rows]
            if (not len(source_rows)or not len(body_rows)or not np.any(np.all(stock_bits==expected_stock,axis=1))
                    or not np.any(np.all(source_bits==expected_stock,axis=1))):
                raise ValueError('Native weld source UV1 differs from actual stock UV0: '+str((key,int(b),int(m))))
            samples+=1
        reports.append(dict(lod=lod,nativeMaterial=material,usedNativeRows=len(used),targetUV1HalfExact=True,
            baselineRows=len(before['keys']),candidateRows=len(after['keys']),triangles=len(after['faces']),indexOrderUnchanged=np.array_equal(before['faces'],after['faces']),
            nonUV1RowOrderUnchanged=before['keys']==after['keys'],actualNativeWeldHalfEqualitySamples=samples,targetFieldSHA256=digest(field_path),maximumPositionMatchErrorMeters=max_error))
    result=dict(schema='malemod.target-stock-detail-uv1-native-audit/1',candidateReceipt=str(candidate_receipt),candidateReceiptSHA256=digest(candidate_receipt),
        baselineCookedSHA256=digest(baseline),candidateCookedSHA256=digest(candidate),baselineBufferSHA256=digest(Path(str(baseline)+'.1.buffer')),
        candidateBufferSHA256=digest(Path(str(candidate)+'.1.buffer')),nativeRoundtripVerified=True,
        UV1Packing='Observed WCC float32 to IEEE half mantissa truncation; all used source rows verified bit-exact, not epsilon acceptance',
        unchangedNativeTriangleCornerAttributes='quantizedposition+fourboneweights/indices+UV0+packedN/T+RGBA; triangle order/winding preserved modulo cyclic rotation',
        nativeUV1='extra stream slot3 offset4, R16G16_FLOAT half2; COLOR0 RGBA8 offset0; stock exact and source target chart exact',sections=reports,globallyAdopted=False,nativeGameplayObserved=False)
    write_json(output,result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate-receipt','baseline','candidate','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(audit(a.candidate_receipt,a.baseline,a.candidate,a.output),indent=2))
