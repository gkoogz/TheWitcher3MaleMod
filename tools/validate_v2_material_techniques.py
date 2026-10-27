"""Explicit-job entry to the existing isolated native technique validator.

Default execution is a read-only preflight. --execute is required for WCC/DXC.
This does not cook a package, build a cache, stage, or launch a game.
"""
import argparse
import json
from pathlib import Path
import shutil
import compile_v2_skin_shaders as native
from mod import ROOT, digest, read_json, write_json
from v2_skin_material import GRAPH, inspect


def preflight(job, output):
    job, output = Path(job).absolute(), Path(output).absolute()
    if not job.resolve().is_relative_to((ROOT/'v2/build/materials').resolve()):
        raise ValueError('Technique job leaves owned material work')
    if output.exists() or not output.resolve().is_relative_to((job/'build').resolve()):
        raise ValueError('Technique output must be fresh and inside this job')
    graph = job/'build/intake'/GRAPH
    compiled = read_json(job/'graph-compiled.json')
    if not compiled.get('nativeCompiled') or compiled['SHA256'] != digest(graph):
        raise ValueError('Technique input is not the exact officially resaved graph')
    material = inspect(graph)
    return dict(job=str(job), output=str(output), graph=str(graph), graphSHA256=digest(graph),
                compiledReceiptSHA256=digest(job/'graph-compiled.json'), material=material,
                expectedTechniqueCount=1212, preflightPassed=True, nativeCommandExecuted=False)


def validate(job, output, execute=False):
    checked = preflight(job, output)
    if not execute:
        return checked
    # The established implementation uses JOB to select its graph and bound
    # output. Scope that selector to this Python process; no intake changes.
    previous = native.JOB
    native.JOB = Path(job).absolute()
    try:
        result = native.compile_one(Path(output), recover_missing_rt=True)
    finally:
        native.JOB = previous
    if result['techniqueCount'] != checked['expectedTechniqueCount']:
        raise ValueError('Native skin technique inventory differs from the established1212')
    source = Path(output)/'recovered-sdk-includes.json'
    target = Path(output)/'recovered-sdk-flat-includes.json'
    if target.exists():
        raise ValueError('Compiler include receipt destination already exists')
    shutil.copy2(source, target)
    if digest(source) != digest(target):
        raise ValueError('Native cache include receipt alias differs')
    result.update(materialContract=checked['material'], allExpectedTechniquesCompiled=True,
                  shaderBytecodeUV1AuditPending=True, nativeCommandExecuted=True)
    write_json(Path(output)/'compile-validation.json', result)
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    print(json.dumps(validate(args.job,args.output,args.execute),indent=2))
