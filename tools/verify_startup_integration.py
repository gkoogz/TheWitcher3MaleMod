"""Compile a candidate's scripts together with the other installed mods."""
import argparse
import uuid
from pathlib import Path

import mod


def verify(directory):
    cfg = mod.settings()
    directory = Path(directory).resolve()
    manifest = mod.verify_package(directory)
    job = mod.ROOT / 'build/startup-integration' / uuid.uuid4().hex[:12]
    workspace = job / 'workspace'
    workspace.mkdir(parents=True)
    target = workspace / 'scripts'
    inputs = []
    paths = {}
    mods = cfg['game'] / 'Mods'
    sources = [(p.name, p / 'content/scripts') for p in sorted(mods.iterdir())
               if p.is_dir() and p.name != manifest['project']]
    sources.append((manifest['project'], directory / 'Mods' / manifest['project'] / 'content/scripts'))
    for name, source in sources:
        if not source.is_dir():
            continue
        for script in sorted(source.rglob('*.ws')):
            relative = script.relative_to(source).as_posix()
            if relative in paths:
                raise RuntimeError('Duplicate script override requires a merge: ' + relative)
            paths[relative] = name
            inputs.append(dict(mod=name, path=relative, sha256=mod.digest(script)))
        mod.copy_tree(source, target)
    native = mod.compile_scripts(cfg, workspace)
    for name, source in sources:
        for item in inputs:
            if item['mod'] == name and mod.digest(source / item['path']) != item['sha256']:
                raise RuntimeError('Script input changed during compilation')
    record = dict(package=directory.relative_to(mod.ROOT).as_posix(), inputs=inputs,
                  native=native, observedGameplay=False)
    mod.write_json(job / 'verification.json', record)
    print('PASS combined candidate/installed script compilation:', job / 'verification.json')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    verify(parser.parse_args().directory)
