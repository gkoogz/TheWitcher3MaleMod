"""Serialize reviewed source-space correction paths with exact binding identity.

Inputs are private generated geometry, never game packages or another person's
captures. The shared Base runtime independently checks each interpolated path.
"""
import argparse
import hashlib
import json
import struct
import importlib.util
import subprocess
from pathlib import Path
import numpy as np


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fnv(data):
    value = 14695981039346656037
    for byte in data:
        value = ((value ^ byte) * 1099511628211) & ((1 << 64) - 1)
    return value


def reference(path):
    data = Path(path).read_bytes()
    offset = 4
    for _ in range(3):
        count = struct.unpack_from('<I', data, offset)[0]
        offset += 4 + count * 48
    count = struct.unpack_from('<I', data, offset)[0]
    offset += 4 + count * 4
    values = np.frombuffer(data, '<f4', 135, offset)
    guide = values[2:38].reshape(-1, 3)
    forward = (guide[2] - guide[0]).astype(float)
    forward /= np.linalg.norm(forward)
    side = np.array([0., 1., 0.])
    side -= forward * np.dot(side, forward)
    side /= np.linalg.norm(side)
    return float(values[-3]), float(values[1]), np.column_stack([forward, side, np.cross(forward, side)])


def build(recipe_path, output, base):
    recipe_path, output = Path(recipe_path).resolve(), Path(output).resolve()
    recipe = json.loads(recipe_path.read_text())
    base = Path(base).resolve()
    shared_path = base / 'malemod_base/attachment_fields.py'
    spec = importlib.util.spec_from_file_location('malemod_attachment_fields', shared_path)
    shared = importlib.util.module_from_spec(spec); spec.loader.exec_module(shared)
    binding = Path(recipe['binding']).resolve()
    original = binding.read_bytes()
    if original[:8] != b'MMBIND03':
        raise ValueError('Expected the versioned shared-waist binding')
    revision = original[8:48]
    radius, length, frame = reference(recipe['referenceSource'])
    up = np.asarray(recipe['measurementUp'], float)
    if up.shape != (3,) or not np.isfinite(up).all() or abs(np.linalg.norm(up) - 1) > 1e-8:
        raise ValueError('Invalid measured body-up direction')
    prepared, reports = [], []
    for lod, entry in enumerate(recipe['lods']):
        meta = np.load(entry['domain'])
        path = [np.load(k['geometry']) for k in entry['knots']]
        before = path[0]['before']
        if before.shape != meta['points'].shape:
            raise ValueError('Corrective domain differs')
        for k in path:
            if not np.array_equal(k['before'], before) or not np.isfinite(k['after']).all():
                raise ValueError('Path does not share one finite reference pose')
        fixed = np.zeros(len(before), bool)
        fixed[meta['unique'] < int(meta['bodyCount'])] = True
        fixed[meta['roles'][:, 0] >= .01] = True
        fixed[meta['protected']] = True
        fixed[meta['waist']] = True
        fixed[meta['seams'][:, :3].astype(int).ravel()] = True
        deltas = [k['after'] - before for k in path]
        # The captured fold limiter was on a shaft-dominant row, outside the
        # saddle. A collar correction must stop following that material. Use
        # the existing interpolation roles instead of a posed-height mask.
        ownership = shared.attachment_strength(meta['roles'][:, 2], meta['roles'][:, 1])
        for delta in deltas:
            delta *= ownership[:, None]
        for delta in deltas:
            if np.linalg.norm(delta[fixed], axis=1).max(initial=0) > 1e-8:
                raise ValueError('Corrective changes the collar or excluded anatomy')
            delta[fixed] = 0
        active = np.max(np.stack([np.linalg.norm(d, axis=1) for d in deltas]), axis=0) > 1e-9
        # Zero authored displacement is not a hard material boundary. Give the
        # constraint projection two neighbouring shaft rings to redistribute
        # strain; body, sewn donors and excluded tissue remain exactly locked.
        active = shared.neighbour_support(meta['faces'], active, fixed)
        ids = np.flatnonzero(active)
        normals = np.load(entry['materialNormals'])
        cosine = normals[:, 2] / np.maximum(np.linalg.norm(normals[:, 1:], axis=1), 1e-12)
        samples = np.flatnonzero((meta['roles'][:, 0] < .01) &
                                (meta['roles'][:, 3] > .04) & (meta['roles'][:, 3] < .08) &
                                (cosine > .98) & (abs(before[:, 1]) < radius * .08))
        rim = meta['seams'][:, 0].astype(int)
        if not len(samples):
            raise ValueError('No measured dorsal sample')
        depth = float(np.max(before[rim] @ up) - np.mean(before[samples] @ up))
        if depth <= 0:
            raise ValueError('Reference has no measured saddle')
        prepared.append((len(before), np.flatnonzero(fixed), ids, samples, rim,
                         [(float(k['weight']), d[ids] @ frame) for k, d in zip(entry['knots'], deltas)]))
        reports.append(dict(lod=lod, points=len(before), correctedRows=len(ids), referenceDepth=depth,
                            fixedRows=int(fixed.sum()), inputs=[dict(path=k['geometry'], sha256=digest(k['geometry'])) for k in entry['knots']]))
    if len(prepared) != 2:
        raise ValueError('Both native LODs are required')
    # Each LOD measures its own landmarks against the same control contract.
    depth = reports[0]['referenceDepth']
    data = bytearray(b'MMCORR03' + struct.pack('<IQ', 3, fnv(original)) + revision)
    data.extend(struct.pack('<3d3dI', radius, length, depth, *up, len(prepared)))
    data[-4:-4] = np.asarray(frame.T, dtype='<f8').tobytes()

    def array(values, dtype):
        values = np.asarray(values, dtype=dtype)
        data.extend(struct.pack('<I', len(values)))
        data.extend(values.tobytes())

    for lod, (count, fixed, ids, samples, rim, knots) in enumerate(prepared):
        data.extend(struct.pack('<Id', count, reports[lod]['referenceDepth']))
        for values in [fixed, ids, samples, rim]:
            array(values, '<u4')
        meta = np.load(recipe['lods'][lod]['domain'])
        follow = shared.frame_follow(meta['roles'][ids, 3])
        array(follow, '<f8')
        data.extend(struct.pack('<I', len(knots)))
        for weight, delta in knots:
            data.extend(struct.pack('<d', weight))
            array(delta, '<f8')
    data.extend(struct.pack('<Q', fnv(data)))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    output.with_suffix(output.suffix + '.sha256').write_text(digest(output) + '\n')
    report = dict(schema='malemod.collar-corrective/3', bindingBaseCommit=revision.decode(),
                  sharedImplementationSHA256=digest(shared_path), sharedSourceRevision=subprocess.check_output(['git', '-C', str(base), 'rev-parse', 'HEAD'], text=True).strip(),
                  bindingSHA256=digest(binding), referenceSourceSHA256=digest(recipe['referenceSource']),
                  recipeSHA256=digest(recipe_path), artifactSHA256=digest(output), referenceRadius=radius,
                  referenceLength=length, referenceDepth=depth, lods=reports,
                  nativeObserved=False, attachmentGatePassed=False)
    output.with_suffix(output.suffix + '.json').write_text(json.dumps(report, indent=2))
    print(output)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recipe', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--base', type=Path, required=True, help='Explicit shared Base checkout; receipt records its revision and implementation hash')
    args = parser.parse_args()
    build(args.recipe, args.output, args.base)
