"""Stage a hash-locked solver profile with measured adapter contacts or explicit diagnostics."""
import argparse,shutil,struct
from pathlib import Path
import numpy as np
from mod import ROOT,read_json,digest,write_json,settings,base_checkout
from packed_mesh_format import CookedMesh

def validate_current_base_proof(path,worker,base,pin):
    proof=read_json(path);current=read_json(base/'provenance/source-surface.json')['currentProcessRuntime']
    from worker_adoption import validate_process_library
    library=base/proof.get('libraryPath','build/surface-process-verified-cmake/Release/malemod_surface.lib')
    source_proof=validate_process_library(base,library,current,require_clean=True,pin=pin)
    if source_proof and (proof.get('sourceConsumptionProofPath')!=source_proof['path'] or proof.get('sourceConsumptionProofSHA256')!=source_proof['sha256']):raise ValueError('Current worker source consumption receipt differs')
    if (proof.get('kind')!='current-base-api-byte-replay' or proof['baseCommit']!=pin or proof['baseDirty']
        or proof['baseProvenanceSHA256']!=digest(base/'provenance/source-surface.json')
        or proof['librarySHA256']!=current['librarySHA256']
        or digest(library)!=current['librarySHA256']
        or proof['workerSHA256']!=digest(worker) or proof['wireVersion'] not in (5,6) or proof['wireVersion']!=current['wireVersion']
        or proof['behaviorRevision']!=2 or proof['behaviorRevision']!=current['behaviorRevision']
        or proof['exitCode']!=0 or proof['frames']!=48 or not proof['byteIdentical']
        or digest(ROOT/proof['executable'])!=proof['executableSHA256']
        or digest(ROOT/proof['report'])!=proof['reportSHA256']
        or digest(ROOT/'tools/verify_worker_revision.py')!=proof['recipeSHA256']):raise ValueError('Current Base revision proof differs')
    return digest(path)

def prepare(output,worker,diagnostic,worker_parity_proof=None,bindings=None,current_base_proof=None):
    output=output.resolve();worker=worker.resolve()
    if not output.is_relative_to(ROOT/'build') or output.exists():raise ValueError('Use a fresh owned build directory')
    cfg=settings();pin=base_checkout(cfg)['commit'];binding_dir=Path(bindings).absolute() if bindings else ROOT/('build/full-runtime/geralt-bindings-'+pin[:7]);binding=binding_dir/'geralt.bindings';receipt=read_json(binding_dir/'manifest.json')
    if receipt['baseCommit']!=pin or digest(binding)!=receipt['artifactSHA256']:raise ValueError('Binding does not match pinned proof')
    profile=read_json(ROOT/'characters/geralt-runtime-bindings.json');c=profile['coordinateCalibration']
    contacts=profile['contacts'];capsule=contacts['pelvisCapsule']
    if not diagnostic:
        proof=read_json(ROOT/'build/full-runtime/geralt-contact-calibration.json')
        if (not capsule or proof['profileSHA256']!=digest(ROOT/'characters/geralt-runtime-bindings.json')
            or proof['capsule']!=capsule or capsule['sampleCount']<100
            or capsule['fitRecipeSHA256']!=digest(ROOT/'tools/calibrate_runtime_contacts.py')
            or capsule['sourceBindingSHA256']!=digest(ROOT/capsule['sourceBinding'])):
            raise ValueError('Measured character contact calibration/provenance differs')
        if len(contacts['thighs'])!=2:raise ValueError('Both measured thigh radii required')
    mesh=ROOT/'build/motion/player-stack-138649950289/package-cfb0915d89d2/cooked/characters/malemod/body/geralt_motion.w2mesh';packed=CookedMesh(mesh.read_bytes());ids=[i for i,n in enumerate(packed.palette) if n=='pelvis']
    if len(ids)!=2:raise ValueError('Expected measured pelvis in both LOD palettes')
    inverse=np.asarray(packed.inverse_binds[ids[0]],dtype='<f8').reshape(4,4).T
    if not np.array_equal(inverse,np.asarray(packed.inverse_binds[ids[1]]).reshape(4,4).T):raise ValueError('LOD pelvis inverse binds differ')
    worker_proof=read_json(ROOT/'provenance/full-runtime.json')['poseInputReplayVerification']['workerSHA256']
    parity_hash=None;current_hash=None
    if worker_parity_proof is not None and current_base_proof is not None:raise ValueError('Choose historical equivalence or intentional current Base revision proof')
    if current_base_proof is not None:
        current_hash=validate_current_base_proof(current_base_proof,worker,Path(cfg['base']),pin)
    elif digest(worker)!=worker_proof:
        if worker_parity_proof is None:raise ValueError('New worker requires exact replay-worker equivalence proof')
        parity=read_json(worker_parity_proof)
        if (parity['referenceWorkerSHA256']!=worker_proof or parity['workerSHA256']!=digest(worker)
            or parity['exitCode']!=0 or parity['frames']!=48 or not parity['byteIdentical']
            or digest(ROOT/parity['executable'])!=parity['executableSHA256']
            or digest(ROOT/parity['report'])!=parity['reportSHA256']):raise ValueError('Worker equivalence proof differs')
        parity_hash=digest(worker_parity_proof)
    output.mkdir(parents=True);shutil.copy2(worker,output/'surface_worker.exe');shutil.copy2(binding,output/'geralt.bindings')
    blob=b'MMRUN001'+pin.encode()+digest(worker).encode()+digest(binding).encode()
    for a in [c['basis'],c['sourceRoot'],c['targetRootNative'],[c['nativeUnitsPerSourceUnit']],inverse]:blob+=np.asarray(a,dtype='<f8').tobytes()
    blob+=struct.pack('<I',2 if diagnostic else 1)
    if not diagnostic:
        blob+=np.asarray([row['radiusSource'] for row in contacts['thighs']],dtype='<f4').tobytes()
        blob+=np.asarray(capsule['sourceEndpoints'],dtype='<f4').tobytes()+struct.pack('<f',capsule['radiusSource'])
    packet=output/'malemod-runtime.profile';packet.write_bytes(blob)
    proof=dict(baseCommit=pin,packetSHA256=digest(packet),workerSHA256=digest(output/'surface_worker.exe'),bindingsSHA256=digest(output/'geralt.bindings'),
               cookedMeshSHA256=digest(mesh),recipeSHA256=digest(Path(__file__)),workerParityProofSHA256=parity_hash,currentBaseRevisionProofSHA256=current_hash,diagnosticSourceContacts=diagnostic,characterContactsCalibrated=not diagnostic,contactProfileSHA256=None if diagnostic else digest(ROOT/'characters/geralt-runtime-bindings.json'),graphicsReplacement=False,installed=False)
    write_json(output/'manifest.json',proof);print('Staged solver profile:',output)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--worker',type=Path,required=True);p.add_argument('--worker-parity-proof',type=Path);p.add_argument('--current-base-proof',type=Path);p.add_argument('--bindings',type=Path);p.add_argument('--diagnostic-source-contacts',action='store_true');a=p.parse_args();prepare(a.output,a.worker,a.diagnostic_source_contacts,a.worker_parity_proof,a.bindings,a.current_base_proof)
