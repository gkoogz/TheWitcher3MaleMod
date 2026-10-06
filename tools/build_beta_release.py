"""Package only the frozen, hash-verified managed installation; never installs."""
import argparse, hashlib, json, shutil, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
from release_exclusions import assert_release_path
VERSION = '0.5.0-beta.2'
def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def inside(root, rel):
    target = (root/rel).resolve()
    if not target.is_relative_to(root.resolve()) or Path(rel).is_absolute() or any(s in ('..','.') for s in Path(rel).parts): raise ValueError('Unsafe managed path')
    return target

def build(output=None,version=VERSION):
    if version not in ('0.5.0-beta.1','0.5.0-beta.2'): raise ValueError('No frozen verified release profile for this version')
    profile=read(ROOT/'release/profiles'/(version+'.json'))
    if profile.get('schema')!='malemod.frozen-release-profile/1': raise ValueError('Invalid frozen profile')
    native = read(ROOT/'local/native-installation.json'); baseline = read(ROOT/'local/installation.json')
    game = Path(native['game']).resolve()
    if Path(baseline['target']).resolve() != game/'Mods/modMaleMod': raise ValueError('Baseline game mismatch')
    rows = native['files'] + [dict(path='Mods/modMaleMod/'+r['path'],sha256=r['sha256']) for r in baseline['files']]
    if len(native['files']) != profile['nativeCount'] or len(baseline['files']) != profile['baselineCount'] or len({r['path'].lower() for r in rows}) != len(rows): raise ValueError('Expected complete frozen snapshot')
    if rows!=profile['files'] or native['baseCommit']!=profile['baseCommit']: raise ValueError('Managed snapshot differs from frozen release profile')
    if digest(game/'bin/x64_dx12/witcher3.exe')!=profile['gameExecutableSHA256']: raise ValueError('Unsupported game executable')
    dll=profile['runtimeSHA256']
    if next(r['sha256'] for r in rows if r['path'].endswith('/malemod_witcher.dll')) != dll: raise ValueError('Runtime is not frozen verified snapshot')
    for r in rows:
        assert_release_path(r['path'])
        if digest(inside(game,r['path'])) != r['sha256']: raise ValueError('Installed file changed: '+r['path'])
    out = Path(output) if output else ROOT/'publish'/('Witcher3MaleMod-'+version+'-Install')
    if out.exists(): raise ValueError('Choose a fresh package directory')
    out.mkdir(parents=True)
    for r in rows:
        target=inside(out/'payload',r['path']);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(game/r['path'],target)
    for p in (ROOT/'release').iterdir():
        if p.is_file(): shutil.copy2(p,out/p.name)
    supported=profile['supportedManualInstalls']
    package_files=[dict(path=p.name,sha256=digest(p)) for p in sorted(out.iterdir()) if p.is_file()]
    manifest=dict(schema=1,version=version,baseCommit=profile['baseCommit'],runtimeSHA256=dll,gameExecutableSHA256=profile['gameExecutableSHA256'],files=rows,packageFiles=package_files,supportedManualInstalls=supported,developmentRoomExcluded=True,frozenProfileSHA256=digest(ROOT/'release/profiles'/(version+'.json')),sourceCheckpointIsNotPayloadBuild=True)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    hashes=[(p.relative_to(out).as_posix(),digest(p)) for p in sorted(out.rglob('*')) if p.is_file()]
    (out/'SHA256SUMS.txt').write_text(''.join(h+'  '+n+'\n' for n,h in hashes))
    archive=out.parent/(out.name+'.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(out.rglob('*')):
            if p.is_file():
                assert_release_path(p.relative_to(out).as_posix())
                z.write(p,p.relative_to(out))
    receipt=dict(version=version,directory=str(out),archive=str(archive),sha256=digest(archive),bytes=archive.stat().st_size,payloadFiles=len(rows),payloadBytes=sum((out/'payload'/r['path']).stat().st_size for r in rows),nativeReceiptSHA256=digest(ROOT/'local/native-installation.json'),baselineReceiptSHA256=digest(ROOT/'local/installation.json'))
    (out.parent/(out.name+'-receipt.json')).write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2));return out
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output');parser.add_argument('--version',default=VERSION);args=parser.parse_args();build(args.output,args.version)
