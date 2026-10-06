"""Repository-only entry point for the verified transient grey development room."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
from mod import ROOT, digest, read_json, settings, write_json, relative_resource
from release_exclusions import assert_release_path


def adopt_release(manifest_path):
    manifest = read_json(manifest_path)
    if manifest.get('schema') != 1:
        raise ValueError('Expected a released anatomy installation manifest')
    game = settings()['game']
    profile = read_json(ROOT/'release/profiles/0.5.0-beta.2.json')
    expected = {r['path']: r['sha256'] for r in profile['files']}
    rows = manifest['files']
    if {r['path']: r['sha256'] for r in rows} != expected or len(rows) != len(expected):
        raise ValueError('Sandbox adoption requires the complete verified beta.2 payload')
    if digest(game/'bin/x64_dx12/witcher3.exe') != profile['gameExecutableSHA256']:
        raise ValueError('Unsupported game executable; reobserve its native ABI')
    native = []; fallback = []
    for row in rows:
        relative_resource(row['path']); assert_release_path(row['path'])
        if digest(game/row['path']) != row['sha256']:
            raise ValueError('Installed release differs: '+row['path'])
        if row['path'].startswith('Mods/modMaleMod/'):
            fallback.append(dict(path=row['path'][len('Mods/modMaleMod/'):],sha256=row['sha256']))
        else:
            native.append(dict(path=row['path'],sha256=row['sha256']))
    values = {
        'native-installation.json': dict(game=str(game),baseCommit=profile['baseCommit'],
            normalStartup=True,diagnosticSourceContacts=False,files=native,
            baselinePreserved=True,adoptedRelease=manifest['version']),
        'installation.json': dict(target=str(game/'Mods/modMaleMod'),files=fallback,
            adoptedRelease=manifest['version'])}
    for name, value in values.items():
        path=ROOT/'local'/name
        if path.exists() and read_json(path)['files'] != value['files']:
            raise ValueError('Preserve existing different local receipt: '+name)
    for name,value in values.items():
        path=ROOT/'local'/name
        if not path.exists(): write_json(path,value)
    print('PASS installed release adoption; game files were not changed')


def run(command):
    subprocess.run(command,cwd=ROOT,check=True)


def check_delta():
    manifest=read_json(ROOT/'dev/sandbox/manifest.json')
    if manifest.get('hashConvention') != 'UTF-8 text with CRLF normalized to LF':
        raise ValueError('Source delta must declare portable text hashing')
    for row in manifest['sourceFiles']:
        path=ROOT/relative_resource(row['path'])
        raw=path.read_bytes().replace(b'\r\n',b'\n')
        if len(raw)!=row['bytes'] or hashlib.sha256(raw).hexdigest()!=row['sha256']:
            raise ValueError('Source delta changed; refresh manifest: '+row['path'])
    for relative in manifest['sharedInfrastructure']:
        if not (ROOT/relative_resource(relative)).is_file():
            raise ValueError('Shared repository infrastructure missing: '+relative)
    print('PASS portable source delta: '+str(len(manifest['sourceFiles']))+' files; no generated/private inputs')


def build():
    from prepare_iteration_platform import prepare
    from prepare_iteration_human import prepare as prepare_human
    from compile_native_scripts import compile_native
    package=prepare()
    workspace=ROOT/'build/iteration-platform-script/workspace'
    destination=workspace/'scripts/local/malemod/iteration_platform.ws'
    destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'probes/native/iteration_platform.ws',destination)
    proof=compile_native(workspace,('MaleModNativeSealedSession',
        'MaleModNativeTestCheckpoint','MaleModNativePoseSample'))
    write_json(ROOT/'build/iteration-platform-script/compile.json',proof)
    prepare_human()
    cmake=os.environ.get('MALEMOD_CMAKE') or shutil.which('cmake')
    if not cmake:raise ValueError('Add CMake to PATH or set MALEMOD_CMAKE to cmake.exe')
    run([cmake,'-S','dev/sandbox','-B','build/iteration-launch','-A','x64'])
    run([cmake,'--build','build/iteration-launch','--config','Release'])
    write_json(ROOT/'build/sandbox.json',dict(schema='malemod.sandbox-local/1',
        package=str(package),driver='probes/native/iteration_platform.ws',
        compileProof='build/iteration-platform-script/compile.json'))
    print('PASS build; next: python tools/sandbox.py verify')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    actions=parser.add_subparsers(dest='action',required=True)
    adopt=actions.add_parser('adopt-release');adopt.add_argument('--manifest',type=Path,required=True)
    actions.add_parser('build');actions.add_parser('verify')
    actions.add_parser('check-delta')
    shortcut=actions.add_parser('shortcut');shortcut.add_argument('--acceptance',type=Path,required=True)
    args=parser.parse_args()
    if args.action=='check-delta':check_delta()
    elif args.action=='adopt-release':adopt_release(args.manifest)
    elif args.action=='build':build()
    else:
        state=read_json(ROOT/'build/sandbox.json')
        if args.action=='verify':
            from run_iteration_world import launch
            launch(Path(state['package']),driver_source=ROOT/state['driver'],compile_proof=ROOT/state['compileProof'])
        else:
            run(['powershell','-NoProfile','-File','tools/Create-IterationShortcut.ps1',
                '-Package',state['package'],'-Acceptance',str(args.acceptance.resolve()),'-Python',sys.executable])


if __name__=='__main__':main()
