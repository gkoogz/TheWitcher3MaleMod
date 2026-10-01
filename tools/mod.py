"""Build REDengine resources with the installed official REDkit, without the editor."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import stat
import subprocess
import sys
import time
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8', newline='\n')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def relative_resource(value):
    """Reject Windows drives/UNC paths and traversal before joining engine paths."""
    native = PureWindowsPath(value)
    parts = value.replace('\\', '/').split('/')
    if native.is_absolute() or native.drive or not value or any(x in ('', '.', '..') for x in parts):
        raise ValueError('Expected a depot-relative resource path: ' + value)
    if any(':' in x for x in parts):
        raise ValueError('Resource path may not contain a stream or drive')
    return Path(*parts)


def inside(root, relative):
    root = Path(root).resolve()
    result = (root / relative_resource(str(relative))).resolve()
    if not result.is_relative_to(root):
        raise ValueError('Path leaves its declared root')
    return result


def required_file(path):
    path = Path(path)
    if not path.is_file() or not path.stat().st_size:
        raise RuntimeError('Missing or empty native output: ' + str(path))
    return path


def settings():
    path = ROOT / 'local/config.json'
    data = read_json(path if path.exists() else ROOT / 'config/local.example.json')
    for key in ('redkit', 'depot', 'game', 'base'):
        candidate = Path(data[key])
        data[key] = (ROOT / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    data['wcc'] = data['redkit'] / 'bin/x64_RedKit/wcc_lite.exe'
    data['timeoutSeconds'] = int(data.get('timeoutSeconds', 600))
    if data['timeoutSeconds'] <= 0:
        raise ValueError('Native timeout must be positive')
    return data


def base_checkout(cfg):
    lock = read_json(ROOT / 'dependencies/base.lock.json')
    result = subprocess.run(['git', '-C', str(cfg['base']), 'rev-parse', 'HEAD'],
                            check=True, text=True, capture_output=True)
    if result.stdout.strip() != lock['commit']:
        raise RuntimeError('Base HEAD differs from dependencies/base.lock.json; update the lock intentionally')
    dirty = subprocess.run(['git', '-C', str(cfg['base']), 'status', '--porcelain', '--untracked-files=no'],
                           check=True, text=True, capture_output=True)
    if dirty.stdout.strip():
        raise RuntimeError('Pinned Base has tracked edits; commit and update its lock before building')
    required_file(cfg['base'] / lock['referenceAsset'])
    return lock


def directory_alias(alias, target):
    """WCC 5.0 startup flags misparse quoted paths; use checked local junctions."""
    alias = Path(alias).absolute()  # Do not resolve the alias back into a path with spaces.
    target = Path(target).resolve()
    if ' ' in str(alias):
        raise RuntimeError('REDkit startup alias must have no spaces; place this checkout in a path without spaces')
    if not target.is_dir():
        raise ValueError('Alias target is not a directory: ' + str(target))
    alias.parent.mkdir(parents=True, exist_ok=True)
    if alias.exists():
        if not os.path.samefile(alias, target):
            raise RuntimeError('Existing build alias points somewhere else: ' + str(alias))
        return alias
    if os.name != 'nt':
        raise RuntimeError('Installed REDkit commands require Windows')
    script = ('$taskAliasData = [Console]::In.ReadToEnd() | ConvertFrom-Json; '
              'New-Item -ItemType Junction -Path $taskAliasData[0] -Target $taskAliasData[1] | Out-Null')
    subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script],
                   input=json.dumps([str(alias), str(target)]), text=True, check=True, capture_output=True)
    if not os.path.samefile(alias, target):
        raise RuntimeError('Directory alias was not created correctly')
    return alias


def native_args(cfg, command, options, workspace, depot_alias):
    # -depot=local uses the split virtual depot. An absolute -depot remap aborts in REDkit 5.0.
    return [str(cfg['wcc']), command, *options,
            '-uncookDir', str(depot_alias) + os.sep,
            '-workspaceDir', str(workspace) + os.sep, '-noninteractivecrash']


def readthrough_depot(stock, workspace):
    """Expose overrides to WCC commandlets that ignore the writable layer.

    Only overridden branches become real directories. Untouched stock folders
    are junctions; never write or recursively clean this read-through tree.
    """
    view = ROOT / 'build/jobs' / ('depot-' + uuid.uuid4().hex[:12])
    view.mkdir(parents=True)
    links = []

    def merge(stock_dir, custom_dir, destination):
        stock_items = {p.name.casefold(): p for p in stock_dir.iterdir()} if stock_dir and stock_dir.is_dir() else {}
        custom_items = {p.name.casefold(): p for p in custom_dir.iterdir()
                        if p.suffix not in ('.db', '.db-shm', '.db-wal')} if custom_dir.is_dir() else {}
        for key in sorted(stock_items.keys() | custom_items.keys()):
            original, custom = stock_items.get(key), custom_items.get(key)
            chosen = custom or original
            target = destination / chosen.name
            if custom and custom.is_dir():
                if original and not original.is_dir():
                    raise ValueError('Workspace directory replaces a stock file: ' + str(custom))
                target.mkdir()
                merge(original, custom, target)
            elif custom:
                if original and original.is_dir():
                    raise ValueError('Workspace file replaces a stock directory: ' + str(custom))
                shutil.copy2(custom, target)
            elif original.is_dir():
                links.append([str(target.absolute()), str(original.resolve())])
            else:
                shutil.copy2(original, target)

    merge(Path(stock), Path(workspace), view)
    if links:
        script = ('$taskDepotLinks = [Console]::In.ReadToEnd() | ConvertFrom-Json; '
                  'foreach ($taskDepotLink in $taskDepotLinks) { '
                  'New-Item -ItemType Junction -Path $taskDepotLink[0] -Target $taskDepotLink[1] '
                  '-ErrorAction Stop | Out-Null }')
        subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script],
                       input=json.dumps(links), text=True, check=True, capture_output=True)
        for alias, target in links:
            if not os.path.samefile(alias, target):
                raise RuntimeError('Read-through depot link verification failed')
    return view


def native_failure(text, returncode):
    # The cooker can return zero after dropping an entity or corrupting names.
    # Known startup configuration warnings are separate from resource failures.
    return bool(returncode or re.search(
        r'\[Error\]\[(WCC|Script)\]|\[Fatal\]|TEMPLATE COOKING FAILED|'
        r'Unable to create uncached entity|Invalid name index|\[resource load failed\]', text))


def run_wcc(cfg, command, options, workspace, label):
    required_file(cfg['wcc'])
    workspace = Path(workspace).absolute()
    workspace.mkdir(parents=True, exist_ok=True)
    depot_alias = readthrough_depot(cfg['depot'], workspace)
    if ' ' in str(workspace):
        raise RuntimeError('WCC workspace startup path must have no spaces')
    log = ROOT / 'build/logs' / (time.strftime('%Y%m%d-%H%M%S') + '-' + label + '-' + uuid.uuid4().hex[:6] + '.log')
    log.parent.mkdir(parents=True, exist_ok=True)
    args = native_args(cfg, command, options, workspace, depot_alias)
    print('REDkit:', command, '| log:', log, flush=True)
    started = time.monotonic()
    try:
        with log.open('w', encoding='utf-8') as output:
            result = subprocess.run(args, cwd=cfg['wcc'].parent, stdout=output,
                                    stderr=subprocess.STDOUT, timeout=cfg['timeoutSeconds'])
    except subprocess.TimeoutExpired as error:
        raise RuntimeError('REDkit timed out; inspect ' + str(log)) from error
    text = log.read_text(encoding='utf-8', errors='replace')
    record = {'command': command, 'args': args, 'exitCode': result.returncode,
              'seconds': round(time.monotonic() - started, 3), 'logSHA256': digest(log),
              'logPath': log.relative_to(ROOT).as_posix(),
              'wccSHA256': digest(cfg['wcc'])}
    write_json(log.with_suffix('.json'), record)
    if native_failure(text, result.returncode):
        raise RuntimeError('Native REDkit command failed; inspect ' + str(log) + '\n' + text[-3500:])
    print('Native command succeeded.', flush=True)
    return record


def copy_tree(source, destination):
    if source.exists():
        for path in source.rglob('*'):
            if path.is_file() and path.suffix not in ('.db', '.db-shm', '.db-wal'):
                target = inside(destination, path.relative_to(source))
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)


def overlay(generated_resources=None):
    destination = ROOT / 'build/jobs' / ('workspace-' + uuid.uuid4().hex[:12])
    destination.mkdir(parents=True)
    copy_tree(ROOT / 'workspace', destination)
    if generated_resources is None:
        copy_tree(ROOT / 'generated/workspace', destination)
    else:
        for resource in generated_resources:
            source = required_file(inside(ROOT / 'generated/workspace', resource))
            target = inside(destination, resource)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    return destination


def prepare_overrides(cfg, recipe):
    records = []
    for override in recipe['overrides']:
        root = {'redkit': cfg['redkit'] / 'r4data', 'depot': cfg['depot']}[override['sourceLayer']]
        source = required_file(inside(root, override['source']))
        if digest(source) != override['sourceSHA256']:
            raise RuntimeError('Stock source changed; inspect and update recipe intentionally: ' + str(source))
        data = source.read_bytes()
        if not data.startswith(b'CR2W'):
            raise ValueError('Expected native CR2W entity')
        expected = override['expectedMesh'].replace('/', '\\').encode()
        excluded = override['excludedMesh'].replace('/', '\\').encode()
        if expected not in data or excluded in data:
            raise RuntimeError('Entity recipe references unexpected meshes')
        target = inside(ROOT / 'generated/workspace', override['destination'])
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and digest(target) != override['sourceSHA256']:
            raise RuntimeError('Generated override has edits; preserve before rebuilding: ' + str(target))
        shutil.copy2(source, target)
        records.append({'source': override['source'], 'destination': override['destination'],
                        'sha256': digest(target)})
    write_json(ROOT / 'generated/override-provenance.json', {'feature': recipe['feature'], 'files': records})
    return records


def export_resource(cfg, resource, output, stock=False):
    relative = relative_resource(resource)
    candidates = [inside(ROOT / 'generated/workspace', relative), inside(ROOT / 'workspace', relative),
                  inside(cfg['depot'], relative), inside(cfg['redkit'] / 'r4data', relative)]
    if stock:
        candidates=candidates[2:]
    source = next((p for p in candidates if p.is_file()), candidates[-1])
    required_file(source)
    output = Path(output).resolve()
    if output.suffix.lower() != '.fbx' or relative.suffix.lower() != '.w2mesh':
        raise ValueError('This command exports a .w2mesh into .fbx')
    if not output.is_relative_to(ROOT / 'build'):
        raise ValueError('Keep native character exports in this repository\'s ignored build/ directory')
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError('Export output already exists; choose a new filename')
    workspace=ROOT/'build/jobs'/('stock-export-'+uuid.uuid4().hex[:12]) if stock else overlay()
    record = run_wcc(cfg, 'export', ['-depot=local', '-file=' + str(relative), '-out=' + str(output)],
                     workspace, 'export')
    required_file(output)
    write_json(output.with_suffix('.provenance.json'), {'resource': relative.as_posix(),
               'sourceSHA256': digest(source), 'outputSHA256': digest(output), 'native': record})
    print('Exported:', output)


def import_mesh(cfg, source, resource):
    source = required_file(Path(source).resolve())
    relative = relative_resource(resource)
    if source.suffix.lower() != '.fbx' or relative.suffix.lower() != '.w2mesh':
        raise ValueError('Expected .fbx source and .w2mesh output')
    destination = inside(ROOT / 'generated/workspace', relative)
    if destination.exists():
        raise ValueError('Imported resource exists; use a new revision path')
    workspace = ROOT / 'generated/workspace'
    workspace.mkdir(parents=True, exist_ok=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # REDkit 5.0's importer writes relative outputs beneath bin/, ignoring the
    # writable workspace layer. An absolute, validated output stays in our repo.
    record = run_wcc(cfg, 'import', ['-depot=local', '-file=' + str(source), '-out=' + str(destination)],
                     workspace, 'import')
    required_file(destination)
    write_json(ROOT / 'generated/imports' / (uuid.uuid4().hex[:12] + '.json'),
               {'resource': relative.as_posix(), 'sourceSHA256': digest(source),
                'materialXMLSHA256': digest(source.with_suffix('.xml')) if source.with_suffix('.xml').exists() else None,
                'outputSHA256': digest(destination), 'native': record})
    print('Imported:', destination)


def compile_scripts(cfg, workspace=None):
    workspace = workspace or overlay()
    combined = ROOT / 'build/jobs' / ('scripts-' + uuid.uuid4().hex[:12])
    combined.mkdir(parents=True)
    copy_tree(cfg['redkit'] / 'r4data/scripts', combined)
    copy_tree(workspace / 'scripts', combined)
    signature = hashlib.sha256()
    for path in sorted(combined.rglob('*.ws')):
        signature.update(path.relative_to(combined).as_posix().encode())
        signature.update(path.read_bytes())
    signature.update(digest(cfg['wcc']).encode())
    signature = signature.hexdigest()
    cache_path = ROOT / 'build/script-check.json'
    if cache_path.exists():
        cache = read_json(cache_path)
        artifact = Path(cache['artifact'])
        if (artifact.resolve().is_relative_to((ROOT / 'build').resolve()) and artifact.is_file() and
                cache['signature'] == signature and digest(artifact) == cache['artifactSHA256']):
            print('Reusing verified script compilation for identical sources/tool.', flush=True)
            return dict(cache['native'], reused=True)
    output = combined.parent / (combined.name + '-compiled')
    output.mkdir()
    record = run_wcc(cfg, 'compilescripts', [str(combined), '-out=' + str(output)], workspace, 'scripts')
    files = list(output.glob('*.redscripts'))
    if not files:
        raise RuntimeError('Compiler reported success without a .redscripts output')
    for path in files:
        required_file(path)
    write_json(cache_path, {'signature': signature, 'artifact': str(files[0]),
                           'artifactSHA256': digest(files[0]), 'native': record})
    return record


def empty_cache_expected(builder, log):
    if 'Found 0 files to process' in log:
        return True
    count = re.search(r'Found (\d+) files to process', log)
    return (builder == 'physics' and count is not None and
            int(count.group(1)) == len(re.findall(r"Mesh '[^'\r\n]+' does not contain collision", log)))


def build(cfg, project_override=None, workspace_override=None):
    lock = base_checkout(cfg)
    project = project_override or read_json(ROOT / 'project.json')
    attachment_record=None
    if project.get('attachmentManifest'):
        attachment_record=validate_attachment(cfg,project['attachmentManifest'])
    if not re.fullmatch(r'mod[A-Za-z0-9_]+', project['name']):
        raise ValueError('Invalid mod directory name')
    override_records = []
    if project.get('overrideRecipe'):
        override_records = prepare_overrides(cfg, read_json(inside(ROOT, project['overrideRecipe'])))
    workspace = Path(workspace_override).resolve() if workspace_override else overlay(project.get('generatedResources'))
    if not workspace.is_relative_to(ROOT/'build'):
        raise ValueError('Package workspace must be an owned build directory')
    job = workspace.parent / ('package-' + uuid.uuid4().hex[:12])
    job.mkdir()
    records = []
    scripts = workspace / 'scripts'
    if scripts.exists() and not project.get('scriptedCook'):
        records.append(compile_scripts(cfg, workspace))
    resource_types = {'.xbm', '.redcloth', '.redfur', '.reddlc', '.redgame', '.redswf', '.swf', '.csv', '.xml'}
    resources = [p for p in workspace.rglob('*') if p.is_file() and
                 (p.suffix.startswith(('.w2', '.w3')) or p.suffix in resource_types)]
    packed = job / 'packed'
    native_dumps=set()
    content = packed / 'Mods' / project['name'] / 'content'
    content.mkdir(parents=True)
    if resources:
        # WCC creates a localization SQLite DB at startup in its writable
        # workspace. Feed -mod a separate, explicit asset intake so this DB and
        # loose scripts cannot accidentally become cooker seeds.
        native_input = job / 'native-input'
        native_input.mkdir()
        for path in resources:
            target = inside(native_input, path.relative_to(workspace))
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        cooked = job / 'cooked'
        cooked.mkdir()
        cook_options=['-platform=' + project['platform'], '-mod=' + str(native_input),
                      '-outdir=' + str(cooked) + os.sep]
        if project.get('scriptedCook'):
            from wcc_scripted import run_scripted_cook
            from verify_cooked_motion import verify_binding
            entity=inside(cooked,project['motionEntity'])
            graph=inside(cooked,'characters/malemod/behavior/deformation.w2beh') if project.get('deformationBridge') else None
            dump_resources=[entity]+([graph] if graph else [])+[inside(cooked,p) for p in project.get('additionalNativeDumps',[])]
            native_dumps={Path(str(item)+'.xml') for item in dump_resources}
            records.append(run_scripted_cook(cfg,cook_options,workspace,'scripted-cook',dump_resources))
            binding=verify_binding(Path(str(entity)+'.xml'),output=project.get('motionOutput','dangle'),
                require_late=(project.get('deformationBridge') or {}).get('lateActivation',False))
            if project.get('deformationBridge') and not binding.get('cookedDeformationBindingVerified'):
                raise RuntimeError('Deformation candidate lacks verified native skeleton/graph/output references')
            if graph:
                from verify_deformation_graph import verify_graph
                probe=read_json(inside(ROOT,project['deformationBridge']['sourceProbe'])/'deformation-probe.json')
                binding['poseGraph']=verify_graph(Path(str(graph)+'.xml'),stock_names=probe['stockNames'],
                    identity_root=probe.get('identityRoot'),transform_controls=probe.get('fullTransformChannels',False),
                    parent_space=probe.get('parentPoseSpace','local'))
            if project.get('motionOutput')=='player':
                from player_stack import verify_native_player
                binding['playerRig']=verify_native_player(cooked,probe)
            write_json(job/'motion-binding-verification.json',binding)
        else:
            records.append(run_wcc(cfg,'cook',cook_options,workspace,'cook'))
        db = required_file(cooked / 'cook.db')
        for builder in project['cacheBuilders']:
            name = {'textures': 'texture.cache', 'physics': 'collision.cache'}[builder]
            out = content / name
            record = run_wcc(cfg, 'buildcache', [builder, '-platform=' + project['platform'],
                             '-db=' + str(db), '-out=' + str(out)], workspace, builder)
            if out.exists() and out.stat().st_size:
                required_file(out)
            elif empty_cache_expected(builder, (ROOT / record['logPath']).read_text(errors='replace')):
                record['cacheStatus'] = 'no eligible resources; no cache emitted'
                if out.exists():
                    out.unlink()  # Empty artifact owned by this fresh build job.
            else:
                required_file(out)
            temporary = Path(str(out) + '.tmp')
            if temporary.exists():
                if temporary.stat().st_size:
                    raise RuntimeError('Native builder left an unfinished cache: ' + str(temporary))
                temporary.unlink()  # Empty temporary owned by this successful cache job.
            records.append(record)
        dep = content / 'dep.cache'
        records.append(run_wcc(cfg, 'dependencies', ['-db=' + str(db), '-out=' + str(dep)], workspace, 'dependencies'))
        required_file(dep)
        bundle_input = job / 'bundle-input'
        bundle_input.mkdir()
        for path in cooked.rglob('*'):
            if path.is_file() and path.suffix not in ('.db', '.cache', '.log') and path not in native_dumps:
                target = inside(bundle_input, path.relative_to(cooked))
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
        bundles = content / 'bundles'
        bundles.mkdir()
        records.append(run_wcc(cfg, 'pack', ['-dir=' + str(bundle_input), '-outdir=' + str(bundles) + os.sep,
                       '-compression=lz4'], workspace, 'pack'))
        if not list(bundles.glob('*.bundle')):
            raise RuntimeError('Packer produced no bundle')
        records.append(run_wcc(cfg, 'metadatastore', ['-path=' + str(content) + os.sep], workspace, 'metadata'))
        required_file(content / 'metadata.store')
    if scripts.exists():
        copy_tree(scripts, content / 'scripts')
    if not resources and not scripts.exists():
        raise RuntimeError('Workspace is empty')
    publish = ROOT / 'publish' / (time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6])
    shutil.copytree(packed, publish)
    files = [{'path': p.relative_to(publish).as_posix(), 'sha256': digest(p), 'bytes': p.stat().st_size}
             for p in sorted(publish.rglob('*')) if p.is_file()]
    manifest = {'project': project['name'], 'version': project['version'], 'baseCommit': lock['commit'],
                'files': files, 'nativeCommands': records, 'gameplayTested': False,
                'scope': project.get('scope', 'native build foundation; no fitted anatomy or live body editor'),
                'nativeOverrides': override_records,'attachment':attachment_record,
                'motionBinding':binding if project.get('scriptedCook') else None,
                'deformationBridge':project.get('deformationBridge')}
    write_json(publish / 'build-manifest.json', manifest)
    archive = publish.with_suffix('.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as package:
        for path in sorted(publish.rglob('*')):
            if path.is_file():
                package.write(path, path.relative_to(publish).as_posix())
    write_json(ROOT / 'publish/latest.json', {'directory': publish.relative_to(ROOT).as_posix(),
                                            'archive': archive.relative_to(ROOT).as_posix(), 'sha256': digest(archive)})
    print('Built game-format package:', archive)
    return publish


def validate_attachment(cfg,manifest_path):
    record=read_json(required_file(inside(ROOT,manifest_path)))
    lock=base_checkout(cfg)
    if record['baseCommit']!=lock['commit']:
        raise RuntimeError('Attachment was built against another Base revision; run tools/mod.py attachment')
    for item in record['files']:
        if digest(required_file(inside(ROOT,item['path'])))!=item['sha256']:
            raise RuntimeError('Attachment input/output changed; rebuild explicitly: '+item['path'])
    if record.get('nativeVerified') is not True:
        raise RuntimeError('Attachment has not passed native round-trip verification')
    fit_report=read_json(required_file(inside(ROOT,record['fitReport'])))
    if fit_report['baseCommit']!=lock['commit'] or fit_report['profileSHA256']!=digest(ROOT/'characters/geralt-attachment.json'):
        raise RuntimeError('Attachment fit provenance does not match the active Base/profile')
    return record


def doctor(cfg):
    lock = base_checkout(cfg)
    required_file(cfg['wcc'])
    required_file(cfg['game'] / 'bin/x64_dx12/witcher3.exe')
    if not cfg['depot'].is_dir():
        raise ValueError('Uncooked depot is missing')
    directory_alias(ROOT / 'build/wcc-depot', cfg['depot'])
    character = read_json(ROOT / 'characters/geralt.json')
    for resource in character['resources'].values():
        required_file(inside(cfg['depot'], resource))
    print('Ready: REDkit, game, depot, native body resources and pinned Base', lock['commit'])
    print('Gameplay and live editing readiness: pending; see characters/geralt.json')


def verify_package(directory):
    directory = Path(directory).resolve()
    if not directory.is_relative_to((ROOT / 'publish').resolve()):
        raise ValueError('Package must be inside this repository\'s publish directory')
    manifest = read_json(directory / 'build-manifest.json')
    paths = set()
    for record in manifest['files']:
        path = inside(directory, record['path'])
        if record['path'] in paths:
            raise ValueError('Duplicate manifest path')
        paths.add(record['path'])
        required_file(path)
        if path.stat().st_size != record['bytes'] or digest(path) != record['sha256']:
            raise RuntimeError('Package file changed: ' + record['path'])
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
    if actual != paths | {'build-manifest.json'}:
        raise RuntimeError('Package contains unrecorded or missing files')
    print('PASS package integrity:', len(paths), 'files; gameplayTested:', manifest['gameplayTested'])
    return manifest


def install_package(cfg, directory):
    directory = Path(directory).resolve()
    manifest = verify_package(directory)
    name = manifest['project']
    if not re.fullmatch(r'mod[A-Za-z0-9_]+', name):
        raise ValueError('Invalid installation mod name')
    version, base_commit = manifest['version'], manifest['baseCommit']
    relative_package = directory.relative_to(ROOT.resolve()).as_posix()
    mods_root = cfg['game'].resolve() / 'Mods'
    mods_root.mkdir(exist_ok=True)
    if mods_root.is_symlink() or not mods_root.resolve().is_relative_to(cfg['game'].resolve()):
        raise ValueError('Mods directory leaves the declared game')
    target = inside(mods_root, name)
    if target.exists():
        raise RuntimeError('Mod already exists; preserve or uninstall the managed version before replacing it')
    source = inside(directory, 'Mods/' + name)
    if not source.is_dir():
        raise RuntimeError('Package has no declared mod tree')
    reject_reparse_tree(source)
    staging = inside(mods_root, '.malemod-staging-' + uuid.uuid4().hex[:12])
    shutil.copytree(source, staging)
    installed = []
    for record in manifest['files']:
        relative = Path(record['path']).relative_to(Path('Mods') / name)
        path = inside(staging, relative)
        if digest(required_file(path)) != record['sha256']:
            raise RuntimeError('Installation copy verification failed')
        installed.append({'path': relative.as_posix(), 'sha256': record['sha256']})
    staging.rename(target)
    write_json(ROOT / 'local/installation.json', {'target': str(target), 'project': name,
               'version': version, 'baseCommit': base_commit,
               'package': relative_package, 'files': installed,
               'gameplayTested': False})
    print('Installed verified mod files:', target)
    print('Restart the game, then re-equip and remove trousers if the current outfit is cached.')


def reject_reparse_tree(root):
    def paths():
        yield root
        yield from root.rglob('*')
    for path in paths():
        attributes = getattr(path.lstat(), 'st_file_attributes', 0)
        if path.is_symlink() or attributes & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400):
            raise RuntimeError('Managed mod tree contains a link/junction; preserve it before deployment: ' + str(path))


def uninstall_package(cfg):
    receipt = read_json(ROOT / 'local/installation.json')
    root = cfg['game'].resolve() / 'Mods'
    target = inside(root, receipt['project'])
    if target != Path(receipt['target']).resolve() or not target.is_dir():
        raise ValueError('Installation receipt does not match the declared game mod')
    reject_reparse_tree(target)
    expected = {x['path']: x['sha256'] for x in receipt['files']}
    actual = {p.relative_to(target).as_posix(): digest(p) for p in target.rglob('*') if p.is_file()}
    if expected != actual:
        raise RuntimeError('Installed files have edits or additions; preserve them before uninstalling')
    backup = ROOT / 'local/uninstalled' / (receipt['project'] + '-' + uuid.uuid4().hex[:12])
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.resolve().is_relative_to((ROOT / 'local').resolve()):
        raise ValueError('Rollback path leaves local storage')
    # Both final absolute targets have been checked before this cross-volume move.
    shutil.move(str(target), str(backup))
    receipt['uninstalledTo'] = str(backup)
    write_json(ROOT / 'local/installation.json', receipt)
    print('Removed managed mod from the game; preserved files:', backup)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('doctor')
    base = commands.add_parser('base')
    base.add_argument('--preferences', type=Path)
    export = commands.add_parser('export')
    export.add_argument('resource')
    export.add_argument('output', type=Path)
    export.add_argument('--stock',action='store_true')
    importer = commands.add_parser('import-mesh')
    importer.add_argument('source', type=Path)
    importer.add_argument('resource')
    commands.add_parser('compile')
    commands.add_parser('build')
    commands.add_parser('attachment')
    installer = commands.add_parser('install')
    installer.add_argument('--directory', type=Path)
    commands.add_parser('uninstall')
    verifier = commands.add_parser('verify')
    verifier.add_argument('--directory', type=Path)
    args = parser.parse_args()
    cfg = settings()
    try:
        if args.command == 'doctor':
            doctor(cfg)
        elif args.command == 'base':
            lock = base_checkout(cfg)
            profile = args.preferences or cfg['base'] / lock['preferenceProfile']
            subprocess.run([sys.executable, str(cfg['base'] / 'tools/build_generic.py'),
                            '--preferences', str(profile), '--output', str(ROOT / 'build/shared/generic-male')], check=True)
        elif args.command == 'export':
            export_resource(cfg, args.resource, args.output,stock=args.stock)
        elif args.command == 'attachment':
            from build_attachment import build_attachment
            build_attachment()
        elif args.command == 'import-mesh':
            import_mesh(cfg, args.source, args.resource)
        elif args.command == 'compile':
            compile_scripts(cfg)
        elif args.command == 'build':
            build(cfg)
        elif args.command == 'install':
            directory = args.directory or ROOT / read_json(ROOT / 'publish/latest.json')['directory']
            install_package(cfg, directory)
        elif args.command == 'uninstall':
            uninstall_package(cfg)
        elif args.command == 'verify':
            directory = args.directory or ROOT / read_json(ROOT / 'publish/latest.json')['directory']
            verify_package(directory)
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print('ERROR:', error, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
