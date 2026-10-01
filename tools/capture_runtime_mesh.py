"""Launch the current DX12 game through the verified local RenderDoc tool.

This gathers rendering evidence. It does not install a deformation candidate,
change game resources/settings, or interpret an editor ABI as a game ABI.
"""
import argparse,datetime,subprocess,os,re,time,json
from pathlib import Path
from mod import ROOT,settings,required_file,digest,write_json


def launch(tool):
    tool=required_file(Path(tool).resolve())
    if not tool.is_relative_to(ROOT/'build/probe/renderdoc'):
        raise ValueError('Use the owned portable diagnostic tool')
    if digest(tool)!='400cb013ea52b9baa818d69dc0a6341776d2a9560edad5bcc6e200fe8c03806d':
        raise ValueError('Diagnostic executable differs from verified RenderDoc 1.46')
    capture_probe=required_file(tool.parent/'control.exe')
    proof=json.loads(required_file(ROOT/'build/probe/renderdoc/probe-build.json').read_text())
    for path,key in [(capture_probe,'executableSHA256'),(tool.parent/'renderdoc.dll','renderdocDLLSHA256'),
                     (ROOT/'tools/native/renderdoc_target.cpp','sourceSHA256')]:
        if digest(required_file(path))!=proof[key]:raise ValueError('Capture probe provenance differs: '+str(path))
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow=0
    process_query=['powershell','-NoProfile','-Command',
        'Get-Process witcher3 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id']
    if subprocess.run(process_query,capture_output=True,text=True,startupinfo=startup,timeout=10).stdout.strip():
        raise RuntimeError('Witcher is already running; preserve the current session')
    executable=required_file(settings()['game']/'bin/x64_dx12/witcher3.exe')
    # SteamAPI identifies a directly launched title by its real installed ID.
    # Preserve the user's Steam session; never write steam_appid.txt into the game.
    manifest=required_file(settings()['game'].parent.parent/'appmanifest_292030.acf')
    entries=dict(re.findall(r'"([^"\n]+)"\s+"([^"\n]+)"',manifest.read_text()))
    if entries.get('appid')!='292030' or entries.get('installdir')!=settings()['game'].name:
        raise ValueError('Steam manifest does not identify the configured game')
    environment=os.environ.copy()
    environment.update(SteamAppId=entries['appid'],SteamGameId=entries['appid'])
    job=ROOT/'build/probe/runtime-captures'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    job.mkdir(parents=True,exist_ok=False)
    args=[str(tool),'capture','--working-dir',str(executable.parent),
          '--capture-file',str(job/'frame'),str(executable)]
    result=subprocess.run(args,capture_output=True,text=True,startupinfo=startup,timeout=60,env=environment)
    # RenderDoc's successful launch returns its target-control port, not zero.
    record=dict(purpose='Observe native DX12 vertex buffers and skinning; no new deformation',
        toolSHA256=digest(tool),gameExecutableSHA256=digest(executable),
        command=args,targetControlPort=result.returncode,stdout=result.stdout,stderr=result.stderr,
        steamAppID=entries['appid'],steamManifestSHA256=digest(manifest),
        sourceSurfaceBackendInstalled=False,startupObserved=False,
        graphicsAPIReady=False,captureObserved=False)
    write_json(job/'launch.json',record)
    if result.returncode<38920 or result.returncode>38999:
        raise RuntimeError('Capture launch did not return a target-control port: '+result.stdout+' '+result.stderr)
    time.sleep(3)
    probe=subprocess.run(process_query,
        capture_output=True,text=True,startupinfo=startup,timeout=10)
    record['startupObserved']=bool(probe.stdout.strip())
    record['processIDs']=[int(p) for p in probe.stdout.split() if p.isdigit()]
    write_json(job/'launch.json',record)
    if not record['startupObserved']:
        raise RuntimeError('Game exited during startup; no frame capture observed. See '+str(job/'launch.json'))
    if len(record['processIDs'])!=1:raise RuntimeError('Expected exactly one running game process')
    # Capture via the target API only. F12 belongs to the user's existing binding.
    result=subprocess.run([str(capture_probe),str(record['targetControlPort']),str(record['processIDs'][0]),'45','capture'],
        capture_output=True,text=True,startupinfo=startup,timeout=55)
    reports=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    if not reports:raise RuntimeError('Capture probe returned no structured status')
    record['graphicsProbe']=reports[-1]
    record['graphicsAPIReady']=record['graphicsProbe'].get('graphicsAPIReady',False)
    captured=record['graphicsProbe'].get('captureObserved',False)
    if captured:
        frame=Path(record['graphicsProbe']['capturePath']).resolve()
        if not frame.is_relative_to(job.resolve()):raise RuntimeError('Capture is outside the owned job')
        record['captureSHA256']=digest(required_file(frame))
        record['captureObserved']=True
    write_json(job/'launch.json',record)
    if result.returncode or not record['captureObserved']:
        raise RuntimeError('Graphics capture is not ready or no frame was saved; no keyboard capture should be requested. See '+str(job/'launch.json'))
    print('Verified graphics device and saved one diagnostic frame through the API. No key pressed.')
    print('Captures: '+str(job))
    return job


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tool',type=Path,default=ROOT/'build/probe/renderdoc/v1.46/RenderDoc_1.46_64/renderdoccmd.exe')
    args=parser.parse_args();launch(args.tool)
