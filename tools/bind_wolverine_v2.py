"""Bind exact cooked Geralt rows to canonical source surface displacements.

Stock/seam baselines are retained verbatim. B04 anatomy interiors restore the
unquantized fitted baseline after cooking. Geometry donors never contain a second
deformation law: each delta is sampled from the canonical whole surface.
"""
import struct,sys,json,hashlib,argparse
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import csr_matrix
from mod import ROOT,digest,read_json,write_json
from packed_mesh_format import CookedMesh,decode_render_chunks
from wcc_fbx import Document,triangles
from v2_native_binding import SECTION_KEYS
sys.path.insert(0,str(ROOT.parent/'Work/python'))


def nearest_triangle(points,vertices,faces):
    # The source body is smooth, but centroid proximity alone is insufficient.
    # Test the closest 32 bounded triangles and choose actual surface distance.
    import trimesh
    tri=vertices[faces];tree=cKDTree(tri.mean(1));_,candidates=tree.query(points,k=32)
    selected=tri[candidates].reshape(-1,3,3)
    query=np.repeat(points,32,axis=0)
    closest=trimesh.triangles.closest_point(selected,query)
    distances=np.linalg.norm(closest-query,axis=1).reshape(-1,32)
    choice=distances.argmin(1);ids=candidates[np.arange(len(points)),choice]
    q=closest.reshape(-1,32,3)[np.arange(len(points)),choice]
    weights=trimesh.triangles.points_to_barycentric(tri[ids],q)
    if np.min(weights)<-1e-5 or not np.isfinite(weights).all():raise ValueError('Invalid body surface donor')
    return faces[ids],weights,distances[np.arange(len(points)),choice]


def complete_body_domain(source,face_parts):
    """Join both canonical native body allocations without welding their rows.

    These are complementary body parts, not interchangeable LODs. In
    particular, the first allocation has no left inner-thigh surface. Keep
    each part's actual bank index so runtime motion and lighting come from the
    same canonical part. Discard only zero-area triangles, which cannot define
    a barycentric surface donor.
    """
    if len(source)!=2 or len(face_parts)!=2:
        raise ValueError('Both canonical body parts are required')
    vertices=[];faces=[];first=0
    for part,triangles in zip(source,face_parts):
        p=np.asarray(part,dtype=float);f=np.asarray(triangles,dtype=np.int64)
        if p.ndim!=2 or p.shape[1]!=3 or f.ndim!=2 or f.shape[1]!=3 or not np.isfinite(p).all() or not len(f) or f.min()<0 or f.max()>=len(p):
            raise ValueError('Invalid canonical body-part topology')
        tri=p[f];twice_area=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)
        # A nonzero source triangle is retained regardless of its size.
        valid=twice_area>0
        if not valid.any():raise ValueError('Canonical body part has no surface triangles')
        vertices.append(p);faces.append(f[valid]+first);first+=len(p)
    return np.vstack(vertices),np.vstack(faces)


def bind(cooked=None,output=None,material_contract=None,source_lighting=False,source_lighting_cases=None,authoritative_lighting_aliases=False,waist_join=None,all_source_body_parts=True):
    r=ROOT/'v2/build';out=Path(output)if output is not None else r/'runtime-binding';out.mkdir(exist_ok=True,parents=True)
    fit=read_json(r/'fitted-geralt/manifest.json')
    if digest(r/'fitted-geralt/geralt-wolverine.fbx')!=fit['fbxSHA256']:raise ValueError('Fit source changed')
    sectioned=cooked is not None
    waist=None
    if waist_join is not None:
        if not sectioned:raise ValueError('Explicit stock waist repair requires B04 cooked resources')
        from v2_waist_binding import load as load_waist
        waist=load_waist(waist_join)
    if source_lighting and not sectioned:raise ValueError('Experimental source lighting requires explicit B04 cooked resources')
    cook=Path(cooked)if sectioned else next((r/'native-fit-02/build').glob('package-*/cooked/characters/models/geralt/body/model'))
    contract=read_json(material_contract)if material_contract is not None else None
    if contract is not None and not sectioned:raise ValueError('Material contract requires an explicit cooked source')
    reference=r/'wolverine-reference/state-2';source=[];source_normals=[];source_tangents=[]
    for file in ['anatomy.packed','body0.packed','body1.packed']:
        raw=np.fromfile(reference/file,'u1').reshape(-1,32)
        source.append(raw[:,:12].copy().view('<f4').reshape(-1,3))
        source_normals.append(raw[:,16:19].astype('<f4')/np.float32(127.5)-np.float32(1))
        source_tangents.append(raw[:,12:15].astype('<f4')/np.float32(127.5)-np.float32(1))
    bank=np.vstack(source);body=np.load(r/'source-body0.npz')
    body_vertices=source[1];body_faces=body['faces']
    if all_source_body_parts:
        body_vertices,body_faces=complete_body_domain(source[1:],[body['faces'],np.load(r/'source-body1.npz')['faces']])
    lower=np.load(r/'fitted-geralt/lod0.npz');rotation=lower['rotation'];root=lower['sourceRoot'];target=lower['targetRoot']
    rigpath=r/'geralt-base/player-rig.json';rig=read_json(rigpath)['_chunks']['CSkeleton #0']['_vars'];bone_names=[x['_vars']['name']['_value']for x in rig['bones']['_elements']]
    if len(bone_names)!=94 or bone_names[9]!='pelvis':raise ValueError('Stock rig identity differs')
    payload=bytearray(b'MMV2B04\0'if sectioned else b'MMV2B03\0');payload+=struct.pack('<I',2)
    payload+=np.asarray(rotation,'<f4').tobytes();payload+=np.asarray(root,'<f4').tobytes();payload+=np.asarray(target,'<f4').tobytes()
    payload+=struct.pack('<I',len(bank));payload+=bank.astype('<f4').tobytes()
    payload+=np.vstack(source_normals).astype('<f4').tobytes()
    if sectioned:payload+=np.vstack(source_tangents).astype('<f4').tobytes()
    fingerprint=[];reports=[];required_bones={}
    for resource,name in enumerate(['l_01_mg__body','t_01_mg__body_hires']):
        path=cook/(name+'.w2mesh');mesh=CookedMesh(path.read_bytes(),allow_stock_torso_mapping=resource==1,allow_multi_section=sectioned);raw=Path(str(path)+'.1.buffer').read_bytes()
        integer=lambda key:struct.unpack('<I',mesh.get(mesh.cooked,key,'Uint32'))[0]
        vertex_bytes=integer('vertexBufferSize');index_offset=integer('indexBufferOffset');index_bytes=integer('indexBufferSize')
        sections=mesh.skin_sections(raw)
        if resource==0 and contract is not None:
            if contract['cookedMeshSHA256']!=digest(path)or contract['cookedBufferSHA256']!=digest(Path(str(path)+'.1.buffer')):
                raise ValueError('Material state contract differs from actual native cook')
            mappings=contract['sectionMaterials']
            if len(mappings)!=len(sections):raise ValueError('Material state section count differs')
            for index,(section,mapping)in enumerate(zip(sections,mappings)):
                if mapping['section']!=index or mapping['lod']!=section['lod']or mapping['nativeMaterial']!=section['material']or mapping['semanticMaterial']not in (0,1,2):
                    raise ValueError('Material state section identity differs')
                section['nativeMaterial']=section['material'];section['material']=mapping['semanticMaterial']
            for lod in (0,1):
                if sorted(s['material']for s in sections if s['lod']==lod)!=[0,1,2]:raise ValueError('Both source skin states and stock body required per LOD')
        elif any(s['material']for s in sections):raise ValueError('An explicit verified material-state contract is required')
        if not sectioned and len(sections)!=2:raise ValueError('Legacy binding requires one section per LOD')
        records=[];counts=[0,0];offsets=[None,None];binding_errors=[];surface_distances=[]
        prefix='upper_'if resource else 'lower_'
        for label,data in [('all',raw),('vertices',raw[:vertex_bytes]),('indices',raw[index_offset:index_offset+index_bytes])]:fingerprint.append((prefix+label,data))
        for section,c in enumerate(sections):
            lod=c['lod'];off=[c[k]for k in SECTION_KEYS[4:8]];n=c['vertexCount'];counts[lod]+=n
            if offsets[lod]is None:offsets[lod]=off
            pos=np.frombuffer(raw,dtype='u1',count=n*16,offset=off[0]).reshape(n,16)
            quant=pos[:,:8].copy().view('<u2').reshape(n,4)[:,:3]
            native=quant.astype(float)/65535*np.asarray(mesh.scale[:3])+np.asarray(mesh.offset[:3])
            if resource==0:
                authored=np.load(r/f'fitted-geralt/lod{lod}.npz');points=authored['points'];original_point_count=len(points);bodycount=int(authored['bodyCount'])
                if waist is not None and lod==1:
                    from v2_waist_binding import extend_points
                    points=extend_points(waist,points)
                distance,rows=cKDTree(points*.01).query(native)
                if distance.max()>3e-5:raise ValueError('Native vertex leaves fitted source')
                matrix=csr_matrix((authored['module_data'],authored['module_indices'],authored['module_indptr']),shape=tuple(authored['module_shape']))
                donors,weights,surface_distance=nearest_triangle((points-target)@rotation+root,body_vertices,body_faces)
                donors+=len(source[0])
                # Both sides of the sewn opening use identical exact source
                # anatomy lineage, including barycentric boundary refinement.
                aliases={int(b):int(m)for b,m in zip(authored['seamBody'],authored['seamModule'])}
                for row in range(original_point_count):
                    module_row=row-bodycount if row>=bodycount else aliases.get(row,-1)-bodycount
                    if module_row<0:continue
                    lo,hi=matrix.indptr[module_row:module_row+2];ids=matrix.indices[lo:hi];w=matrix.data[lo:hi]
                    if len(ids)>3:raise ValueError('Source lineage exceeds triangle support')
                    donors[row]=0;weights[row]=0;donors[row,:len(ids)]=ids;weights[row,:len(w)]=w
                if waist is not None and lod==1:
                    # Appended stock rows are NOT module CSR rows. They carry
                    # the exact measured upper-body source lineage instead.
                    donors[original_point_count:]=waist['lineage']['donors']
                    weights[original_point_count:]=waist['lineage']['weights']
                donors=donors[rows];weights=weights[rows];surface_distance=surface_distance[rows]
                binding_errors.append(float(distance.max()))
            else:
                donors,weights,surface_distance=nearest_triangle((native*100-target)@rotation+root,body_vertices,body_faces);donors+=len(source[0])
                binding_errors.append(0.)
            surface_distances.append(float(surface_distance.max()))
            # Position/bones/weights and packed lighting baseline exactly match
            # the native allocation; dynamic positions use unbounded float IA.
            light=raw[off[2]:off[2]+n*8]
            for i in range(n):
                records.append(struct.pack('<3f',*(quant[i].astype(float)/65535))+bytes(pos[i,8:16])+light[i*8:i*8+8]+struct.pack('<3I3f',*donors[i],*weights[i]))
            for slot,stride in enumerate([16,4,8,8]):
                label=prefix+f'lod{lod}_'+(f'section{section}_'if sectioned else '')+f'stream{slot}'
                fingerprint.append((label,raw[off[slot]:off[slot]+n*stride]))
        payload+=struct.pack('<5I',len(records),index_bytes,vertex_bytes if sectioned else 0,0,0)
        payload+=struct.pack('<6f',*mesh.scale[:3],*mesh.offset[:3])
        payload+=struct.pack('<8I',0,counts[0],*counts,*[x[1]for x in offsets],*[x[3]for x in offsets])
        if sectioned:
            payload+=struct.pack('<I',len(sections))
            for section in sections:payload+=struct.pack('<10I',*(section[key]for key in SECTION_KEYS))
        payload+=struct.pack('<I',len(mesh.palette))
        for bone_name,inverse in zip(mesh.palette,mesh.inverse_binds):
            index=bone_names.index(bone_name);required_bones[bone_name]=index
            payload+=struct.pack('<I',index)+np.asarray(inverse,'<f4').reshape(4,4).T.tobytes()
        payload+=b''.join(records)
        reports.append(dict(resource=name,cookedPath=str(path.resolve()),cookedSHA256=digest(path),bufferSHA256=digest(Path(str(path)+'.1.buffer')),nativeVertices=counts,sections=sections,maximumNativeBindingErrorMeters=binding_errors,maximumSourceBodyDonorDistance=surface_distances,palette=mesh.palette))
    binding=out/'geralt-source-binding.bin';binding.write_bytes(payload)
    waist_report=None
    if waist is not None:
        from v2_waist_binding import calibrate
        waist_report=calibrate(binding,cook,waist,out/'source-waist.json')
    precision=None
    if sectioned:
        from v2_source_precision import restore_binding
        precision=restore_binding(binding,r/'fitted-geralt',cook/'l_01_mg__body.w2mesh',out/'source-precision.json')
    lighting=None
    if source_lighting:
        from v2_source_lighting import restore_binding as restore_lighting
        if authoritative_lighting_aliases and source_lighting_cases is None:raise ValueError('Authoritative lighting alias correction requires actual changing source cases')
        lighting=restore_lighting(binding,r/'fitted-geralt',cook/'l_01_mg__body.w2mesh',reference/'anatomy.packed',out/'source-lighting.json',source_lighting_cases,authoritative_lighting_aliases)
    elif authoritative_lighting_aliases:raise ValueError('Authoritative lighting aliases require source lighting restoration')
    fp=bytearray(b'MMGPH01\0')+struct.pack('<I',len(fingerprint))
    for label,data in fingerprint:
        name=label.encode('ascii');fp+=struct.pack('<IH',len(data),len(name))+data[:32]+hashlib.sha256(data).digest()+name
    (out/'graphics-owned-fingerprints.bin').write_bytes(fp)
    script='import function MaleModNativeBonePose(epoch : int, bone : int, seconds : float, x : Vector, y : Vector, z : Vector, origin : Vector);\nfunction MaleModSampleRenderBones(epoch : int, seconds : float, inverse : Matrix)\n{\nvar bone : int;\nvar m : Matrix;\nm=thePlayer.GetLocalToWorld();\nMaleModNativeBonePose(epoch,-1,seconds,m.X,m.Y,m.Z,VecTransform(m,Vector(0,0,0,1)));\n'
    for name,index in required_bones.items():
        script+=f"bone=thePlayer.GetBoneIndex('{name}');if(bone!={index}){{return;}}\nm=thePlayer.GetBoneWorldMatrixByIndex(bone);\nMaleModNativeBonePose(epoch,bone,seconds,VecTransformDir(inverse,m.X),VecTransformDir(inverse,m.Y),VecTransformDir(inverse,m.Z),VecTransform(inverse,VecTransform(m,Vector(0,0,0,1))));\n"
    (out/'render_bones.ws').write_text(script+'}\n')
    report=dict(schema='malemod.witcher-v2-native-binding/'+('4'if sectioned else'3'),bindingSHA256=digest(binding),fitManifestSHA256=digest(r/'fitted-geralt/manifest.json'),referenceManifestSHA256=digest(reference.parent/'manifest.json'),fingerprintsSHA256=digest(out/'graphics-owned-fingerprints.bin'),stockRigSHA256=digest(rigpath),poseScriptSHA256=digest(out/'render_bones.ws'),rotation=rotation.tolist(),sourceRoot=root.tolist(),targetRoot=target.tolist(),resources=reports,nativeObserved=False,attachmentGatePassed=False)
    if material_contract is not None:report.update(materialContract=str(Path(material_contract).resolve()),materialContractSHA256=digest(material_contract))
    if precision is not None:report.update(sourcePrecision=precision,sourcePrecisionReceiptSHA256=digest(out/'source-precision.json'))
    if lighting is not None:report.update(sourceLighting=lighting,sourceLightingReceiptSHA256=digest(out/'source-lighting.json'))
    if waist_report is not None:report.update(sourceWaist=waist_report,sourceWaistReceiptSHA256=digest(out/'source-waist.json'))
    if all_source_body_parts:
        report['canonicalBodyDomain']=dict(parts=[dict(bankFirstVertex=17528,vertices=len(source[1]),topologySHA256=digest(r/'source-body0.npz')),dict(bankFirstVertex=17528+len(source[1]),vertices=len(source[2]),topologySHA256=digest(r/'source-body1.npz'))],surfaceTriangles=len(body_faces),bothComplementaryParts=True,sourceNumericsModified=False)
    write_json(out/'manifest.json',report);print(json.dumps(report,indent=2))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--cooked',type=Path,help='Explicit officially cooked multi-section model directory')
    parser.add_argument('--output',type=Path);parser.add_argument('--material-contract',type=Path)
    parser.add_argument('--source-lighting',action='store_true',help='Experimental raw source-interior TBN restoration; default OFF')
    parser.add_argument('--source-lighting-cases',type=Path,help='Actual captured source checkpoint directory required before correcting close frame-donor aliases')
    parser.add_argument('--source-lighting-authoritative-aliases',action='store_true',help='Use exact authored UV/topology for all near-position lighting aliases; requires changing-case proof and native review')
    parser.add_argument('--waist-join',type=Path,help='Explicit hash-closed LOD1 stock-waist authoring receipt; default OFF')
    parser.set_defaults(all_source_body_parts=True)
    parser.add_argument('--all-source-body-parts',action='store_true',help='Use both complementary canonical body allocations for Geralt body donors (default)')
    parser.add_argument('--legacy-body0-only',dest='all_source_body_parts',action='store_false',help='Reproduce the historical incomplete body0-only donor domain; do not use for a new candidate')
    args=parser.parse_args();bind(args.cooked,args.output,args.material_contract,args.source_lighting,args.source_lighting_cases,args.source_lighting_authoritative_aliases,args.waist_join,args.all_source_body_parts)
