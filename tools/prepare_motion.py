"""Author an isolated native motion cage from the verified rest attachment.

Never installs. New mm_* joints are authored joints, not observed game bones.
All stock body influences, seam donors and source binding artifacts are retained.
"""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import numpy as np
from scipy.sparse import csr_matrix
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
from mod import ROOT, settings, base_checkout, digest, write_json
from wcc_fbx import Document, Node, Property
from native_joint_frames import orient_chain,verify_rest_axes


def scalar(kind, value):
    # WolvenKit CFloat.SetValue accepts float/double, not integer JSON tokens.
    # An integer token silently drops the property and leaves native defaults.
    return {'_type': kind, '_value': float(value) if kind == 'Float' else value}
def array(kind, elements): return {'_type': kind, '_elements': elements}
def reference(kind, key): return {'_type': kind, '_vars': {'_reference': scalar('string', key)}}
def handle(kind, key):
    result = reference('handle:'+kind, key)
    result['_vars']['_chunkHandle'] = scalar('bool', True)
    return result
def vector(kind, values):
    return {'_type': kind, '_vars': {c: scalar('Float', float(x)) for c, x in zip('XYZW', values)}}
def matrix(value):
    return {'_type': 'Matrix', '_vars': {c: vector('Vector', row) for c, row in zip('XYZW', value.T)}}
def rigdata(value):
    return {'_type':'SSkeletonRigData', '_vars': {
        'Position': vector('SVector4D', [*value[:3,3], 1]),
        'Rotation': vector('SVector4D', Rotation.from_matrix(value[:3,:3]).as_quat()),
        'Scale': vector('SVector4D', [1,1,1,1])}}


def rig_world(rig):
    names = [x['_vars']['name']['_value'] for x in rig['bones']['_elements']]
    parents = [x['_value'] for x in rig['parentIndices']['_elements']]
    worlds = []
    for i, data in enumerate(rig['rigdata']['_elements']):
        fields = data['_vars']
        read = lambda field, axes: [fields[field]['_vars'][c]['_value'] for c in axes]
        m = np.eye(4)
        m[:3,:3] = Rotation.from_quat(read('Rotation','XYZW')).as_matrix()
        m[:3,3] = read('Position','XYZ')
        if parents[i] >= i: raise ValueError('Native rig not parent-first')
        worlds.append(worlds[parents[i]] @ m if parents[i] >= 0 else m)
    return names, parents, worlds


def p(tag, value): return Property(tag, value)
def n(name, *props, children=None): return Node(name, list(props), children or [], bool(children))
def property70(name, kind, values):
    return n('P', p('S',name), p('S',kind), p('S',''), p('S','A'), *[p('D',float(v)) for v in values])


def add_bones(document, mesh, names, worlds, parents, weights):
    objects = {x.values[0]:x for x in document.objects}
    links = document.root('Connections').children
    skin_id = next(x.values[1] for x in links if x.values[0]=='OO' and x.values[2]==mesh.values[0]
                   and objects[x.values[1]].name=='Deformer')
    clusters = document.skin(mesh)
    pelvis_cluster = next(c for name,c in clusters if name=='pelvis')
    pelvis_id = next(x.values[1] for x in links if x.values[0]=='OO' and x.values[2]==pelvis_cluster.values[0])
    stock_world = pelvis_cluster.array('TransformLink').reshape(4,4).T
    new_ids = []
    next_id = max(objects)+100
    for j, name in enumerate(names):
        model_id, cluster_id, attribute_id = next_id, next_id+1, next_id+2
        next_id += 3; new_ids.append(model_id)
        parent_world = stock_world if parents[j] < 0 else worlds[parents[j]]
        local = np.linalg.inv(parent_world) @ worlds[j]
        model = n('Model', p('L',model_id), p('S',name+'\x00\x01Model'), p('S','LimbNode'), children=[
            n('Version',p('I',232)), n('Properties70',children=[
                property70('Lcl Translation','Lcl Translation',local[:3,3]),
                property70('Lcl Rotation','Lcl Rotation',Rotation.from_matrix(local[:3,:3]).as_euler('xyz',degrees=True)),
                property70('Lcl Scaling','Lcl Scaling',[1,1,1])]),
            n('Shading',p('C',True)),n('Culling',p('S','CullingOff'))])
        attribute = n('NodeAttribute',p('L',attribute_id),p('S',name+'\x00\x01NodeAttribute'),p('S','LimbNode'),
                      children=[n('TypeFlags',p('S','Skeleton'))])
        cluster = copy.deepcopy(pelvis_cluster)
        cluster.props = [p('L',cluster_id),p('S',name+'\x00\x01SubDeformer'),p('S','Cluster')]
        ids = np.flatnonzero(weights[:,j] > 0)
        cluster.set_array('Indexes',ids);cluster.set_array('Weights',weights[ids,j])
        cluster.set_array('TransformLink',worlds[j].T)
        # WCC's export stores the inverse bone bind here (identity mesh frame).
        cluster.set_array('Transform',np.linalg.inv(worlds[j]).T)
        document.objects.extend([model,attribute,cluster])
        for child,parent in [(model_id,pelvis_id if parents[j]<0 else new_ids[parents[j]]),
                             (attribute_id,model_id),(model_id,cluster_id),(cluster_id,skin_id)]:
            links.append(n('C',p('S','OO'),p('L',child),p('L',parent)))
        for pose in [x for x in document.objects if x.name=='Pose']:
            # Only extend the bind pose containing this LOD's pelvis.
            if any(x.name=='PoseNode' and x.child('Node').values==[pelvis_id] for x in pose.children):
                pose.children.append(n('PoseNode',children=[n('Node',p('L',model_id)),
                     n('Matrix',p('d',worlds[j].T.reshape(-1)))]))
                count=pose.child('NbPoseNodes').props[0];count.value+=1;count.raw=None
    # FBX object definitions are advisory, but keep the counts consistent.
    definitions=document.root('Definitions')
    for entry in definitions.children:
        if entry.name=='ObjectType' and entry.values[0] in ['Model','NodeAttribute','Deformer']:
            count=entry.child('Count').props[0];count.value+=len(names);count.raw=None
    count=definitions.child('Count').props[0];count.value+=3*len(names);count.raw=None


def prepare():
    cfg=settings();pin=base_checkout(cfg);sys.path.insert(0,str(cfg['base']))
    from malemod_base.motion_binding import reference_fields,reference_cage_centres,reference_cage_weights,sample_mechanical_guide
    from malemod_base.graft import topology_ids,limit_influences
    rest=json.loads((ROOT/'generated/attachment.json').read_text())
    fitpath=ROOT/rest['fitReport'];fit=json.loads(fitpath.read_text());fbx=fitpath.with_suffix('.fbx')
    # fit report uses .fit.json; source has the same stem without .fit.
    fbx=fitpath.with_name(fitpath.name.replace('.fit.json','.fbx'))
    if digest(fbx)!=fit['outputSHA256']:raise ValueError('Rest FBX changed')
    job=ROOT/'build/motion'/('cage-'+uuid.uuid4().hex[:12]);job.mkdir(parents=True)
    converter=ROOT/'build/research/wkit-current/MaleModCR2W.exe'
    rig_source=cfg['redkit']/'r4data/characters/base_entities/man_base/man_base.w2rig'
    rig_json=job/'native-rig.json'
    subprocess.run([str(converter),'export',str(rig_source),str(rig_json)],check=True,capture_output=True)
    rig=json.loads(rig_json.read_text())['_chunks']['CSkeleton #0']['_vars']
    stock_names,stock_parents,stock_world=rig_world(rig)
    document=Document(fbx)
    # Calibrate from every stock skin bone; reject changes in frame or scale.
    position_error=rotation_error=0.
    for name,cluster in document.skin(document.meshes[0]):
        native=stock_world[stock_names.index(name)];exported=cluster.array('TransformLink').reshape(4,4).T
        position_error=max(position_error,float(np.max(abs(exported[:3,3]-100*native[:3,3]))))
        rotation_error=max(rotation_error,float(np.max(abs(exported[:3,:3]-native[:3,:3]))))
    # Observed r_foot bind differs by 1.407e-4 in rotation coefficients between
    # the stock body mesh and man_base rig; retain each source's actual data.
    if position_error>1e-3 or rotation_error>2e-4:raise ValueError('Native rig calibration failed')
    bank=np.load(cfg['base']/'assets/wolverine-reference/geometry.npz');fields=reference_fields(bank)
    names=['mm_shaft_%02d'%i for i in range(8)]+['mm_scrotum_l','mm_scrotum_r']
    parents=[-1]+list(range(7))+[-1,-1]
    worlds=None;lods=[]
    for lod,mesh in enumerate(document.meshes):
        binding=fitpath.parent/fit['lods'][lod]['bindings'];b=np.load(binding)
        lineage=csr_matrix((b['module_lineage_data'],b['module_lineage_indices'],b['module_lineage_indptr']),
                           shape=tuple(b['module_lineage_shape']))
        mf=np.clip(lineage@fields,0,1)
        body_count=len(b['points'])-lineage.shape[0]
        points=b['points'];module=points[body_count:]
        if worlds is None:
            centres=reference_cage_centres(module,mf,points[b['body_seam']].mean(0),module[:,0],1.)
            if fit.get('sourceMechanics'):
                mechanical=fit['sourceMechanics'];guide=np.asarray(mechanical['shaftGuide'])
                sampled,_=sample_mechanical_guide(guide,np.linspace(0,1,8))
                centres=np.vstack([sampled,mechanical['lobeCenters']])
                profile=json.loads((ROOT/'characters/geralt-attachment.json').read_text())
                centres=(centres-np.asarray(fit['sourceRoot']))@np.asarray(profile['basis']).T*fit['sourceToFBXScale']+profile['targetRoot']
            worlds=np.tile(np.eye(4),(len(names),1,1));worlds[:,:3,3]=centres
            worlds=orient_chain(worlds)
            if fit.get('sourceMechanics'):
                for side in range(2):worlds[8+side,:3,:3]=np.asarray(profile['basis'])@np.asarray(mechanical['lobeAxes'][side]).T
        distance=cKDTree(points[b['body_seam']]).query(module)[0]
        # Authored Geralt envelope in observed FBX units: 2-unit lateral blend,
        # 5-unit seam transition. The anatomy binding law itself lives in Base.
        lateral=module[:,0]
        if fit.get('sourceMechanics'):
            # Source Y maps to native -X in this measured character basis.
            # Mechanical lobe order must match the corresponding skin donors.
            lateral=-(module[:,0]-profile['targetRoot'][0])
        dynamic=reference_cage_weights(mf,lateral,2.,distance,5.)
        _,aliases=topology_ids(points)
        fixed=np.isin(aliases,aliases[b['body_seam']])
        dynamic[fixed[body_count:]]=0
        new_weights=np.zeros((len(points),len(names)));new_weights[body_count:]=dynamic
        original=b['weights'];amount=new_weights.sum(1)
        full=np.column_stack([original*(1-amount[:,None]),new_weights*original.sum(1)[:,None]])
        full,discard=limit_influences(full,4,.3)
        np.testing.assert_allclose(full[b['body_seam']],full[b['module_seam']],atol=1e-12)
        np.testing.assert_array_equal(full[:body_count,:original.shape[1]],original[:body_count])
        for i,(_,cluster) in enumerate(document.skin(mesh)):
            ids=np.flatnonzero(full[:,i]>0);cluster.set_array('Indexes',ids);cluster.set_array('Weights',full[ids,i])
        add_bones(document,mesh,names,worlds,parents,full[:,original.shape[1]:])
        np.savez_compressed(job/('motion-lod%d.npz'%lod),weights=full,points=points,faces=b['faces'],
                            body_seam=b['body_seam'],module_seam=b['module_seam'],fields=mf)
        lods.append({'lod':lod,'sourceBindingSHA256':digest(binding),'maximumDiscardedWeight':float(discard.max()),
                     'originalBones':fit['lods'][lod]['bones'],'newBones':names})
    output=job/'geralt-motion.fbx';document.save(output);shutil.copy2(fbx.with_suffix('.xml'),output.with_suffix('.xml'))
    # Author the dynamic skeleton using measured native units. Preserve every
    # observed stock joint; new joints have explicit authored world rest frames.
    native_world=worlds.copy();native_world[:,:3,3]/=100
    skeleton={k:copy.deepcopy(rig[k]) for k in ['bones','parentIndices','rigdata']}
    local_new=[]
    for i,name in enumerate(names):
        parent=stock_names.index('pelvis') if parents[i]<0 else len(stock_names)+parents[i]
        pw=stock_world[parent] if parent<len(stock_names) else native_world[parents[i]]
        local=np.linalg.inv(pw)@native_world[i];local_new.append(local)
        skeleton['bones']['_elements'].append({'_type':'SSkeletonBone','_vars':{'name':scalar('StringAnsi',name),'nameAsCName':scalar('CName',name)}})
        skeleton['parentIndices']['_elements'].append(scalar('Int16',parent))
        skeleton['rigdata']['_elements'].append(rigdata(local))
    dyng_source=cfg['redkit']/'r4data/characters/models/geralt/armor/armor_shirt/dyng_pendant_01_mg__shirt.w3dyng'
    dyng_template=job/'stock-dyng.json'
    subprocess.run([str(converter),'export',str(dyng_source),str(dyng_template)],check=True,capture_output=True)
    source=json.loads(dyng_template.read_text())
    dyng=source['_chunks']['CDyngResource #0']['_vars']
    source['_chunks']['CSkeleton #1']['_vars']=skeleton
    for key in ['importFile','importFileTimeStamp']:dyng.pop(key,None)
    all_names=stock_names+names
    parent_names=[stock_names[i] if i>=0 else '' for i in stock_parents]+[
        'pelvis' if i<0 else names[i] for i in parents]
    local_stock=[]
    for i,w in enumerate(stock_world):local_stock.append(np.linalg.inv(stock_world[stock_parents[i]])@w if stock_parents[i]>=0 else w)
    values={'nodeNames':('String',all_names),'nodeParents':('String',parent_names),
            'nodeMasses':('Float',[1.]*len(all_names)),
            'nodeStifnesses':('Float',[0.]*len(stock_names)+[0.,.8,.7,.6,.5,.4,.3,.3,.2,.2]),
            'nodeDistances':('Float',[0.]*len(stock_names)+[0.,.01,.025,.04,.06,.08,.10,.12,.04,.04])}
    for key,(kind,items) in values.items():dyng[key]=array('array:2,0,'+kind,[scalar(kind,x) for x in items])
    dyng['nodeTransforms']=array('array:2,0,Matrix',[matrix(m) for m in local_stock+local_new])
    pairs=[(len(stock_names)+i-1,len(stock_names)+i) for i in range(1,8)]
    for key,kind,items in [('linkAs','Int32',[a for a,b in pairs]),('linkBs','Int32',[b for a,b in pairs]),
                         ('linkTypes','Int32',[0]*len(pairs)),('linkLengths','Float',[
                             float(np.linalg.norm(native_world[i,:3,3]-native_world[i-1,:3,3])) for i in range(1,8)])]:
        # Retain the native array element type rather than inferring integer width.
        native_kind=dyng[key]['_elements'][0]['_type']
        dyng[key]['_elements']=[scalar(native_kind,x) for x in items]
    for key in list(dyng):
        if key.startswith('collision'):dyng[key]['_elements']=[]
    from native_motion_profile import apply_profile
    native_profile=apply_profile(source,names,native_world)
    dyng_json=job/'motion-dyng.json';write_json(dyng_json,source)
    dyng_out=job/'characters/malemod/physics/geralt_motion.w3dyng';dyng_out.parent.mkdir(parents=True)
    subprocess.run([str(converter),'import',str(dyng_json),str(dyng_out)],check=True,capture_output=True)
    report={'baseCommit':pin['commit'],'nativeRigSHA256':digest(rig_source),'sourceFBXSHA256':digest(fbx),
            'nativeToFBXTranslationScale':100,'maximumBindPositionError':position_error,
            'maximumBindRotationError':rotation_error,'lods':lods,'newBones':names,
            'authoredWorldRestFBX':worlds.tolist(),'nativeRestAxes':verify_rest_axes(worlds),'nativeProfile':native_profile,'nativeVerified':False,'observedGameplay':False,
            'limitations':['native secondary-motion approximation; no XPBD parity','body contacts not calibrated',
                           'live rest shape bridge pending'],'fbx':str(output),'dyng':str(dyng_out)}
    report.update(fitReport=fitpath.relative_to(ROOT).as_posix(),fitSHA256=digest(fitpath),sourceMechanics=fit.get('sourceMechanics'))
    write_json(job/'motion.json',report);print(job);return job


if __name__=='__main__':prepare()
