"""Adopt frozen native body resources into a revised numerical Base runtime.

Original cook manifest/commands/material receipts are never relabeled. A
separate runtime receipt proves package bytes and authoring inputs unchanged.
No WCC, native selection, Release staging, install or game process operations.
"""
import argparse,subprocess
from pathlib import Path
from mod import ROOT,settings,base_checkout,read_json,write_json,digest,verify_package

BASE_INPUTS=['assets/wolverine-reference/geometry.npz','assets/materials/wolverine/R14-skin-natural.dds','assets/materials/wolverine/SharedBody-normal.dds','malemod_base/graft.py','malemod_base/part_boundary.py','malemod_base/material_atlas.py','malemod_base/skin_match.py','malemod_base/refinement.py','malemod_base/motion_binding.py','malemod_base/presentation_binding.py']
CHARACTER_INPUTS=['characters/geralt-attachment.json','characters/geralt-runtime-bindings.json','tools/prepare_body_boundary.py','tools/build_body_boundary.py']

def original_hash(repo,commit,path):
    import hashlib
    value=subprocess.run(['git','-C',str(repo),'show',commit+':'+path],check=True,capture_output=True).stdout
    return hashlib.sha256(value).hexdigest()

def text_source_hash(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n',b'\n')).hexdigest()

def artifact_closure(job):
    cooked=Path(read_json(job/'package.json')['cooked'])
    resources=[cooked/'characters/malemod/body/geralt_motion.w2mesh',cooked/'characters/models/geralt/body/model/t_01_mg__body_hires.w2mesh',*sorted((cooked/'characters/malemod/body/overall_overall-stable-layout').glob('*.w2mesh'))]
    if len(resources)!=13:raise ValueError('Exact native body resource family missing')
    artifacts=[job/n for n in ['package.json','manifest.json','material-imports.json','skin-match.json','ambient-match.json','lower.fbx','upper.fbx',*[f'part{i}.npz' for i in range(4)]]]
    authored=read_json(job/'manifest.json')
    if len(authored['sourcePaths'])!=2 or len(authored['sourceHashes'])!=2 or authored['knots']!=37:raise ValueError('Measured two-resource waist authoring contract differs')
    for name,expected in zip(authored['sourcePaths'],authored['sourceHashes']):
        source=Path(name)
        if digest(source)!=expected:raise ValueError('Measured native character export differs')
        artifacts.append(source)
    artifacts.extend([p for resource in resources for p in [resource,Path(str(resource)+'.1.buffer')]])
    materials=read_json(job/'material-imports.json')
    for row in materials['materials']:
        native=job/'intake/characters/malemod/materials'/('body_'+row['channel']+'.xbm')
        if digest(native)!=row['nativeSHA256']:raise ValueError('Accepted material bytes changed')
        artifacts.append(native)
    artifacts.append(ROOT/read_json(ROOT/'characters/geralt-runtime-bindings.json')['rig'])
    return artifacts

def validate_adoption(path,package,pin,cfg):
    receipt=read_json(path);manifest=verify_package(package)
    if (receipt['kind']!='frozen-native-body-runtime-adoption' or receipt['runtimeBaseCommit']!=pin
        or receipt['nativeBuildBaseCommit']!=manifest['baseCommit']
        or receipt['package']!=package.absolute().relative_to(ROOT).as_posix()
        or receipt['packageManifestSHA256']!=digest(package/'build-manifest.json')
        or receipt['files']!=manifest['files']
        or receipt['recipeSHA256']!=digest(Path(__file__))):raise ValueError('Native body runtime adoption identity differs')
    for row in receipt['frozenBaseInputs']:
        if digest(cfg['base']/row['path'])!=row['sha256'] or original_hash(cfg['base'],manifest['baseCommit'],row['path'])!=row['sha256']:raise ValueError('Adopted native body Base authoring input changed')
    for row in receipt['frozenCharacterInputs']:
        if digest(ROOT/row['path'])!=row['sha256'] or text_source_hash(ROOT/row['path'])!=row['sourceSHA256'] or original_hash(ROOT,receipt['nativeBuildAdapterCommit'],row['path'])!=row['sourceSHA256']:raise ValueError('Adopted native body character/recipe changed')
    for row in receipt['nativeArtifacts']:
        if digest(ROOT/row['path'])!=row['sha256']:raise ValueError('Adopted native body material/topology changed')
    # Fixed input set is required; an edited receipt cannot omit a source gate.
    if [r['path'] for r in receipt['frozenBaseInputs']]!=BASE_INPUTS or [r['path'] for r in receipt['frozenCharacterInputs']]!=CHARACTER_INPUTS:raise ValueError('Native body source closure differs')
    job=ROOT/receipt['bodyJob']
    if not job.resolve().is_relative_to((ROOT/'build/body-boundary').resolve()):raise ValueError('Adopted job outside owned body authoring tree')
    if [r['path'] for r in receipt['nativeArtifacts']]!=[p.relative_to(ROOT).as_posix() for p in artifact_closure(job)]:raise ValueError('Native body artifact closure differs')
    materials=read_json(job/'material-imports.json')
    if materials['baseCommit']!=manifest['baseCommit'] or not materials['nativeHandleVerified']:raise ValueError('Native material historical receipt differs')
    return receipt

def prepare(package,job,output,adapter_commit='f0d61b9'):
    cfg=settings();pin=base_checkout(cfg)['commit'];package=package.absolute();job=job.absolute();output=output.absolute()
    adapter_commit=subprocess.run(['git','-C',str(ROOT),'rev-parse',adapter_commit+'^{commit}'],check=True,capture_output=True,text=True).stdout.strip()
    # The body authoring tree is an intentional disk-space junction. Preserve
    # repository-relative provenance while validating its resolved ownership.
    if not output.resolve().is_relative_to((ROOT/'build/full-runtime').resolve()) or output.exists() or not job.resolve().is_relative_to((ROOT/'build/body-boundary').resolve()):raise ValueError('Use fresh owned adoption output and original job')
    manifest=verify_package(package)
    if manifest['project']!='mod0000MaleModBodyBoundary':raise ValueError('Expected accepted priority body package')
    old=manifest['baseCommit'];base_rows=[];character_rows=[]
    for name in BASE_INPUTS:
        value=digest(cfg['base']/name)
        if original_hash(cfg['base'],old,name)!=value:raise ValueError('Native body authoring input changed: '+name)
        base_rows.append(dict(path=name,sha256=value))
    for name in CHARACTER_INPUTS:
        value=digest(ROOT/name)
        source=text_source_hash(ROOT/name)
        if original_hash(ROOT,adapter_commit,name)!=source:raise ValueError('Native character authoring input changed: '+name)
        character_rows.append(dict(path=name,sha256=value,sourceSHA256=source))
    artifacts=artifact_closure(job)
    # Material XBMs and their generation receipts remain at the historical pin.
    materials=read_json(job/'material-imports.json')
    if materials['baseCommit']!=old or not materials['nativeHandleVerified']:raise ValueError('Historical material generation receipt differs')
    receipt=dict(kind='frozen-native-body-runtime-adoption',runtimeBaseCommit=pin,nativeBuildBaseCommit=old,nativeBuildAdapterCommit=adapter_commit,
                 package=package.relative_to(ROOT).as_posix(),packageManifestSHA256=digest(package/'build-manifest.json'),files=manifest['files'],bodyJob=job.relative_to(ROOT).as_posix(),
                 frozenBaseInputs=base_rows,frozenCharacterInputs=character_rows,nativeArtifacts=[dict(path=p.relative_to(ROOT).as_posix(),sha256=digest(p)) for p in artifacts],
                 recipeSHA256=digest(Path(__file__)),nativeRecooked=False,nativeCommandsPreserved=True,materialImportReceiptsPreserved=True,selectionModified=False,installed=False,observedGameplay=False)
    output.mkdir(parents=True);path=output/'manifest.json';write_json(path,receipt);validate_adoption(path,package,pin,cfg)
    print('Verified unchanged native body adopted for revised numerical runtime:',path);return path

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',type=Path,required=True);p.add_argument('--job',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--adapter-commit',default='f0d61b9');a=p.parse_args();prepare(a.package,a.job,a.output,a.adapter_commit)
