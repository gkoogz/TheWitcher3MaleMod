"""Record actual compiler inputs and the coupled private modular candidate."""
import argparse
import hashlib
from pathlib import Path
import subprocess
from mod import ROOT, digest, read_json, write_json
from native_preview import load_preview
from install_modular_native import coupled_identity


def record(preview, build, base, output):
    preview, build, base, output = [Path(p).resolve() for p in (preview, build, base, output)]
    if output.exists():
        raise ValueError('Use a fresh provenance output')
    game, data = load_preview(preview, verify_files=False)
    bundle = coupled_identity(data)
    for relative, expected in bundle.items():
        if digest(game/relative) != expected:
            raise ValueError('Coupled runtime changed: '+relative)
    if digest(build/'Release/malemod_witcher.dll') != bundle['bin/x64_dx12/malemod-native/malemod_witcher.dll']:
        raise ValueError('Build and native preview DLL differ')
    pin = read_json(ROOT/'dependencies/modular.lock.json')
    for relative, expected in pin['files'].items():
        raw = (base/relative).read_bytes().replace(b'\r\n', b'\n')
        committed = subprocess.check_output(['git', 'show', pin['commit']+':'+relative], cwd=base)
        if hashlib.sha256(raw).hexdigest() != expected or hashlib.sha256(committed).hexdigest() != expected:
            raise ValueError('Shared source differs from module pin: '+relative)
    logs = list((build/'malemod_witcher.dir/Release').glob('*/CL.read.1.tlog'))
    if len(logs) != 1:
        raise ValueError('Expected actual compiler dependency log')
    inputs = set()
    for line in logs[0].read_text(encoding='utf-16').splitlines():
        for value in line.lstrip('^').split('|'):
            path = Path(value)
            if path.is_file() and (path.is_relative_to(base) or path.is_relative_to(ROOT)):
                inputs.add(path)
    if not inputs or not any(p.name.lower() == 'modular_transfer.hpp' for p in inputs):
        raise ValueError('Compiler dependency log lacks the shared modular code')
    files = [dict(path=str(p), sha256=digest(p)) for p in sorted(inputs)]
    logs += list((build/'malemod_witcher.dir/Release').glob('*/CL.command.1.tlog'))
    logs += list((build/'malemod_witcher.dir/Release').glob('*/link.command.1.tlog'))
    value = dict(schema='malemod.modular-build-source/1', sharedSourceRevision=pin['commit'],
        numericalWorkerRevision=pin['numericalWorkerRevision'], coupledArtifacts=bundle,
        adapterRevision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        adapterDirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT)),
        compilerInputs=files, compilerLogs=[dict(path=str(p),sha256=digest(p)) for p in logs],
        modulePinSHA256=digest(ROOT/'dependencies/modular.lock.json'),
        cmakeCacheSHA256=digest(build/'CMakeCache.txt'),
        omissions=['SDK/system headers are identified in the retained compiler logs, not redistributed.',
                   'Game assets, captures, private settings and binary payloads remain local.'],
        fullAttachmentGatePassed=False, installed=False)
    write_json(output,value)
    print(str(output)+' | compiler inputs: '+str(len(files)))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['preview','build','base','output']:
        parser.add_argument('--'+name,type=Path,required=True)
    record(**vars(parser.parse_args()))
