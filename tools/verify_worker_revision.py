"""Prove native worker transport against the current Base API, not old geometry."""
import argparse,subprocess
from pathlib import Path
from mod import ROOT,read_json,digest,write_json,settings

def verify(worker,executable,output,library=None,base=None):
    worker=worker.resolve();executable=executable.resolve();output=output.resolve()
    if not output.is_relative_to(ROOT/'build') or output.exists():raise ValueError('Use a fresh owned proof directory')
    base=Path(base if base else settings()['base']).resolve()
    revision=subprocess.run(['git','-C',str(base),'rev-parse','HEAD'],check=True,capture_output=True,text=True).stdout.strip()
    dirty=subprocess.run(['git','-C',str(base),'status','--porcelain','--untracked-files=no','--','CMakeLists.txt','include','src','malemod_base','legacy','tools','provenance','assets','modules','profiles'],check=True,capture_output=True,text=True).stdout.strip()
    provenance=read_json(base/'provenance/source-surface.json');current=provenance['currentProcessRuntime']
    from worker_adoption import validate_process_library
    library=Path(library).resolve() if library else base/'build/surface-process-verified-cmake/Release/malemod_surface.lib'
    source_proof=validate_process_library(base,library,current,require_clean=not bool(dirty),pin=revision)
    output.mkdir(parents=True)
    result=subprocess.run([str(executable),str(worker)],capture_output=True,text=True,timeout=300)
    report=output/'replay.txt';report.write_text(result.stdout+result.stderr,encoding='utf-8')
    passed=result.returncode==0 and 'byte-identical for 48 frames' in result.stdout
    proof=dict(kind='current-base-api-byte-replay',baseCommit=revision,baseDirty=bool(dirty),baseProvenanceSHA256=digest(base/'provenance/source-surface.json'),librarySHA256=digest(library),workerSHA256=digest(worker),
               executable=executable.relative_to(ROOT).as_posix(),executableSHA256=digest(executable),report=report.relative_to(ROOT).as_posix(),reportSHA256=digest(report),recipeSHA256=digest(Path(__file__)),
               frames=48,byteIdentical=passed,exitCode=result.returncode,wireVersion=current['wireVersion'],behaviorRevision=current['behaviorRevision'],libraryPath=library.relative_to(base).as_posix(),observedGameplay=False)
    if source_proof:proof.update(sourceConsumptionProofPath=source_proof['path'],sourceConsumptionProofSHA256=source_proof['sha256'])
    write_json(output/'manifest.json',proof)
    if not passed:raise RuntimeError('Current Base/native worker replay failed: '+result.stdout+result.stderr)
    print('PASS current Base API/native worker48frame exact replay:',output/'manifest.json')
    if dirty:print('Diagnostic proof: re-run against clean committed Base before profile adoption.')
    return output/'manifest.json'

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--worker',type=Path,required=True);p.add_argument('--executable',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--library',type=Path);p.add_argument('--base',type=Path);a=p.parse_args();verify(a.worker,a.executable,a.output,a.library,a.base)
