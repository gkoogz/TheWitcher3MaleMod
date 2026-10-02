"""Fixed authored rig and pinned Base secondary motion delivery. No size controls."""
import copy,json,sys
from pathlib import Path
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

def generate(base,rig,job,enabled=True,cage=None,mechanics=None,surface_points=None):
    sys.path.insert(0,str(base))
    from malemod_base.physics_controls import evaluate,suspension_limits
    from malemod_base.motion_binding import sample_mechanical_guide
    cage=Path(cage).resolve() if cage else ROOT/CAGE
    cage_dir=cage.parent if cage.suffix=='.npz' else cage
    cage=cage_dir/'motion-lod0.npz'
    cage_receipt=json.loads((cage_dir/'motion.json').read_text())
    fit_path=ROOT/cage_receipt.get('fitReport',FIT)
    fit=json.loads(fit_path.read_text())
    if not fit.get('sourceMechanics'):raise ValueError('Rebuild cage from evaluated Wolverine defaults, not posed reference')
    if cage_receipt['fitSHA256']!=digest(fit_path):raise ValueError('Cage baseline fit changed')
    source=mechanics if mechanics is not None else fit['sourceMechanics'];profile=json.loads((ROOT/'characters/geralt-attachment.json').read_text())
    names,parents,worlds=rig_world(rig['_chunks']['CSkeleton #0']['_vars'])
    frames=np.array([np.linalg.inv(worlds[9])@w for w in worlds[94:]])
    bind_points=frames[:,:3,3].copy();joint_points=bind_points.copy();wp=np.array(worlds)[94:,:3,3]
    k=fit['sourceToFBXScale']/100;basis=np.asarray(profile['basis'])
    convert=lambda p:((np.asarray(p)-fit['sourceRoot'])@basis.T*fit['sourceToFBXScale']+profile['targetRoot'])/100
    local=lambda p:(p-worlds[9][:3,3])@worlds[9][:3,:3]
    points=local(convert(np.vstack([source['shaftGuide'],source['lobeCenters']])))
    sample_points,_=sample_mechanical_guide(points[:12],np.linspace(0,1,8))
    if mechanics is not None:joint_points=np.vstack([sample_points,points[12:14]])
    neutral_error=float(np.linalg.norm(np.vstack([sample_points,points[12:]])-joint_points,axis=1).max())
    if neutral_error>1e-5:raise ValueError('Default guide and authored skin frames disagree')
    lengths=np.full(11,source['restLength']*k/11)
    directions=np.diff(points[:12],axis=0);directions=np.vstack([directions,directions[-1]])
    directions/=np.linalg.norm(directions,axis=1)[:,None]
    from malemod_base.controls import VERSION
    controls=evaluate({'format':'malemod.controls','version':VERSION,'values':{}},mode=2,rest_length=source['restLength'])
    data=np.load(cage);mesh=(data['points'] if surface_points is None else surface_points)/100;weights=data['weights'];body_count=len(mesh)-len(data['fields'])
    # A measured, volume-bearing distal body supplies a complete orientation.
    # Keep the approved mesh and shaft binding law; render bones 5..7 recover
    # one accepted physical transform rather than independent tangent guesses.
    fields=data['fields'];head_mask=(fields[:,2]>=.78)&(fields[:,0]>.9)&(fields[:,1]<.05)
    head_skin=local(mesh[body_count:][head_mask]);head_axes=frames[7,:3,:3]
    head_origin=head_skin.mean(0)
    bounds=(head_skin-head_origin)@head_axes
    head_extent=np.maximum(np.ptp(bounds,axis=0)*.5,1e-4)
    supports=np.vstack([head_origin]+[head_origin+sign*head_axes[:,axis]*head_extent[axis] for axis in range(3) for sign in [-1,1]])
    points=np.vstack([points,supports]);head_rest_center=np.vstack([points[8:12],points[14:21]]).mean(0)
    radii=[[source['proximalRadius']*k*.85]*3 for i in range(12)]+(np.asarray(source['lobeRadii'])*k).tolist()
    radii += [[.025*k]*3]*7
    thighs=['r_thigh','r_shin','l_thigh','l_shin'];indices=[names.index(n) for n in thighs]
    thigh_radii=[]
    for side in range(2):
        a,b=[worlds[i][:3,3] for i in indices[side*2:side*2+2]]
        col=fit['lods'][0]['bones'].index(thighs[side*2])
        p=mesh[:body_count][weights[:body_count,col]>.5];ab=b-a
        t=np.clip((p-a)@ab/(ab@ab),0,1);dist=np.linalg.norm(p-a-t[:,None]*ab,axis=1)
        thigh_radii.append(float(np.quantile(dist,.95)))
    init=['physicsEnabled = '+str(enabled).lower()+';']
    sizes={'restPoints':21,'restFrames':10,'bindJointPoints':10,'jointRestPoints':10,'lobeRestFrames':2,'restDirections':8,'lengths':11,'radii':21,'thighRadii':2,'thighIndices':4,
           'physicsPosition':21,'physicsOld':21,'physicsVelocity':21,'physicsInvMass':21,'targets':21,'oldTargets':21,
           'capsules':4,'oldCapsules':4,'bendLambda':10,'bendCompliance':10,'materialLambda':2,'lengthLambda':11,'bends':10,'lobeRotations':2,
           'anchorOffsets':2,'materialOffsets':2,'previousAnchors':2,'previousMaterial':2,
           'tetherRest':2,'tetherLimit':2,'suspensionLambda':2,'shearLambdaX':2,'shearLambdaY':2}
    init += [f'{key}.Resize({n});' for key,n in sizes.items()]
    for i in range(21):
        init += [f'restPoints[{i}] = {vector(points[i])};',f'radii[{i}] = {vector(radii[i])};']
        mass=controls.lobe_mass if 12<=i<14 else controls.shaft_mass
        if 8<=i<12 or i>=14:mass*=4/11 # eleven supports share the original four station masses
        init += [f'physicsInvMass[{i}] = {number(0 if i<2 else 1/mass)};']
    init += [f'headRestCenter = {vector(head_rest_center)};', 'headRotation = Vector(0.0,0.0,0.0,1.0);']
    for i in range(10):
        init += [f'bindJointPoints[{i}] = {vector(bind_points[i])};',f'jointRestPoints[{i}] = {vector(joint_points[i])};',f'restFrames[{i}] = MatrixIdentity();',f"deformationRoot.SetBehaviorVectorVariable('{names[94+i]}_scale',Vector(1.0,1.0,1.0,0.0));"]
        for j,axis in enumerate('XYZ'):init += [f'restFrames[{i}].{axis} = {vector(frames[i,:3,j])};']
    for i in range(2):
        lobe_frame=worlds[9][:3,:3].T@basis@np.asarray(source['lobeAxes'][i]).T
        init += [f'lobeRestFrames[{i}] = MatrixIdentity();']
        for j,axis in enumerate('XYZ'):init += [f'lobeRestFrames[{i}].{axis} = {vector(lobe_frame[:,j])};']
    _,sample_directions=sample_mechanical_guide(np.asarray(source['shaftGuide']),np.linspace(0,1,8))
    sample_directions=sample_directions@basis.T@worlds[9][:3,:3]
    for i in range(8):init += [f'restDirections[{i}] = {vector(sample_directions[i])};']
    for i in range(11):init += [f'lengths[{i}] = {number(lengths[i])};']
    for i in range(10):
        t=i/10
        init += [f'bendCompliance[{i}] = {number(controls.shaft_bend_compliance*(.02+.98*t*t)*source["bendMultipliers"][i])};']
    for i in range(4):init += [f'thighIndices[{i}] = {indices[i]};']
    center,tangent=sample_mechanical_guide(np.asarray(source['shaftGuide']),.12)
    init += [f'attachmentRestTangent = {vector(tangent@basis.T@worlds[9][:3,:3])};']
    for i in range(2):
        # Translate the cord's surface endpoint to the center representation.
        up=np.asarray(source['lobeAxes'][i][2]);anchor=np.asarray(source['lobeAnchors'][i])-up*(source['lobeRadii'][i][2]*.23)
        anchor_offset=(anchor-center)@basis.T@worlds[9][:3,:3]*k
        material_offset=(np.asarray(source['lobeCenters'][i])-center)@basis.T@worlds[9][:3,:3]*k
        init += [f'anchorOffsets[{i}] = {vector(anchor_offset)};',f'materialOffsets[{i}] = {vector(material_offset)};']
        rest,limit=suspension_limits(float(np.linalg.norm(np.asarray(source['lobeCenters'][i])-anchor)),radii[12+i][1]/k)
        init += [f'thighRadii[{i}] = {number(thigh_radii[i])};',f'tetherRest[{i}] = {number(rest*k)};',f'tetherLimit[{i}] = {number(limit*k)};',f'lobeRotations[{i}] = Vector(0.0,0.0,0.0,1.0);']
    coefficients=asdict(controls)
    for key in ('shaft_gravity','lobe_gravity'):coefficients[key]*=k
    coefficients['linear_acceleration_limit']=4*coefficients['shaft_gravity']
    coefficients['total_acceleration_limit']=6*coefficients['shaft_gravity']
    methods,receipt=emit(base)
    step=(ROOT/'probes/runtime/physicsStep.ws.inc').read_text()
    for key,value in coefficients.items():step=step.replace('@'+key+'@',number(value))
    step=step.replace('@padding@',number(.025*k))
    source=(ROOT/'probes/runtime/fixedPhysics.ws').read_text()
    for key,value in coefficients.items():source=source.replace('@'+key+'@',number(value))
    source=source.replace('// OBSERVED_RIG_CHECKS','\n'.join(f"if (deformationRoot.skeleton.bones[{i}].nameAsCName != '{name}') {{ reason = \"rig mapping changed\"; return false; }}" for i,name in enumerate(names)))
    source=source.replace('// INITIALIZE_CONSTANTS','\n'.join(init)).replace('// PHYSICS_METHODS',methods+'\n'+step)
    publish=[]
    for i,name in enumerate(names[94:]):
        publish.append(f'if (i == {i}) {{')
        for axis in 'XYZ':
            publish += [f"physicsAccepted = deformationRoot.SetBehaviorVariable('{name}_translate_{axis.lower()}',delta.{axis}) && physicsAccepted;",f"physicsAccepted = deformationRoot.SetBehaviorVariable('{name}_rotate_{axis.lower()}',angles.{axis}) && physicsAccepted;"]
        publish.append('}')
    source=source.replace('// PUBLISH_JOINTS','\n'.join(publish))
    receipt.update(fixedScale=1,enabled=enabled,solver='pelvis-relative flexible source guide coupled to a volume-bearing distal body; point suspension and support contacts',
        coefficients=coefficients,sourceToNativeLength=k,restLengths=lengths.tolist(),jointRadii=radii,thighRadii=thigh_radii,
        thighBones=thighs,fitReceipt=fit_path.relative_to(ROOT).as_posix(),fitSHA256=digest(fit_path),cage=cage.relative_to(ROOT).as_posix(),cageSHA256=digest(cage),
        sourceBaseline=fit['sourceBaseline'],physicsNodes=21,renderJoints=10,bendTarget='zero curvature in flexible shaft; rigid distal material',
        distalBody=dict(supportIndices=[8,9,10,11,14,15,16,17,18,19,20],offAxisSupports=supports.tolist(),restCenter=head_rest_center.tolist(),
                       renderJoints=names[99:102],originalHeadMassPreserved=True,orientation='3D covariance fit with independent roll',
                       restGeometryUnchanged=True,shaftBindingLawAndKnotsUnchanged=True,
                       suspensionPartition='source ApplySuspendedSkin Smooth01 split; native four-influence truncation'),
        neutralGuideToRenderJointError=neutral_error,
        solverSpace='pelvis local; relative velocity damping; local gravity and thigh capsules',
        poseDelivery=dict(rotationSpace='bone bind local',rotationOperator='current quaternion right-multiplied by local delta',axisOrder='intrinsic XYZ',conversion='conjugate parent-space delta by bind rotation'),
        frameMotion=dict(response=20,linearAccelerationLimit=coefficients['linear_acceleration_limit'],totalAccelerationLimit=coefficients['total_acceleration_limit'],angularVelocityLimit=10,angularAccelerationLimit=40,units='native length/time; angular radians/time',sourceParity=False),
        colliderCalibration='95th percentile stock thigh radial envelope; source default ovoid radii and shaft radius times 0.85',
        omissions=['full source surface deformation','angular contact effective mass and reaction torques','Hermite guide Jacobian','pressure deformation','dynamic pelvic collar','source gait/side filtering and live root spring response'],
        runtimeParity=False,observedGameplay=False)
    write_json(job/'fixed-physics.json',receipt)
    return source,receipt
