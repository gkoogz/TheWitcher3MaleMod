"""Stage an explicit diagnostic solver profile outside the game.

Production export is blocked until Geralt's complete contact calibration exists.
This stages no graphics replacement, game scripts, installation or game launch.
"""
import argparse,shutil,struct
from pathlib import Path
import numpy as np
from mod import ROOT,read_json,digest,write_json,settings,base_checkout
from packed_mesh_format import CookedMesh

def prepare(output,worker,diagnostic):
    output=output.resolve();worker=worker.resolve()
    if not output.is_relative_to(ROOT/'build') or output.exists():raise ValueError('Use a fresh owned build directory')
    pin=base_checkout(settings())['commit'];binding_dir=ROOT/('build/full-runtime/geralt-bindings-'+pin[:7]);binding=binding_dir/'geralt.bindings';receipt=read_json(binding_dir/'manifest.json')
    if receipt['baseCommit']!=pin or digest(binding)!=receipt['artifactSHA256']:raise ValueError('Binding does not match pinned proof')
    profile=read_json(ROOT/'characters/geralt-runtime-bindings.json');c=profile['coordinateCalibration']
    if not diagnostic:raise ValueError('Complete calibrated Geralt pelvis envelope remains required for production; use explicit diagnostic mode only')
    mesh=ROOT/'build/motion/player-stack-138649950289/package-cfb0915d89d2/cooked/characters/malemod/body/geralt_motion.w2mesh';packed=CookedMesh(mesh.read_bytes());ids=[i for i,n in enumerate(packed.palette) if n=='pelvis']
    if len(ids)!=2:raise ValueError('Expected measured pelvis in both LOD palettes')
    inverse=np.asarray(packed.inverse_binds[ids[0]],dtype='<f8').reshape(4,4).T
    if not np.array_equal(inverse,np.asarray(packed.inverse_binds[ids[1]]).reshape(4,4).T):raise ValueError('LOD pelvis inverse binds differ')
    worker_proof=read_json(ROOT/'provenance/full-runtime.json')['poseInputReplayVerification']['workerSHA256']
    if digest(worker)!=worker_proof:raise ValueError('Worker differs from verified full source replay')
    output.mkdir(parents=True);shutil.copy2(worker,output/'surface_worker.exe');shutil.copy2(binding,output/'geralt.bindings')
    blob=b'MMRUN001'+pin.encode()+digest(worker).encode()+digest(binding).encode()
    for a in [c['basis'],c['sourceRoot'],c['targetRootNative'],[c['nativeUnitsPerSourceUnit']],inverse]:blob+=np.asarray(a,dtype='<f8').tobytes()
    blob+=struct.pack('<I',2);packet=output/'malemod-runtime.profile';packet.write_bytes(blob)
    proof=dict(baseCommit=pin,packetSHA256=digest(packet),workerSHA256=digest(output/'surface_worker.exe'),bindingsSHA256=digest(output/'geralt.bindings'),
               cookedMeshSHA256=digest(mesh),recipeSHA256=digest(Path(__file__)),diagnosticSourceContacts=True,characterContactsCalibrated=False,graphicsReplacement=False,installed=False)
    write_json(output/'manifest.json',proof);print('Staged explicit diagnostic solver profile:',output)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--worker',type=Path,required=True);p.add_argument('--diagnostic-source-contacts',action='store_true');a=p.parse_args();prepare(a.output,a.worker,a.diagnostic_source_contacts)
