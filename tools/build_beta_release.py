"""Package only the frozen, hash-verified managed installation; never installs."""
import argparse, hashlib, json, shutil, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.5.0-beta.1'
DLL = '879972cf06e2a6abca7b74ae3498085eac6e936c1c69cc0f3020f027eac8d216'
def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def inside(root, rel):
    target = (root/rel).resolve()
    if not target.is_relative_to(root.resolve()) or Path(rel).is_absolute() or any(s in ('..','.') for s in Path(rel).parts): raise ValueError('Unsafe managed path')
    return target

def build(output=None):
    native = read(ROOT/'local/native-installation.json'); baseline = read(ROOT/'local/installation.json')
    game = Path(native['game']).resolve()
    if Path(baseline['target']).resolve() != game/'Mods/modMaleMod': raise ValueError('Baseline game mismatch')
    rows = native['files'] + [dict(path='Mods/modMaleMod/'+r['path'],sha256=r['sha256']) for r in baseline['files']]
    if len(native['files']) != 25 or len(baseline['files']) != 5 or len({r['path'].lower() for r in rows}) != 30: raise ValueError('Expected complete 25+5 snapshot')
    if next(r['sha256'] for r in rows if r['path'].endswith('/malemod_witcher.dll')) != DLL: raise ValueError('Runtime is not frozen verified snapshot')
    for r in rows:
        if digest(inside(game,r['path'])) != r['sha256']: raise ValueError('Installed file changed: '+r['path'])
    out = Path(output) if output else ROOT/'publish'/('Witcher3MaleMod-'+VERSION+'-Install')
    if out.exists(): raise ValueError('Choose a fresh package directory')
    out.mkdir(parents=True)
    for r in rows:
        target=inside(out/'payload',r['path']);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(game/r['path'],target)
    for p in (ROOT/'release').iterdir():
        if p.is_file(): shutil.copy2(p,out/p.name)
    supported=[dict(version='0.4.31-baseline',files=rows[25:]),dict(version='verified-manual-20261003',files=rows)]
    prior_path=ROOT/'local/native-backup-20261002-230911/receipt.json'
    if prior_path.exists():
        prior=read(prior_path);old=prior['files']+rows[25:]
        if len({r['path'].lower() for r in old})!=len(old) or any(r['path'] not in {s['path'] for s in rows} for r in old): raise ValueError('Unsupported prior receipt paths')
        supported.append(dict(version='accepted-manual-20261002-230911',files=old))
    package_files=[dict(path=p.name,sha256=digest(p)) for p in sorted(out.iterdir()) if p.is_file()]
    manifest=dict(schema=1,version=VERSION,baseCommit=native['baseCommit'],runtimeSHA256=DLL,files=rows,packageFiles=package_files,supportedManualInstalls=supported)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    hashes=[(p.relative_to(out).as_posix(),digest(p)) for p in sorted(out.rglob('*')) if p.is_file()]
    (out/'SHA256SUMS.txt').write_text(''.join(h+'  '+n+'\n' for n,h in hashes))
    archive=out.parent/(out.name+'.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(out.rglob('*')):
            if p.is_file(): z.write(p,p.relative_to(out))
    receipt=dict(version=VERSION,directory=str(out),archive=str(archive),sha256=digest(archive),bytes=archive.stat().st_size,payloadFiles=len(rows),payloadBytes=sum((out/'payload'/r['path']).stat().st_size for r in rows),nativeReceiptSHA256=digest(ROOT/'local/native-installation.json'),baselineReceiptSHA256=digest(ROOT/'local/installation.json'))
    (out.parent/(out.name+'-receipt.json')).write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2));return out
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output');args=parser.parse_args();build(args.output)
