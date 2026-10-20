"""Strictly scoped optional skin material package for modular native candidates."""
from pathlib import Path
from mod import digest, verify_package

PROJECT = 'mod00000MaleModNeckMaterial'
PATHS = {'Mods/'+PROJECT+'/content/'+name for name in
         ('bundles/blob0.bundle', 'dep.cache', 'metadata.store', 'texture.cache')}
ROOT_PATHS = PATHS | {'Mods/'+PROJECT+'/content/bundles/buffers0.bundle'}


def describe(directory):
    directory = Path(directory).resolve()
    manifest = verify_package(directory)
    rows = manifest['files']
    paths={r['path'] for r in rows}
    if manifest['project'] != PROJECT or paths not in (PATHS,ROOT_PATHS) or len(rows)!=len(paths):
        raise ValueError('Expected the bounded modular skin package, optionally including its body buffer bundle')
    return dict(manifest=str(directory/'build-manifest.json'),
                manifestSHA256=digest(directory/'build-manifest.json'),
                files=[dict(path=r['path'], sha256=r['sha256']) for r in rows])


def identities(descriptor):
    if not descriptor:
        return {}
    rows = descriptor['files']
    paths={r['path'] for r in rows}
    if paths not in (PATHS,ROOT_PATHS) or len(rows)!=len(paths):
        raise ValueError('Unexpected material package paths')
    return {r['path']: r['sha256'] for r in rows}
