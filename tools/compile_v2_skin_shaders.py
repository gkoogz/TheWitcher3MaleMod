"""Validate every single owned skin graph technique with native DX12 DXC.

Resave/cook serialize material data; cookmaterials compiles the native shader
permutations. build_v2_skin_cache.py emits the cache from the final cook DB.
Never scan all materials, replace SDK caches or edit game files.
"""
import argparse
import json
from pathlib import Path
import shutil
import re
import mod
from mod import ROOT,digest,read_json,write_json
from build_v2_anatomy_material import JOB,complete_depot
from v2_skin_material import GRAPH,inspect


def recover_rt_includes(executable,runtime):
    """Recover omitted includes from mutually identical native embedded copies.

    The shipped SDK's sparse plaintext tree includes these files by name but
    omits their bodies. Its executable retains complete preprocessed sources
    with original #line boundaries. No shader expressions/layouts are inferred.
    """
    data=Path(executable).read_bytes()
    recovered=[]
    for name in ['OctEncoding.fx','RTCameraCB.fx','RTCameraRay.fx','include_rtRadianceShared.fx']:
        # The observed native parser resolves shared includes from its flat
        # ../shaders/include root, including Simple.fx's ../../../include path.
        target=(runtime/'include' if name=='include_rtRadianceShared.fx' else runtime/'bin/shaders/include')/name
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():raise ValueError('Refusing to replace an SDK shader include')
        copies=[]
        for match in re.finditer(rb'#line 1 "[^\n\x00"]*'+name.encode()+rb'"\r?\n',data):
            start=match.end();at=start;parts=[]
            while True:
                end=re.search(rb'\x00|#line \d+ "([^\n\x00"]*)"\r?\n',data[at:])
                if end is None:raise ValueError('Embedded shader section is unterminated')
                parts.append(data[at:at+end.start()]);at+=end.end()
                # Consecutive #line markers can remain inside the same file
                # (e.g. a stripped guard); they are not section boundaries.
                if not end.group(1) or not end.group(1).endswith(name.encode()):break
            body=b''.join(parts).strip()
            copies.append((start,body))
        if len(copies)<2 or len({b for _,b in copies})!=1:
            raise ValueError('Embedded shader include has no unique corroborated body: '+name)
        body=copies[0][1]
        if not body or any(c<9 or 13<c<32 or c>126 for c in body):
            raise ValueError('Embedded shader include is not bounded ASCII source')
        guard='MALEMOD_RECOVERED_SDK_'+name.replace('.','_').upper()
        target.write_bytes(('#ifndef '+guard+'\n#define '+guard+'\n').encode()+body+b'\n#endif\n')
        import hashlib
        recovered.append(dict(name=name,embeddedOffsets=[o for o,_ in copies],identicalCopies=len(copies),
                              embeddedBodySHA256=hashlib.sha256(body).hexdigest(),bytes=len(body),
                              path=str(target),SHA256=digest(target),onlyWrapperAdded='duplicate-include guard'))
    return dict(sourceExecutableSHA256=digest(executable),files=recovered,SDKFilesModified=False)


def compile_one(destination,recover_missing_rt=False):
    destination=Path(destination).absolute()
    if destination.exists() or not destination.resolve().is_relative_to((JOB/'build').resolve()):
        raise ValueError('Use a fresh owned anatomy build shader directory')
    graph=JOB/'build/intake'/GRAPH
    proof=read_json(JOB/'graph-compiled.json')
    if not proof.get('nativeCompiled') or proof['SHA256']!=digest(graph):
        raise ValueError('Skin graph is not the exact officially resaved graph')
    inspect(graph)
    destination.mkdir(parents=True)
    workspace=destination/'workspace'
    copied=workspace/GRAPH
    copied.parent.mkdir(parents=True)
    shutil.copy2(graph,copied)
    cfg=mod.settings()
    cfg['depot']=complete_depot(cfg)
    # The compiler also has GetBaseDirectory-relative diagnostic paths. Copy
    # its runtime and tiny include/config trees so even implicit cache/dump
    # writes remain under the owned job, never the SDK installation.
    runtime=destination/'runtime'
    binary=runtime/'bin/x64_RedKit'
    binary.mkdir(parents=True)
    originals=cfg['wcc'].parent
    runtime_files=[]
    for source in sorted(originals.iterdir()):
        if source.is_file() and (source.name=='wcc_lite.exe' or source.suffix.lower()in ['.dll','.hlsl']):
            target=binary/source.name
            shutil.copy2(source,target)
            if digest(source)!=digest(target):raise ValueError('Owned shader compiler runtime differs')
            runtime_files.append(dict(name=source.name,SHA256=digest(target)))
    for directory in ['D3D12_0','crashreporter']:
        if(originals/directory).is_dir():shutil.copytree(originals/directory,binary/directory)
    for directory in ['config','r4config','shaders']:
        if(cfg['redkit']/'bin'/directory).is_dir():shutil.copytree(cfg['redkit']/'bin'/directory,runtime/'bin'/directory)
    for name in ['gameconf.cfg','depot_info.json','io_priority_table.xml','redscripts.ini','splashscreen.bmp']:
        source=cfg['redkit']/'bin'/name
        if source.is_file():shutil.copy2(source,runtime/'bin'/name)
    # Startup uses gameconf's r4data before commandlet overrides. This view is
    # an owned copy at its root; all scoped graph writes use workspace below.
    import subprocess
    subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',
                    '$taskShaderLink=[Console]::In.ReadToEnd()|ConvertFrom-Json; New-Item -ItemType Junction -Path $taskShaderLink.source -Target $taskShaderLink.target -ErrorAction Stop | Out-Null'],
                    input=json.dumps(dict(source=str(runtime/'r4data'),target=str(cfg['depot']))),text=True,check=True,capture_output=True)
    for directory in [runtime/'bin/shadersDump',binary/'shadersDump']:
        directory.mkdir()
    cfg['wcc']=binary/'wcc_lite.exe'
    recovered=recover_rt_includes(cfg['wcc'],runtime) if recover_missing_rt else None
    if recovered:write_json(destination/'recovered-sdk-includes.json',recovered)
    output=destination/'cache'
    output.mkdir()
    prior=mod.ROOT
    mod.ROOT=destination
    try:
        command=mod.run_wcc(cfg,'cookmaterials',['pc_dx12','-material='+GRAPH.replace('/','\\'),'-outDir='+str(output)],workspace,'single-source-skin-dx12-shaders')
    finally:
        mod.ROOT=prior
    files=[dict(path=str(p),SHA256=digest(p),bytes=p.stat().st_size)for p in sorted(output.rglob('*'))if p.is_file()]
    dumps=sorted((runtime/'bin/shadersDump').glob('dump_PC_DX12_*.txt'))
    if len(dumps)!=1:raise ValueError('Native compiler did not emit one bounded technique dump')
    techniques=re.findall(r"Compiled '([^']+)'",dumps[0].read_text())
    log=(destination/command['logPath']).read_text()
    counts=re.findall(r': (\d+) techniques to compile',log)
    if len(counts)!=1 or len(techniques)!=int(counts[0]) or len(set(techniques))!=len(techniques):
        raise ValueError('Native compiler technique inventory is incomplete')
    if not any('MeshSkinned' in t and 'UseInstancing' in t and 'HasExtraStreams' in t for t in techniques):
        raise ValueError('Native skinned instancing with extra streams was not compiled')
    result=dict(schema='malemod.witcher-v2-source-skin-technique-validation/1',graph=GRAPH,graphSHA256=digest(graph),
                compilerInputSHA256=digest(copied),command=command,files=files,allMaterialsScan=False,
                techniqueCount=len(techniques),dumpSHA256=digest(dumps[0]),emittedCache=bool(files),
                runtimeFiles=runtime_files,recoveredSDKIncludes=recovered,SDKFilesModified=False,nativeObserved=False)
    write_json(destination/'compile-validation.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--recover-sdk-rt-includes',action='store_true')
    args=parser.parse_args()
    print(json.dumps(compile_one(args.output,args.recover_sdk_rt_includes),indent=2))
