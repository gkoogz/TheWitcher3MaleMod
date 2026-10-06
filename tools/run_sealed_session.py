"""Run the installed adapter in a noninteractive private Windows station.

No desktop switch, host focus, keyboard/mouse input or test injector is used.
The stock Continue test is the only temporary game script.
"""
import argparse,json,shutil,subprocess,time
from pathlib import Path
from mod import ROOT,read_json,write_json,digest,settings

VERIFICATION_STAGES = list(range(64,117))
VERIFICATION_TIMEOUT_SECONDS = 420

def wait_for_verification(receipt, timeout_seconds=VERIFICATION_TIMEOUT_SECONDS):
    """Observe only this private process's ordered checkpoints, with a deadline.

    This deliberately does not terminate a game or alter focus/audio. The
    delivery recorder owns functional and visual approval of these captures.
    """
    if timeout_seconds <= 0: raise ValueError('Verification timeout must be positive')
    receipt_path = Path(receipt).resolve()
    session = read_json(receipt_path)
    if not receipt_path.is_relative_to((ROOT/'build/probe').resolve()): raise ValueError('Expected owned private receipt')
    child = session['observations']
    if not child['noninteractiveWindowStation'] or child['physicalInputUsed']: raise ValueError('Expected private station')
    trace = Path(session['modulePath']).parent/f"verification-{child['processID']}.jsonl"
    deadline = time.monotonic()+timeout_seconds
    rows = []
    while time.monotonic() < deadline:
        if trace.exists() and trace.stat().st_mtime >= session.get('launchedUnixSeconds',0):
            # The final line can still be in flight while the native logger
            # writes it. Only complete newline-terminated JSON records count.
            lines = trace.read_bytes().splitlines(keepends=True)
            rows = [json.loads(line) for line in lines if line.endswith(b'\n')]
            rows = [row for row in rows if 64 <= row['stage'] <= 116]
            stages = [row['stage'] for row in rows]
            if stages != VERIFICATION_STAGES[:len(stages)]: raise ValueError('Private checkpoint order differs')
            if stages == VERIFICATION_STAGES: break
        time.sleep(.25)
    complete = [row['stage'] for row in rows] == VERIFICATION_STAGES
    result = dict(complete=complete,expectedStages=VERIFICATION_STAGES,
        observedStages=[row['stage'] for row in rows],timeoutSeconds=timeout_seconds,
        lastTelemetry=rows[-1] if rows else None,processID=child['processID'])
    write_json(receipt_path.parent/'wait-status.json',result)
    if not complete: raise TimeoutError('Private verification incomplete; inspect '+str(receipt_path.parent/'wait-status.json'))
    return result

def run(wait=False, timeout_seconds=VERIFICATION_TIMEOUT_SECONDS, *, driver_source=None, compile_proof=None, launcher_path=None, game_arguments=()):
    game=settings()['game'];installed=read_json(ROOT/'local/native-installation.json')
    if installed['game']!=str(game):raise ValueError('Managed game path differs')
    for f in installed['files']:
        if digest(game/f['path'])!=f['sha256']:raise ValueError('Managed installation hash differs: '+f['path'])
    query=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',
        'Get-Process witcher3 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id'],capture_output=True,text=True)
    if query.stdout.strip():raise ValueError('Preserve the existing game; private test requires a fresh process')
    source=Path(driver_source).resolve() if driver_source else ROOT/'probes/native/autocontinue.ws'
    proof_path=Path(compile_proof).resolve() if compile_proof else ROOT/'build/probe/native-session-compile.json'
    if not (source.is_relative_to(ROOT/'probes/native') or source.is_relative_to(ROOT/'build/collar-sessions')) or not proof_path.is_relative_to(ROOT/'build'):raise ValueError('Expected owned driver and compile proof')
    proof=read_json(proof_path)
    if proof['exitCode'] or proof['ownedSourceHashes']['local/malemod/'+source.name]!=digest(source):raise ValueError('Private driver compilation proof differs')
    addon=game/'Mods/modMaleModContinueTest/content/scripts/local/malemod/autocontinue.ws'
    if addon.exists():raise ValueError('Temporary source exists; preserve it')
    job=ROOT/'build/probe'/('sealed-session-'+time.strftime('%Y%m%d-%H%M%S'));job.mkdir()
    addon.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,addon)
    launcher=Path(launcher_path).absolute() if launcher_path else ROOT/'build/native-runtime-controller/Release/launch_sealed.exe'
    if not launcher.is_relative_to(ROOT/'build') or not launcher.is_file():raise ValueError('Expected owned private launcher')
    if any(argument!='-windowed' for argument in game_arguments):raise ValueError('Unreviewed private game startup argument')
    output=open(job/'launcher.txt','w');errors=open(job/'launcher-errors.txt','w')
    launched_seconds=time.time()
    process=subprocess.Popen([str(launcher),str(game/'bin/x64_dx12/witcher3.exe'),*game_arguments],stdout=output,stderr=errors,text=True,
        creationflags=subprocess.CREATE_NO_WINDOW);output.close();errors.close()
    deadline=time.monotonic()+20;line=''
    while time.monotonic()<deadline:
        lines=(job/'launcher.txt').read_text().splitlines()
        if lines:line=lines[0];break
        if process.poll() is not None:break
        time.sleep(.05)
    if not line.startswith('{'):
        error=(job/'launcher-errors.txt').read_text()
        if digest(addon)==digest(source):addon.unlink()
        raise RuntimeError('Private launch failed; inspect '+str(job))
    child=json.loads(line)
    if not child['noninteractiveWindowStation'] or child['physicalInputUsed']:raise ValueError('Private isolation did not verify')
    module=game/'bin/x64_dx12/malemod-native/malemod_witcher.dll'
    receipt=dict(purpose='Private noninteractive game verification',driver=str(source),driverCompileProofSHA256=digest(proof_path),launcherSHA256=digest(launcher),gameArguments=list(game_arguments),modulePath=str(module),moduleSHA256=digest(module),
        installationReceiptSHA256=digest(ROOT/'local/native-installation.json'),temporaryContinueSource=str(addon),temporaryContinueSHA256=digest(source),
        launcherPID=process.pid,observations=child,injectorUsed=False,physicalDesktopSwitch=False,launchedUnixSeconds=launched_seconds,
        expectedVerificationStages=VERIFICATION_STAGES,verificationTimeoutSeconds=timeout_seconds)
    write_json(job/'receipt.json',receipt);print(str(job/'receipt.json'));print(json.dumps(child))
    if wait: wait_for_verification(job/'receipt.json',timeout_seconds)
    return receipt
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wait',action='store_true')
    parser.add_argument('--timeout-seconds',type=float,default=VERIFICATION_TIMEOUT_SECONDS)
    args=parser.parse_args()
    run(args.wait,args.timeout_seconds)
