"""Preserve source skin/UV fields for runtime original-surface cuts."""
import argparse,struct,sys
from pathlib import Path
import numpy as np
from scipy import sparse
from scipy.spatial import cKDTree
from mod import ROOT,read_json,digest
from wcc_fbx import Document,triangles
from prepare_modular_render import carrier,barycentric,measured_rig_names

def prepare(base,body,assembly,module,runtime,dynamic,native,source,render,output,stock_rig=None):
    sys.path.insert(0,str(base))
    from malemod_base.modular_anatomy import Mesh,vertex_normals
    from malemod_base.modular_shading import corner_frames,boundary_uv_field
    from malemod_base.graft import boundary_loops
    from tools.build_modular_anatomy import read_source
    if output.exists():raise ValueError('Use a new material binding artifact')
    b=np.load(body);m=np.load(assembly/'body-union.npz');d=sparse.load_npz(assembly/'body-union-donors.npz');bd=sparse.load_npz(body.with_name(body.stem+'-donors.npz'))
    profile=read_json(ROOT/'characters/geralt-runtime-bindings.json');names=measured_rig_names(profile,stock_rig)
    pelvis=names.index('pelvis');stock_uv=[];colors=[];reflection=[];weights=[];source_faces=[];offset=0
    for path in [ROOT/'build/probe/geralt_lower.fbx',ROOT/'build/inspection/candidates/t_01_mg__body_hires.fbx']:
        doc=Document(path);mesh=doc.meshes[0];points=mesh.array('Vertices').reshape(-1,3)
        def field(name,key,width):return next(c for c in mesh.children if c.name==name and c.values==[0]).array(key).reshape(-1,width)
        uv=field('LayerElementUV','UV',2).copy();uv[:,0]*=.5;uv[:,1]=1-uv[:,1];stock_uv.append(uv)
        colors.append(field('LayerElementColor','Colors',4));r=field('LayerElementReflectionUV','UV',2).copy();r[:,1]=1-r[:,1];reflection.append(r)
        w=np.zeros((len(points),len(names)))
        for name,cluster in doc.skin(mesh):w[cluster.array('Indexes'),names.index(name)]=cluster.array('Weights')
        weights.append(w);source_faces.append(triangles(mesh)+offset);offset+=len(points)
    stock_uv=np.vstack(stock_uv);stock_faces=np.vstack(source_faces);stock_w=np.vstack(weights);stock_c=np.vstack(colors);stock_r=np.vstack(reflection)
    body_uv=stock_uv[stock_faces[b['source_faces']]]
    original,_,_,_,_=read_source(source);original_uv=np.zeros((len(original.points),2));original_uv[original.faces]=original.corner_uv
    module_uv=m['corner_uv'].copy();body_faces=(m['source_faces']>=0)&(m['source_faces']<len(stock_faces))
    # Generated surface pieces inherit the actual material donors. A full
    # [0,1] chart is a topology parameter, not an anatomical texture island.
    generated=m['source_faces']<0;module_only=np.asarray(d[:,:offset].sum(1)).ravel()<1e-10
    selected=generated&module_only[m['faces']].all(1)
    source_field=d[:,offset:]@original_uv
    # Geometric donors on the completed proximal cylinder all originate at
    # the cut section. They preserve lineage, but collapse a texture dimension.
    # Restore axial extent while preserving the exact retained cut-edge UVs.
    owner=np.load(runtime.parent/'ownership.npz');attachment=np.load(module/'attachment.npz')
    shaft=np.any((owner['frames']>=1)&(owner['frames']<=12)&(owner['weights']>0),axis=1)&module_only
    axial=np.clip((m['points'][:,0]-attachment['root'][0])/(attachment['section_center'][0]-attachment['root'][0]),0,1)
    generated_shaft=shaft&(m['points'][:,0]<attachment['section_center'][0]-1e-7)
    source_field[generated_shaft,1]=.02+(source_field[generated_shaft,1]-.02)*axial[generated_shaft]
    # Original boundary-constrained chart. The optional dedicated neck atlas
    # is authored separately by prepare_neck_material.py with its coupled maps.
    rings=owner['neck_rings'];ids=rings.ravel()
    mapping=np.full(len(m['points']),-1,dtype=int);mapping[ids]=np.arange(len(ids))
    faces=m['faces'];patch=faces[(mapping[faces]>=0).all(1)]
    fixed=np.r_[np.arange(rings.shape[1]),np.arange(len(ids)-rings.shape[1],len(ids))]
    source_field[ids]=boundary_uv_field(m['points'][ids],mapping[patch],fixed,source_field[ids[fixed]])
    module_uv[selected]=source_field[m['faces'][selected]]
    module_uv[~body_faces,:,0]=(module_uv[~body_faces,:,0]+1)*.5
    # Original body face values are unused in the module domain but retain a
    # finite chart for tangent preparation.
    module_uv[body_faces]=body_uv[m['source_faces'][body_faces]]
    all_w=np.zeros((d.shape[1],len(names)));all_w[:offset]=stock_w;all_w[offset:,pelvis]=1
    all_c=np.ones((d.shape[1],4));all_c[:offset]=stock_c
    all_r=np.zeros((d.shape[1],2));all_r[:offset]=stock_r
    bm=Mesh(b['points'],b['faces'],body_uv,bd,b['source_faces'],b['generated']);bm.normal_field=vertex_normals(bm)
    mm=Mesh(m['points'],m['faces'],module_uv,d,m['source_faces'],m['generated'],m['normal_field'])
    prepared=[]
    dtype=np.dtype([('uv','<f4',(2,)),('normal','<f4',(3,)),('tangent','<f4',(3,)),('sign','<f4'),('bones','<u4',(4,)),('weights','<f4',(4,)),('color','<f4',(4,)),('reflection','<f4',(2,))])
    for mesh,w,c,r in [(bm,bd@stock_w,bd@stock_c,bd@stock_r),(mm,d@all_w,d@all_c,d@all_r)]:
        light=corner_frames(mesh);ids=np.argsort(-w,axis=1,kind='stable')[:,:4];ww=np.take_along_axis(w,ids,axis=1);ww/=ww.sum(1)[:,None]
        row=np.empty(mesh.faces.shape,dtype=dtype);row['uv']=mesh.corner_uv;row['normal']=mesh.normal_field[mesh.faces];row['tangent']=light['tangent'];row['sign']=light['sign'];row['bones']=ids[mesh.faces];row['weights']=ww[mesh.faces];row['color']=c[mesh.faces];row['reflection']=r[mesh.faces];prepared.append(row)
    cal=profile['coordinateCalibration'];p=(b['points']-cal['sourceRoot'])@np.array(cal['basis']).T*cal['nativeUnitsPerSourceUnit']+cal['targetRootNative'];fixed=np.zeros(len(p),dtype='u1');native_points=np.zeros_like(p)
    protected=np.unique(np.concatenate(boundary_loops(b['faces'])));_,_,lods=carrier(render);candidates=[]
    for lod in lods:
        if lod['header'][1]:continue
        for row in lod['rows']:
            if struct.unpack_from('<I',row,112)[0]:candidates.append(struct.unpack_from('<3d',row,88))
    distance,nearest=cKDTree(candidates).query(p[protected])
    if distance.max()>.002:raise ValueError('Original external boundary differs from measured native carrier')
    fixed[protected]=1;native_points[protected]=np.array(candidates)[nearest]
    with output.open('wb') as f:
        f.write(b'MMMAT001'+digest(runtime).encode()+digest(dynamic).encode()+digest(native).encode())
        f.write(struct.pack('<3I',len(b['points']),len(b['faces']),len(m['faces'])))
        manifest=read_json(native.parent/'manifest.json');f.write(bytes(int(row['nativeOutwardWinding']) for row in manifest['parts']))
        f.write(fixed.tobytes());f.write(native_points.astype('<f8').tobytes());f.write((b['source_faces']>=len(source_faces[0])).astype('u1').tobytes())
        for row in prepared:f.write(row.tobytes())
    output.with_suffix(output.suffix+'.sha256').write_text(digest(output)+'\n');print(output,digest(output))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['base','body','assembly','module','runtime','dynamic','native','source','render','output']:p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--stock-rig',type=Path)
    a=p.parse_args();prepare(**vars(a))
