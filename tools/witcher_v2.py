"""Witcher v2: untouched Geralt base and exact canonical Wolverine reference.

No command in this entry point installs a runtime or revives the archived v1.
"""
import argparse
import contextlib
import csv
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT/'v2'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


def checked_reference():
    lock=read(V2/'wolverine.lock.json')
    roots={name:(ROOT/relative).resolve() for name,relative in lock['checkouts'].items()}
    for name,commit in lock['commits'].items():
        actual=subprocess.check_output(['git','-C',str(roots[name]),'rev-parse','HEAD'],text=True).strip()
        if actual!=commit:
            raise ValueError('Pinned reference checkout changed: '+name)
    for row in lock['files']:
        if sha(roots[row['repository']]/row['path'])!=row['sha256']:
            raise ValueError('Pinned reference source changed: '+row['path'])
    return lock,roots


def prepare_body():
    import numpy as np
    import mod
    from wcc_fbx import Document,triangles
    cfg=mod.settings()
    profile=read(V2/'geralt-base.json')
    destination=V2/'build/geralt-base'
    destination.mkdir(parents=True,exist_ok=True)
    rows=[]
    for row in profile['resources']:
        source=cfg[row['layer']]/row['resource']
        if sha(source)!=row['sha256']:
            raise ValueError('Vanilla input changed: '+row['resource'])
        if row['role']=='bare-entity':
            if b'l_01_mg__body.w2mesh' not in source.read_bytes() or b'l_01_mg__underwear.w2mesh' in source.read_bytes():
                raise ValueError('Starting entity has unexpected mesh references')
            continue
        output=destination/(row['role']+'.fbx')
        provenance=output.with_suffix('.provenance.json')
        if output.exists():
            receipt=read(provenance)
            if receipt['sourceSHA256']!=row['sha256'] or receipt['outputSHA256']!=sha(output):
                raise ValueError('Existing stock export changed: '+str(output))
        else:
            # Native helper uses only a fresh stock depot view. Redirect its
            # scratch root to v2 so v1 generated/workspace can never be an input.
            previous=mod.ROOT
            try:
                mod.ROOT=V2
                mod.export_resource(cfg,row['resource'],output,stock=True)
            finally:
                mod.ROOT=previous
        doc=Document(output)
        lods=[]
        for mesh in doc.meshes:
            vertices=mesh.array('Vertices').reshape(-1,3)
            faces=triangles(mesh)
            if not np.isfinite(vertices).all() or faces.min()<0 or faces.max()>=len(vertices):
                raise ValueError('Invalid native body geometry')
            skin=doc.skin(mesh)
            lods.append(dict(vertices=len(vertices),triangles=len(faces),bones=[n for n,_ in skin],
                positionSHA256=hashlib.sha256(vertices.tobytes()).hexdigest(),
                topologySHA256=hashlib.sha256(faces.tobytes()).hexdigest(),
                bounds=[vertices.min(0).tolist(),vertices.max(0).tolist()]))
        assets={p.name:sha(p) for p in output.parent.glob(output.stem+'.*') if p.is_file()}
        rows.append(dict(role=row['role'],resource=row['resource'],sourceSHA256=row['sha256'],
                         exportSHA256=sha(output),lods=lods,artifacts=assets))
    record=dict(schema='malemod.witcher-v2-geralt-base/1',profileSHA256=sha(V2/'geralt-base.json'),
        vanillaOnly=True,anatomyAttached=False,nativeRoundTripTested=False,observedGameplay=False,
        resources=rows)
    write(destination/'manifest.json',record)
    print('PASS untouched stock Geralt base: '+str(len(rows))+' body parts; anatomy not yet attached')


def build_reference():
    lock,roots=checked_reference()
    work=V2/'build/wolverine-reference';work.mkdir(parents=True,exist_ok=True)
    compiler=Path(os.environ.get('MALEMOD_VCVARS32','C:/BuildTools/VC/Auxiliary/Build/vcvars32.bat'))
    dx=Path(os.environ.get('MALEMOD_DIRECTX_SDK','C:/Program Files (x86)/Microsoft DirectX SDK (June 2010)'))
    if not compiler.is_file() or not (dx/'Include/d3d9.h').is_file():
        raise ValueError('Reference requires the existing x86 MSVC and June2010 DirectX SDK')
    entry=work/'reference_entry.cpp'
    entry.write_text('#define MALEMOD_WOLVERINE_RUNTIME "'+(roots['wolverine']/'src/runtime/d3d9_proxy.cpp').as_posix()+'"\n'
        '#define MALEMOD_WOLVERINE_CPU_BUFFER "'+(roots['wolverine']/'tools/r14/cpu_buffer.h').as_posix()+'"\n'
        '#include "'+(roots['base']/'tools/wolverine_v2_reference.cpp').as_posix()+'"\n')
    executable=work/'reference.exe'
    script=work/'build-reference.cmd'
    script.write_text('@echo off\ncall "'+str(compiler)+'" >nul\nif errorlevel 1 exit /b 1\n'
        'cl.exe /nologo /O2 /fp:precise /MT /EHsc /std:c++17 '
        '/I"'+str(roots['wolverineBase']/'include')+'" '
        '/I"'+str(roots['wolverine']/'third-party')+'" /I"'+str(dx/'Include')+'" '
        '"'+str(entry)+'" /Fo:"'+str(work/'reference.obj')+'" /Fe:"'+str(executable)+'" '
        '/link /LIBPATH:"'+str(dx/'Lib/x86')+'" d3d9.lib d3dx9.lib d3d11.lib d3dcompiler.lib user32.lib gdi32.lib ole32.lib winmm.lib\n'
        'exit /b %ERRORLEVEL%\n',encoding='utf-8')
    log=work/'build.log'
    with log.open('w') as stream:
        result=subprocess.run(['cmd.exe','/d','/c',str(script)],cwd=work,stdout=stream,stderr=subprocess.STDOUT)
    if result.returncode or not executable.is_file():
        raise RuntimeError('Reference build failed; see '+str(log)+'\n'+log.read_text(errors='replace')[-4500:])
    checked_reference()
    record=dict(schema='malemod.wolverine-v2-reference-build/1',lockSHA256=sha(V2/'wolverine.lock.json'),
        executableSHA256=sha(executable),entrySHA256=sha(entry),buildLogSHA256=sha(log),
        architecture='x86',arithmetic='/O2 /fp:precise',canonicalNumericalSourceIncludedDirectly=True,
        installedDLLReproduced=False,nativeGameplayTested=False)
    write(work/'build.json',record)
    print('PASS canonical Wolverine offline reference build')


def reference():
    import numpy as np
    checked_reference()
    work=V2/'build/wolverine-reference';executable=work/'reference.exe'
    build=read(work/'build.json')
    if build['lockSHA256']!=sha(V2/'wolverine.lock.json') or build['executableSHA256']!=sha(executable):
        raise ValueError('Reference build is stale')
    results=[]
    for state in range(3):
        target=work/('state-'+str(state));target.mkdir(exist_ok=True)
        controls=target/'controls.txt';controls.write_text(str(state)+' '+' '.join(['50']*17)+'\n')
        subprocess.run([str(executable),str(controls),str(target),'120'],cwd=work,check=True)
        packed=np.fromfile(target/'anatomy.packed',dtype='u1').reshape(-1,32)
        positions=packed[:,:12].copy().view('<f4').reshape(-1,3)
        if not np.isfinite(positions).all():raise ValueError('Non-finite source reference')
        trace=list(csv.DictReader((target/'frames.csv').open()))
        timings=[float(r['physicsMs'])+float(r['surfaceMs']) for r in trace[30:]]
        result=dict(state=state,controls=[state]+[50]*17,frames=len(trace),
            offlineCPUMeanMs=statistics.mean(timings),offlineCPUP95Ms=float(np.percentile(timings,95)),
            source=read(target/'source.json'),files={p.name:sha(p) for p in sorted(target.iterdir()) if p.is_file()})
        results.append(result)
    write(work/'manifest.json',dict(schema='malemod.wolverine-v2-reference/1',
        lockSHA256=sha(V2/'wolverine.lock.json'),build=build,cases=results,
        observedGameplay=False,geraltPhysicsImplemented=False,garmentEvaluated=False,
        performanceParityPassed=False,attachmentGatePassed=False))
    print('PASS three canonical source states; CPU reference only, no Geralt/native parity claim')


def status():
    archive=read(ROOT/'provenance/v1-archive.json')
    print('Witcher v1 archived: '+archive['repositories'][1]['commit'])
    print('Active work: Wolverine-parity v2; original grey room retained')
    print('Geralt stock base: '+('prepared' if (V2/'build/geralt-base/manifest.json').is_file() else 'not yet exported'))
    print('Canonical source reference: '+('evaluated' if (V2/'build/wolverine-reference/manifest.json').is_file() else 'not yet evaluated'))
    print('Geralt graft: '+('authored; native review required' if (V2/'build/fitted-geralt/manifest.json').is_file() else 'pending'))
    trace=V2/'build/canonical-trace/proof.json'
    if trace.is_file():
        proof=read(trace)
        print('Canonical changing trace: '+('PASS' if proof.get('passed') else 'FAIL')+'; native performance is a separate gate')
    print('Per-frame runtime and canonical jockstrap: development preview; see docs/HANDOFF.md')
    print('Full attachment/performance acceptance pending; no v2 installed')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('status','prepare-body','build-reference','reference','check-reference'))
    args=parser.parse_args()
    try:
        if args.action=='status':status()
        elif args.action=='prepare-body':prepare_body()
        elif args.action=='build-reference':build_reference()
        elif args.action=='reference':reference()
        else:checked_reference();print('PASS exact pinned reference sources')
    except (ValueError,RuntimeError,OSError,subprocess.CalledProcessError) as error:
        print('ERROR: '+str(error),file=sys.stderr);return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
