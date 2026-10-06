"""Separate measured CClipMap tail authoring bridge; preserves current converter."""
from pathlib import Path
import shutil,subprocess,json
from mod import ROOT,digest,write_json

def build():
    original=ROOT/'build/research/wkit-current'
    proof=json.loads((original/'toolchain.json').read_text())
    for field,name in [('executableSHA256','MaleModCR2W.exe'),('librarySHA256','WolvenKit.CR2W.dll')]:
        if digest(original/name)!=proof[field]:raise ValueError('Original converter differs')
    output=ROOT/'build/iteration-storage/clipmap-bridge-v1';output.mkdir(exist_ok=True)
    for path in original.glob('*.dll'):
        if path.name!='WolvenKit.CR2W.dll':shutil.copy2(path,output/path.name)
    lines=(original/'compile.rsp').read_text().splitlines()
    replaced=0
    for i,line in enumerate(lines):
        if line.startswith('/out:'):lines[i]='/out:"'+str(output/'WolvenKit.CR2W.dll')+'"'
        elif line.endswith('\\Types\\W3\\Partial\\CClipMap.cs"'):
            lines[i]='"'+str(ROOT/'tools/native/IterationClipMap.cs')+'"';replaced+=1
    if replaced!=1:raise ValueError('Expected one original ClipMap schema source')
    rsp=output/'compile.rsp';rsp.write_text('\n'.join(lines))
    compiler=Path('C:/BuildTools/MSBuild/Current/Bin/Roslyn/csc.exe')
    subprocess.run([str(compiler),'@'+str(rsp)],check=True)
    subprocess.run([str(compiler),'/nologo','/reference:'+str(output/'WolvenKit.CR2W.dll'),
        '/out:'+str(output/'MaleModCR2W.exe'),str(ROOT/'tools/native/Cr2wBridge.cs')],check=True)
    if digest(original/'WolvenKit.CR2W.dll')!=proof['librarySHA256']:raise ValueError('Original converter changed')
    write_json(output/'toolchain.json',dict(schema='malemod.iteration-clipmap-bridge/1',
        originalToolchainSHA256=digest(original/'toolchain.json'),
        originalLibrarySHA256=proof['librarySHA256'],writeVersion=159,
        customSchemaSHA256=digest(ROOT/'tools/native/IterationClipMap.cs'),
        executableSHA256=digest(output/'MaleModCR2W.exe'),librarySHA256=digest(output/'WolvenKit.CR2W.dll')))
    print(output)

if __name__=='__main__':build()
