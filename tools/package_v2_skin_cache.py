"""Copy a verified private native package and add its exact compiled DX12 cache."""
import argparse
import json
from pathlib import Path
import shutil
import time
import uuid
import zipfile
from mod import digest,read_json,write_json
from build_v2_anatomy_material import JOB


def package(package_info,shader_receipt,job=None):
    job=Path(job).absolute()if job is not None else JOB
    if not job.resolve().is_relative_to(JOB.parent.resolve()):raise ValueError('Package job leaves owned material work')
    package_info=Path(package_info);shader_receipt=Path(shader_receipt)
    source=read_json(package_info);shaders=read_json(shader_receipt)
    if shaders.get('schema')!='malemod.witcher-v2-source-skin-shaders/1' or not shaders['files'] or shaders['packageInfoSHA256']!=digest(package_info) or shaders['command']['exitCode']!=0:
        raise ValueError('Shader compilation does not bind this exact native package')
    original=Path(source['directory']);manifest=read_json(original/'build-manifest.json')
    recorded={r['path'] for r in manifest['files']}
    if {p.relative_to(original).as_posix()for p in original.rglob('*')if p.is_file()}!=recorded|{'build-manifest.json'}:
        raise ValueError('Native source package contains unrecorded files')
    for row in manifest['files']:
        path=original/row['path']
        if path.stat().st_size!=row['bytes']or digest(path)!=row['sha256']:raise ValueError('Native source package changed')
    for row in shaders['files']:
        path=Path(row['path'])
        if path.name!='shaderDx12_0.cache'or path.stat().st_size!=row['bytes']or digest(path)!=row['SHA256']:
            raise ValueError('Native shader cache changed or unobserved cache filename')
    destination=job/'publish'/(time.strftime('%Y%m%d-%H%M%S')+'-shaders-'+uuid.uuid4().hex[:6])
    shutil.copytree(original,destination)
    content=destination/'Mods/mod000000WitcherV2/content'
    for row in shaders['files']:
        target=content/Path(row['path']).name
        if target.exists():raise ValueError('Refusing to replace a packaged shader cache')
        shutil.copy2(row['path'],target)
        manifest['files'].append(dict(path=target.relative_to(destination).as_posix(),sha256=digest(target),bytes=target.stat().st_size))
    manifest['files'].sort(key=lambda row:row['path'])
    manifest['nativeCommands'].append(shaders['command'])
    compilation=dict(receiptPath=str(shader_receipt),receiptSHA256=digest(shader_receipt),graphSHA256=shaders['graphSHA256'],graphs=shaders.get('graphs',[]),allMaterialsScan=False)
    manifest['shaderCompilation']=compilation
    write_json(destination/'build-manifest.json',manifest)
    archive=destination.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED)as output:
        for path in sorted(destination.rglob('*')):
            if path.is_file():output.write(path,path.relative_to(destination).as_posix())
    result=dict(source,directory=str(destination),shaderCompilation=compilation,
                sourcePackageInfoPath=str(package_info),sourcePackageInfoSHA256=digest(package_info))
    info=job/'package-with-shaders.json';write_json(info,result)
    write_json(job/'publish/latest.json',dict(directory=destination.relative_to(job).as_posix(),archive=archive.relative_to(job).as_posix(),sha256=digest(archive)))
    return dict(packageInfo=str(info),packageInfoSHA256=digest(info),directory=str(destination),files=len(manifest['files']))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-info',type=Path,default=JOB/'package.json')
    parser.add_argument('--shader-receipt',type=Path,required=True)
    parser.add_argument('--job',type=Path)
    args=parser.parse_args();print(json.dumps(package(args.package_info,args.shader_receipt,args.job),indent=2))
