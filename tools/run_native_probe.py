"""Run one verified native/script probe and remove its temporary owned addon.

The installed anatomy package, game binaries, settings and keys are preserved.
Never launches into an existing session or leaves an import requiring the probe
DLL on future ordinary launches. This is not a full-runtime installation.
"""
import argparse,json,shutil,subprocess,time
from pathlib import Path
from mod import ROOT,settings,digest,read_json,write_json,required_file


def run(native_build='build/native-x64',pose=False):
    cfg=settings();game=cfg['game']
    query=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',
        'Get-Process witcher3 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id'],capture_output=True,text=True)
    if query.stdout.strip():raise RuntimeError('Game is running; preserve its session')
    proof_path=ROOT/('build/probe/native-pose-compile.json' if pose else 'build/probe/native-ready-compile.json')
    workspace=ROOT/('build/probe/native-pose-workspace' if pose else 'build/probe/native-ready-workspace')
    proof=read_json(proof_path)
    source=required_file(ROOT/'probes/native/ready.ws')
    staged=required_file(workspace/'scripts/local/malemod/ready.ws')
    if (source.read_bytes()!=staged.read_bytes() or not proof.get('artifactSHA256')
            or proof.get('ownedSourceHashes',{}).get('local/malemod/ready.ws')!=digest(source)):
        raise RuntimeError('Probe script differs from the compiled input')
    required_file(ROOT/proof['artifact'])
    if digest(ROOT/proof['artifact'])!=proof['artifactSHA256']:
        raise RuntimeError('Compiler artifact differs from proof')
    expected={'local/malemod/ready.ws':source}
    if pose:expected['local/malemod/pose.ws']=required_file(ROOT/'probes/native/pose.ws')
    if proof['ownedSourceHashes']!={name:digest(path) for name,path in expected.items()} or any((workspace/'scripts'/name).read_bytes()!=path.read_bytes() for name,path in expected.items()):
        raise RuntimeError('Complete staged probe sources differ from compiler proof')
    addon=game/'Mods/modMaleModNativeProbe'
    if addon.exists():raise RuntimeError('Owned probe path already exists; do not overwrite it')
    job=ROOT/'build/probe'/('native-live-'+time.strftime('%Y%m%d-%H%M%S'));job.mkdir(parents=True,exist_ok=False)
    installed=addon/'content/scripts/local/malemod/ready.ws'
    installed_files={addon/'content/scripts'/name:path for name,path in expected.items()}
    baseline=read_json(ROOT/'local/installation.json')
    for item in baseline['files']:
        if digest(Path(baseline['target'])/item['path'])!=item['sha256']:
            raise RuntimeError('Installed baseline differs before native probe')
    native_build=(ROOT/native_build).resolve()
    if not native_build.is_relative_to(ROOT/'build'):raise ValueError('Expected an owned native build')
    launcher=required_file(native_build/'Release/launch_native.exe')
    module=required_file(native_build/'Release/malemod_witcher.dll')
    fingerprint=native_build/'Release/graphics-owned-fingerprints.bin'
    fingerprint_hash=None
    if fingerprint.exists():
        from prepare_graphics_fingerprints import COOKED
        spec=read_json(fingerprint.with_suffix('.json'))
        if (digest(fingerprint)!=spec['packetSHA256'] or digest(ROOT/'tools/prepare_graphics_fingerprints.py')!=spec['recipeSHA256'] or digest(ROOT/'tools/packed_mesh_format.py')!=spec['readerSHA256'] or
            any(digest(COOKED/f['resource'])!=f['meshSHA256'] or digest(Path(str(COOKED/f['resource'])+'.1.buffer'))!=f['bufferSHA256'] for f in spec['sources']) or
            spec['installedBundleHashes']!=[f for f in baseline['files'] if f['path'].endswith('.bundle')]):raise RuntimeError('Owned fingerprints differ from verified inputs')
        fingerprint_hash=digest(fingerprint)
    receipt=dict(purpose='Observe script native call and read-only graphics API',
        scriptSHA256=digest(source),ownedSourceHashes=proof['ownedSourceHashes'],compilerProofSHA256=digest(proof_path),
        moduleSHA256=digest(module),launcherSHA256=digest(launcher),modulePath=module.relative_to(ROOT).as_posix(),
        baselineVersion=baseline['version'],fullRuntimeInstalled=False,addonRemoved=False,poseProbe=pose,fingerprintPacketSHA256=fingerprint_hash)
    try:
        installed.parent.mkdir(parents=True,exist_ok=False)
        for target,origin in installed_files.items():shutil.copy2(origin,target)
        result=subprocess.run([str(launcher),str(game/'bin/x64_dx12/witcher3.exe'),str(module)],capture_output=True,text=True,timeout=240)
        (job/'launcher.txt').write_text(result.stdout+'\n'+result.stderr)
        receipt.update(exitCode=result.returncode,output=result.stdout,stderr=result.stderr)
        rows=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
        if rows:receipt['observations']={key:value for row in rows for key,value in row.items()}
        if result.returncode:raise RuntimeError('Native probe launcher failed; inspect '+str(job))
    finally:
        for target,origin in installed_files.items():
            if not target.exists():continue
            if digest(target)!=proof['ownedSourceHashes'][target.relative_to(addon/'content/scripts').as_posix()]:
                write_json(job/'receipt.json',receipt)
                raise RuntimeError('Probe script changed unexpectedly; preserve it for inspection')
            target.unlink()
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
    parser.add_argument('--pose',action='store_true')
    args=parser.parse_args();run(args.native_build,args.pose)
