"""Stage a verified body package and native contracts for managed installation."""
import argparse,shutil,time,json,uuid
from pathlib import Path
from mod import ROOT,read_json,write_json,digest,verify_package


def stage(job,bindings,render,profile,fingerprints):
    job,bindings,render,profile,fingerprints=[ROOT/Path(p) for p in [job,bindings,render,profile,fingerprints]]
    original=ROOT/read_json(job/'package.json')['directory'];manifest=verify_package(original)
    pin=read_json(ROOT/'dependencies/base.lock.json')['commit']
    if manifest['baseCommit']!=pin:raise ValueError('Body package differs from Base pin')
    # Resource paths inside the cooked bundles remain untouched. A dedicated
    # early-loading mod folder makes the owned body overrides deterministic.
    name='mod0000MaleModBodyBoundary';output=ROOT/'publish'/('body-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
    destination=output/'Mods'/name;destination.parent.mkdir(parents=True)
    shutil.copytree(original/'Mods'/manifest['project'],destination)
    manifest['repackagedFrom']=original.relative_to(ROOT).as_posix();manifest['repackagerSHA256']=digest(Path(__file__));manifest['project']=name
    manifest['files']=[dict(path=p.relative_to(output).as_posix(),sha256=digest(p),bytes=p.stat().st_size) for p in sorted(destination.rglob('*')) if p.is_file()]
    write_json(output/'build-manifest.json',manifest);verify_package(output)
    release=ROOT/'build/native-runtime-controller/Release'
    for name in ['surface_worker.exe','geralt.bindings','malemod-runtime.profile']:shutil.copy2(profile/name,release/name)
    shutil.copy2(render/'geralt.render',release/'geralt.render');(release/'geralt.render.sha256').write_text(digest(render/'geralt.render')+'\n')
    shutil.copy2(fingerprints/'graphics-owned-fingerprints.bin',release/'graphics-owned-fingerprints.bin')
    write_json(ROOT/'build/full-runtime/current-install.json',dict(profile=profile.relative_to(ROOT).as_posix(),render=render.relative_to(ROOT).as_posix(),bodyPackage=output.relative_to(ROOT).as_posix(),fingerprints=fingerprints.relative_to(ROOT).as_posix(),bindings=bindings.relative_to(ROOT).as_posix()))
    print('Staged managed body/native update:',output)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['job','bindings','render','profile','fingerprints']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();stage(a.job,a.bindings,a.render,a.profile,a.fingerprints)
