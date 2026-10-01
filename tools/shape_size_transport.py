"""Calibrated native delivery of Base's source-backed independent cage fits."""
import copy
import importlib
import json
import sys
import numpy as np
from scipy.spatial.transform import Rotation
from mod import ROOT, digest, write_json
from prepare_motion import rig_world, rigdata


def independent_rig(rig):
    result=copy.deepcopy(rig)
    v=result['_chunks']['CSkeleton #0']['_vars']
    names,parents,worlds=rig_world(v)
    if names[9]!='pelvis' or len(names)!=104:
        raise ValueError('Reinspect observed private player rig')
    for i in range(94,104):
        v['parentIndices']['_elements'][i]['_value']=9
        v['rigdata']['_elements'][i]=rigdata(np.linalg.inv(worlds[9])@worlds[i])
    _,new_parents,new_worlds=rig_world(v)
    error=float(np.max(np.abs(np.array(worlds)-new_worlds)))
    if error>1e-10:raise ValueError('Independent rest conversion changed world bind frames')
    return result,dict(originalParents=parents[94:],independentParents=new_parents[94:],
                       neutralWorldFrameMaxError=error,stockPrefixUnchanged=True)


def build_transport(base,rig,job):
    sys.path.insert(0,str(base))
    shared=importlib.import_module('malemod_base.shape_transport')
    fit_path=ROOT/'build/attachment/fit-20260930-075013-7ae7f2/geralt-anatomy.fit.json'
    fit=json.loads(fit_path.read_text())
    profile=json.loads((ROOT/'characters/geralt-attachment.json').read_text())
    # Use the observed fit, never the source solver's anatomical root as fit origin.
    scale=fit['sourceToFBXScale'];basis=np.asarray(profile['basis'])
    source_root=np.asarray(fit['sourceRoot']);target_root=np.asarray(profile['targetRoot'])
    _,_,worlds=rig_world(rig['_chunks']['CSkeleton #0']['_vars'])
    rotations=np.array([w[:3,:3] for w in worlds[94:]])
    positions=np.array([w[:3,3] for w in worlds[94:]])
    origins=((positions*100-target_root)/scale)@basis+source_root
    frames=np.einsum('ij,njk->nik',basis.T,rotations)
    bank=base/'assets/wolverine-reference/geometry.npz'
    with np.load(bank,allow_pickle=False) as data:
        evaluator=shared.ShapeTransport(data,origins,frames)
        lattice=evaluator.lattice()
    lattice[...,:3]*=scale/100
    # Native localSpace RotateBone left-multiplies the incoming quaternion.
    # XYZ node order gives Rz*Ry*Rx; express the fitted right-side bone delta
    # in its pelvis parent's coordinates, then use extrinsic XYZ angles.
    parent_rotation=worlds[9][:3,:3]
    local_rotations=np.einsum('ij,njk->nik',parent_rotation.T,rotations)
    fitted_rotations=lattice[...,6:].reshape(4,4,4,4,10,3,3)
    deltas=local_rotations@fitted_rotations@local_rotations.transpose(0,2,1)
    angles=Rotation.from_matrix(deltas.reshape(-1,3,3)).as_euler('xyz',degrees=True).reshape(4,4,4,4,10,3)
    # Crown scaling is about .76 of the shaft, as in source, rather than about
    # knot 6. Bone skinning still approximates the source's folded transition.
    translated=positions+np.einsum('nij,...nj->...ni',rotations,lattice[...,:3])
    reference_anchor=positions[0]+.76*(positions[7]-positions[0])
    # Both crown joints share one affine transform, about the same anchor.
    # Recover its current anchor from knot 6; interpolating independently fitted
    # centroids created the previous sharp distal transition.
    anchor=translated[...,6,:]-lattice[...,6,3,None]*(positions[6]-reference_anchor)
    offsets=np.einsum('nji,...nj->...ni',rotations,translated-anchor[...,None,:])
    table=np.concatenate((lattice[...,:6],angles,offsets),axis=-1)
    if not np.isfinite(table).all():raise ValueError('Nonfinite source-backed pose table')
    np.savez_compressed(job/'source-size-poses.npz',poses=table,sourceOrigins=origins,sourceFrames=frames)
    receipt=dict(backend='source-measured-coherent-cage',sourceBankSHA256=digest(bank),
        sharedShapeTransportSHA256=digest(base/'malemod_base/shape_transport.py'),
        fitReceipt=str(fit_path.relative_to(ROOT)),fitReceiptSHA256=digest(fit_path),
        mappedKnots={key:shared.mapped_knots(key).tolist() for key in shared.AXES},
        latticeShape=list(table.shape),minimumScale=float(lattice[...,3:6].min()),
        maximumScale=float(lattice[...,3:6].max()),
        sourceSurfaceParity=False,physicsParity=False,observedGameplay=False,
        neutralSourceRadius=evaluator.reference_frame.body_radius,
        neutralSourceLength=evaluator.reference_frame.rest_length,
        shaftTransport='common radius; measured axial span along calibrated export axis',
        crownTransport='one common similarity transform about calibrated .76 anchor',
        omissions=list(evaluator.shape.evaluate().omitted_stages)+['bone approximation of folded glans attachment',
            'short-profile previous-length fallback uses measured neutral rather than gameplay history'])
    write_json(job/'source-size-transport.json',receipt)
    return table,receipt
