"""Load the usual save through stock menu code and verify native full-solver callbacks.

Temporary scripts are removed after compilation; no key bindings or saves are
written. This does not claim rendering replacement or production contacts.
"""
import argparse,json,shutil,subprocess,time
from pathlib import Path
from mod import ROOT,settings,digest,read_json,write_json,required_file

def run(profile_path=ROOT/'build/full-runtime/runtime-profile-166cb02',render_path=ROOT/'build/full-runtime/render-contract-166cb02-v2'):
    game=settings()['game']
    query=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',
        'Get-Process witcher3 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id'],capture_output=True,text=True)
    if query.stdout.strip():raise RuntimeError('Close the existing game before the new module is loaded')
    proof=read_json(ROOT/'build/probe/native-session-compile.json')
    sources={f'local/malemod/{n}.ws':ROOT/f'probes/native/{n}.ws' for n in ['runtime','autocontinue']}
    render=Path(render_path).resolve();render_manifest=read_json(render/'manifest.json')
    if not render.is_relative_to(ROOT/'build') or digest(render/'render_bones.ws')!=render_manifest['boneSourceSHA256'] or digest(render/'geralt.render')!=render_manifest['packetSHA256']:raise ValueError('Render contract proof differs')
    sources['local/malemod/render_bones.ws']=render/'render_bones.ws'
    if proof['exitCode'] or proof['scriptImportsStubbed'] or proof['ownedSourceHashes']!={n:digest(p) for n,p in sources.items()}:
        raise ValueError('Session source differs from official compiler proof')
    if digest(ROOT/proof['artifact'])!=proof['artifactSHA256']:raise ValueError('Compiler artifact differs')
    baseline=read_json(ROOT/'local/installation.json')
    def intact():return all(digest(Path(baseline['target'])/f['path'])==f['sha256'] for f in baseline['files'])
    if not intact():raise ValueError('Installed baseline differs before session')
    profile=Path(profile_path).resolve();manifest=read_json(profile/'manifest.json')
    if render_manifest['baseCommit']!=manifest['baseCommit'] or render_manifest['bindingsSHA256']!=manifest['bindingsSHA256']:raise ValueError('Render/profile pins differ')
    if not profile.is_relative_to(ROOT/'build'):raise ValueError('Use an owned runtime profile')
    release=ROOT/'build/native-runtime-controller/Release'
    for name,field in [('malemod-runtime.profile','packetSHA256'),('surface_worker.exe','workerSHA256'),('geralt.bindings','bindingsSHA256')]:
        if digest(profile/name)!=manifest[field]:raise ValueError('Runtime profile dependency differs')
        target=release/name
        if target.exists() and digest(target)!=manifest[field]:raise ValueError('Existing runtime dependency differs; preserve it')
        if not target.exists():shutil.copy2(profile/name,target)
    target=release/'geralt.render'
    if target.exists() and digest(target)!=render_manifest['packetSHA256']:raise ValueError('Existing render contract differs; preserve it')
    if not target.exists():shutil.copy2(render/'geralt.render',target)
    (release/'geralt.render.sha256').write_text(render_manifest['packetSHA256']+'\n')
    addon=game/'Mods/modMaleModNativeSession'
    if addon.exists():raise ValueError('Temporary addon already exists; preserve it')
    job=ROOT/'build/probe'/('native-session-'+time.strftime('%Y%m%d-%H%M%S'));job.mkdir(parents=True,exist_ok=False)
    receipt=dict(purpose='Observe full source/target solver through live script callbacks and stock Continue',
                 moduleSHA256=digest(release/'malemod_witcher.dll'),modulePath=(release/'malemod_witcher.dll').relative_to(ROOT).as_posix(),workerSHA256=manifest['workerSHA256'],
                 profileSHA256=manifest['packetSHA256'],ownedSourceHashes=proof['ownedSourceHashes'],
                 compilerProofSHA256=digest(ROOT/'build/probe/native-session-compile.json'),
                 graphicsReplacement=False,diagnosticSourceContacts=True,fullRuntimeInstalled=False)
    files={addon/'content/scripts'/n:p for n,p in sources.items()}
    try:
        for target,source in files.items():target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        result=subprocess.run([str(required_file(release/'launch_native.exe')),str(game/'bin/x64_dx12/witcher3.exe'),
                               str(required_file(release/'malemod_witcher.dll')),'--render'],capture_output=True,text=True,timeout=240)
        (job/'launcher.txt').write_text(result.stdout+result.stderr)
        receipt.update(exitCode=result.returncode)
        receipt['observations']={k:v for line in result.stdout.splitlines() if line.startswith('{') for k,v in json.loads(line).items()}
        receipt['graphicsReplacement']=receipt['observations'].get('geometryExecutionObserved',False)
        if result.returncode:raise RuntimeError('Session launch failed; inspect '+str(job))
    finally:
        for target,source in files.items():
            if not target.exists():continue
            if digest(target)!=proof['ownedSourceHashes'][target.relative_to(addon/'content/scripts').as_posix()]:raise RuntimeError('Temporary source changed; preserve it')
            target.unlink()
        for directory in [addon/'content/scripts/local/malemod',addon/'content/scripts/local',addon/'content/scripts',addon/'content',addon]:
            if directory.exists():directory.rmdir()
        receipt['addonRemoved']=not addon.exists();receipt['baselinePreserved']=intact();write_json(job/'receipt.json',receipt)
    print(json.dumps(receipt,indent=2));return receipt

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--profile',type=Path,default=ROOT/'build/full-runtime/runtime-profile-166cb02');parser.add_argument('--render-contract',type=Path,default=ROOT/'build/full-runtime/render-contract-166cb02-v2');a=parser.parse_args();run(a.profile,a.render_contract)
