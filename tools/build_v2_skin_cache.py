"""Build the DX12 material cache from the final owned native cook database.

This is the official REDkit _step_cook_shaders.bat buildcache route, without
global static shaders. An isolated compiler uses exact recovered SDK includes.
"""
import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path
import mod
from mod import digest,read_json,write_json
from build_v2_anatomy_material import JOB,complete_depot
from v2_skin_material import GRAPH,inspect


def calibrated_range_diagnostics(output,command,baseline_record,file_count=1):
    """Accept only the exact pre-file warnings reproduced by an empty cook DB."""
    baseline_record=Path(baseline_record);baseline=read_json(baseline_record)
    database=Path(baseline['args'][next(i for i,a in enumerate(baseline['args'])if a.startswith('-db='))].split('=',1)[1])
    if read_json(database)!={'files':[]} or baseline['exitCode']!=0 or command['exitCode']!=0:
        raise ValueError('Calibration must be a successful exact empty cook database')
    target=(output/command['logPath']).read_text()
    control=(baseline_record.parent/baseline_record.with_suffix('.log').name).read_text()
    if 'Found 0 files to process' not in control or 'Processing [' in control:
        raise ValueError('Calibration unexpectedly processed material files')
    def errors(text):return Counter(re.findall(r'\[Error\]\[WCC\] (.*)',text))
    expected=errors(control)
    if not expected or errors(target)!=expected or any(not re.fullmatch(r'Min (?:cannot be larger than max|must be smaller than max,) [-0-9.]+ < [-0-9.]+',x)for x in expected):
        raise ValueError('Native diagnostics differ from exact stock empty-database baseline')
    marker=target.index('Found '+str(file_count)+' files to process')
    if '[Error][WCC]' in target[marker:] or mod.native_failure('\n'.join(l for l in target.splitlines()if '[Error][WCC]'not in l),command['exitCode']):
        raise ValueError('Nonbaseline native failure or failure during material processing')
    return dict(baselineRecordPath=str(baseline_record),baselineRecordSHA256=digest(baseline_record),
                baselineDatabaseSHA256=digest(database),identicalPreProcessingDiagnostics=sum(expected.values()),
                uniqueDiagnostics=len(expected),materialProcessingErrors=0)


def build(output,compiler_job,package_info,baseline_record=None,resume=False,job=None,additional_graphs=()):
    job=Path(job).absolute()if job is not None else JOB
    materials=(mod.ROOT/'v2/build/materials').resolve()
    if not job.resolve().is_relative_to(materials):raise ValueError('Material job leaves owned material work')
    output=Path(output).absolute();compiler_job=Path(compiler_job).absolute()
    if (output.exists()and not resume) or not output.resolve().is_relative_to((job/'build').resolve()):
        raise ValueError('Use a fresh owned anatomy shader-cache output directory')
    if not compiler_job.resolve().is_relative_to(materials):
        raise ValueError('Compiler runtime must remain inside owned anatomy build')
    recovered=read_json(compiler_job/'recovered-sdk-flat-includes.json')
    for row in recovered['files']:
        if digest(Path(row['path']))!=row['SHA256']:raise ValueError('Recovered SDK include changed')
    cfg=mod.settings();cfg['depot']=complete_depot(cfg)
    if digest(cfg['wcc'])!=recovered['sourceExecutableSHA256']:raise ValueError('SDK compiler executable changed')
    cfg['wcc']=compiler_job/'runtime/bin/x64_RedKit/wcc_lite.exe'
    if digest(cfg['wcc'])!=recovered['sourceExecutableSHA256']:raise ValueError('Owned compiler executable changed')
    package_info=Path(package_info);package=read_json(package_info);manifest=read_json(Path(package['directory'])/'build-manifest.json')
    cook=next(c for c in manifest['nativeCommands']if c['command']=='cook')
    depot=Path(cook['args'][cook['args'].index('-uncookDir')+1])
    workspace=Path(cook['args'][cook['args'].index('-workspaceDir')+1])
    graph=workspace/GRAPH;proof=inspect(graph)
    if digest(depot/GRAPH)!=proof['SHA256'] or read_json(job/'graph-compiled.json')['SHA256']!=proof['SHA256']:
        raise ValueError('Final native cook and officially resaved graph differ')
    database=Path(package['cooked'])/'cook.db'
    if not database.is_file():raise ValueError('Final owned native cook database missing')
    graphs=[GRAPH,*additional_graphs]
    if len(set(graphs))!=len(graphs)or any(not p.startswith('characters/malemod/')or '..'in Path(p).parts for p in graphs):raise ValueError('Unobserved owned graph scope')
    entries={r['path'].replace('\\','/')for r in read_json(database)['files']if r.get('class')=='CMaterialGraph'}
    if entries!=set(graphs):raise ValueError('Native cook graph inventory differs from explicit scope')
    graph_inventory=[]
    for relative in graphs:
        if digest(workspace/relative)!=digest(depot/relative):raise ValueError('Cooked native graph intake differs')
        graph_inventory.append(dict(path=relative,SHA256=digest(workspace/relative)))
    output.mkdir(parents=True,exist_ok=resume)
    prior=mod.ROOT;mod.ROOT=output
    try:
        if resume:
            records=list((output/'build/logs').glob('*.json'))
            if len(records)!=1:raise ValueError('Resume requires one exact native command record')
            command=read_json(records[0])
            if command['command']!='buildcache' or '-db='+str(database)not in command['args'] or '-out='+str(output)+os.sep not in command['args'] or command['wccSHA256']!=digest(cfg['wcc']):
                raise ValueError('Existing native command does not bind these exact inputs/outputs')
        else:
            try:
                command=mod.run_wcc(cfg,'buildcache',['shaders','-platform=pc_dx12','-db='+str(database),'-out='+str(output)+os.sep],workspace,'source-skin-native-shader-cache',existing_depot=depot)
            except RuntimeError:
                records=list((output/'build/logs').glob('*.json'))
                if not baseline_record or len(records)!=1:raise
                command=read_json(records[0])
                # The exact empty-database comparison below is mandatory;
                # every other native error remains fatal.
                calibrated_range_diagnostics(output,command,baseline_record,len(graphs))
    finally:mod.ROOT=prior
    calibration=calibrated_range_diagnostics(output,command,baseline_record,len(graphs))if baseline_record else None
    if resume and not calibration:raise ValueError('Resume requires exact stock diagnostic calibration')
    # The native builder also emits an empty static-cache header and a build
    # optimization sidecar. Retail consumes the complete material cache only.
    files=[dict(path=str(p),SHA256=digest(p),bytes=p.stat().st_size)for p in sorted(output.glob('shaderDx12_0.cache'))]
    if not files or any(Path(r['path']).name!='shaderDx12_0.cache' or r['bytes']<=1024 for r in files):
        raise ValueError('Native shader builder did not emit expected populated DX12 material cache')
    result=dict(schema='malemod.witcher-v2-source-skin-shaders/1',graph=GRAPH,graphSHA256=proof['SHA256'],
                compilerInputSHA256=proof['SHA256'],command=command,files=files,allMaterialsScan=False,
                nativeCookDatabaseSHA256=digest(database),packageInfoSHA256=digest(package_info),
                graphs=graph_inventory,recoveredSDKIncludes=recovered,SDKFilesModified=False,nativeObserved=False)
    text=(output/command['logPath']).read_text()
    processed=re.findall(r"Processing \[\d+/\d+\] - '([^']+)'",text)
    if {p.replace('\\','/')for p in processed}!=set(graphs)or len(processed)!=len(graphs):raise ValueError('Native builder processed an unexpected material graph')
    if calibration:result['nativeDiagnosticCalibration']=calibration
    write_json(output/'receipt.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--compiler-job',type=Path,required=True)
    parser.add_argument('--package-info',type=Path,default=JOB/'package.json')
    parser.add_argument('--baseline-record',type=Path)
    parser.add_argument('--resume-native',action='store_true')
    parser.add_argument('--job',type=Path)
    parser.add_argument('--additional-graph',action='append',default=[])
    args=parser.parse_args()
    print(json.dumps(build(args.output,args.compiler_job,args.package_info,args.baseline_record,args.resume_native,args.job,args.additional_graph),indent=2))
