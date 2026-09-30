"""Compile a runtime-only revision while preserving a verified native package.

Use only when serialized controller fields/classes and native resources are
unchanged. Native cook evidence is inherited explicitly, not claimed as rerun.
"""
import argparse
from mod import *


def build_patch(source, version):
    source = Path(source).resolve()
    manifest = verify_package(source)
    if not (manifest.get('motionBinding') or {}).get('cookedControllerBindingVerified'):
        raise RuntimeError('Source lacks cooked controller evidence')
    workspace = ROOT / 'build/jobs' / ('script-patch-' + uuid.uuid4().hex[:12])
    scripts = workspace / 'scripts/local'
    scripts.mkdir(parents=True)
    script = ROOT / 'probes/runtime/maleModPhysics.ws'
    shutil.copy2(script, scripts / script.name)
    compilation = compile_scripts(settings(), workspace)
    package = ROOT / 'publish' / (time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6])
    package.mkdir()
    script_path = 'Mods/modMaleMod/content/scripts/local/maleModPhysics.ws'
    preserved = []
    for item in manifest['files']:
        target = inside(package, item['path'])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(script if item['path'] == script_path else inside(source, item['path']), target)
        if item['path'] != script_path:
            if digest(target) != item['sha256']:
                raise RuntimeError('Native asset changed during script patch')
            preserved.append(item)
    if script_path not in {item['path'] for item in manifest['files']}:
        raise RuntimeError('Source does not contain the expected controller script')
    manifest.update(version=version, gameplayTested=False)
    manifest['scriptPatch'] = {
        'sourcePackage': source.relative_to(ROOT).as_posix(),
        'sourceManifestSHA256': digest(source / 'build-manifest.json'),
        'sourceScriptSHA256': digest(script), 'nativeFilesPreserved': preserved,
        'serializedControllerLayoutChanged': False,
        'compilation': compilation,
    }
    manifest['files'] = [dict(path=p.relative_to(package).as_posix(), sha256=digest(p), bytes=p.stat().st_size)
                         for p in sorted(package.rglob('*')) if p.is_file()]
    write_json(package / 'build-manifest.json', manifest)
    verify_package(package)
    archive = package.with_suffix('.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as handle:
        for path in sorted(package.rglob('*')):
            if path.is_file(): handle.write(path, path.relative_to(package).as_posix())
    write_json(ROOT / 'publish/latest.json', dict(directory=package.relative_to(ROOT).as_posix(),
               archive=archive.relative_to(ROOT).as_posix(), sha256=digest(archive)))
    print('Built script-only patch:', package)
    return package


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    build_patch(args.source, args.version)
