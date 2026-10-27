"""Prepare only a measured LOD1 stock waist one-ring repair; never cook/stage.

The native corner-map proof is an explicit input. Old authored rows stay exact,
including newly unreferenced waist rows. Only the 52 incident stock faces are
replaced. New top rows retain frozen upper-body donor/lighting lineage for the
subsequent explicitly reviewed B04 calibration step.
"""
import argparse,collections,itertools,json,shutil,sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from mod import ROOT,digest,read_json,write_json
from wcc_fbx import Document,triangles
from v2_native_binding import read_binding,cooked_resource

def face_key(t):return min(tuple(np.roll(t,k))for k in range(3))

def replace_faces(original,remove,replacement):
    original=np.asarray(original);replacement=np.asarray(replacement);remove=np.asarray(remove,dtype=int)
    if len(remove)!=52 or len(set(remove))!=52 or remove.min()<0 or remove.max()>=len(original):raise ValueError('Exactly52 distinct incident faces required')
    if replacement.shape!=(63,3)or replacement.min()<0:raise ValueError('Exactly63 replacement triangles required')
    keep=np.ones(len(original),bool);keep[remove]=False
    return np.vstack([original[keep],replacement]),keep

def direct_layers(mesh):
    result={}
    for node in mesh.children:
        if not node.name.startswith('LayerElement')or node.name=='LayerElementMaterial':continue
        if node.child('MappingInformationType').values!=['ByVertice']or node.child('ReferenceInformationType').values!=['Direct']:raise ValueError('Unobserved vertex attribute mapping')
        key={'LayerElementNormal':'Normals','LayerElementColor':'Colors','LayerElementUV':'UV','LayerElementReflectionUV':'UV'}.get(node.name)
        if key is None:raise ValueError('Unobserved vertex attribute')
        result[(node.name,int(node.values[0]))]=(node,key)
    return result

def audit_authoring_scope(source,candidate,lineage):
    """Check the saved FBX, including every unrelated property and old row."""
    old,new=Document(source),Document(candidate);a,b=old.meshes[1],new.meshes[1];z=np.load(lineage);remove=z['removedAuthorFaces'];replacement=z['replacementAuthorFaces'];count=len(a.array('Vertices'))//3
    keep=np.ones(len(triangles(a)),bool);keep[remove]=False
    np.testing.assert_array_equal(triangles(b),np.vstack([triangles(a)[keep],replacement]))
    allowed={id(a.child('Vertices').props[0]):'prefix',id(a.child('PolygonVertexIndex').props[0]):'faces'}
    for node,key in direct_layers(a).values():allowed[id(node.child(key).props[0])]='prefix'
    for node in a.children:
        if node.name=='LayerElementMaterial':allowed[id(node.child('Materials').props[0])]='materials'
    for _,node in old.skin(a):
        for key in('Indexes','Weights'):allowed[id(node.child(key).props[0])]='prefix'
    checked=0;changed=[]
    def walk(x,y,path):
        nonlocal checked
        if x.name!=y.name or len(x.props)!=len(y.props)or len(x.children)!=len(y.children):raise ValueError('Unrelated FBX structure changed')
        for i,(p,q)in enumerate(zip(x.props,y.props)):
            if p.tag!=q.tag:raise ValueError('FBX property type changed')
            mode=allowed.get(id(p));checked+=1
            if mode=='prefix':
                if len(q.value)<len(p.value)or not np.array_equal(q.value[:len(p.value)],p.value):raise ValueError('Original vertex/skin attribute prefix changed')
                if len(q.value)!=len(p.value):changed.append(path+f':{i}')
            elif mode=='materials':np.testing.assert_array_equal(q.value,np.r_[p.value[keep],np.zeros(63,p.value.dtype)])
            elif mode=='faces':pass
            elif p.encode()!=q.encode():raise ValueError('Unrelated FBX property changed at '+path+f':{i}')
        for i,(p,q)in enumerate(zip(x.children,y.children)):walk(p,q,path+'/'+p.name+f'[{i}]')
    if len(old.nodes)!=len(new.nodes):raise ValueError('FBX root structure changed')
    for i,(x,y)in enumerate(zip(old.nodes,new.nodes)):walk(x,y,x.name+f'[{i}]')
    return dict(schema='malemod.stock-LOD1-waist-authored-scope/1',passed=True,sourceSHA256=digest(source),candidateSHA256=digest(candidate),lineageSHA256=digest(lineage),checkedProperties=checked,allUnrelatedEncodedPropertiesByteIdentical=True,allOriginalVertexAndSkinArraysPrefixExact=True,allSourceFacesAndAttributesExact=True,allLOD0PropertiesExact=True,only52StockLOD1FacesReplacedBy63=True,changedArrayPaths=changed)

def native_domain(binding,resource):
    _,mesh,raw,sections=cooked_resource(resource)
    section=next(s for s in sections if s['lod']==1 and s['material']==0)
    res=binding['resources'][resource];sl=slice(section['firstVertex'],section['firstVertex']+section['vertexCount'])
    p=res['rows']['baseline'][sl,:12].copy().view('<f4').reshape(-1,3)*np.array(res['scale'],np.float32)+np.array(res['bias'],np.float32)
    uv=np.frombuffer(raw,'<f2',section['vertexCount']*2,section['uvOffset']).reshape(-1,2).astype(float)
    return section,p.astype(float),uv

def match_rows(binding,resource,mesh,global_rows,domains=False):
    section,p,uv=native_domain(binding,resource);auth=mesh.array('Vertices').reshape(-1,3)*.01
    layer=next(n for n in mesh.children if n.name=='LayerElementUV'and n.values==[0]);authuv=layer.array('UV').reshape(-1,2).copy();authuv[:,1]=1-authuv[:,1]
    mats=next(n for n in mesh.children if n.name=='LayerElementMaterial'and n.values==[0]).array('Materials')
    stock=set(np.unique(triangles(mesh)[mats==0]).tolist())
    tree=cKDTree(auth);first=binding['resources'][resource]['firstVertex']+section['firstVertex'];result=[]
    for row in global_rows:
        local=int(row)-first
        if not 0<=local<len(p):raise ValueError('Corner outside actual LOD1 stock section')
        candidates=tree.query_ball_point(p[local],3e-5)
        candidates=[i for i in candidates if i in stock and np.max(abs(authuv[i]-uv[local]))<=.00051]
        if not candidates:raise ValueError('Native stock row has no authored position/UV match')
        error=[np.linalg.norm(auth[i]-p[local])+np.linalg.norm(authuv[i]-uv[local])*1e-4 for i in candidates]
        ordered=[candidates[i]for i in np.argsort(error)]
        result.append(ordered if domains else ordered[0])
    return result if domains else np.asarray(result,dtype=int)

def prepare(output,prototype,corners,corner_proof,source,upper,bindings):
    output=Path(output)
    if output.exists():raise ValueError('Use a fresh owned output directory')
    proof=read_json(corner_proof);binding_path=Path(bindings)/'geralt-source-binding.bin'
    if proof.get('schema')!='malemod.waist-bridge-native-corner-contract/1'or proof.get('sourceBindingSHA256')!=digest(binding_path)or proof.get('prototypeSHA256')!=digest(prototype)or proof.get('facesGlobalRowsSHA256')!=digest(corners)or not proof.get('passed'):raise ValueError('Corner proof is not closed against the selected inputs')
    z=np.load(prototype);corner=np.load(corners)['facesGlobalRows'];pointrows=z['rows'];faces=z['faces']
    if corner.shape!=(63,3)or faces.shape!=(63,3):raise ValueError('Wrong private topology dimensions')
    b=read_binding(binding_path);doc=Document(source);udoc=Document(upper)
    if len(doc.meshes)!=2 or len(udoc.meshes)!=2:raise ValueError('Both original LODs required')
    lower=doc.meshes[1];umesh=udoc.meshes[1];before=triangles(lower);oldpoints=lower.array('Vertices').reshape(-1,3).copy();oldcount=len(oldpoints)
    upper_first=b['resources'][1]['firstVertex'];all_lower=np.unique(corner[corner<upper_first]);all_upper=np.unique(corner[corner>=upper_first])
    if len(all_upper)>34:raise ValueError('Upper duplicate row budget exceeded')
    lower_map=dict(zip(all_lower,match_rows(b,0,lower,all_lower)));upper_map=dict(zip(all_upper,match_rows(b,1,umesh,all_upper)))
    sec,_,_=native_domain(b,0);native_faces=z['originalLowerSectionFaces'][z['removedSectionFaces']]
    rowbase=sec['firstVertex'];native_global=native_faces+b['resources'][0]['firstVertex']+rowbase
    material=next(n for n in lower.children if n.name=='LayerElementMaterial'and n.values==[0]).array('Materials')
    domains=dict(zip(np.unique(native_global),match_rows(b,0,lower,np.unique(native_global),domains=True)))
    authored=collections.defaultdict(list)
    for i,t in enumerate(before):
        if material[i]==0:authored[face_key(t)].append(i)
    remove=[]
    for t in native_global:
        choices=set()
        for candidate in itertools.product(*(domains[int(v)]for v in t[::-1])):choices.update(authored.get(face_key(candidate),[]))
        choices-=set(remove)
        if len(choices)!=1:raise ValueError('Native incident triangle has no unique oriented authored stock face')
        remove.append(choices.pop())
    if len(remove)!=52:raise ValueError('Native incident faces do not match52 authored stock triangles')
    indexmap=dict(lower_map);indexmap.update({int(row):oldcount+i for i,row in enumerate(all_upper)})
    # Actual native indices are CW; FBX author's existing faces are CCW.
    replacement=np.array([[indexmap[int(row)]for row in t[::-1]]for t in corner])
    newfaces,keep=replace_faces(before,remove,replacement)
    lowerlayers=direct_layers(lower);upperlayers=direct_layers(umesh)
    if set(lowerlayers)!=set(upperlayers):raise ValueError('Upper/lower author attribute layout differs')
    copied=np.array([upper_map[int(row)]for row in all_upper])
    lower.set_array('Vertices',np.vstack([oldpoints,umesh.array('Vertices').reshape(-1,3)[copied]]))
    for key,(node,array)in lowerlayers.items():
        cols=3 if array=='Normals'else 4 if array=='Colors'else 2
        original=node.array(array).reshape(oldcount,cols).copy();unode,uarray=upperlayers[key]
        node.set_array(array,np.vstack([original,unode.array(uarray).reshape(-1,cols)[copied]]))
    for node in lower.children:
        if node.name=='LayerElementMaterial':
            values=node.array('Materials');node.set_array('Materials',np.r_[values[keep],np.zeros(63,values.dtype)])
    indices=newfaces.copy();indices[:,2]=-indices[:,2]-1;lower.set_array('PolygonVertexIndex',indices)
    # Existing lower transforms stay byte-exact. Add only existing named-bone weights.
    clusters=dict(doc.skin(lower));up=b['resources'][1];native_rows=up['rows'][all_upper-up['firstVertex']]['baseline']
    rig=read_json(ROOT/'v2/build/geralt-base/player-rig.json')['_chunks']['CSkeleton #0']['_vars'];names=[x['_vars']['name']['_value']for x in rig['bones']['_elements']]
    append=collections.defaultdict(list)
    for i,row in enumerate(native_rows):
        for local,weight in zip(row[12:16],row[16:20]):
            if weight:append[names[up['palette'][int(local)][0]]].append((oldcount+i,int(weight)/255.))
    for name,items in append.items():
        if name not in clusters:raise ValueError('New upper bone absent from lower author palette')
        cluster=clusters[name];cluster.set_array('Indexes',np.r_[cluster.array('Indexes'),np.array([i for i,w in items],np.int32)]);cluster.set_array('Weights',np.r_[cluster.array('Weights'),[w for i,w in items]])
    # Verify every old attribute prefix and every untouched polygon before saving.
    np.testing.assert_array_equal(lower.array('Vertices').reshape(-1,3)[:oldcount],oldpoints)
    np.testing.assert_array_equal(triangles(lower)[:keep.sum()],before[keep])
    output.mkdir(parents=True);fbx=output/'geralt-waist-join.fbx';doc.save(fbx);xml=Path(source).with_suffix('.xml');shutil.copyfile(xml,fbx.with_suffix('.xml'))
    np.savez(output/'upper-row-lineage.npz',newAuthorRows=np.arange(oldcount,oldcount+len(all_upper)),upperGlobalRows=all_upper,upperAuthorRows=copied,upperBaseline=native_rows,donors=up['rows'][all_upper-up['firstVertex']]['donors'],weights=up['rows'][all_upper-up['firstVertex']]['weights'],upperScale=np.array(up['scale']),upperBias=np.array(up['bias']),removedAuthorFaces=np.array(remove),replacementAuthorFaces=replacement)
    result=dict(schema='malemod.local-stock-LOD1-waist-authoring/1',outputFBX=str(fbx),outputFBXSHA256=digest(fbx),outputXMLSHA256=digest(fbx.with_suffix('.xml')),sourceFBX=str(source),sourceSHA256=digest(source),upperFBX=str(upper),upperSHA256=digest(upper),bindingSHA256=digest(binding_path),cornerProofSHA256=digest(corner_proof),prototypeSHA256=digest(prototype),upperLineageSHA256=digest(output/'upper-row-lineage.npz'),oldVertices=oldcount,newUpperRows=len(all_upper),oldFaces=len(before),removedFaces=len(remove),newFaces=len(newfaces),replacementFaces=63,unchangedLOD0=True,originalVertexAttributesRetained=True,unchangedFacesOutside52=True,LOD1StockMaterialOnly=True,requiresPostCookUpperDonorAndPackedLightingCalibration=True,notCooked=True,notAdopted=True)
    write_json(output/'waist-join.json',result);return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--prototype',type=Path,required=True);p.add_argument('--corners',type=Path,required=True);p.add_argument('--corner-proof',type=Path,required=True);p.add_argument('--source',type=Path,default=ROOT/'v2/build/materials/physical-skin-field-01/geralt-physical-skin.fbx');p.add_argument('--upper',type=Path,default=ROOT/'v2/build/geralt-base/torso.fbx');p.add_argument('--bindings',type=Path,default=ROOT/'v2/build/runtime-binding');a=p.parse_args();print(json.dumps(prepare(a.output,a.prototype,a.corners,a.corner_proof,a.source,a.upper,a.bindings),indent=2))
if __name__=='__main__':main()
