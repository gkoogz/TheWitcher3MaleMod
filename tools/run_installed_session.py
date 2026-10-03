"""Verify normal executable startup; no injector, keypress or persistent auto-load."""
import ctypes as C,json,os,shutil,subprocess,time
from ctypes import wintypes as W
from mod import ROOT,read_json,write_json,digest,settings

def run():
    cfg=settings();game=cfg['game'];installed=read_json(ROOT/'local/native-installation.json')
    if installed['game']!=str(game):raise ValueError('Installation path differs')
    for f in installed['files']:
        if digest(game/f['path'])!=f['sha256']:raise ValueError('Managed installed hash differs: '+f['path'])
    query=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',
        'Get-Process witcher3 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id'],capture_output=True,text=True)
    if query.stdout.strip():raise ValueError('Existing game must close before normal-startup check')
    source=ROOT/'probes/native/autocontinue.ws';proof=read_json(ROOT/'build/probe/native-session-compile.json')
    if proof['exitCode'] or proof['ownedSourceHashes']['local/malemod/autocontinue.ws']!=digest(source):raise ValueError('Stock Continue compiler proof differs')
    addon=game/'Mods/modMaleModContinueTest/content/scripts/local/malemod/autocontinue.ws'
    if addon.exists():raise ValueError('Temporary Continue source exists; preserve it')
    job=ROOT/'build/probe'/('installed-session-'+time.strftime('%Y%m%d-%H%M%S'));job.mkdir()
    addon.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,addon)
    env=os.environ.copy();env.update(SteamAppId='292030',SteamGameId='292030')
    process=subprocess.Popen([str(game/'bin/x64_dx12/witcher3.exe')],cwd=game/'bin/x64_dx12',env=env)
    k=C.WinDLL('kernel32',use_last_error=True);times=k.GetProcessTimes;times.restype=W.BOOL;times.argtypes=[W.HANDLE,C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME)]
    created,exited,kernel,user=W.FILETIME(),W.FILETIME(),W.FILETIME(),W.FILETIME()
    if not times(int(process._handle),C.byref(created),C.byref(exited),C.byref(kernel),C.byref(user)):raise C.WinError(C.get_last_error())
    module=game/'bin/x64_dx12/malemod-native/malemod_witcher.dll'
    receipt=dict(purpose='Normal installed startup and live output verification',modulePath=str(module),moduleSHA256=digest(module),
        installationReceiptSHA256=digest(ROOT/'local/native-installation.json'),temporaryContinueSource=str(addon),temporaryContinueSHA256=digest(source),
        observations=dict(processID=process.pid,processCreationTime=str((created.dwHighDateTime<<32)|created.dwLowDateTime)),injectorUsed=False)
    write_json(job/'receipt.json',receipt);print(str(job/'receipt.json'));print(json.dumps(receipt['observations']));return receipt
if __name__=='__main__':run()
