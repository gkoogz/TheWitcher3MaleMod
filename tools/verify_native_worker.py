"""Prove initialization/admission worker changes preserve the original source bytes."""
import subprocess
from mod import ROOT,digest,read_json,write_json

def verify():
    reference=ROOT/'build/native-x86-motion/Release/surface_worker.exe'
    worker=ROOT/'build/native-runtime-worker/Release/surface_worker.exe'
    exe=ROOT/'build/native-runtime-controller/Release/worker_initialization_test.exe'
    if digest(reference)!=read_json(ROOT/'provenance/full-runtime.json')['poseInputReplayVerification']['workerSHA256']:
        raise ValueError('Historical replay worker differs')
    result=subprocess.run([str(exe),str(reference),str(worker)],capture_output=True,text=True,timeout=120)
    report=ROOT/'build/full-runtime/worker-initialization-test.txt'
    report.write_text(result.stdout+result.stderr)
    if result.returncode or not result.stdout.startswith('PASS: original, direct and initialized workers are byte-identical for 48'):
        raise RuntimeError('Worker equivalence failed: '+str(report))
    proof=dict(referenceWorkerSHA256=digest(reference),workerSHA256=digest(worker),
               executable=exe.relative_to(ROOT).as_posix(),executableSHA256=digest(exe),
               report=report.relative_to(ROOT).as_posix(),reportSHA256=digest(report),
               sourceSHA256=digest(ROOT/'native/worker_initialization_test.cpp'),frames=48,byteIdentical=True,exitCode=result.returncode)
    write_json(ROOT/'build/full-runtime/worker-initialization-test.json',proof)
    print(result.stdout,end='')

if __name__=='__main__':verify()
