"""Resume only downstream commandlets from an exact successful owned cook."""
from pathlib import Path
import json
import re
from mod import digest, validate_readonly_depot


def files(directory):
    return [dict(path=p.relative_to(directory).as_posix(), sha256=digest(p))
            for p in sorted(directory.rglob('*')) if p.is_file()
            and p.suffix not in ('.db-shm', '.db-wal')]


def validate_continuation(root, cfg, workspace, project, receipt_path):
    receipt_path = Path(receipt_path)
    receipt = json.loads(receipt_path.read_text())
    job = Path(receipt['job'])
    if (receipt.get('schema') != 'malemod.native-build-continuation/1'
            or job.parent.resolve() != workspace.parent.resolve()
            or not job.absolute().is_relative_to(root / 'build')
            or not re.fullmatch(r'package-[0-9a-f]{12}', job.name)
            or receipt_path.resolve().parent != job.resolve()
            or receipt['project'] != project or project.get('scriptedCook')):
        raise ValueError('Native continuation is not the exact owned plain-cook recipe')
    for name in ('bundle-input',):
        if (job / name).exists():
            raise ValueError('Native continuation already started downstream packing')
    content = job / 'packed/Mods' / project['name'] / 'content'
    if content.exists() and any(content.iterdir()):
        raise ValueError('Native continuation has existing downstream outputs')
    for directory in ('native-input', 'cooked'):
        if files(job / directory) != receipt[directory]:
            raise ValueError('Native continuation bytes changed: ' + directory)
    workspace_files = [f for f in files(workspace) if not f['path'].endswith('.db')]
    if workspace_files != receipt['workspaceFiles']:
        raise ValueError('Native continuation workspace changed')
    command_path = root / receipt['cookRecordPath']
    if digest(command_path) != receipt['cookRecordSHA256']:
        raise ValueError('Cook command receipt changed')
    command = json.loads(command_path.read_text())
    if (command['command'] != 'cook' or command['exitCode'] != 0
            or digest(root / command['logPath']) != command['logSHA256']
            or digest(cfg['wcc']) != command['wccSHA256']):
        raise ValueError('Native continuation lacks exact successful cooker/tool proof')
    args = command['args']
    for prefix, expected in (('-mod=', job / 'native-input'), ('-outdir=', job / 'cooked')):
        matched = [Path(a[len(prefix):]) for a in args if a.startswith(prefix)]
        if len(matched) != 1 or matched[0].resolve() != expected.resolve():
            raise ValueError('Cook input/output differs from continuation job')
    if Path(args[args.index('-workspaceDir') + 1]).resolve() != workspace.resolve():
        raise ValueError('Cook workspace differs from continuation')
    view = Path(args[args.index('-uncookDir') + 1])
    validate_readonly_depot('buildcache', workspace, view)
    return job, command
