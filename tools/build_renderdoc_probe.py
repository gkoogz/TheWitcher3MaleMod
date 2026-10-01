"""Build the diagnostic replay client from verified local RenderDoc headers."""
import argparse,json,subprocess
from pathlib import Path
from mod import ROOT,digest,required_file,write_json

def quoted(path):
    value=str(path)
    if any(c in value for c in '\r\n"%&|<>^!'):raise ValueError('Unsafe compiler path')
    return '"'+value+'"'

def build(vcvars):
    owned=ROOT/'build/probe/renderdoc';api=owned/'api'
    headers=json.loads(required_file(api/'provenance.json').read_text())
    if headers['version']!='v1.46':raise ValueError('Replay header version differs')
    for entry in headers['headers']:
        path=(api/entry['path']).resolve()
        if not path.is_relative_to(api) or digest(required_file(path))!=entry['sha256']:
            raise ValueError('Replay header differs: '+entry['path'])
    directory=owned/'v1.46/RenderDoc_1.46_64'
    source=required_file(ROOT/'tools/native/renderdoc_target.cpp')
    library=required_file(api/'renderdoc.lib')
    executable=directory/'control.exe'
    command=owned/'compile-target.cmd'
    command.write_text('@call '+quoted(required_file(vcvars))+' >nul\n'
        '@if errorlevel 1 exit /b %errorlevel%\n'
        '@cl /nologo /O2 /MT /EHsc /std:c++17 /DRENDERDOC_PLATFORM_WIN32 /I'+quoted(api)+' '
        +quoted(source)+' '+quoted(library)+' /Fo'+quoted(owned/'control.obj')
        +' /Fe'+quoted(executable)+'\n@exit /b %errorlevel%\n',newline='\n')
    result=subprocess.run(['cmd','/d','/c',str(command)],cwd=ROOT,check=True)
    write_json(owned/'probe-build.json',dict(sourceSHA256=digest(source),
        executableSHA256=digest(required_file(executable)),
        renderdocDLLSHA256=digest(required_file(directory/'renderdoc.dll')),
        headerManifestSHA256=digest(api/'provenance.json'),replayMarkerExported=True))
    print(executable)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vcvars',type=Path,default=Path('C:/BuildTools/VC/Auxiliary/Build/vcvars64.bat'))
    build(parser.parse_args().vcvars)
