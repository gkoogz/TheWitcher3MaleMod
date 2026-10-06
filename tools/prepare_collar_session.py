"""Compose and officially compile a private collar review in the grey room."""
from pathlib import Path
import re,shutil
from mod import ROOT,digest,write_json,read_json,settings
from compile_native_scripts import compile_native
IMPORTS=('MaleModNativeSealedSession','MaleModNativeTestCheckpoint','MaleModNativePoseSample','MaleModNativeSetControl','MaleModNativeGarmentControl','MaleModNativeClinicalControl')

def compile_merged(workspace):
    # Compile the actual complete managed mod set, not just the test extension.
    game=settings()['game'];installed=read_json(ROOT/'local/native-installation.json')
    for row in installed['files']:
        if '/content/scripts/' not in row['path']:continue
        source=game/row['path']
        if digest(source)!=row['sha256']:raise ValueError('Installed script changed')
        relative=row['path'].split('/content/scripts/',1)[1];target=workspace/'scripts'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    fallback=read_json(ROOT/'local/installation.json')
    for row in fallback['files']:
        if '/scripts/' not in row['path']:continue
        source=Path(fallback['target'])/row['path']
        if digest(source)!=row['sha256']:raise ValueError('Rig script changed')
        target=workspace/'scripts'/row['path'].split('/scripts/',1)[1];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    names=set()
    for source in (workspace/'scripts').rglob('*.ws'):names.update(re.findall(r'import function (MaleMod\w+)\(',source.read_text()))
    return compile_native(workspace,tuple(sorted(names)))

def prepare():
    platform=ROOT/'probes/native/iteration_platform.ws';cases=ROOT/'probes/native/collar_cases.ws'
    text=platform.read_text();needle='    if (maleModIterationFloorReady) { SetShowFlag(SHOW_Particles,false); }'
    if text.count(needle)!=1 or text.count('        MaleModIterationWalk();')!=1:raise ValueError('Maintained room bootstrap changed; review composition')
    text=text.replace(needle,needle+'\n    if (maleModIterationStarted) {MaleModCollarCaseStep();return;}')
    text=text.replace('        MaleModIterationWalk();','        // The collar driver owns its later bounded walk.')
    directory=ROOT/'build/collar-sessions/grey';workspace=directory/'workspace';source=workspace/'scripts/local/malemod/collar_integrity.ws'
    source.parent.mkdir(parents=True,exist_ok=True);source.write_text(text+'\n'+cases.read_text())
    proof=compile_merged(workspace)
    write_json(directory/'compile.json',proof);write_json(directory/'composition.json',dict(platformSHA256=digest(platform),casesSHA256=digest(cases),source=str(source),sourceSHA256=digest(source),compilerProofSHA256=digest(directory/'compile.json'),physicalInputUsed=False))
    print(source)

def campaign():
    bootstrap=ROOT/'probes/native/autocontinue.ws';platform=ROOT/'probes/native/iteration_platform.ws';cases=ROOT/'probes/native/collar_cases.ws'
    stock=bootstrap.read_text();marker='@addField(CR4Game)\nprivate var maleModStartRequested : bool;'
    if stock.count(marker)!=1:raise ValueError('Maintained campaign save bootstrap changed')
    stock=stock[stock.index(marker):].replace('MaleModPrivateVerificationStep();','MaleModCollarCampaignStep();')
    room=platform.read_text();walk=room[room.index('class MaleModIterationWalkController'):room.index('function MaleModIterationDisableStudioShadows')]
    prefix='import function MaleModNativeSealedSession() : bool;\nimport function MaleModNativeTestCheckpoint(stage : int) : bool;\n@addField(CR4Game)\nprivate var maleModIterationStarted : bool;\n@addMethod(CR4Game)\nfunction MaleModCollarCampaignStep(){if(!thePlayer || IsPaused()){return;}maleModIterationStarted=true;MaleModCollarCaseStep();}\n'
    directory=ROOT/'build/collar-sessions/campaign';workspace=directory/'workspace';source=workspace/'scripts/local/malemod/collar_integrity.ws';source.parent.mkdir(parents=True,exist_ok=True)
    source.write_text(prefix+stock+'\n'+walk+'\n'+cases.read_text())
    proof=compile_merged(workspace)
    write_json(directory/'compile.json',proof);write_json(directory/'composition.json',dict(bootstrapSHA256=digest(bootstrap),platformSHA256=digest(platform),casesSHA256=digest(cases),source=str(source),sourceSHA256=digest(source),compilerProofSHA256=digest(directory/'compile.json'),physicalInputUsed=False,ordinarySaveWrites=False))
    print(source)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--campaign',action='store_true');a=p.parse_args();campaign() if a.campaign else prepare()
