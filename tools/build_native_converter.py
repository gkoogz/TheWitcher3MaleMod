"""Build the version-159 authoring converter from pinned local vendor inputs.

Obtain WolvenKit-7 commit and release archive documented in NATIVE-CONVERTER.md.
Vendor sources and binaries remain ignored; this never edits the game or SDK.
"""
import fnmatch
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET
from mod import ROOT,digest,write_json


def build():
    source=ROOT/'build/research/WolvenKit-7'
    expected='c3c1c2028177de37c97a2706412b499a5c04cbf4'
    if subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()!=expected:
        raise ValueError('WolvenKit source commit differs from the inspected revision')
    archive=ROOT/'build/research/WolvenKit-7.2.0.zip'
    if digest(archive)!='d68d6b04d1bafefd962bb03d784df3784b7ee30744a38349b3769e7496e7d29e':
        raise ValueError('Vendor release archive mismatch')
    # Always derive the two narrow patches from Git's pinned source. Reject
    # other local vendor edits instead of silently compiling unknown code.
    paths=['WolvenKit.CR2W/CR2W/CR2WFile.cs',
           'WolvenKit.CR2W/Types/BufferedTypes/BufferedClasses.cs']
    changed=subprocess.check_output(['git','-C',str(source),'diff','--name-only','HEAD'],text=True).splitlines()
    if set(changed)-set(paths):raise ValueError('Unreviewed vendor source edits')
    for relative in paths:
        original=subprocess.check_output(['git','-C',str(source),'show','HEAD:'+relative],text=True)
        if relative.endswith('CR2WFile.cs'):
            if original.count('version = 162,')!=1:raise ValueError('Unexpected version initializer')
            modified=original.replace('version = 162,','version = 159,')
        else:
            needle='[Ordinal(1001)] [REDBuffer] public CArray<CHandle<IAttachment>> AttachmentsChild { get; set; }'
            if original.count(needle)!=1:raise ValueError('Unexpected CNode schema')
            modified=original.replace(needle,needle+'\n        [Ordinal(1002)] [REDBuffer] public CMatrix4x4 RedkitTransform { get; set; }')
        (source/relative).write_text(modified,encoding='utf-8')
    project=source/'WolvenKit.CR2W';xml=ET.parse(project/'WolvenKit.CR2W.csproj')
    excluded=[e.attrib['Remove'].replace('\\','/') for e in xml.iter('Compile') if 'Remove' in e.attrib]
    files=[p for p in project.rglob('*.cs') if not any(x in p.relative_to(project).parts for x in ['bin','obj'])
           and not any(fnmatch.fnmatchcase(p.relative_to(project).as_posix(),pattern) for pattern in excluded)]
    output=ROOT/'build/research/wkit-current';output.mkdir(exist_ok=True)
    release=ROOT/'build/research/wkit720'
    omitted={'WolvenKit.CR2W.dll','WebView2Loader.dll','discord-rpc.dll','System.Diagnostics.DiagnosticSource.dll'}
    references=[]
    for path in release.glob('*.dll'):
        if path.name in omitted:continue
        target=output/path.name
        if target.exists() and digest(target)!=digest(path):raise ValueError('Changed converter dependency '+path.name)
        if not target.exists():shutil.copy2(path,target)
        references.append(path)
    references.append(Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/System.Numerics.dll'))
    csc=Path('C:/BuildTools/MSBuild/Current/Bin/Roslyn/csc.exe')
    rsp=output/'compile.rsp'
    lines=['/nologo','/target:library','/unsafe','/platform:x64','/define:NGE_VERSION',
           '/out:"'+str(output/'WolvenKit.CR2W.dll')+'"']
    lines += ['/reference:"'+str(p)+'"' for p in references]
    lines += ['"'+str(p)+'"' for p in files+[ROOT/'tools/native/MaleModPhysicsItem.cs']]
    rsp.write_text('\n'.join(lines))
    subprocess.run([str(csc),'@'+str(rsp)],cwd=ROOT,check=True)
    subprocess.run([str(csc),'/nologo','/reference:'+str(output/'WolvenKit.CR2W.dll'),
                    '/out:'+str(output/'MaleModCR2W.exe'),str(ROOT/'tools/native/Cr2wBridge.cs')],check=True)
    write_json(output/'toolchain.json',{'vendorCommit':expected,'writeVersion':159,'readVersions':{'resources':159,'skeleton':161},
        'sourceFiles':len(files),'executableSHA256':digest(output/'MaleModCR2W.exe'),
        'librarySHA256':digest(output/'WolvenKit.CR2W.dll'),
        'patchSourceSHA256':digest(ROOT/'tools/build_native_converter.py')})


if __name__=='__main__':build()
