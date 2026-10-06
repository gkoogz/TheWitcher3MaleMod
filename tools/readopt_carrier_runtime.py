"""Readopt unchanged rigid material carriers without relabeling their cook.

The packets contain only observed rigid buffer dimensions, not anatomy or
numerical code. Their original cook and optical receipts remain immutable.
"""
import argparse,copy,shutil,struct
from pathlib import Path
from mod import ROOT,read_json,write_json,digest,settings,base_checkout,verify_package

KINDS={'clinical':('manifest.json','clinical.render','package','modMaleModClinical',b'MMFLD001'),
       'garment':('package.json','garment.render','directory','modMaleModGarments',b'MMCLT001')}

def validate(directory,kind,pin):
    directory=Path(directory).absolute();name,packet,key,project,magic=KINDS[kind]
    m=read_json(directory/name);a=m.get('frozenCarrierAdoption',{})
    source=ROOT/a['source'];original=read_json(source/name)
    package=ROOT/original[key];p=verify_package(package)
    if (a.get('kind')!='frozen-rigid-carrier-runtime-adoption' or m['baseCommit']!=pin
        or a['nativeBuildBaseCommit']!=p['baseCommit'] or original['baseCommit']!=p['baseCommit']
        or a['sourceManifestSHA256']!=digest(source/name)
        or a['packageManifestSHA256']!=digest(package/'build-manifest.json')
        or a['files']!=p['files'] or p['project']!=project or a['recipeSHA256']!=digest(Path(__file__))):
        raise ValueError('Frozen material carrier adoption identity differs')
    expected=copy.deepcopy(original);expected['baseCommit']=pin;expected['frozenCarrierAdoption']=a
    if m!=expected:raise ValueError('Carrier adoption changed an original optical/resource field')
    data=(directory/packet).read_bytes()
    if digest(directory/packet)!=original['packetSHA256'] or data!=(source/packet).read_bytes() or data[:8]!=magic or len(data)!=8+28*len(m['resources']):
        raise ValueError('Carrier ABI/resource packet changed')
    for index,row in enumerate(m['resources']):
        scale=struct.unpack_from('<6fI',data,8+28*index)
        if scale[6]!=384 or any(x<=0 for x in scale[:3]):raise ValueError('Unobserved rigid carrier buffer dimensions')
        path=Path(row['path']) if kind=='clinical' else Path(m['cooked'])/'characters/malemod/garments'/(row['kind']+'.w2mesh')
        path=path if path.is_absolute() else ROOT/path
        if digest(path)!=row['meshSHA256'] or digest(Path(str(path)+'.1.buffer'))!=row['bufferSHA256']:raise ValueError('Rigid carrier mesh/buffer changed')
    job=ROOT/original['authoring'] if kind=='clinical' else source
    required=[job/'authoring.json']+([job/'material-proof.json'] if kind=='garment' else [])
    expected_artifacts=[dict(path=f.relative_to(ROOT).as_posix(),sha256=digest(f)) for f in required]
    if a['authoringArtifacts']!=expected_artifacts:raise ValueError('Carrier authoring proof closure differs')
    for row in a['authoringArtifacts']:
        if digest(ROOT/row['path'])!=row['sha256']:raise ValueError('Frozen carrier authoring/material proof changed')
    if kind=='clinical':
        from prepare_clinical_render import verify_materials
        if verify_materials(ROOT/m['authoring'])!=m['textures']:raise ValueError('Frozen clinical material import changed')
        if digest(settings()['base']/'legacy/wolverine/src/runtime/splat_bakes.bin')!=m['bakeSHA256']:raise ValueError('Clinical bake changed')
    return m

def prepare(source,kind,output):
    source,output=Path(source).absolute(),Path(output).absolute();name,packet,key,project,magic=KINDS[kind]
    if output.exists() or not output.is_relative_to(ROOT/'build/full-runtime') or not source.is_relative_to(ROOT/'build'):raise ValueError('Use fresh owned runtime output and existing authored carrier')
    pin=base_checkout(settings())['commit'];original=read_json(source/name);package=ROOT/original[key];p=verify_package(package)
    if p['project']!=project or p['baseCommit']!=original['baseCommit']:raise ValueError('Original carrier cook differs')
    job=ROOT/original['authoring'] if kind=='clinical' else source
    artifacts=[job/'authoring.json']+([job/'material-proof.json'] if kind=='garment' else [])
    adoption=dict(kind='frozen-rigid-carrier-runtime-adoption',source=source.relative_to(ROOT).as_posix(),sourceManifestSHA256=digest(source/name),
                  nativeBuildBaseCommit=p['baseCommit'],packageManifestSHA256=digest(package/'build-manifest.json'),files=p['files'],
                  authoringArtifacts=[dict(path=f.relative_to(ROOT).as_posix(),sha256=digest(f)) for f in artifacts],
                  recipeSHA256=digest(Path(__file__)),nativeRecooked=False,numericalRuntimeVerified=False,observedGameplay=False)
    m=copy.deepcopy(original);m['baseCommit']=pin;m['frozenCarrierAdoption']=adoption
    output.mkdir(parents=True);shutil.copy2(source/packet,output/packet);write_json(output/name,m);validate(output,kind,pin)
    print('Verified unchanged rigid carrier adoption:',output)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--kind',choices=KINDS,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();prepare(a.source,a.kind,a.output)
