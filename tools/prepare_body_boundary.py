"""Author Geralt's separate lower/upper resources around one measured waist.

Offline only. Original rigs, part boundaries and anatomical graft lineage are
retained; the shared Base refines the four actual waist loops together.
"""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
from scipy.sparse import csr_matrix
from mod import ROOT,settings,read_json,write_json,digest
from wcc_fbx import Document,triangles


def prepare(output):
    cfg=settings();sys.path.insert(0,str(cfg['base']))
    from malemod_base.graft import topology_ids,boundary_loops,smooth_normals,limit_influences
    from malemod_base.part_boundary import weld_parts
    from malemod_base.material_atlas import atlas_uv
    from malemod_base.refinement import refine
    output=Path(output).absolute()
    if not output.is_relative_to(ROOT/'build') or output.exists():raise ValueError('Use a fresh owned build directory')
    bank=read_json(ROOT/'build/overall/overall-stable-layout/overall.json')
    paths=[ROOT/bank['cage']/'geralt-motion.fbx',ROOT/'build/inspection/candidates/t_01_mg__body_hires.fbx']
    documents=[Document(p) for p in paths]
    records=[(d,m) for d in documents for m in d.meshes]
    meshes=[(m.array('Vertices').reshape(-1,3),triangles(m)) for d,m in records]
    loops=[]
    for p,f in meshes:
        keep,alias=topology_ids(p,1e-5);candidates=boundary_loops(alias[f])
        loop=min(candidates,key=lambda l:abs(p[keep[l],2].mean()-107))
        if not 104 < p[keep[loop],2].mean() < 110:raise ValueError('Actual waist not found')
        loops.append(loop)
    # The prior union retained 0.0012-FBX-unit edges, below the measured cooked
    # quantization cell. Avoid unsupported sub-cell topology on native import;
    # this refinement is not evidence about the reported rear lighting patch.
    # Cluster only cross-part near-identical knots; retain original edge donors.
    weld=weld_parts(meshes,loops,np.array([[1,0,0],[0,1,0]]),np.array([0,-1,107]),12,1.25,knot_tolerance=.001)
    # Fields are aligned by observed joint names, not palette ordinals, which
    # differ between the upper and lower exports.
    names=list(dict.fromkeys(n for d,m in records for n,c in d.skin(m)))
    weights=[]
    for (d,m),(p,f) in zip(records,meshes):
        w=np.zeros((len(p),len(names)))
        for name,c in d.skin(m):w[c.array('Indexes'),names.index(name)]=c.array('Weights')
        weights.append(w)
    canonical=weld.parts[0].field(weights[0])[weld.parts[0].seam]
    canonical,discard=limit_influences(canonical,4,.3)
    # Resolve the expanding circular support with actual surface triangles.
    # Keep every original part/attachment edge: refinement changes interiors,
    # retaining their sparse UV/color/skin lineage and positional aliases.
    for part_id,part in enumerate(weld.parts):
        old_module=0
        if part_id<2:
            original_binding=np.load(ROOT/bank['fit'].rsplit('/',1)[0]/('geralt-anatomy-lod%d.bindings.npz'%(part_id%2)))
            old_module=int(original_binding['module_lineage_shape'][0])
        old_body=len(meshes[part_id][0])-old_module
        for iteration in range(3):
            keep,ids=topology_ids(part.points,1e-5)
            boundary=boundary_loops(ids[part.faces]);locked_keys={tuple(sorted((int(a),int(b)))) for loop in boundary for a,b in zip(loop,np.roll(loop,-1))}
            edges={tuple(sorted((int(a),int(b)))) for tri in part.faces for a,b in [(tri[0],tri[1]),(tri[1],tri[2]),(tri[2],tri[0])]}
            locked=[e for e in edges if tuple(sorted((int(ids[e[0]]),int(ids[e[1]])))) in locked_keys or (old_module and any(old_body<=v<len(meshes[part_id][0]) for v in e))]
            tri=part.points[part.faces];center=tri.mean(1)
            longest=np.max(np.linalg.norm(tri-np.roll(tri,1,axis=1),axis=2),axis=1)
            selected=(center[:,1]>1)&(center[:,2]>75)&(center[:,2]<128)&(np.hypot(center[:,0],center[:,2]-97.5)<32)&(longest>2.0)
            if old_module:selected &= ~np.any((part.faces>=old_body)&(part.faces<len(meshes[part_id][0])),axis=1)
            if not selected.any():break
            p,f,transfer,parents=refine(part.points,part.faces,selected,locked,ids)
            part.points=p;part.faces=f;part.lineage=transfer@part.lineage;part.face_lineage=part.face_lineage[parents]
            _,part.aliases=topology_ids(p,1e-5)
    output.mkdir(parents=True);rows=[]
    source=np.load(cfg['base']/'assets/wolverine-reference/geometry.npz')
    for part_id,((d,m),part,(original,faces)) in enumerate(zip(records,weld.parts,meshes)):
        lod=part_id%2;lower=part_id<2
        old_binding=np.load(ROOT/bank['fit'].rsplit('/',1)[0]/('geralt-anatomy-lod%d.bindings.npz'%lod)) if lower else None
        module=int(old_binding['module_lineage_shape'][0]) if lower else 0
        original_body=len(original)-module
        # Refined body vertices precede the unchanged anatomical module.
        order=np.r_[np.arange(original_body),np.arange(len(original),len(part.points)),np.arange(original_body,len(original))] if lower else np.arange(len(part.points))
        inverse=np.argsort(order);points=part.points[order];new_faces=inverse[part.faces]
        if lower:
            # Waist harmonic fitting must not perturb the anatomy's original
            # straight-edge attachment constraints. Re-publish their exact
            # donor interpolation to both halves and all positional UV aliases.
            aliases=part.aliases[order]
            for slave,other,(a,b,t) in zip(old_binding['body_seam'],old_binding['module_seam'],old_binding['body_edge_donors']):
                value=points[inverse[int(a)]]*(1-t)+points[inverse[int(b)]]*t
                points[(aliases==aliases[inverse[slave]])|(aliases==aliases[inverse[other]])]=value
        body=len(points)-module;lineage=part.lineage[order]
        w=part.bind_field(weights[part_id],canonical)[order]
        w,discard=limit_influences(w,4,.3)
        for name,c in d.skin(m):
            values=w[:,names.index(name)];ids=np.flatnonzero(values>0)
            c.set_array('Indexes',ids);c.set_array('Weights',values[ids])
        normals=smooth_normals(points,new_faces)
        for layer in m.children:
            if not layer.name.startswith('LayerElement'):continue
            if layer.name=='LayerElementMaterial':layer.set_array('Materials',np.zeros(len(new_faces),dtype=np.int32));continue
            if layer.child('MappingInformationType').values!=['ByVertice'] or layer.child('ReferenceInformationType').values!=['Direct']:raise ValueError('Unsupported actual attribute mapping')
            channel,width={'LayerElementNormal':('Normals',3),'LayerElementColor':('Colors',4),'LayerElementUV':('UV',2),'LayerElementReflectionUV':('UV',2)}[layer.name]
            value=lineage@layer.array(channel).reshape(-1,width)
            if channel=='Normals':value=normals
            elif layer.name=='LayerElementUV' and layer.values[0]==0:
                value=atlas_uv(value,0)
                if lower:
                    ml=csr_matrix((old_binding['module_lineage_data'],old_binding['module_lineage_indices'],old_binding['module_lineage_indptr']),shape=tuple(old_binding['module_lineage_shape']))
                    module_uv=ml@old_binding['original_module_uv']
                    # Wolverine's source UV is already Direct3D top-origin.
                    # WCC flips FBX V at import: undo it before native cooking
                    # so the sampled source texture coordinates remain exact.
                    module_uv[:,1]=1-module_uv[:,1]
                    value[body:]=atlas_uv(module_uv,1)
            layer.set_array(channel,value)
        m.set_array('Vertices',points);indices=new_faces.copy();indices[:,2]=-indices[:,2]-1;m.set_array('PolygonVertexIndex',indices)
        arrays=dict(points=points,faces=new_faces,bodyCount=np.array(body),waist=inverse[part.seam],protected=inverse[part.protected],weights=w,boneNames=np.array(names),lineage_data=lineage.data,lineage_indices=lineage.indices,lineage_indptr=lineage.indptr,lineage_shape=lineage.shape)
        if lower:
            for key in ['body_seam','module_seam']:arrays[key]=inverse[old_binding[key]]
            arrays['body_edge_donors']=old_binding['body_edge_donors']
            for key in ['module_lineage_data','module_lineage_indices','module_lineage_indptr','module_lineage_shape']:arrays[key]=old_binding[key]
        np.savez_compressed(output/('part%d.npz'%part_id),**arrays)
        rows.append(dict(part=part_id,lod=lod,resource='lower' if lower else 'upper',vertices=len(points),bodyVertices=body,orientation=json.loads(json.dumps(part.orientation,default=lambda v:v.item()))))
    # Common shading at the measured weld; UV tangent islands remain separate.
    normal=smooth_normals(weld.parts[0].points,weld.parts[0].faces)[weld.parts[0].seam]
    for part_id,((d,m),part) in enumerate(zip(records,weld.parts)):
        a=np.load(output/('part%d.npz'%part_id));v=m.child('LayerElementNormal').array('Normals').reshape(-1,3).copy();keep,aliases=topology_ids(a['points'],1e-5)
        for j,k in enumerate(a['waist']):v[aliases==aliases[k]]=normal[j]
        m.child('LayerElementNormal').set_array('Normals',v)
    # Native materials are supplied explicitly in adjacent import XML; stale
    # embedded stock artwork is omitted, not copied into source control.
    for d,path,label in zip(documents,paths,['lower','upper']):
        for obj in d.objects:
            if obj.name=='Video':
                obj.children=[c for c in obj.children if c.name!='Content']
        target=output/(label+'.fbx');d.save(target)
        target.with_suffix('.xml').write_text('''<?xml version="1.0" encoding="UTF-8"?>
<mesh><mesh_data autohideDistance="100.00" isTwoSided="false" useExtraStreams="true" mergeInGlobalShadowMesh="true" entityProxy="false"><LODs><LOD_info distance="0.00"/><LOD_info distance="6.00"/></LODs></mesh_data><materials><material name="Material0" local="true" base="characters\\models\\common\\materials\\skin_body\\skin_body__mg_01.w2mi"><param name="Diffuse" type="handle:ITexture" value="characters\\malemod\\materials\\body_diffuse.xbm"/><param name="Normal" type="handle:ITexture" value="characters\\malemod\\materials\\body_normal.xbm"/><param name="Ambient" type="handle:ITexture" value="characters\\malemod\\materials\\body_ambient.xbm"/></material></materials></mesh>''')
    np.savez_compressed(output/'waist.npz',points=weld.canonical,weights=canonical,names=np.array(names),normal=normal)
    write_json(output/'manifest.json',dict(sourcePaths=[str(p) for p in paths],sourceHashes=[digest(p) for p in paths],knots=len(weld.canonical),recipeSHA256=digest(Path(__file__)),parts=rows,nativeRoundTrip=False,observedGameplay=False))
    print('Authored common waist:',output,len(weld.canonical),'samples')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);prepare(p.parse_args().output)
