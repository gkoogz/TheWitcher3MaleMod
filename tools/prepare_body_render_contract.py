"""Bind the two observed cooked body resources to one combined surface."""
import argparse,struct,sys
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix
from mod import ROOT,settings,base_checkout,read_json,write_json,digest,run_wcc
from packed_mesh_format import CookedMesh
from inspect_packed_mesh import inspect


def prepare(job,cooked,binding_dir,output):
    job,cooked,binding_dir,output=[Path(p).absolute() for p in [job,cooked,binding_dir,output]]
    cfg=settings();pin=base_checkout(cfg)['commit'];sys.path.insert(0,str(cfg['base']))
    from malemod_base.graft import topology_ids
    from malemod_base.motion_binding import reference_fields
    from malemod_base.presentation_binding import presentation_bindings
    if not all(p.is_relative_to(ROOT/'build') for p in [job,cooked,binding_dir,output]) or output.exists():raise ValueError('Use fresh owned build output')
    binding=binding_dir/'geralt.bindings';binding_report=read_json(binding_dir/'manifest.json')
    if binding_report['baseCommit']!=pin or digest(binding)!=binding_report['artifactSHA256']:raise ValueError('Binding pin/hash differs')
    profile=read_json(ROOT/'characters/geralt-runtime-bindings.json');rig=read_json(ROOT/profile['rig'])['_chunks']['CSkeleton #0']['_vars'];names=[b['_vars']['name']['_value'] for b in rig['bones']['_elements']]
    paths=[cooked/'characters/malemod/body/geralt_motion.w2mesh',cooked/'characters/models/geralt/body/model/t_01_mg__body_hires.w2mesh']
    output.mkdir(parents=True);meshes=[];specs=[];palette=[];inverse=[]
    for label,path in zip(['lower','upper'],paths):
        run_wcc(cfg,'dumpfile',['-file='+str(path),'-out=\\\\?\\'],job/'intake','inspect-cooked-'+label)
        spec=inspect(path,Path(str(path)+'.xml'),job/(label+'.fbx'),output/('inspection-'+label));specs.append(spec)
        mesh=CookedMesh(path.read_bytes());meshes.append(mesh);palette.extend(names.index(n) for n in mesh.palette);inverse.extend(np.asarray(mesh.inverse_binds).reshape(-1,4,4).transpose(0,2,1))
    cal=profile['coordinateCalibration'];blob=b'MMRND004'+pin.encode()+digest(binding).encode()+np.asarray([*np.asarray(cal['basis']).flatten(),*cal['sourceRoot'],*cal['targetRootNative'],cal['nativeUnitsPerSourceUnit']],dtype='<f8').tobytes()
    blob+=struct.pack('<I',len(palette))+np.asarray(palette,dtype='<u4').tobytes()+np.asarray(inverse,dtype='<f8').tobytes()+struct.pack('<I',2)
    first_vertex=first_palette=0;resources=[]
    for mesh,spec in zip(meshes,specs):
        count=sum(r['nativeVertices'] for r in spec['lods']);resource=dict(firstVertex=first_vertex,vertexCount=count,firstPalette=first_palette,paletteCount=len(mesh.palette),indexBytes=spec['indexBufferSize'])
        blob+=struct.pack('<5I',*resource.values())+np.asarray(mesh.scale[:3],dtype='<f4').tobytes()+np.asarray(mesh.offset[:3],dtype='<f4').tobytes();resources.append(resource)
        first_vertex+=count;first_palette+=len(mesh.palette)
    blob+=struct.pack('<I',4);rows=[]
    source_fields=reference_fields(np.load(cfg['base']/'assets/wolverine-reference/geometry.npz'))
    fit=read_json(ROOT/'build/attachment/fit-20261001-193459-664950/geralt-anatomy.fit.json')
    lobes=(np.asarray(fit['sourceMechanics']['lobeCenters'])-cal['sourceRoot'])@np.asarray(cal['basis']).T*cal['nativeUnitsPerSourceUnit']+cal['targetRootNative']
    first_vertex=0
    for resource in range(2):
      first_index=0
      for lod in range(2):
        part=np.load(job/('part%d.npz'%(resource*2+lod)));data=np.load(output/('inspection-'+['lower','upper'][resource])/('lod%d.npz'%lod));spec=specs[resource]['lods'][lod]
        pos=data['position'];skin=data['skin'].copy();uv=data['uv'];lighting=data['lighting'];ids=data['nearestAuthored'];faces=data['nativeFaces'].copy();n=len(pos)
        skin[:,:4]+=resources[resource]['firstPalette']
        low=binding_report['lods'][lod]['lowerBodyVertices'];upper=binding_report['lods'][lod]['upperBodyVertices'];authored=binding_report['lods'][lod]['renderVertices']
        mapping=ids.copy()
        if resource==0:mapping[mapping>=low]+=upper
        else:mapping+=low
        nw=lighting[:,:4].copy().view('<u4').reshape(-1);tw=lighting[:,4:].copy().view('<u4').reshape(-1)
        normals=np.stack([(nw>>i)&1023 for i in [0,10,20]],1)/1023*2-1;tangents=np.stack([(tw>>i)&1023 for i in [0,10,20]],1)/1023*2-1;signs=(tw>>30)/3*2-1
        tri=pos[faces];dot=(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])*normals[faces].mean(1)).sum(1);agreement=(dot[np.abs(dot)>1e-15]>0).mean()
        if agreement<.2:faces=faces[:,[0,2,1]];agreement=1-agreement
        if agreement<.8:raise ValueError('Native winding mismatch')
        _,groups=np.unique(np.column_stack([np.round(pos/1e-5).astype(np.int64),nw]),axis=0,return_inverse=True)
        keep,aliases=topology_ids(part['points'],1e-5);protected=np.isin(aliases[ids],aliases[part['protected']]);knots=np.zeros(len(part['points']),dtype=np.uint32)
        for j,k in enumerate(part['waist']):knots[aliases==aliases[k]]=j+1
        boundary=knots[ids];calibration=protected
        pf=np.zeros(n,dtype=np.uint32);pa=np.zeros(n)
        if resource==0:
            ml=csr_matrix((part['module_lineage_data'],part['module_lineage_indices'],part['module_lineage_indptr']),shape=tuple(part['module_lineage_shape']))
            field=np.zeros((len(part['points']),3));field[low:]=np.clip(ml@source_fields,0,1)
            palette_array=np.asarray(palette);amount=(skin[:,4:]*(palette_array[skin[:,:4]]>=94)).sum(1)/skin[:,4:].sum(1)
            pf,pa=presentation_bindings(field[ids],pos,lobes,amount)
        blob+=struct.pack('<9I',resource,lod,n,authored,first_vertex,first_index,len(faces)*3,spec['streamOffsets'][1],spec['streamOffsets'][3])
        for i in range(n):blob+=struct.pack('<II',int(mapping[i]),int(groups[i]))+skin[i].tobytes()+np.asarray([*uv[i],*normals[i],*tangents[i],signs[i],*pos[i]],dtype='<f8').tobytes()+struct.pack('<IIdI',int(calibration[i]),int(pf[i]),float(pa[i]),int(boundary[i]))
        blob+=struct.pack('<I',len(faces))+np.asarray(faces,dtype='<u4').tobytes()
        rows.append(dict(resource=resource,lod=lod,nativeVertices=n,authoredVertices=authored,boundaryAliases=int((boundary>0).sum()),protectedAliases=int(calibration.sum())))
        first_vertex+=n;first_index+=len(faces)*3
    packet=output/'geralt.render';packet.write_bytes(blob)
    # Render pose sampler includes the union of the actual palettes.
    stock=list(dict.fromkeys(n for m in meshes for n in m.palette))
    source='import function MaleModNativeBonePose(epoch : int, bone : int, seconds : float, x : Vector, y : Vector, z : Vector, origin : Vector);\n\nfunction MaleModSampleRenderBones(epoch : int, seconds : float, inverse : Matrix)\n{\n    var bone : int;\n    var m : Matrix;\n    m = thePlayer.GetLocalToWorld();\n    MaleModNativeBonePose(epoch,-1,seconds,m.X,m.Y,m.Z,VecTransform(m,Vector(0,0,0,1)));\n'
    for name in stock:
        source+=f"    bone = thePlayer.GetBoneIndex('{name}');\n    if (bone != {names.index(name)}) {{ return; }}\n    m = thePlayer.GetBoneWorldMatrixByIndex(bone);\n    MaleModNativeBonePose(epoch,bone,seconds,VecTransformDir(inverse,m.X),VecTransformDir(inverse,m.Y),VecTransformDir(inverse,m.Z),VecTransform(inverse,VecTransform(m,Vector(0,0,0,1))));\n"
    source+='}\n';(output/'render_bones.ws').write_text(source)
    write_json(output/'manifest.json',dict(baseCommit=pin,contractVersion=4,packetSHA256=digest(packet),bindingsSHA256=digest(binding),boneSourceSHA256=digest(output/'render_bones.ws'),resources=resources,lods=rows,recipeSHA256=digest(Path(__file__)),nativeOutput=False,observedGameplay=False))
    print('Prepared coherent lower/upper render contract:',output)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['job','cooked','bindings','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();prepare(a.job,a.cooked,a.bindings,a.output)
