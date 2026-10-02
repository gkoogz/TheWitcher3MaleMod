"""Run one verified native/script probe and remove its temporary owned addon.

The installed anatomy package, game binaries, settings and keys are preserved.
Never launches into an existing session or leaves an import requiring the probe
DLL on future ordinary launches. This is not a full-runtime installation.
"""
import argparse,json,shutil,subprocess,time
from pathlib import Path
from mod import ROOT,settings,digest,read_json,write_json,required_file


def run(native_build='build/native-x64'):
    cfg=settings();game=cfg['game']
    query=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',
        'Get-Process witcher3 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id'],capture_output=True,text=True)
    if query.stdout.strip():raise RuntimeError('Game is running; preserve its session')
    proof=read_json(ROOT/'build/probe/native-ready-compile.json')
    source=required_file(ROOT/'probes/native/ready.ws')
    staged=required_file(ROOT/'build/probe/native-ready-workspace/scripts/local/malemod/ready.ws')
    if (source.read_bytes()!=staged.read_bytes() or not proof.get('artifactSHA256')
            or proof.get('ownedSourceHashes',{}).get('local/malemod/ready.ws')!=digest(source)):
        raise RuntimeError('Probe script differs from the compiled input')
    required_file(ROOT/proof['artifact'])
    if digest(ROOT/proof['artifact'])!=proof['artifactSHA256']:
        raise RuntimeError('Compiler artifact differs from proof')
    addon=game/'Mods/modMaleModNativeProbe'
    if addon.exists():raise RuntimeError('Owned probe path already exists; do not overwrite it')
    job=ROOT/'build/probe'/('native-live-'+time.strftime('%Y%m%d-%H%M%S'));job.mkdir(parents=True,exist_ok=False)
    installed=addon/'content/scripts/local/malemod/ready.ws'
    baseline=read_json(ROOT/'local/installation.json')
    for item in baseline['files']:
        if digest(Path(baseline['target'])/item['path'])!=item['sha256']:
            raise RuntimeError('Installed baseline differs before native probe')
    native_build=(ROOT/native_build).resolve()
    if not native_build.is_relative_to(ROOT/'build'):raise ValueError('Expected an owned native build')
    launcher=required_file(native_build/'Release/launch_native.exe')
    module=required_file(native_build/'Release/malemod_witcher.dll')
    receipt=dict(purpose='Observe script native call and read-only graphics API',
        scriptSHA256=digest(source),compilerProofSHA256=digest(ROOT/'build/probe/native-ready-compile.json'),
        moduleSHA256=digest(module),launcherSHA256=digest(launcher),modulePath=module.relative_to(ROOT).as_posix(),
        baselineVersion=baseline['version'],fullRuntimeInstalled=False,addonRemoved=False)
    try:
        installed.parent.mkdir(parents=True,exist_ok=False);shutil.copy2(source,installed)
        result=subprocess.run([str(launcher),str(game/'bin/x64_dx12/witcher3.exe'),str(module)],capture_output=True,text=True,timeout=240)
        (job/'launcher.txt').write_text(result.stdout+'\n'+result.stderr)
        receipt.update(exitCode=result.returncode,output=result.stdout,stderr=result.stderr)
        rows=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
        if rows:receipt['observations']={key:value for row in rows for key,value in row.items()}
        if result.returncode:raise RuntimeError('Native probe launcher failed; inspect '+str(job))
    finally:
        if installed.exists():
            if digest(installed)!=receipt['scriptSHA256']:
                write_json(job/'receipt.json',receipt)
                raise RuntimeError('Probe script changed unexpectedly; preserve it for inspection')
            installed.unlink()
        if addon.exists():
            for directory in [installed.parent,installed.parent.parent,installed.parent.parent.parent,addon/'content',addon]:
                directory.rmdir() # Only the empty directories created by this probe.
        receipt['addonRemoved']=not addon.exists()
        receipt['installedBaselineHashesPreserved']=all(digest(Path(baseline['target'])/f['path'])==f['sha256'] for f in baseline['files'])
        write_json(job/'receipt.json',receipt)
    print(json.dumps(receipt.get('observations',{}),indent=2));print('Probe addon removed; receipt:',job)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-build',default='build/native-x64')
    run(parser.parse_args().native_build)
