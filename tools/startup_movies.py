"""Build and install a separate startup-video skip from the local REDkit scripts."""
import argparse
import difflib
from pathlib import Path
import shutil
import subprocess
import uuid

import mod


NAME = 'modLocalSkipStartupMovies'
RESOURCE = Path('game/r4Game.ws')
ORIGINAL = "\t\tmenus.PushBack( 'StartupMoviesMenu' );"
REPLACEMENT = '\t\t// Local PC startup: proceed directly to the normal menu queue.'


def files(root):
    return {p.relative_to(root).as_posix(): mod.digest(p)
            for p in sorted(root.rglob('*')) if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true')
    args = parser.parse_args()
    cfg = mod.settings()
    destination = cfg['game'] / 'Mods' / NAME
    if args.install:
        subprocess.run(['powershell', '-NoProfile', '-Command',
                        "if (Get-Process witcher3 -ErrorAction SilentlyContinue) { exit 1 }"],
                       check=True)
        if destination.exists():
            raise RuntimeError('Skip mod already exists; inspect before replacing it')

    # Game-derived scripts remain in ignored build outputs. Only this recipe is authored.
    job = mod.ROOT / 'build/startup-movies' / uuid.uuid4().hex[:12]
    workspace = job / 'workspace'
    workspace.mkdir(parents=True)
    source = cfg['redkit'] / 'r4data/scripts' / RESOURCE
    stock = source.read_text(encoding='utf-8-sig')
    if stock.count(ORIGINAL) != 1:
        raise RuntimeError('Startup queue changed; inspect the installed stock script')
    patched = stock.replace(ORIGINAL, REPLACEMENT, 1)
    package = job / 'package' / NAME
    target = package / 'content/scripts' / RESOURCE
    target.parent.mkdir(parents=True)
    target.write_text(patched, encoding='utf-8', newline='\n')
    (job / 'startup.diff').write_text(''.join(difflib.unified_diff(
        stock.splitlines(True), patched.splitlines(True),
        fromfile='stock/game/r4Game.ws', tofile=NAME + '/game/r4Game.ws')),
        encoding='utf-8')

    # Compile the combined currently installed scripts, catching duplicate overrides.
    mods_root = cfg['game'] / 'Mods'
    installed_before = {p.name: files(p) for p in mods_root.iterdir() if p.is_dir()}
    for installed in mods_root.iterdir():
        scripts = installed / 'content/scripts'
        if scripts.is_dir():
            if (scripts / RESOURCE).exists():
                raise RuntimeError('Existing r4Game.ws override requires a merge: ' + str(scripts))
            mod.copy_tree(scripts, workspace / 'scripts')
    mod.copy_tree(package / 'content/scripts', workspace / 'scripts')
    native = mod.compile_scripts(cfg, workspace)
    record = {'name': NAME, 'source': str(source), 'sourceSHA256': mod.digest(source),
              'change': 'Remove only StartupMoviesMenu from PopulateMenuQueueStartupOnce',
              'native': native, 'package': str(package), 'files': files(package),
              'gameplay': 'Not yet observed', 'installed': False}
    if args.install:
        subprocess.run(['powershell', '-NoProfile', '-Command',
                        "if (Get-Process witcher3 -ErrorAction SilentlyContinue) { exit 1 }"],
                       check=True)
        shutil.copytree(package, destination)
        assert files(destination) == record['files'], 'Installed file hash mismatch'
        assert all(files(mods_root / name) == hashes
                   for name, hashes in installed_before.items()), 'Existing mod changed'
        record.update(installed=True, destination=str(destination))
        mod.write_json(mod.ROOT / 'local/startup-movies-install.json', record)
    mod.write_json(job / 'verification.json', record)
    print('Installed:' if args.install else 'Verified package:', destination if args.install else package)
    print('Receipt:', job / 'verification.json')


if __name__ == '__main__':
    main()
