"""Verify and bind the ordered worker to unchanged character calibration."""
import argparse
import subprocess
from pathlib import Path
from mod import ROOT, digest, read_json, write_json
from worker_adoption import validate_process_library


def validate(path, worker, reference=None):
    proof = read_json(path)
    pin = read_json(ROOT/'dependencies/worker.lock.json')
    if (proof.get('schema') != 'malemod.ordered-worker-adoption/1'
            or proof.get('revision') != pin['commit']
            or proof.get('bindingRevision') != pin['bindingRevision']
            or proof.get('workerSHA256') != digest(worker)
            or proof.get('workerPinSHA256') != digest(ROOT/'dependencies/worker.lock.json')):
        raise ValueError('Worker adoption identity differs')
    if reference is not None and proof.get('referenceSHA256') != digest(reference):
        raise ValueError('Worker parity reference is not the installed worker')
    if set(proof.get('tests', {})) != {'numerical-and-donor-parity', 'split-cadence', 'worker-api'}:
        raise ValueError('Incomplete ordered worker regression')
    for test in proof['tests'].values():
        if test.get('exitCode') != 0:
            raise ValueError('Worker regression failed')
    for item in proof['evidence']:
        if digest(Path(item['path'])) != item['sha256']:
            raise ValueError('Worker evidence changed: '+item['path'])
    source = read_json(proof['sourceProof'])
    if source['sourceCommit'] != pin['commit'] or source['sourceDirty']:
        raise ValueError('Worker requires clean exact source-consumption proof')
    if proof['librarySHA256'] != source['library']['sha256']:
        raise ValueError('Worker linked a different numerical library')
    base = Path(proof['base'])
    validate_process_library(base, base/source['library']['path'],
                             read_json(base/'provenance/source-surface.json')['currentProcessRuntime'],
                             require_clean=True, pin=pin['commit'])
    return proof


def record(build, worker_build, base, native, reference, output):
    build, worker_build, base, native, reference, output = [
        Path(p).resolve() for p in (build, worker_build, base, native, reference, output)]
    if not output.is_relative_to((ROOT/'build').resolve().parent) or output.exists():
        raise ValueError('Use a fresh report under consolidated Work')
    pin = read_json(ROOT/'dependencies/worker.lock.json')
    source_path = base/pin['sourceConsumptionProof']
    source = read_json(source_path)
    cache = (worker_build/'CMakeCache.txt').read_text()
    for key in ('MALEMOD_ALLOW_DIRTY_BASE_DIAGNOSTIC', 'MALEMOD_ALLOW_UNVERIFIED_SURFACE_LIBRARY'):
        if key+':BOOL=OFF' not in cache:
            raise ValueError('Deployment cannot use diagnostic build opt-ins')
    library_line = next(x for x in cache.splitlines() if x.startswith('MALEMOD_SURFACE_LIBRARY:FILEPATH='))
    library = Path(library_line.split('=',1)[1])
    if source['sourceDirty'] or source['sourceCommit'] != pin['commit'] or digest(library) != source['library']['sha256']:
        raise ValueError('Source/library identity is not clean and verified')
    worker = worker_build/'Release/surface_worker.exe'
    tests = {
        'numerical-and-donor-parity': [build/'Release/mechanical_worker_test.exe', worker, reference, native/'geralt.modular-transfer'],
        'split-cadence': [build/'Release/split_cadence_test.exe', worker, native],
        'worker-api': [worker_build/'Release/worker_revision_test.exe', worker],
    }
    output.mkdir(parents=True)
    results = {}
    evidence = [source_path, library, worker_build/'CMakeCache.txt',
                ROOT/'native/surface_worker.cpp', ROOT/'native/mechanical_worker_test.cpp',
                ROOT/'native/split_cadence_test.cpp', ROOT/'native/worker_revision_test.cpp']
    for name, command in tests.items():
        run = subprocess.run([str(p) for p in command], capture_output=True, text=True)
        log = output/(name+'.log')
        log.write_text(run.stdout+run.stderr)
        evidence.extend([log, command[0]])
        if run.returncode:
            raise RuntimeError('Worker regression failed: '+str(log))
        results[name] = dict(exitCode=run.returncode, log=str(log))
    value = dict(schema='malemod.ordered-worker-adoption/1', revision=pin['commit'],
                 base=str(base),
                 bindingRevision=pin['bindingRevision'], workerSHA256=digest(worker),
                 referenceSHA256=digest(reference), librarySHA256=digest(library),
                 workerPinSHA256=digest(ROOT/'dependencies/worker.lock.json'),
                 sourceProof=str(source_path), tests=results,
                 evidence=[dict(path=str(p), sha256=digest(p)) for p in evidence],
                 nativeAttachmentGatePassed=False, installed=False)
    path = output/'proof.json'
    write_json(path,value)
    validate(path, worker, reference)
    print(path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('build','worker-build','base','native','reference','output'):
        parser.add_argument('--'+name, type=Path, required=True)
    record(**vars(parser.parse_args()))
