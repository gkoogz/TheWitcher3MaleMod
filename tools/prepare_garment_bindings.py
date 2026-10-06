"""Bind shared garments to measured Geralt surfaces; no skeleton inference."""
import argparse,heapq,json,struct,sys
from pathlib import Path
import numpy as np
from mod import ROOT,read_json,write_json,digest,settings

def prepare(job,render,output):
    job,render,output=map(lambda p:Path(p).absolute(),(job,render,output))
    if not all(p.is_relative_to(ROOT/'build') for p in (job,render,output)) or output.exists():
        raise ValueError('Use fresh owned output and owned input artifacts')
    part=np.load(job/'part0.npz');native=np.load(render/'inspection-lower/lod0.npz')
    points=part['points']/100;body=int(part['bodyCount']);ids=native['nearestAuthored']
    representatives={}
    for i,k in enumerate(ids):representatives.setdefault(int(k),i)
    from scipy.spatial import cKDTree
    known=np.array(list(representatives));distance,nearest=cKDTree(points[known]).query(points)
    for k in np.flatnonzero(distance<1e-7):representatives.setdefault(int(k),representatives[int(known[nearest[k]])])
    def measured(seq):
        missing=[int(k) for k in seq if int(k) not in representatives]
        if missing:raise ValueError('Measured donor missing in cooked topology: '+str(missing[:8]))
        return [representatives[int(k)] for k in seq]
    frame=read_json(ROOT/'characters/geralt-runtime-bindings.json')['coordinateCalibration']
    origin=np.array(frame['targetRootNative']);waist=part['waist'].copy();opening=part['body_seam'].copy()
    # Geralt's exported local axes are +X lateral,+Y anterior,+Z superior.
    # These are the observed mesh calibration, independent of the shaft pitch.
    waist=waist[np.argsort(np.arctan2(points[waist,1]-points[waist,1].mean(),points[waist,0]))]
    opening=opening[np.argsort(np.arctan2(points[opening,2]-origin[2],points[opening,0]-origin[0]))]
    # Actual body-edge routes begin at the side hip, descend behind it, cup
    # the under-glute crease and return through the inside thigh to the pouch.
    faces=part['faces'];edges=set()
    for a,b,c in faces:
        for x,y in ((a,b),(b,c),(c,a)):
            if x<body and y<body:edges.add(tuple(sorted((int(x),int(y)))))
    _,alias=np.unique(np.round(points[:body]/1e-7).astype(np.int64),axis=0,return_inverse=True)
    adjacency=[[] for _ in range(body)]
    groups={}
    for i,k in enumerate(alias):groups.setdefault(int(k),[]).append(i)
    for group in groups.values():
        for i in group[1:]:adjacency[group[0]].append((i,0.));adjacency[i].append((group[0],0.))
    for a,b in edges:
        d=float(np.linalg.norm(points[a]-points[b]));adjacency[a].append((b,d));adjacency[b].append((a,d))
    def path(a,b,side,posterior=False,front_limit=-.045):
        costs={a:0.};previous={};queue=[(0.,a)]
        while queue:
            cost,k=heapq.heappop(queue)
            if cost!=costs[k]:continue
            if k==b:break
            for n,d in adjacency[k]:
                penalty=1+max(0.,-side*points[n,0])*40
                # Keep the descending half behind the hip. The return half
                # must reach the anterior pouch through the medial crotch.
                if posterior:penalty+=max(0.,points[n,1]-front_limit)*80
                else:penalty+=max(0.,abs(points[n,0])-.115)*60
                nc=cost+d*penalty
                if nc<costs.get(n,float('inf')):costs[n]=nc;previous[n]=k;heapq.heappush(queue,(nc,n))
        if b not in costs:raise ValueError('Disconnected measured strap surface')
        route=[b]
        while route[-1]!=a:route.append(previous[route[-1]])
        return route[::-1]
    cfg=settings();sys.path.insert(0,str(cfg['base']))
    from malemod_base.garment_routes import classic_route_targets,CLASSIC_ROUTE_VERSION
    straps=[];waypoints=[];route_metrics=[]
    for side in (-1,1):
        candidates=waist[points[waist,0]*side>.75*np.max(points[waist,0]*side)]
        # These target coordinates are calibrated to this measured Geralt
        # export, not inferred joint names. The previous lowest-Z search
        # selected the posterior thigh at .740m and made a visible garter.
        # The lateral hip midpoint is measured at authored 18/99, roughly
        # 66.5mm forward of the old posterior attachment. Start on the side,
        # then guide the elastic around the glute rather than down the thigh.
        targets,steering=classic_route_targets(points[candidates],[side*.164105,-.018537,1.087141],[side*.085,-.122,.870],[side*.02772,-.09969,.87283],[0,1,0],[0,0,1])
        start=int(candidates[np.argmin(np.linalg.norm(points[candidates]-targets[0],axis=1))])
        hip_target=np.array([side*.126055,-.112,.97438])
        hip=int(np.argmin(np.linalg.norm(points[:body]-hip_target,axis=1)))
        glutes=np.flatnonzero((points[:body,0]*side>.07)&(points[:body,0]*side<.11)&(points[:body,1]<-.10)&(points[:body,2]>.83)&(points[:body,2]<.89))
        if not len(glutes):raise ValueError('No measured under-glute donor')
        mid=int(glutes[np.argmin(np.linalg.norm(points[glutes]-targets[1],axis=1))])
        ends=opening[points[opening,0]*side>0]
        end=int(ends[np.argmin(points[ends,2])])
        medial=int(np.argmin(np.linalg.norm(points[:body]-targets[2],axis=1)))
        inner_target=np.array([side*.010195,-.026715,.87003])
        inner=int(np.argmin(np.linalg.norm(points[:body]-inner_target,axis=1)))
        lateral=path(start,hip,side,True,points[start,1])
        posterior=path(hip,mid,side,True)
        return_parts=[path(mid,medial,side),path(medial,inner,side),path(inner,end,side)]
        returning=return_parts[0]+return_parts[1][1:]+return_parts[2][1:]
        descending=lateral+posterior[1:]
        route=descending+returning[1:]
        if np.max(points[descending,1])>points[start,1]+1e-7 or np.max(points[posterior,1])>-.045 or np.max(np.abs(points[returning,0]))>.115:
            raise ValueError('Measured strap route left posterior hip/medial crotch corridor')
        anchors=[start,hip,mid,medial,inner,end]
        straps.append(measured(route));waypoints.append(anchors)
        route_metrics.append(dict(attachment='Slightly anterior lateral hip',routeSteering=steering,waypointPositions=points[anchors].tolist(),descendingMaximumAnterior=float(np.max(points[descending,1])),returnMaximumLateral=float(np.max(np.abs(points[returning,0]))),length=float(np.linalg.norm(np.diff(points[route],axis=0),axis=1).sum())))
    anatomy=np.arange(body,len(points));anatomy=anatomy[np.isin(anatomy,ids)]
    amap={int(k):i for i,k in enumerate(anatomy)}
    triangles=[[amap[int(k)] for k in tri] for tri in faces if all(int(k) in amap for k in tri)]
    contours=[measured(waist),measured(opening),measured(anatomy),*straps]
    # Semantic guides are transferred from preserved authored source lineage.
    # They select measured live anatomy samples; no geometry/bone/radius
    # classification is performed in the runtime or cloth initializer.
    from scipy.sparse import csr_matrix
    from malemod_base.garment_regions import reference_anatomy_semantics,anatomy_regions,REGIONS,SEMANTIC_VERSION
    source_asset=cfg['base']/'assets/wolverine-reference/geometry.npz'
    semantic_exporter=cfg['base']/'malemod_base/garment_regions.py'
    ml=csr_matrix((part['module_lineage_data'],part['module_lineage_indices'],part['module_lineage_indptr']),shape=tuple(part['module_lineage_shape']))
    semantic=np.clip(ml@reference_anatomy_semantics(np.load(source_asset)),0,1)
    if len(semantic)!=len(points)-body:raise ValueError('Module semantic lineage differs from full authored anatomy')
    native_semantic=semantic[ids[np.asarray(contours[2])]-body]
    regions=anatomy_regions(native_semantic)
    from malemod_base.garment_reactions import reference_reaction_bindings,bounded_reaction_bindings,REACTION_BINDING_VERSION
    reaction_exporter=cfg['base']/'malemod_base/garment_reactions.py'
    mechanical=bounded_reaction_bindings(ml@reference_reaction_bindings(np.load(source_asset)))
    native_mechanical=mechanical[ids[np.asarray(contours[2])]-body]
    # Cloth contacts use the measured body surface, separately from the broad
    # anatomy-solver capsules. Preserve both resources around the waistband;
    # the upper resource starts after both lower LOD vertex ranges.
    manifest=read_json(render/'manifest.json')
    upper=np.load(render/'inspection-upper/lod0.npz')
    winding=[]
    def outward_faces(data,selected,label):
        # REDengine draw winding is opposite the outward stock vertex normals.
        # The contact mesh owns its outward convention; native draw buffers are
        # unchanged. Decode the observed packed 10-bit normals as the render
        # contract does, then record the actual orientation counts.
        packed=data['lighting'][:,:4].copy().view('<u4').reshape(-1)
        normals=np.stack([(packed>>shift)&1023 for shift in (0,10,20)],1)/1023*2-1
        xyz=data['position'][selected]
        dot=(np.cross(xyz[:,1]-xyz[:,0],xyz[:,2]-xyz[:,0])*normals[selected].mean(1)).sum(1)
        positive=int(np.sum(dot>1e-15));negative=int(np.sum(dot<-1e-15));degenerate=len(dot)-positive-negative
        if not positive+negative or min(positive,negative)>.02*(positive+negative):raise ValueError('Ambiguous observed body contact winding: '+label)
        flipped=negative>positive
        winding.append(dict(resource=label,outwardBefore=positive,inwardBefore=negative,degenerate=degenerate,reversedForContacts=flipped,nativeDrawBuffersChanged=False))
        return selected[:,[0,2,1]] if flipped else selected
    # Native import removed six unused/merged authored vertices. Contact
    # topology must use the real retained native faces rather than inventing
    # replacements for authored indices that have no runtime vertex.
    lower_native=np.flatnonzero(ids<body).astype(np.uint32)
    lower_to_contact={int(k):i for i,k in enumerate(lower_native)}
    retained=outward_faces(native,native['nativeFaces'][np.all(ids[native['nativeFaces']]<body,axis=1)],'lower')
    lower_faces=np.array([[lower_to_contact[int(k)] for k in face] for face in retained],dtype=np.uint32)
    body_ids=lower_native
    upper_first=int(manifest['resources'][1]['firstVertex'])
    upper_ids=np.arange(len(upper['position']),dtype=np.uint32)+upper_first
    upper_faces=outward_faces(upper,upper['nativeFaces'],'upper')
    body_faces=np.concatenate([lower_faces,upper_faces.astype(np.uint32)+len(lower_native)])
    body_ids=np.concatenate([body_ids,upper_ids])
    if body_faces.max()>=len(body_ids):raise ValueError('Measured body contact topology outside its surface')
    blob=b'MMGRB003'+manifest['baseCommit'].encode()+digest(render/'geralt.render').encode()+struct.pack('<3d',*origin)
    for contour in contours:blob+=struct.pack('<I',len(contour))+np.asarray(contour,dtype='<u4').tobytes()
    blob+=struct.pack('<I',len(triangles))+np.asarray(triangles,dtype='<u4').tobytes()
    blob+=struct.pack('<I',len(body_ids))+body_ids.astype('<u4').tobytes()
    blob+=struct.pack('<I',len(body_faces))+body_faces.astype('<u4').tobytes()
    for name in REGIONS:blob+=struct.pack('<I',len(regions[name]))+regions[name].astype('<u4').tobytes()
    output.mkdir(parents=True);packet=output/'garment.bindings';packet.write_bytes(blob)
    # Companion preserves every existing MMGRB003 byte and binds the measured
    # force ownership to the exact same Base/render pin and native vertex IDs.
    reaction_blob=b'MMGRE001'+manifest['baseCommit'].encode()+digest(render/'geralt.render').encode()+struct.pack('<I',len(contours[2]))
    for vertex,weights in zip(contours[2],native_mechanical):reaction_blob+=struct.pack('<I14d',vertex,*weights)
    reaction_packet=output/'garment.reactions';reaction_packet.write_bytes(reaction_blob)
    write_json(output/'manifest.json',dict(contractVersion=3,anatomySemantics=dict(version=SEMANTIC_VERSION,sourceAssetSHA256=digest(source_asset),exporterSHA256=digest(semantic_exporter),partLineageSHA256=digest(job/'part0.npz'),fullAnatomyVertices=len(contours[2]),fullAnatomyTriangles=len(triangles),groupCounts={name:len(regions[name]) for name in REGIONS},nativeDrawIndicesChanged=False),baseCommit=manifest['baseCommit'],renderSHA256=digest(render/'geralt.render'),packetSHA256=digest(packet),bodyJob=str(job.relative_to(ROOT)),recipeSHA256=digest(Path(__file__)),donorCounts=list(map(len,contours)),triangles=len(triangles),bodyContactVertices=len(body_ids),bodyContactTriangles=len(body_faces),bodyContactResources=[0,1],bodyContactWinding=winding,bodyContactInputs=[dict(path='inspection-'+name+'/lod0.npz',sha256=digest(render/('inspection-'+name)/'lod0.npz')) for name in ('lower','upper')],measuredGluteWaypoints=waypoints,measuredStrapRoutes=route_metrics,frameAxes=[[1,0,0],[0,1,0],[0,0,1]],observedGameplay=False))
    adoption=read_json(output/'manifest.json');adoption['physicalReactionBinding']=dict(version=REACTION_BINDING_VERSION,packetSHA256=digest(reaction_packet),sourceAssetSHA256=digest(source_asset),exporterSHA256=digest(reaction_exporter),nativeVertices=len(native_mechanical),generalizedBodies=14,nonlinearSurfaceJacobian=False);write_json(output/'manifest.json',adoption)
    adoption['sharedStrapRoute']=dict(version=CLASSIC_ROUTE_VERSION,contractSHA256=digest(Path(cfg['base'])/'malemod_base/garment_routes.py'))
    write_json(output/'manifest.json',adoption)
    return output
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('job','render','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(prepare(a.job,a.render,a.output))
