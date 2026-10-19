"""Strictly scoped optional texture package for modular native candidates."""
from pathlib import Path
from mod import digest, verify_package

PROJECT = 'mod00000MaleModNeckMaterial'
PATHS = {'Mods/'+PROJECT+'/content/'+name for name in
         ('bundles/blob0.bundle', 'dep.cache', 'metadata.store', 'texture.cache')}


def describe(directory):
    directory = Path(directory).resolve()
    manifest = verify_package(directory)
    rows = manifest['files']
    if manifest['project'] != PROJECT or {r['path'] for r in rows} != PATHS:
        raise ValueError('Expected the four-file texture-only neck package')
    return dict(manifest=str(directory/'build-manifest.json'),
                manifestSHA256=digest(directory/'build-manifest.json'),
                files=[dict(path=r['path'], sha256=r['sha256']) for r in rows])


def identities(descriptor):
    if not descriptor:
        return {}
    rows = descriptor['files']
    if len(rows) != len(PATHS) or {r['path'] for r in rows} != PATHS:
        raise ValueError('Unexpected material package paths')
    return {r['path']: r['sha256'] for r in rows}
