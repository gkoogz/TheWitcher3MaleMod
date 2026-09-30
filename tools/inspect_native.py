"""Dump an owned copy using REDkit, including older native format versions."""
import argparse
from pathlib import Path
import shutil
import uuid
from mod import ROOT, settings, required_file, run_wcc, digest, write_json


def inspect(source):
    source = required_file(Path(source).resolve())
    with source.open('rb') as stream:
        if stream.read(4) != b'CR2W':
            raise ValueError('Expected a native CR2W resource')
    source_hash = digest(source)
    job = ROOT/'build/inspection'/('native-'+uuid.uuid4().hex[:12])
    job.mkdir(parents=True)
    local = job/source.name
    shutil.copy2(source, local)
    if digest(local) != source_hash:
        raise RuntimeError('Native input changed while copying')
    # This commandlet concatenates out + absolute input + '.xml'. Windows'
    # extended path prefix makes that a valid absolute, job-owned output.
    native = run_wcc(settings(), 'dumpfile', ['-file='+str(local), '-out=\\\\?\\'],
                     job, 'inspect-native')
    output = required_file(job/(local.name+'.xml'))
    if digest(source) != source_hash:
        raise RuntimeError('Native input changed during inspection')
    record = dict(source=str(source), sourceSHA256=source_hash, output=str(output),
                  outputSHA256=digest(output), native=native)
    write_json(job/'inspection.json', record)
    print(output)
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    inspect(parser.parse_args().source)
