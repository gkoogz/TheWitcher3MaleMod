"""Export exact owned cooked vertex lineage, pose bindings and lighting inputs.

Native geometry stays ignored. Does not alter a cooked asset or game installation.
"""
import argparse,struct,sys
from pathlib import Path
import numpy as np
from mod import ROOT,read_json,digest,write_json,base_checkout,settings
from packed_mesh_format import CookedMesh
from prepare_graphics_fingerprints import COOKED

def prepare(output):
    cfg=settings();pin=base_checkout(cfg)['commit'];output=output.resolve()
    sys.path.insert(0,str(cfg['base']))
    from malemod_base.graft import topology_ids,boundary_loops
    if not output.is_relative_to(ROOT/'build') or output.exists():raise ValueError('Use a fresh owned render contract')
    inspected=ROOT/'build/full-runtime/packed-neutral-verified-4';spec=read_json(inspected/'inspection.json')
    mesh_path=COOKED/'geralt_motion.w2mesh';mesh=CookedMesh(mesh_path.read_bytes())
    if digest(mesh_path)!=spec['meshSHA256'] or digest(Path(str(mesh_path)+'.1.buffer'))!=spec['bufferSHA256']:raise ValueError('Owned mesh differs from inspection')
    binding=ROOT/f'build/full-runtime/geralt-bindings-{pin[:7]}/geralt.bindings'
    if digest(binding)!=read_json(binding.parent/'manifest.json')['artifactSHA256']:raise ValueError('Binding proof differs')
    profile=read_json(ROOT/'characters/geralt-runtime-bindings.json');rig_path=ROOT/profile['rig']
    if digest(rig_path)!=profile['rigSHA256']:raise ValueError('Observed rig differs')
    rig=read_json(rig_path)['_chunks']['CSkeleton #0']['_vars'];names=[b['_vars']['name']['_value'] for b in rig['bones']['_elements']]
    if len(names)!=104 or names[9]!='pelvis':raise ValueError('Expected observed 104-joint player rig')
    bone_ids=np.asarray([names.index(n) for n in mesh.palette],dtype='<u4')
    if len(bone_ids)!=46 or not np.array_equal(bone_ids[:23],bone_ids[23:]):raise ValueError('LOD bone palettes differ')
    inverse=np.asarray(mesh.inverse_binds,dtype='<f8').reshape(46,4,4).transpose(0,2,1).copy()
    # Added bones all follow the pelvis. The complete source surface supplies
    # their deformation; the rejected ten-bone dynamics must not deform it again.
    custom=[i for i,n in enumerate(mesh.palette) if n.startswith('mm_')]
    parents=[p['_value'] for p in rig['parentIndices']['_elements']]
    if any(parents[int(bone_ids[i])]!=9 for i in custom):raise ValueError('Added bone is not pelvis-relative')
    output.mkdir(parents=True)
    blob=b'MMRND002'+pin.encode()+digest(binding).encode()+struct.pack('<I',46)+bone_ids.tobytes()+inverse.tobytes()+struct.pack('<I',2)
    rows=[];first_vertex=0;first_index=0
    for lod in range(2):
        data=np.load(inspected/f'lod{lod}.npz');pos=data['position'];skin=data['skin'];lighting=data['lighting'];uv=data['uv'];lineage=data['nearestAuthored'];faces=data['nativeFaces'].copy()
        n=len(pos);normal_word=lighting[:,:4].copy().view('<u4').reshape(-1);tangent_word=lighting[:,4:].copy().view('<u4').reshape(-1)
        normals=np.stack([(normal_word>>i)&1023 for i in (0,10,20)],axis=1)/1023*2-1
        tangents=np.stack([(tangent_word>>i)&1023 for i in (0,10,20)],axis=1)/1023*2-1
        signs=(tangent_word>>30)/3*2-1
        keys=np.column_stack([np.round(pos/1e-5).astype(np.int64),normal_word]);_,groups=np.unique(keys,axis=0,return_inverse=True)
        tri=pos[faces];area=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);dot=(area*normals[faces].mean(axis=1)).sum(axis=1);valid=np.abs(dot)>1e-15
        agreement=float((dot[valid]>0).mean())
        if agreement<.2:faces=faces[:,[0,2,1]];agreement=1-agreement
        if agreement<.8:raise ValueError('Native winding does not agree with authored normals')
        binding_row=read_json(binding.parent/'manifest.json')['lods'][lod]
        authored=binding_row['renderVertices']
        b=np.load(ROOT/binding_row['bindingPath'])
        _,aliases=topology_ids(b['body_original_points'],1e-5)
        boundary=np.concatenate(boundary_loops(aliases[b['body_original_faces']]))
        protected=np.flatnonzero(np.isin(aliases,boundary))
        calibration=np.isin(lineage,protected)&np.all((bone_ids[skin[:,:4]]<94)|(skin[:,4:]==0),axis=1)
        if calibration.sum()<8:raise ValueError('Not enough stock protected vertices for live space validation')
        if lineage.max()>=authored or skin[:,:4].max()>=46 or np.any(skin[:,4:].sum(axis=1)==0):raise ValueError('Native lineage/skin invalid')
        offsets=spec['lods'][lod]['streamOffsets']
        blob+=struct.pack('<6I',n,authored,first_vertex,first_index,len(faces)*3,offsets[1])
        blob+=struct.pack('<I',offsets[3])
        for i in range(n):blob+=struct.pack('<II',int(lineage[i]),int(groups[i]))+skin[i].tobytes()+np.asarray([*uv[i],*normals[i],*tangents[i],signs[i],*pos[i]],dtype='<f8').tobytes()+struct.pack('<I',int(calibration[i]))
        blob+=struct.pack('<I',len(faces))+np.asarray(faces,dtype='<u4').tobytes()
        rows.append(dict(lod=lod,nativeVertices=n,authoredVertices=authored,indices=len(faces)*3,firstVertex=first_vertex,firstIndex=first_index,windingNormalAgreement=agreement))
        first_vertex+=n;first_index+=len(faces)*3
    packet=output/'geralt.render';packet.write_bytes(blob)
    # Generated from observed names; no stock SDK script is committed.
    stock=list(dict.fromkeys(mesh.palette))
    source='import function MaleModNativeBonePose(epoch : int, bone : int, seconds : float, x : Vector, y : Vector, z : Vector, origin : Vector);\n'
    source+='\nfunction MaleModSampleRenderBones(epoch : int, seconds : float, inverse : Matrix)\n{\n    var bone : int;\n    var m : Matrix;\n'
    source+='    m = thePlayer.GetLocalToWorld();\n    MaleModNativeBonePose(epoch,-1,seconds,m.X,m.Y,m.Z,VecTransform(m,Vector(0,0,0,1)));\n'
    for name in stock:
        source+=f"    bone = thePlayer.GetBoneIndex('{name}');\n    if (bone != {names.index(name)}) {{ return; }}\n    m = thePlayer.GetBoneWorldMatrixByIndex(bone);\n    MaleModNativeBonePose(epoch,bone,seconds,\n        VecTransformDir(inverse,m.X),\n        VecTransformDir(inverse,m.Y),\n        VecTransformDir(inverse,m.Z),\n        VecTransform(inverse,VecTransform(m,Vector(0,0,0,1))));\n"
    source+='}\n';(output/'render_bones.ws').write_text(source)
    write_json(output/'manifest.json',dict(baseCommit=pin,packetSHA256=digest(packet),bindingsSHA256=digest(binding),meshSHA256=digest(mesh_path),
                bufferSHA256=spec['bufferSHA256'],rigSHA256=digest(rig_path),recipeSHA256=digest(Path(__file__)),inspectionSHA256=digest(inspected/'inspection.json'),
                boneSourceSHA256=digest(output/'render_bones.ws'),stockPoseBones=stock,lods=rows,nativeOutput=False,observedGameplay=False))
    print('Prepared exact native rendering contract:',output)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);prepare(p.parse_args().output)
