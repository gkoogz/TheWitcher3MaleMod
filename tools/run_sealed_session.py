"""Run the installed adapter in a noninteractive private Windows station.

No desktop switch, host focus, keyboard/mouse input or test injector is used.
The stock Continue test is the only temporary game script.
"""
import json,shutil,subprocess,time
from mod import ROOT,read_json,write_json,digest,settings

def run():
    game=settings()['game'];installed=read_json(ROOT/'local/native-installation.json')
    if installed['game']!=str(game):raise ValueError('Managed game path differs')
    for f in installed['files']:
        if digest(game/f['path'])!=f['sha256']:raise ValueError('Managed installation hash differs: '+f['path'])
    query=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',
        'Get-Process witcher3 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id'],capture_output=True,text=True)
    if query.stdout.strip():raise ValueError('Preserve the existing game; private test requires a fresh process')
    source=ROOT/'probes/native/autocontinue.ws';proof=read_json(ROOT/'build/probe/native-session-compile.json')
    if proof['exitCode'] or proof['ownedSourceHashes']['local/malemod/autocontinue.ws']!=digest(source):raise ValueError('Stock Continue proof differs')
    addon=game/'Mods/modMaleModContinueTest/content/scripts/local/malemod/autocontinue.ws'
    if addon.exists():raise ValueError('Temporary source exists; preserve it')
    job=ROOT/'build/probe'/('sealed-session-'+time.strftime('%Y%m%d-%H%M%S'));job.mkdir()
    addon.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,addon)
    launcher=ROOT/'build/native-runtime-controller/Release/launch_sealed.exe'
    output=open(job/'launcher.txt','w');errors=open(job/'launcher-errors.txt','w')
    process=subprocess.Popen([str(launcher),str(game/'bin/x64_dx12/witcher3.exe')],stdout=output,stderr=errors,text=True,
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
    receipt=dict(purpose='Private noninteractive game verification',modulePath=str(module),moduleSHA256=digest(module),
        installationReceiptSHA256=digest(ROOT/'local/native-installation.json'),temporaryContinueSource=str(addon),temporaryContinueSHA256=digest(source),
        launcherPID=process.pid,observations=child,injectorUsed=False,physicalDesktopSwitch=False)
    write_json(job/'receipt.json',receipt);print(str(job/'receipt.json'));print(json.dumps(child));return receipt
if __name__=='__main__':run()
