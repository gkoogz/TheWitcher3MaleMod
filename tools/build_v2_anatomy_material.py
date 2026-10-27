"""Import and cook only the fresh owned v2 source-skin material job."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import struct
import zipfile
import xml.etree.ElementTree as ET
import mod
from mod import ROOT, digest, read_json, write_json
from v2_cloth_material import native_objects
from v2_skin_material import GRAPH, inspect

JOB = ROOT / 'v2/build/materials/anatomy-01'


def complete_depot(cfg):
    """SDK graph resources plus verified vanilla maps, never fallback images."""
    record = JOB / 'build/complete-depot.json'
    if record.exists():
        saved = read_json(record)
        view = Path(saved['directory'])
        if not view.resolve().is_relative_to((JOB / 'build').resolve()):
            raise ValueError('Complete material depot leaves owned job')
        for row in saved['stockTextures']:
            if digest(Path(row['source'])) != row['sha256'] or digest(view / row['relative']) != row['sha256']:
                raise ValueError('Verified stock skin dependency changed')
        return view
    support = JOB / 'build/sdk-stock-support'
    paths = ['characters/models/geralt/body/model/body_01_mg__geralt_' + key + '.xbm' for key in ['d01','n01','a01']]
    paths += ['characters/models/common/textures/detailmaps_pbr/detailmap_skin_02.xbm']
    rows = []
    for relative in paths:
        source = cfg['depot'] / relative
        target = support / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        rows.append(dict(relative=relative, source=str(source), sha256=digest(source)))
    view = mod.readthrough_depot(cfg['redkit'] / 'r4data', support)
    write_json(record, dict(directory=str(view), stockTextures=rows, SDKUntouched=True))
    return view


def configure_groups(cfg):
    original = cfg['depot'] / 'engine/textures/texturegroups.xml'
    root = ET.fromstring(original.read_bytes())
    for name, compression in [('V2AnatomyColor', 'TCM_QualityColor'), ('V2AnatomyNormal', 'TCM_NormalsHigh')]:
        if any(g.attrib.get('name') == name for g in root):
            raise ValueError('Source texture group namespace collision')
        group = ET.SubElement(root, 'group', name=name)
        for tag, value in [('compression', compression), ('maxsize', '4096'), ('resizable', '0'), ('category', 'Characters')]:
            ET.SubElement(group, tag, value=value)
    ET.indent(root)
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def texture_properties(path):
    reader, imports, objects = native_objects(path)
    if imports or [o[0] for o in objects] not in [['CBitmapTexture'], ['CBitmapTexture', 'CSourceTexture']]:
        raise ValueError('Unobserved source skin texture resource')
    p = objects[0][2]
    result = {k: struct.unpack('<I', p[k][1])[0] for k in ['width', 'height']}
    result.update({k: reader.names[struct.unpack('<H', p[k][1])[0]] for k in ['compression', 'textureGroup']})
    if result['width'] != 4096 or result['height'] != 4096:
        raise ValueError('Native source texture lost its 4096 resolution')
    if len(objects) == 2:
        source = objects[1][2]
        if any(struct.unpack('<I', source[k][1])[0] != v for k, v in [('width',4096),('height',4096),('pitch',16384)]):
            raise ValueError('Native source texture raw extent differs')
    return result


def import_assets(textures_path=None, replace=False):
    cfg = mod.settings()
    cfg['depot'] = complete_depot(cfg)
    cfg['base'] = ROOT.parent / 'Work/dependencies/base-wolverine'
    workspace = JOB / 'build/intake'
    graph = workspace / GRAPH
    compiled = read_json(JOB / 'graph-compiled.json')
    if not compiled.get('nativeCompiled') or not compiled.get('compiledPayloadChanged') or compiled['SHA256'] != digest(graph):
        raise ValueError('Native anatomy graph lacks its exact official compiler receipt')
    inspect(graph)
    textures_path = Path(textures_path) if textures_path else JOB / 'source-textures/textures.json'
    if not textures_path.resolve().is_relative_to(JOB.resolve()):
        raise ValueError('Texture receipt leaves owned anatomy job')
    report = read_json(textures_path)
    import_root = JOB / 'build' / ('texture-imports-' + digest(textures_path)[:12])
    groups = configure_groups(cfg)
    group_file = workspace / 'engine/textures/texturegroups.xml'
    group_file.parent.mkdir(parents=True, exist_ok=True)
    group_file.write_bytes(groups)
    assets = workspace / 'characters/malemod/anatomy'
    assets.mkdir(parents=True, exist_ok=True)
    tasks = [row for lod in report['lods'] for row in lod['files']]
    for row in tasks:
        if digest(Path(row['path'])) != row['sha256']:
            raise ValueError('Source anatomy image changed: ' + row['path'])
    prior = mod.ROOT
    mod.ROOT = JOB
    try:
        def do_import(row):
            source = Path(row['path'])
            group = 'V2AnatomyNormal' if row['role'] == 'Normal' else 'V2AnatomyColor'
            target = assets / source.with_suffix('.xbm').name
            scratch = import_root / source.stem
            config = scratch / 'engine/textures/texturegroups.xml'
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_bytes(groups)
            if target.exists():
                if not replace or not target.resolve().is_relative_to(workspace.resolve()):
                    raise ValueError('Use explicit owned replacement for existing texture: ' + str(target))
                texture_properties(target)
            command = mod.run_wcc(cfg, 'import', ['-depot=local', '-file=' + str(source), '-out=' + str(target), '-texturegroup=' + group], scratch, 'v2-anatomy-' + source.stem)
            actual = texture_properties(target)
            if actual['textureGroup'] != group or actual['compression'] != ('TCM_NormalsHigh' if group == 'V2AnatomyNormal' else 'TCM_QualityColor'):
                raise ValueError('Native texture import ignored owned texture group: ' + repr(actual))
            receipt = dict(sourceSHA256=digest(source), path=str(target), SHA256=digest(target), properties=actual, command=command)
            write_json(import_root / (source.stem + '.json'), receipt)
            return receipt
        with ThreadPoolExecutor(max_workers=2) as pool:
            textures = list(pool.map(do_import, tasks))
        fbx = JOB / 'geralt-anatomy.fbx'
        sidecar = fbx.with_suffix('.xml')
        xml = ET.parse(sidecar)
        for material in xml.getroot().find('materials'):
            if material.attrib['name'] == 'Material0':
                continue
            for param in material:
                if param.attrib['name'] == 'RSpecScale2':
                    param.attrib['value'] = '.2'
                if param.attrib['name'] in ['Normal', 'Ambient', 'SpecularColor']:
                    value = param.attrib['value']
                    param.attrib['value'] = value.replace('-natural-', '-').replace('-erect-', '-')
        xml.write(sidecar, encoding='utf-8', xml_declaration=True)
        target = workspace / 'characters/models/geralt/body/model/l_01_mg__body.w2mesh'
        target.parent.mkdir(parents=True, exist_ok=True)
        command = mod.run_wcc(cfg, 'import', ['-depot=local', '-file=' + str(fbx), '-out=' + str(target)], workspace, 'v2-anatomy-body-import')
        result = dict(schema='malemod.witcher-v2-source-skin-import/1', sourceTexturesPath=str(textures_path), sourceTexturesSHA256=digest(textures_path),
                      graphCompilerSHA256=digest(JOB / 'graph-compiled.json'), graphSHA256=digest(graph), textures=textures,
                      mesh=dict(path=str(target), SHA256=digest(target), command=command), nativeGameplayObserved=False)
        write_json(JOB / 'imports.json', result)
        return result
    finally:
        mod.ROOT = prior


def cook(shader_receipt=None):
    cfg = mod.settings()
    cfg['depot'] = complete_depot(cfg)
    cfg['base'] = ROOT.parent / 'Work/dependencies/base-wolverine'
    report = read_json(JOB / 'imports.json')
    graph=JOB/'build/intake'/GRAPH
    graph_proof=read_json(JOB/'graph-compiled.json')
    if digest(graph)!=graph_proof['SHA256'] or report['graphSHA256']!=digest(graph):
        raise ValueError('Officially resaved graph/import provenance differs')
    shaders=None
    if shader_receipt is not None:
        shaders=read_json(shader_receipt)
        if shaders.get('schema')!='malemod.witcher-v2-source-skin-shaders/1' or not shaders['files'] or shaders['graphSHA256']!=digest(graph) or shaders['command']['exitCode']!=0:
            raise ValueError('Shader cache does not compile the exact current graph')
        for row in shaders['files']:
            path=Path(row['path'])
            if path.name!='shaderDx12_0.cache' or path.stat().st_size!=row['bytes'] or digest(path)!=row['SHA256']:
                raise ValueError('Unobserved or changed native source shader cache')
    if digest(Path(report['mesh']['path'])) != report['mesh']['SHA256']:
        raise ValueError('Imported body changed')
    for row in report['textures']:
        if digest(Path(row['path'])) != row['SHA256']:
            raise ValueError('Imported source texture changed')
    lock = read_json(ROOT / 'dependencies/base.lock.json')
    lock['commit'] = '47023a7f53d794cff84f2f423ba6a7d1fb98ec0f'
    write_json(JOB / 'dependencies/base.lock.json', lock)
    prior = mod.ROOT
    mod.ROOT = JOB
    try:
        # Carry the exact already-owned torso, bare entities and all canonical
        # jockstrap material carriers into this standalone replacement package.
        previous = ROOT / 'v2/build/standalone-assets-02/build/intake'
        lower = Path('characters/models/geralt/body/model/l_01_mg__body.w2mesh')
        retained = []
        for source in sorted(previous.rglob('*')):
            if not source.is_file() or source.suffix in ['.db', '.db-shm', '.db-wal']:
                continue
            relative = source.relative_to(previous)
            if relative == lower:
                continue
            target = JOB / 'build/intake' / relative
            if target.exists() and digest(target) != digest(source):
                raise ValueError('Retained standalone asset collides with fresh job: ' + str(relative))
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            retained.append(dict(path=relative.as_posix(), sha256=digest(source)))
        project = dict(name='mod000000WitcherV2', version='2.0.0-source-skin', platform='pc', cacheBuilders=['textures'], reuseReadOnlyDepot=True,
                       scope='Original Wolverine UV and natural/erect maps on native Geralt body sections; canonical geometry and worker unchanged')
        package = mod.build(cfg, project, JOB / 'build/intake')
        manifest = read_json(package / 'build-manifest.json')
        if shaders:
            content=package/'Mods/mod000000WitcherV2/content'
            for row in shaders['files']:
                target=content/Path(row['path']).name
                if target.exists():raise ValueError('Refusing to replace an existing packaged cache')
                shutil.copy2(row['path'],target)
                manifest['files'].append(dict(path=target.relative_to(package).as_posix(),sha256=digest(target),bytes=target.stat().st_size))
            manifest['files'].sort(key=lambda row:row['path'])
            manifest['nativeCommands'].append(shaders['command'])
            manifest['shaderCompilation']=dict(receiptPath=str(shader_receipt),receiptSHA256=digest(Path(shader_receipt)),graphSHA256=digest(graph),allMaterialsScan=False)
            write_json(package/'build-manifest.json',manifest)
            archive=package.with_suffix('.zip')
            with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as output:
                for path in sorted(package.rglob('*')):
                    if path.is_file():output.write(path,path.relative_to(package).as_posix())
            write_json(JOB/'publish/latest.json',dict(directory=package.relative_to(JOB).as_posix(),archive=archive.relative_to(JOB).as_posix(),sha256=digest(archive)))
        command = next(c for c in manifest['nativeCommands'] if c['command'] == 'cook')
        cooked = Path(next(a.split('=', 1)[1] for a in command['args'] if a.startswith('-outdir=')))
        previous_info = read_json(ROOT / 'v2/build/standalone-assets-02/package.json')
        result = dict(directory=str(package), cooked=str(cooked), importsSHA256=digest(JOB / 'imports.json'), retainedAssets=retained,
                      stockEntitySHA256=previous_info['stockEntitySHA256'],entitySHA256=previous_info['entitySHA256'],nativeGameplayObserved=False)
        if shaders:result['shaderCompilation']=manifest['shaderCompilation']
        write_json(JOB / 'package.json', result)
        return result
    finally:
        mod.ROOT = prior


def import_specular(textures_path):
    """Refresh only the two source specular maps; preserve native geometry."""
    cfg=mod.settings();cfg['depot']=complete_depot(cfg)
    textures_path=Path(textures_path);bake=read_json(textures_path)
    if bake.get('sourceSpecularSRGB')is not True:raise ValueError('Specular refresh requires source sRGB bake')
    previous=read_json(JOB/'imports.json');graph=JOB/'build/intake'/GRAPH
    compiled=read_json(JOB/'graph-compiled.json')
    if inspect(graph)['SHA256']!=compiled['SHA256']:raise ValueError('Graph was not officially resaved')
    if digest(Path(previous['mesh']['path']))!=previous['mesh']['SHA256']:raise ValueError('Native imported geometry changed')
    old={Path(row['path']).name:row for row in previous['textures']};results=[]
    groups=configure_groups(cfg);scratch_root=JOB/'build/specular-srgb-import'
    prior=mod.ROOT;mod.ROOT=JOB
    try:
        for lod in bake['lods']:
            for row in lod['files']:
                source=Path(row['path']);name=source.with_suffix('.xbm').name
                if digest(source)!=row['sha256']or name not in old:raise ValueError('Unexpected refreshed source texture')
                retained=old[name];target=Path(retained['path'])
                if digest(target)!=retained['SHA256']:raise ValueError('Owned native texture changed')
                if row['role']!='SourceSpec':
                    if retained['sourceSHA256']!=row['sha256']:raise ValueError('Specular-only refresh changed another source map')
                    results.append(retained);continue
                if not target.resolve().is_relative_to((JOB/'build/intake').resolve()):raise ValueError('Native specular target leaves owned intake')
                scratch=scratch_root/source.stem;config=scratch/'engine/textures/texturegroups.xml';config.parent.mkdir(parents=True,exist_ok=True);config.write_bytes(groups)
                command=mod.run_wcc(cfg,'import',['-depot=local','-file='+str(source),'-out='+str(target),'-texturegroup=V2AnatomyColor'],scratch,'v2-specular-srgb-'+source.stem)
                properties=texture_properties(target)
                if properties['textureGroup']!='V2AnatomyColor'or properties['compression']!='TCM_QualityColor':raise ValueError('Native specular import changed texture contract')
                result=dict(sourceSHA256=digest(source),path=str(target),SHA256=digest(target),properties=properties,command=command)
                write_json(scratch_root/(source.stem+'.json'),result);results.append(result)
        if len(results)!=10:raise ValueError('Specular refresh lost retained native textures')
        report=dict(previous,sourceTexturesPath=str(textures_path),sourceTexturesSHA256=digest(textures_path),
                    graphCompilerSHA256=digest(JOB/'graph-compiled.json'),graphSHA256=digest(graph),textures=results,
                    refresh=dict(kind='source sRGB specular encoding only',bodyReimported=False,unchangedTextureCount=8))
        write_json(JOB/'imports.json',report);return report
    finally:mod.ROOT=prior


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['import', 'import-specular', 'cook'])
    parser.add_argument('--textures', type=Path)
    parser.add_argument('--replace-owned-textures', action='store_true')
    parser.add_argument('--shader-receipt',type=Path)
    args = parser.parse_args()
    print(json.dumps(import_assets(args.textures, args.replace_owned_textures) if args.action == 'import' else import_specular(args.textures)if args.action=='import-specular'else cook(args.shader_receipt), indent=2))
