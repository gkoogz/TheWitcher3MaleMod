"""Stage one coherent pinned body, garment and clinical runtime selection."""
import argparse,shutil
from pathlib import Path
from mod import ROOT,read_json,write_json,digest,settings,base_checkout,verify_package
from prepare_graphics_fingerprints import prepare
from readopt_body_runtime import validate_adoption

def stage(selection):
    path=Path(selection).resolve()
    if not path.is_relative_to(ROOT/'build/full-runtime'):raise ValueError('Expected owned selection')
    selected=read_json(path);pin=base_checkout(settings())['commit']
    inputs={key:ROOT/selected[key] for key in ['profile','render','clinical','garments','garmentCarrier']}
    manifests={key:read_json(directory/('package.json' if key=='garmentCarrier' else 'manifest.json')) for key,directory in inputs.items()}
    if any(m['baseCommit']!=pin for m in manifests.values()):raise ValueError('Selection contains mixed Base revisions')
    if manifests['render']['bindingsSHA256']!=manifests['profile']['bindingsSHA256'] or manifests['garments']['renderSHA256']!=manifests['render']['packetSHA256']:raise ValueError('Binding lineage differs')
    validate_adoption(ROOT/selected['bodyAdoption'],ROOT/selected['bodyPackage'],pin,settings())
    for key in ['clinical','garmentCarrier']:
        package=manifests[key]['package' if key=='clinical' else 'directory']
        if verify_package(ROOT/package)['baseCommit']!=pin:
            from readopt_carrier_runtime import validate
            validate(inputs[key],'clinical' if key=='clinical' else 'garment',pin)
    body=read_json(ROOT/selected['bodyJob']/'package.json')
    prepare(Path(selected['fingerprints']),Path(body['cooked'])/'characters/malemod/body',
        Path(body['cooked'])/'characters/models/geralt/body/model/t_01_mg__body_hires.w2mesh',
        Path(manifests['clinical']['cookRoot'])/'characters/malemod/clinical',
        Path(manifests['garmentCarrier']['cooked'])/'characters/malemod/garments')
    release=ROOT/'build/native-runtime-controller/Release'
    for key,names in [('profile',['surface_worker.exe','geralt.bindings','malemod-runtime.profile']),('render',['geralt.render']),('clinical',['clinical.render']),('garments',['garment.bindings','garment.reactions']),('garmentCarrier',['garment.render'])]:
        for name in names:
            source=inputs[key]/name
            expected=manifests[key]['physicalReactionBinding']['packetSHA256'] if name=='garment.reactions' else manifests[key]['workerSHA256' if name=='surface_worker.exe' else 'bindingsSHA256' if name=='geralt.bindings' else 'packetSHA256']
            if digest(source)!=expected:raise ValueError('Artifact changed: '+name)
            shutil.copy2(source,release/name)
            if name in {'geralt.render','clinical.render','garment.bindings','garment.reactions','garment.render'}:(release/(name+'.sha256')).write_text(expected+'\n')
    shutil.copy2(ROOT/selected['fingerprints']/'graphics-owned-fingerprints.bin',release/'graphics-owned-fingerprints.bin')
    (release/'malemod-overlay.enable').write_text('1\n')
    current=ROOT/'build/full-runtime/current-install.json'
    if current.exists():shutil.copy2(current,path.parent/'selection-before-extended.json')
    write_json(current,selected)
    print('Staged coherent runtime at Base '+pin)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('selection',type=Path);a=p.parse_args();stage(a.selection)
