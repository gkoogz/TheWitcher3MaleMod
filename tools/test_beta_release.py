"""Exercise installer clean/manual-upgrade/exact rollback without launching games."""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile
from mod import ROOT,read_json,digest,settings,write_json
from release_exclusions import assert_release_path


def test(package, previous):
    package=Path(package).resolve();manifest=read_json(package/'manifest.json')
    for p in package.rglob('*'):
        if p.is_file():assert_release_path(p.relative_to(package).as_posix())
    checks=[]
    with tempfile.TemporaryDirectory(prefix='witcher-release-') as temporary:
        root=Path(temporary);game=root/'game';exe=game/'bin/x64_dx12/witcher3.exe';exe.parent.mkdir(parents=True)
        shutil.copy2(settings()['game']/'bin/x64_dx12/witcher3.exe',exe)
        preserve=game/'bin/x64_dx12/malemod-native/preferences.json';preserve.parent.mkdir(parents=True)
        preserve.write_bytes(b'USER PREFERENCES - preserve exactly')
        unrelated=game/'Mods/another-mod.txt';unrelated.parent.mkdir(parents=True);unrelated.write_bytes(b'OTHER MOD')
        def unchanged():
            assert preserve.read_bytes()==b'USER PREFERENCES - preserve exactly'
            assert unrelated.read_bytes()==b'OTHER MOD'
        def action(name,backup=None,success=True):
            args=['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(package/'Manage.ps1'),'-Action',name,'-GamePath',str(game)]
            if backup:args+=['-BackupId',backup]
            result=subprocess.run(args,capture_output=True,text=True)
            if (result.returncode==0)!=success:raise ValueError(name+' unexpected result: '+result.stdout+result.stderr)
            unchanged()
            if success:return re.search(r'Rollback ID: ([0-9a-f]{32})',result.stdout).group(1)
        def verify(rows):
            for row in rows:
                assert digest(game/row['path'])==row['sha256'],row['path']
        clean=action('Install');verify(manifest['files']);checks.append('clean40 install/settings preserved')
        action('Rollback',clean)
        assert all(not (game/r['path']).exists() for r in manifest['files']);checks.append('clean install exact rollback')
        with zipfile.ZipFile(previous) as oldzip:
            old=__import__('json').loads(oldzip.read('manifest.json'))
            for row in old['files']:
                target=game/row['path'];target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(oldzip.read('payload/'+row['path']))
        upgraded=action('Upgrade');verify(manifest['files']);checks.append('beta1 manual30 to beta2 managed40 upgrade')
        action('Rollback',upgraded);verify(old['files'])
        added={r['path'] for r in manifest['files']}-{r['path'] for r in old['files']}
        assert all(not (game/p).exists() for p in added);checks.append('exact30 rollback/removal of added10')
        action('Upgrade');verify(manifest['files'])
        current=action('Upgrade');verify(manifest['files'])
        action('Rollback',current);verify(manifest['files']);checks.append('managed40 idempotent upgrade/exact40 rollback')
        original_package=package;package=root/'tampered-package';shutil.copytree(original_package,package)
        (package/'payload'/manifest['files'][0]['path']).write_bytes(b'tampered package payload')
        action('Upgrade',success=False);verify(manifest['files']);package=original_package
        checks.append('tampered package rejected before installed bytes change')
        exe.write_bytes(b'unsupported executable')
        action('Upgrade',success=False);shutil.copy2(settings()['game']/'bin/x64_dx12/witcher3.exe',exe)
        verify(manifest['files']);checks.append('unsupported executable rejected before mutation')
        changed=game/manifest['files'][0]['path'];saved=changed.read_bytes();changed.write_bytes(b'unknown changed proxy')
        action('Upgrade',success=False);assert changed.read_bytes()==b'unknown changed proxy';changed.write_bytes(saved)
        checks.append('edited managed file refused/preserved')
        removed=action('Uninstall');assert all(not (game/r['path']).exists() for r in manifest['files'])
        action('Rollback',removed);verify(manifest['files']);checks.append('uninstall/rollback complete40/preferences preserved')
    proof=dict(schema='malemod.beta-package-test/1',version=manifest['version'],checks=checks,passed=True,
        packageManifestSHA256=digest(package/'manifest.json'),gameLaunched=False,
        gameplayEvidenceSeparate='provenance/frozen-beta2-delivery.json')
    write_json(ROOT/'build/release-beta2-tests.json',proof);print(proof)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,required=True);parser.add_argument('--previous',type=Path,required=True)
    args=parser.parse_args();test(args.package,args.previous)
