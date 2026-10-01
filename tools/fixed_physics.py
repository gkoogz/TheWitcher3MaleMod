"""Fixed authored rig and pinned Base secondary motion delivery. No size controls."""
import copy,json,sys
from dataclasses import asdict
import numpy as np
from mod import ROOT,digest,write_json
from prepare_motion import rig_world,rigdata
from physics_codegen import emit

FIT='build/attachment/fit-20261001-050243-44cbb5/geralt-anatomy.fit.json'
CAGE='build/motion/cage-dec402309e13/motion-lod0.npz'

def independent_rig(rig):
    result=copy.deepcopy(rig);v=result['_chunks']['CSkeleton #0']['_vars']
    names,parents,worlds=rig_world(v)
    if names[9]!='pelvis' or len(names)!=104:raise ValueError('Observed player rig changed')
    for i in range(94,104):
        v['parentIndices']['_elements'][i]['_value']=9
        v['rigdata']['_elements'][i]=rigdata(np.linalg.inv(worlds[9])@worlds[i])
    _,new_parents,new_worlds=rig_world(v)
    error=float(np.max(np.abs(np.array(worlds)-new_worlds)))
    if error>1e-10:raise ValueError('Rest conversion changed bind frames')
    return result,dict(originalParents=parents[94:],independentParents=new_parents[94:],neutralWorldFrameMaxError=error,stockPrefixUnchanged=True)

def number(v):return format(float(v),'.12f')
def vector(v):return 'Vector('+','.join(number(x) for x in v)+',0.0)'

def generate(base,rig,job,enabled=True):
    sys.path.insert(0,str(base))
    from malemod_base.physics_controls import evaluate,suspension_limits
    names,parents,worlds=rig_world(rig['_chunks']['CSkeleton #0']['_vars'])
    frames=np.array([np.linalg.inv(worlds[9])@w for w in worlds[94:]])
    points=frames[:,:3,3];wp=np.array(worlds)[94:,:3,3]
    lengths=np.linalg.norm(np.diff(wp[:8],axis=0),axis=1)
    directions=np.diff(points[:8],axis=0);directions=np.vstack([directions,directions[-1]])
    directions/=np.linalg.norm(directions,axis=1)[:,None]
    fit=json.loads((ROOT/FIT).read_text());k=fit['sourceToFBXScale']/100
    from malemod_base.controls import VERSION
    controls=evaluate({'format':'malemod.controls','version':VERSION,'values':{}},mode=2,rest_length=float(lengths.sum()/k))
    data=np.load(ROOT/CAGE);mesh=data['points']/100;weights=data['weights']
    radii=[]
    for i in range(10):
        selected=mesh[weights[:,13+i]>(.1 if i==0 else (.95 if i>=8 else .45))]-wp[i]
        if len(selected)<10:raise ValueError('Insufficient measured joint envelope')
        if i<8:
            d=worlds[9][:3,:3]@directions[i]
            r=np.quantile(np.linalg.norm(selected-np.outer(selected@d,d),axis=1),.95)
            radii.append([r,r,r])
        else:radii.append(np.quantile(np.abs(selected@worlds[94+i][:3,:3]),.99,axis=0).tolist())
    thighs=['r_thigh','r_shin','l_thigh','l_shin'];indices=[names.index(n) for n in thighs]
    thigh_radii=[]
    for side in range(2):
        a,b=[worlds[i][:3,3] for i in indices[side*2:side*2+2]]
        col=fit['lods'][0]['bones'].index(thighs[side*2])
        p=mesh[:1021][weights[:1021,col]>.5];ab=b-a
        t=np.clip((p-a)@ab/(ab@ab),0,1);dist=np.linalg.norm(p-a-t[:,None]*ab,axis=1)
        thigh_radii.append(float(np.quantile(dist,.95)))
    init=['physicsEnabled = '+str(enabled).lower()+';']
    sizes={'restPoints':10,'restFrames':10,'restDirections':8,'lengths':7,'radii':10,'thighRadii':2,'thighIndices':4,
           'physicsPosition':10,'physicsOld':10,'physicsVelocity':10,'physicsInvMass':10,'targets':10,'oldTargets':10,
           'capsules':4,'oldCapsules':4,'bendLambda':6,'materialLambda':2,'lengthLambda':7,'bends':6,'lobeRotations':2,
           'tetherRest':2,'tetherLimit':2,'suspensionLambda':2,'shearLambdaX':2,'shearLambdaY':2}
    init += [f'{key}.Resize({n});' for key,n in sizes.items()]
    for i in range(10):
        init += [f'restPoints[{i}] = {vector(points[i])};',f'radii[{i}] = {vector(radii[i])};',f'restFrames[{i}] = MatrixIdentity();']
        for j,axis in enumerate('XYZ'):init += [f'restFrames[{i}].{axis} = {vector(frames[i,:3,j])};']
        mass=controls.shaft_mass if i<8 else controls.lobe_mass
        init += [f'physicsInvMass[{i}] = {number(0 if i<2 else 1/mass)};',f"deformationRoot.SetBehaviorVectorVariable('{names[94+i]}_scale',Vector(1.0,1.0,1.0,0.0));"]
    for i in range(8):init += [f'restDirections[{i}] = {vector(directions[i])};']
    for i in range(7):init += [f'lengths[{i}] = {number(lengths[i])};']
    for i in range(4):init += [f'thighIndices[{i}] = {indices[i]};']
    for i in range(2):
        rest,limit=suspension_limits(float(np.linalg.norm(wp[8+i]-wp[0])/k),radii[8+i][1]/k)
        init += [f'thighRadii[{i}] = {number(thigh_radii[i])};',f'tetherRest[{i}] = {number(rest*k)};',f'tetherLimit[{i}] = {number(limit*k)};',f'lobeRotations[{i}] = Vector(0.0,0.0,0.0,1.0);']
    coefficients=asdict(controls)
    for key in ('shaft_gravity','lobe_gravity'):coefficients[key]*=k
    methods,receipt=emit(base)
    step=(ROOT/'probes/runtime/physicsStep.ws.inc').read_text()
    for key,value in coefficients.items():step=step.replace('@'+key+'@',number(value))
    step=step.replace('@padding@',number(.025*k))
    source=(ROOT/'probes/runtime/fixedPhysics.ws').read_text()
    source=source.replace('// OBSERVED_RIG_CHECKS','\n'.join(f"if (deformationRoot.skeleton.bones[{i}].nameAsCName != '{name}') {{ reason = \"rig mapping changed\"; return false; }}" for i,name in enumerate(names)))
    source=source.replace('// INITIALIZE_CONSTANTS','\n'.join(init)).replace('// PHYSICS_METHODS',methods+'\n'+step)
    publish=[]
    for i,name in enumerate(names[94:]):
        publish.append(f'if (i == {i}) {{')
        for axis in 'XYZ':
            publish += [f"physicsAccepted = deformationRoot.SetBehaviorVariable('{name}_translate_{axis.lower()}',delta.{axis}) && physicsAccepted;",f"physicsAccepted = deformationRoot.SetBehaviorVariable('{name}_rotate_{axis.lower()}',angles.{axis}) && physicsAccepted;"]
        publish.append('}')
    source=source.replace('// PUBLISH_JOINTS','\n'.join(publish))
    receipt.update(fixedScale=1,enabled=enabled,solver='Base XPBD curved rod, damped suspension and support contacts; WitcherScript fixed step',
        coefficients=coefficients,sourceToNativeLength=k,restLengths=lengths.tolist(),jointRadii=radii,thighRadii=thigh_radii,
        thighBones=thighs,fitReceipt=FIT,fitSHA256=digest(ROOT/FIT),cage=CAGE,cageSHA256=digest(ROOT/CAGE),
        colliderCalibration='95th percentile stock thigh radial envelope; lobe weighted envelope maxima; shaft radial 95th percentile',
        omissions=['full source surface deformation','angular contact effective mass and reaction torques','Hermite guide Jacobian','pressure deformation','dynamic pelvic collar'],
        runtimeParity=False,observedGameplay=False)
    write_json(job/'fixed-physics.json',receipt)
    return source,receipt
