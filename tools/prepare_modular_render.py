"""Bind an immutable Base modular surface to observed Geralt skin/material data.

No game files are modified. Original native body boundaries and both resource
palettes are retained. The binary is bound to exact shared and carrier hashes.
"""
import argparse,hashlib,json,struct,sys
from pathlib import Path
import numpy as np
from scipy import sparse
from scipy.spatial import cKDTree
from wcc_fbx import Document,triangles
from mod import ROOT,digest,read_json

def carrier(path):
    raw=path.read_bytes();offset=240
    def take(dtype,n):
        nonlocal offset
        a=np.frombuffer(raw,dtype,n,offset).copy();offset+=a.nbytes;return a
    def u():return int(take('<u4',1)[0])
    if raw[:8]!=b'MMRND006':raise ValueError('Expected observed multipart carrier')
    n=u();palette=take('<u4',n);take('<f8',n*16);resources=[]
    for _ in range(u()):resources.append((take('<u4',5),take('<f4',6)))
    lods=[]
    for _ in range(u()):
        header=take('<u4',9);rows=take('u1',int(header[2])*156).reshape(-1,156)
        faces=take('<u4',u()*3).reshape(-1,3);take('u1',u()*20)
        lods.append(dict(header=header,rows=rows,faces=faces))
    if offset!=len(raw):raise ValueError('Incomplete carrier parse')
    return palette,resources,lods

def barycentric(p,tri):
    a=tri[:,1]-tri[:,0];b=tri[:,2]-tri[:,0];q=p-tri[:,0]
    aa=np.einsum('ij,ij->i',a,a);ab=np.einsum('ij,ij->i',a,b);bb=np.einsum('ij,ij->i',b,b)
    aq=np.einsum('ij,ij->i',a,q);bq=np.einsum('ij,ij->i',b,q);den=aa*bb-ab*ab
    if np.any(abs(den)<1e-16):raise ValueError('Degenerate stock source face')
    u=(bb*aq-ab*bq)/den;v=(aa*bq-ab*aq)/den
    return np.c_[1-u-v,u,v]

def native_winding(inspection):
    """Measure the cooker's orientation; the analysis contract reorders faces."""
    d=np.load(inspection);p=d['position'];f=d['nativeFaces']
    word=d['lighting'][:,:4].copy().view('<u4').ravel()
    n=np.stack([(word>>k)&1023 for k in [0,10,20]],1)/1023*2-1
    dot=np.einsum('ij,ij->i',np.cross(p[f[:,1]]-p[f[:,0]],p[f[:,2]]-p[f[:,0]]),n[f].mean(1))
    significant=abs(dot)>1e-15
    if not significant.any():raise ValueError('Native winding evidence is degenerate')
    outward=float((dot[significant]>0).mean())
    if .02<outward<.98:raise ValueError('Native winding is inconsistent')
    return outward>.5


def measured_rig_names(profile, stock_rig=None):
    """Read native names; optionally reconstitute only the recorded name table.

    The compact authoring set need not retain a historical generated rig JSON.
    No transforms or new joints are inferred from the stock fallback.
    """
    path = stock_rig or ROOT/profile['rig']
    rig = read_json(path)['_chunks']['CSkeleton #0']['_vars']
    names = [b['_vars']['name']['_value'] for b in rig['bones']['_elements']]
    if stock_rig:
        contract = profile['skeleton']
        if len(names) != contract['stockPrefixCount']:
            raise ValueError('Stock rig prefix differs from recorded character binding')
        for joint in contract['addedJoints']:
            if joint['index'] != len(names) or joint['name'] in names:
                raise ValueError('Recorded extension name order differs')
            names.append(joint['name'])
        if len(names) != contract['totalJoints']:
            raise ValueError('Recorded joint count differs')
    pelvis = profile['skeleton']['pelvis']
    if names[pelvis['index']] != pelvis['name']:
        raise ValueError('Observed pelvis name/index differs')
    return names


def prepare(base,assembly,runtime,lineage,render,inspection,output,stock_rig=None,winding_reference=None):
    sys.path.insert(0,str(base))
    from malemod_base.modular_shading import corner_frames
    from malemod_base.modular_anatomy import Mesh
    from malemod_base.graft import boundary_loops
    if output.exists():raise ValueError('Use a fresh modular native output directory')
    asset=runtime/'display.modular'
    if asset.read_bytes()[:8]!=b'MMMOD002':raise ValueError('Shared modular version differs')
    m=np.load(assembly/'body-union.npz');p=m['points'];f=m['faces'];sf=m['source_faces'];uv=m['corner_uv'].copy()
    donors=sparse.load_npz(assembly/'body-union-donors.npz');line=np.load(lineage)
    native_palette,resources,lods=carrier(render)
    profile=read_json(ROOT/'characters/geralt-runtime-bindings.json')
    names=measured_rig_names(profile,stock_rig);pelvis=names.index('pelvis')
    reference=None
    if winding_reference:
        reference=read_json(winding_reference/'manifest.json')
        if (reference['carrierSHA256']!=digest(render) or
                reference['artifactSHA256']!=digest(winding_reference/'geralt.modular-native')):
            raise ValueError('Winding reference is not bound to this exact native carrier')
        if {(r['resource'],r['lod']) for r in reference['parts']}!={(0,0),(0,1),(1,0),(1,1)}:
            raise ValueError('Winding reference has incomplete resource/LOD coverage')
    paths=[ROOT/'build/probe/geralt_lower.fbx',ROOT/'build/inspection/candidates/t_01_mg__body_hires.fbx']
    original=[];uvs=[];colors=[];reflect=[];weights=[];source_triangles=[];offset=0
    for path in paths:
        d=Document(path);mesh=d.meshes[0];points=mesh.array('Vertices').reshape(-1,3);faces=triangles(mesh)
        def field(name,index,channel,width):return next(x for x in mesh.children if x.name==name and x.values==[index]).array(channel).reshape(-1,width)
        original.append(points);source_triangles.append(faces+offset);offset+=len(points)
        u=field('LayerElementUV',0,'UV',2).copy();u[:,1]=1-u[:,1];u[:,0]*=.5;uvs.append(u)
        colors.append(field('LayerElementColor',0,'Colors',4));rr=field('LayerElementReflectionUV',0,'UV',2).copy();rr[:,1]=1-rr[:,1];reflect.append(rr)
        w=np.zeros((len(points),len(names)))
        for name,cluster in d.skin(mesh):w[cluster.array('Indexes'),names.index(name)]=cluster.array('Weights')
        weights.append(w)
    source_points=line['points'];source_faces=np.vstack(source_triangles);stock_uv=np.vstack(uvs);stock_weight=np.vstack(weights)
    if len(source_points)!=len(stock_uv):raise ValueError('Stock lineage bank differs')
    # The actual face parent identifies the correct UV island even when the
    # geometric cut shares one vertex across several positional aliases.
    body_faces=(sf>=0)&(sf<len(source_faces));selected=np.flatnonzero(body_faces)
    for corner in range(3):
        parent=source_faces[sf[selected]];b=barycentric(p[f[selected,corner]],source_points[parent])
        uv[selected,corner]=np.einsum('ni,nij->nj',b,stock_uv[parent])
    uv[~body_faces,:,0]=(uv[~body_faces,:,0]+1)*.5
    bc=len(source_points);all_weights=np.zeros((donors.shape[1],len(names)));all_weights[:bc]=stock_weight;all_weights[bc:,pelvis]=1
    w=donors@all_weights
    # The same canonical seam donor must yield the same byte skin weights in
    # both resource palettes. Quantize once in skeleton-name space.
    bone_ids=np.argsort(-w,axis=1,kind='stable')[:,:4];weights4=np.take_along_axis(w,bone_ids,axis=1)
    weights4/=weights4.sum(1)[:,None];unrounded=weights4*255;quant=np.floor(unrounded).astype(np.uint8)
    remainder=255-quant.sum(1);order=np.argsort(-(unrounded-quant),axis=1,kind='stable')
    for j in range(3):selected_rows=np.flatnonzero(remainder>j);quant[selected_rows,order[selected_rows,j]]+=1
    all_colors=np.ones((donors.shape[1],4));all_colors[:bc]=np.vstack(colors)
    all_reflect=np.zeros((donors.shape[1],2));all_reflect[:bc]=np.vstack(reflect)
    color=np.round(np.clip(donors@all_colors,0,1)*255).astype('u1');reflection=(donors@all_reflect).astype('<f2')
    geometry=Mesh(p,f,uv,donors,sf,m['generated'],m['normal_field']);lighting=corner_frames(geometry)
    upper=body_faces&(sf>=len(source_triangles[0]))
    # Keep exact native neck/wrist/ankle vertices. Other body points remain on
    # the original body; the shared waist is one geometric vertex in both parts.
    cal=profile['coordinateCalibration'];basis=np.array(cal['basis']);scale=cal['nativeUnitsPerSourceUnit'];target=(p-cal['sourceRoot'])@basis.T*scale+cal['targetRootNative']
    protected=np.zeros(len(p),dtype=bool)
    visible=np.asarray(m['visible_faces'],dtype=int) if 'visible_faces' in m else np.arange(len(f))
    if visible.ndim!=1 or len(np.unique(visible))!=len(visible) or np.any((visible<0)|(visible>=len(f))):
        raise ValueError('Invalid visible fallback face selection')
    for loop in boundary_loops(f[visible]):protected[loop]=True
    fixed=np.zeros_like(target);fixed_mask=np.zeros(len(p),dtype=bool)
    candidates=[]
    for lod in lods:
        if lod['header'][1]:continue
        for row in lod['rows']:
            if struct.unpack_from('<I',row,112)[0]:candidates.append(struct.unpack_from('<3d',row,88))
    distance,nearest=cKDTree(candidates).query(target[protected]);
    if distance.max()>.002:raise ValueError('Stock external boundary does not match observed carrier')
    fixed[protected]=np.asarray(candidates)[nearest];fixed_mask[protected]=True
    output.mkdir(parents=True);blob=bytearray(b'MMMODW01'+digest(asset).encode()+digest(render).encode()+struct.pack('<I',len(p)))
    blob+=fixed_mask.astype('u1').tobytes()+fixed.astype('<f8').tobytes()
    reports=[]
    for resource in range(2):
        face_ids=visible[(upper if resource else ~upper)[visible]];geometric=f[face_ids].ravel();corner_uv=uv[face_ids].reshape(-1,2);tangent=lighting['tangent'][face_ids].reshape(-1,3);sign=lighting['sign'][face_ids].ravel()
        # Share only equal geometry + UV + tangent-sign aliases; no per-face
        # duplication of smooth vertices and no loss of mirrored UV handedness.
        keys=np.c_[geometric,np.round(corner_uv,12),sign];_,first,inverse=np.unique(keys,axis=0,return_index=True,return_inverse=True)
        geometric=geometric[first];corner_uv=corner_uv[first];tangent=tangent[first];sign=sign[first];indices=inverse.reshape(-1,3)
        for lod in range(2):
            old=next(x for x in lods if tuple(x['header'][:2])==(resource,lod));r=resources[resource][0];first_palette=int(r[2]);palette_count=int(r[3]);half=palette_count//2
            palette=native_palette[first_palette+lod*half:first_palette+(lod+1)*half]
            remap={int(b):i+lod*half for i,b in enumerate(palette)};skin=np.zeros((len(geometric),4),dtype='u1')
            for i,g in enumerate(geometric):
                for j,b in enumerate(bone_ids[g]):
                    if quant[g,j] and int(b) not in remap:raise ValueError(f'Observed palette lacks weighted joint {names[b]}')
                    skin[i,j]=remap.get(int(b),remap[pelvis])
            blob+=struct.pack('<6I',resource,lod,int(old['header'][5]),int(old['header'][6]),len(geometric),indices.size)
            for i,g in enumerate(geometric):
                blob+=struct.pack('<I',int(g))+skin[i].tobytes()+quant[g].tobytes()+corner_uv[i].astype('<f2').tobytes()+color[g].tobytes()+reflection[g].tobytes()+struct.pack('<4d',*tangent[i],sign[i])
            if reference:
                measured=next(r for r in reference['parts'] if (r['resource'],r['lod'])==(resource,lod))
                outward=measured['nativeOutwardWinding']
                if type(outward) is not bool:raise ValueError('Invalid measured winding')
                evidence_hash=measured['windingEvidenceSHA256']
            else:
                evidence=inspection/('inspection-'+['lower','upper'][resource])/f'lod{lod}.npz'
                outward=native_winding(evidence);evidence_hash=digest(evidence)
            native_indices=indices if outward else indices[:,[0,2,1]]
            blob+=native_indices.astype('<u4').tobytes();reports.append(dict(resource=resource,lod=lod,vertices=len(geometric),triangles=len(indices),nativeOutwardWinding=outward,windingEvidenceSHA256=evidence_hash))
    path=output/'geralt.modular-native';path.write_bytes(blob);path.with_suffix(path.suffix+'.sha256').write_text(digest(path)+'\n')
    np.savez_compressed(output/'material-preview.npz',corner_uv=uv,skin=bone_ids,weights=quant,color=color,reference=target,fixed_mask=fixed_mask,fixed=fixed)
    report=dict(schema='malemod.witcher-modular-render/1',artifactSHA256=digest(path),sharedSHA256=digest(asset),carrierSHA256=digest(render),parts=reports,stock=[dict(path=str(p),sha256=digest(p)) for p in paths],singularUVFaces=len(lighting['singular_uv_faces']),nativeObserved=False,installed=False)
    if stock_rig:report['stockRigNames']=dict(path=str(stock_rig.resolve()),sha256=digest(stock_rig),extensionProfileSHA256=digest(ROOT/'characters/geralt-runtime-bindings.json'))
    if reference:report['windingReference']=dict(path=str(winding_reference.resolve()),manifestSHA256=digest(winding_reference/'manifest.json'),carrierReverified=True)
    (output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ['base','assembly','runtime','lineage','render','output']:parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--inspection',type=Path)
    parser.add_argument('--stock-rig',type=Path)
    parser.add_argument('--winding-reference',type=Path,help='Previously verified native binding for this exact carrier')
    a=parser.parse_args()
    if not a.inspection and not a.winding_reference:parser.error('Provide inspection or exact-carrier winding reference')
    prepare(**vars(a))
