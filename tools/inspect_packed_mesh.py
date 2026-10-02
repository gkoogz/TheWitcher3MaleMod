"""Inspect an owned format-164 cooked mesh against its authored FBX.

This reads actual official dumps/buffers. It neither changes a native asset nor
assumes that the inspected resource is the one currently drawn by the game.
"""
import argparse,struct,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from wcc_fbx import Document,triangles
from packed_mesh_format import CookedMesh
from mod import ROOT,digest,write_json


def inspect(mesh,dump,fbx,output):
    mesh,dump,fbx,output=[Path(p).resolve() for p in (mesh,dump,fbx,output)]
    if not all(p.is_relative_to(ROOT/'build') for p in (mesh,dump,fbx,output)):
        raise ValueError('Use owned ignored inspection artifacts')
    if output.exists():raise ValueError('Do not overwrite inspection evidence')
    raw=mesh.read_bytes()
    if raw[:4]!=b'CR2W' or struct.unpack_from('<I',raw,4)[0]!=164:raise ValueError('Only observed cooked format 164 is supported')
    text=dump.read_text()
    # WCC emits duplicate attributes in its diagnostic table section. Parse only
    # its well-formed objects section, without rewriting any diagnostic content.
    objects=ET.fromstring(text[text.index('<objects '):text.index('</objects>')+10])
    cooked=objects.find('.//prop[@name="cookedData"]')
    def prop(name):
        p=cooked.find('.//prop[@name="'+name+'"]')
        if p is None:raise ValueError('Missing cooked property '+name)
        return p
    def vector(name):return np.array([float(prop(name).find('.//prop[@name="'+a+'"]').text) for a in 'XYZ'])
    native_mesh=CookedMesh(raw)
    scale,offset=np.asarray(native_mesh.scale[:3]),np.asarray(native_mesh.offset[:3])
    if not np.allclose(scale,vector('quantizationScale'),rtol=2e-6,atol=1e-7) or not np.allclose(offset,vector('quantizationOffset'),rtol=2e-6,atol=1e-7):
        raise ValueError('Binary quantization differs from official dump')
    chunks=bytes(int(e.text) for e in prop('renderChunks').find('array'))
    if len(chunks)!=75 or chunks[0]!=2:raise ValueError('Unobserved render chunk layout')
    buffer=Path(str(mesh)+'.1.buffer');data=buffer.read_bytes()
    vb=int(prop('vertexBufferSize').text);iboffset=int(prop('indexBufferOffset').text);ibsize=int(prop('indexBufferSize').text)
    if vb>iboffset or iboffset+ibsize!=len(data):raise ValueError('Unexpected native buffer bounds')
    doc=Document(fbx)
    if len(doc.meshes)!=2:raise ValueError('Expected two observed FBX LODs')
    output.mkdir(parents=True)
    reports=[]
    index_cursor=iboffset
    for lod,source in enumerate(doc.meshes):
        chunk=chunks[1+37*lod:1+37*(lod+1)]
        stream=[struct.unpack_from('<I',chunk,1+4*i)[0] for i in range(4)]
        # The observed packed fields end with a 16-bit vertex count, 32-bit
        # index count and two 0x27 flags before the LOD mask. Bounds below fail
        # closed when a future cooker changes this exact two-chunk layout.
        n=struct.unpack_from('<H',chunk,27)[0];indices=struct.unpack_from('<I',chunk,29)[0]
        position=np.ndarray((n,8),dtype='<u2',buffer=data,offset=stream[0],strides=(16,2))[:,:3].astype(float)/65535*scale+offset
        skin=np.ndarray((n,8),dtype='u1',buffer=data,offset=stream[0]+8,strides=(16,1)).copy()
        uv=np.ndarray((n,2),dtype='<f2',buffer=data,offset=stream[1],strides=(4,2)).astype(float)
        lighting=np.ndarray((n,8),dtype='u1',buffer=data,offset=stream[2],strides=(8,1)).copy()
        authored=source.array('Vertices').reshape(-1,3)/100
        distances,lineage=cKDTree(authored).query(position)
        if distances.max()>np.linalg.norm(scale/65535)*1.1:raise ValueError('Native position decode exceeds a quantization cell')
        source_uv=source.child('LayerElementUV').array('UV').reshape(-1,2) if sum(c.name=='LayerElementUV' for c in source.children)==1 else next(c for c in source.children if c.name=='LayerElementUV' and c.values[0]==0).array('UV').reshape(-1,2)
        normals=source.child('LayerElementNormal').array('Normals').reshape(-1,3)
        normals=normals/np.linalg.norm(normals,axis=1)[:,None]
        source_uv=source_uv.astype('<f4');source_uv[:,1]=np.float32(1)-source_uv[:,1]
        skin_names=[name for name,cluster in doc.skin(source)]
        if len(native_mesh.palette)!=sum(len(doc.skin(mesh)) for mesh in doc.meshes):raise ValueError('Native skin palettes differ from LOD dimensions')
        palette_begin=sum(len(doc.skin(mesh)) for mesh in doc.meshes[:lod])
        palette_end=palette_begin+len(skin_names)
        if native_mesh.palette[palette_begin:palette_end]!=skin_names:raise ValueError('Native LOD bone ordering differs')
        bind_errors=[]
        for (_,cluster),matrix in zip(doc.skin(source),native_mesh.inverse_binds[palette_begin:palette_end]):
            authored_bind=cluster.array('Transform').reshape(4,4).T.copy();authored_bind[:3,3]/=100
            bind_errors.append(float(np.abs(authored_bind-np.asarray(matrix).reshape(4,4).T).max()))
        if max(bind_errors)>1e-6:raise ValueError('Native inverse binds differ from authored calibration')
        source_weights=np.zeros((len(authored),len(skin_names)))
        for column,(name,cluster) in enumerate(doc.skin(source)):
            source_weights[cluster.array('Indexes').astype(int),column]=cluster.array('Weights')
        native_weights=np.zeros((n,len(skin_names)))
        for slot in range(4):
            for bone in np.unique(skin[:,slot]):
                if bone>=len(native_mesh.palette) or native_mesh.palette[bone] not in skin_names:raise ValueError('Native skin palette differs from authored bones')
                hit=skin[:,slot]==bone
                native_weights[hit,skin_names.index(native_mesh.palette[bone])]+=skin[hit,slot+4]/255
        normal_bits=lighting[:,:4].copy().view('<u4').reshape(-1)
        decoded_normal=np.stack([(normal_bits>>i)&1023 for i in (0,10,20)],axis=1)/1023*2-1
        candidates=cKDTree(authored).query_ball_point(position,np.linalg.norm(scale/65535)*1.1)
        # Resolve coincident UV aliases using observed attributes. A nearest
        # position alone can select the opposite side of a texture seam.
        ambiguous=0;maximum_alias_distance=0.
        for i,near in enumerate(candidates):
            near=np.asarray(near)
            errors=np.abs(source_uv[near]-uv[i])
            normal_error=np.abs(normals[near]-decoded_normal[i])
            weight_error=np.abs(source_weights[near]-native_weights[i])
            valid=near[(errors.max(1)<.0011)&(normal_error.max(1)<.003)&(weight_error.max(1)<=1/255+1e-7)]
            if not len(valid):raise ValueError('No authored position/UV/normal donor for native vertex '+str(i))
            score=np.linalg.norm(source_uv[valid]-uv[i],axis=1)+np.linalg.norm(normals[valid]-decoded_normal[i],axis=1)
            lineage[i]=valid[np.argmin(score)]
            if len(valid)>1:
                ambiguous+=1;maximum_alias_distance=max(maximum_alias_distance,float(np.linalg.norm(authored[valid]-authored[lineage[i]],axis=1).max()))
        variants={}
        for start in (0,4):
            decoded=lighting[:,start:start+3].astype(float)/255*2-1
            variants['unorm8-'+str(start)]=float(np.linalg.norm(decoded-normals[lineage],axis=1).max())
        variants['unorm10-0']=float(np.abs(decoded_normal-normals[lineage]).max())
        # The observed cooker truncates IEEE half values toward zero, including
        # the V flip. Compare exact values rather than a general UV tolerance.
        values=source_uv[lineage].astype('<f4');nearest=values.astype('<f2');half_bits=nearest.copy().view('<u2')
        half_bits[np.abs(nearest.astype('<f4'))>np.abs(values)]-=1
        if not np.array_equal(half_bits.view('<f2'),uv):raise ValueError('Native UV truncation/aliases differ')
        native_faces=np.frombuffer(data,dtype='<u2',count=indices,offset=index_cursor).reshape(-1,3).copy();index_cursor+=indices*2
        if native_faces.max()>=n:raise ValueError('Native triangle leaves LOD')
        # Collapse equivalent authored attribute aliases for a topology check.
        from collections import Counter
        attributes=np.hstack([authored,source_uv,normals,source_weights])
        _,groups=np.unique(np.round(attributes,7),axis=0,return_inverse=True)
        canonical=lambda f:Counter(tuple(sorted(map(int,t))) for t in f)
        topology_matches=canonical(groups[lineage[native_faces]])==canonical(groups[triangles(source)])
        np.savez_compressed(output/f'lod{lod}.npz',position=position,skin=skin,uv=uv,lighting=lighting,nearestAuthored=lineage,nativeFaces=native_faces)
        reports.append(dict(lod=lod,chunkHex=chunk.hex(),streamOffsets=stream,nativeVertices=n,authoredVertices=len(authored),
            nativeIndices=indices,maximumNearestPositionError=float(distances.max()),
            maximumNearestUVError=float(np.linalg.norm(uv-source_uv[lineage],axis=1).max()),normalDecodeDiagnostics=variants,
            ambiguousAttributeDonors=ambiguous,maximumAmbiguousPositionSpread=maximum_alias_distance,
            minimumSkinWeightSum=int(skin[:,4:].sum(1).min()),maximumSkinWeightSum=int(skin[:,4:].sum(1).max()),
            maximumBoneIndex=int(skin[:,:4].max()),namedSkinWeightsVerified=True,
            maximumNamedSkinWeightError=float(np.abs(native_weights-source_weights[lineage]).max()),exactUVTruncationVerified=True,
            nativeTopologyMatchesAuthored=topology_matches,inverseBindVerified=True,maximumInverseBindComponentError=max(bind_errors),
            mappingVerified=topology_matches,nativeLightingVerified=False))
    report=dict(meshSHA256=digest(mesh),bufferSHA256=digest(buffer),dumpSHA256=digest(dump),fbxSHA256=digest(fbx),
        recipeSHA256=digest(Path(__file__)),binaryReaderSHA256=digest(Path(__file__).with_name('packed_mesh_format.py')),cookedVersion=164,
        quantizationScale=scale.tolist(),quantizationOffset=offset.tolist(),exactQuantizationConstantsVerified=True,
        skinPalette=native_mesh.palette,inverseBindMatrices=native_mesh.inverse_binds,boneIndexMapping=native_mesh.bone_mapping,
        vertexBufferSize=vb,indexBufferOffset=iboffset,indexBufferSize=ibsize,lods=reports,
        nativeVertexOutput=False,observedGameplay=False)
    write_json(output/'inspection.json',report);print(report);return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ['mesh','dump','fbx','output']:p.add_argument('--'+arg,type=Path,required=True)
    a=p.parse_args();inspect(a.mesh,a.dump,a.fbx,a.output)
