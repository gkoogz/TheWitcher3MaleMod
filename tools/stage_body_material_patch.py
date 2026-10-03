"""Stage an encoding-corrected body package without changing runtime selection.

Verifies all native body/Overall vertex buffers, render layouts, skin palettes,
material handles and bounded cook-only header changes against the selected body
package. Does not install, copy Release files or alter current-install.json.
"""
import argparse,shutil,struct,time,uuid
from pathlib import Path
from mod import ROOT,read_json,write_json,digest,verify_package
from packed_mesh_format import CookedMesh
from build_body_boundary import material_policy


def native_box(mesh):
    properties,tail=mesh.object(mesh.properties['boundingBox'][1])
    if tail:raise ValueError('Unobserved native bounding box tail')
    result=[]
    for name in ['Min','Max']:
        vector,tail=mesh.object(properties[name][1])
        if tail:raise ValueError('Unobserved native bound vector tail')
        result.extend(struct.unpack('<f',vector[a][1])[0] for a in 'XYZ')
    return result


def native_bound_fourth_components(mesh):
    properties,_=mesh.object(mesh.properties['boundingBox'][1])
    return {name:mesh.object(properties[name][1])[0]['W'][1].hex() for name in ['Min','Max']}


def material_children(mesh):
    offset,count,_=struct.unpack_from('<III',mesh.raw,40+4*12)
    result=[]
    for kind,flags,parent,size,position,template,crc in struct.iter_unpack('<HHIIIII',mesh.raw[offset:offset+count*24]):
        if mesh.names[kind]=='CMaterialInstance':result.append(mesh.raw[position:position+size])
    return result


def native_chunks(mesh):
    kind,data=mesh.properties['chunks']
    if kind!='array:2,0,SMeshChunkPacked':raise ValueError('Unobserved native chunks type')
    count=struct.unpack_from('<I',data)[0];tail=data[4:];result=[]
    for _ in range(count):
        properties,tail=mesh.object(tail)
        # Enum payloads index the name pool; adding the merge property moves
        # these indices without changing the observed native vertex type.
        if 'vertexType' in properties:
            enum,value=properties['vertexType']
            if enum!='EMeshVertexType' or len(value)!=2:raise ValueError('Unobserved native vertex type')
            properties['vertexType']=(enum,mesh.names[struct.unpack('<H',value)[0]])
        result.append(properties)
    if tail:raise ValueError('Unobserved native chunks tail')
    return result


def stage(job, allow_shadow_merge_policy=False):
    job=Path(job).absolute()
    if not job.is_relative_to(ROOT/'build'):raise ValueError('Use an owned body material job')
    selection=read_json(ROOT/'build/full-runtime/current-install.json')
    pin=read_json(ROOT/'dependencies/base.lock.json')['commit']
    materials=read_json(job/'material-imports.json')
    if materials['baseCommit']!=pin or not materials['nativeHandleVerified']:raise ValueError('Material job pin/native handle proof differs')
    for row in materials['materials']:
        group,compression=material_policy(row['channel'])
        if row.get('textureGroup')!=group or row.get('compression')!=compression or not row.get('nativeMetadataVerified'):
            raise ValueError('Material lacks measured encoding proof')
        if row['channel']=='ambient':
            calibration=job/'ambient-match.json'
            if not calibration.exists() or row.get('ambientMatchSHA256')!=digest(calibration):
                raise ValueError('Packed skin material lacks its measured channel calibration')
    old_job=ROOT/selection['bodyJob'];new_package=read_json(job/'package.json');old_package=read_json(old_job/'package.json')
    old_cooked,new_cooked=Path(old_package['cooked']),Path(new_package['cooked'])
    body='characters/malemod/body'
    resources=['characters/malemod/body/geralt_motion.w2mesh','characters/models/geralt/body/model/t_01_mg__body_hires.w2mesh']
    resources.extend(p.relative_to(new_cooked).as_posix() for p in sorted((new_cooked/body/'overall_overall-stable-layout').glob('*.w2mesh')))
    if len(resources)!=13:raise ValueError('Missing exact body resource family')
    proofs=[]
    for resource in resources:
        old,new=old_cooked/resource,new_cooked/resource
        old_mesh,new_mesh=CookedMesh(old.read_bytes()),CookedMesh(new.read_bytes())
        buffer_hash=digest(Path(str(new)+'.1.buffer'))
        if buffer_hash!=digest(Path(str(old)+'.1.buffer')):raise ValueError('Material patch changes native vertex/index bytes')
        comparable_names=new_mesh.names
        if allow_shadow_merge_policy and 'mergeInGlobalShadowMesh' not in old_mesh.names:
            comparable_names=[name for name in comparable_names if name!='mergeInGlobalShadowMesh']
        if old_mesh.names!=comparable_names or old_mesh.cooked!=new_mesh.cooked or old_mesh.palette!=new_mesh.palette or old_mesh.inverse_binds!=new_mesh.inverse_binds or old_mesh.bone_mapping!=new_mesh.bone_mapping or native_chunks(old_mesh)!=native_chunks(new_mesh):
            raise ValueError('Material patch changes native render layout or skin binding')
        if material_children(old_mesh)!=material_children(new_mesh):raise ValueError('Material patch changes mesh material handles')
        expected_properties=set(old_mesh.properties)
        permitted=set()
        if allow_shadow_merge_policy:
            # Official SDK CMesh property. This changes global merge policy,
            # not chunk shadow eligibility, geometry or shadow draw casting.
            if new_mesh.properties.get('mergeInGlobalShadowMesh')!=('Bool',b'\x00'):
                raise ValueError('Shadow policy experiment lacks explicit native false flag')
            expected_properties.add('mergeInGlobalShadowMesh')
            # Nested property indices shift after adding the observed name;
            # cookedData and chunks have already been compared semantically.
            permitted.update(['mergeInGlobalShadowMesh','chunks','cookedData'])
        if expected_properties!=set(new_mesh.properties) or any(old_mesh.properties[k]!=new_mesh.properties[k] for k in old_mesh.properties if k not in {'boundingBox'}|permitted):
            raise ValueError('Unobserved body mesh property change')
        error=max(abs(a-b) for a,b in zip(native_box(old_mesh),native_box(new_mesh)))
        if error>2e-6:raise ValueError('Native recook bounds changed beyond measured rounding')
        proofs.append(dict(resource=resource,oldMeshSHA256=digest(old),newMeshSHA256=digest(new),bufferSHA256=buffer_hash,vertexIndexBytesIdentical=True,renderSkinLayoutAndMaterialHandlesIdentical=True,shadowMergePolicyExplicitlyFalse=allow_shadow_merge_policy,maximumCookedXYZBoundsRounding=error,oldBoundFourthComponentBytes=native_bound_fourth_components(old_mesh),newBoundFourthComponentBytes=native_bound_fourth_components(new_mesh)))
    original=ROOT/new_package['directory'];manifest=verify_package(original)
    if manifest['baseCommit']!=pin:raise ValueError('New package Base pin differs')
    name='mod0000MaleModBodyBoundary';output=ROOT/'publish'/('body-material-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
    destination=output/'Mods'/name;destination.parent.mkdir(parents=True)
    shutil.copytree(original/'Mods'/manifest['project'],destination)
    manifest['repackagedFrom']=original.relative_to(ROOT).as_posix();manifest['repackagerSHA256']=digest(Path(__file__));manifest['project']=name
    manifest['files']=[dict(path=p.relative_to(output).as_posix(),sha256=digest(p),bytes=p.stat().st_size) for p in sorted(destination.rglob('*')) if p.is_file()]
    write_json(output/'build-manifest.json',manifest);verify_package(output)
    receipt=dict(baseCommit=pin,package=output.relative_to(ROOT).as_posix(),bodyJob=job.relative_to(ROOT).as_posix(),previousBodyJob=selection['bodyJob'],selectionChanges=dict(bodyPackage=output.relative_to(ROOT).as_posix(),bodyJob=job.relative_to(ROOT).as_posix()),shadowMergePolicyExperiment=allow_shadow_merge_policy,runtimeSelectionModified=False,releaseFilesModified=False,installed=False,observedGameplay=False,resources=proofs)
    write_json(job/'material-patch-stage.json',receipt)
    print('Staged encoding-corrected priority package:',output)
    print('Preserve every selection field; replace only bodyPackage/bodyJob with selectionChanges from',job/'material-patch-stage.json')
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--job',type=Path,required=True)
    p.add_argument('--allow-shadow-merge-policy',action='store_true',help='Require only the supported explicit false merge flag; retain all native shadow chunk/layout bytes')
    a=p.parse_args();stage(a.job,a.allow_shadow_merge_policy)
