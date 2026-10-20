"""Pack exact donor-preserving authoring paths for private native review.

No post-authoring ownership mask or smoothing is applied. Generated anatomy
and native payloads remain private; the recipe and shared solver are reusable.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
import numpy as np
from build_collar_corrective import fnv, reference


def build(recipe_path, output, base):
    recipe = json.loads(Path(recipe_path).read_text())
    sys.path.insert(0, str(Path(base).resolve()))
    from malemod_base.surface_bending import bending_report, chord_report
    binding = Path(recipe['binding']).read_bytes()
    if binding[:8] != b'MMBIND03':
        raise ValueError('Expected a shared-waist binding')
    radius, length, _ = reference(recipe['referenceSource'])
    prepared, proofs = [], []
    count = int(recipe.get('pathSteps', 80))
    if not 1 <= count <= 128:
        raise ValueError('Invalid path resolution')
    for lod, entry in enumerate(recipe['lods']):
        domain = np.load(entry['domain'])
        fixed = np.zeros(len(domain['points']), bool)
        fixed[domain['protected']] = True
        fixed[domain['roles'][:, 0] >= .05] = True
        poses, hashes = [], []
        last_angle = 0
        for pose in entry['poses']:
            angle = float(pose['angle'])
            if not last_angle < angle <= 100:
                raise ValueError('Pose angles must be strictly increasing')
            last_angle = angle
            if pose.get('zero'):
                poses.append((angle, np.zeros((2, len(fixed), 3))))
                continue
            path, before = [], None
            for part_index, part in enumerate(pose['parts']):
                raw = Path(part).read_bytes()
                data = np.load(part)
                if 'knots' not in data or len(data['knots']) < 2:
                    raise ValueError('Complete authoring path is required')
                fraction = float(data['fraction']) if 'fraction' in data else float(data['fractions'][-1])
                if part_index == len(pose['parts'])-1 and fraction != 1:
                    raise ValueError('Partial authoring result is not a complete corrective')
                if before is None:
                    before = data['before']
                elif not np.array_equal(before, data['before']):
                    raise ValueError('Parts must retain the same immutable reference')
                path.extend(data['knots'])
                hashes.append(dict(path=part, sha256=hashlib.sha256(raw).hexdigest()))
            path = np.asarray(path)
            delta = path-before
            if np.max(abs(delta[:, fixed]), initial=0) > 1e-8:
                raise ValueError('Authored path moves excluded anatomy')
            for slave, a, b, w in domain['seams']:
                error = delta[:, int(slave)]-(1-w)*delta[:, int(a)]-w*delta[:, int(b)]
                if np.max(abs(error), initial=0) > 1e-7:
                    raise ValueError('Authored path changes original-edge donors')
            for positions in path:
                report = bending_report(before, positions, domain['faces'])
                if report['new_fold_pairs'] or report['collapsed_faces']:
                    raise ValueError('Authored path fails triangle bounds')
            if recipe.get('evaluation') != 'immediate-frame':
                for left, right in zip(path[:-1], path[1:]):
                    if not chord_report(before, left, right, domain['faces'])['safe']:
                        raise ValueError('Authored path folds between its saved knots')
            poses.append((angle, delta))
        if not poses or entry['poses'][-1].get('zero') is not True:
            raise ValueError('A final zero-response pose is required')
        # Keep every authored corner. Uniform resampling can shortcut a curved
        # trajectory and fold a thin triangle between two valid authored knots.
        fractions = sorted({round(i/(len(path)-1), 15)
                            for _, path in poses for i in range(1, len(path))})
        if len(fractions) > 128:
            raise ValueError('Exact pose-path union exceeds the native knot bound')
        sampled = []
        for angle, path in poses:
            knots = []
            for fraction in fractions:
                t = fraction*(len(path)-1); i = min(int(t), len(path)-2); w = t-i
                knots.append((1-w)*path[i]+w*path[i+1])
            sampled.append((angle, np.asarray(knots)))
        poses = sampled
        active = np.zeros(len(fixed), bool)
        for _, knots in poses:
            active |= np.max(np.linalg.norm(knots, axis=2), axis=0) > 1e-10
        # Never erase a tiny dependent displacement while retaining its donors.
        for slave, a, b, _ in domain['seams']:
            if active[int(a)] or active[int(b)]:
                active[int(slave)] = True
        if np.any(active & fixed):
            raise ValueError('Sewn support intersects excluded anatomy')
        ids = np.flatnonzero(active)
        prepared.append((len(fixed), np.flatnonzero(fixed), ids, poses, fractions))
        proofs.append(dict(lod=lod, correctedRows=len(ids), inputs=hashes))
    if len(prepared) != 2:
        raise ValueError('Both LODs are required')
    output = Path(output)
    data = bytearray(b'MMSEWN02'+struct.pack('<IQ', 2, fnv(binding))+binding[8:48])
    data.extend(struct.pack('<ddI', radius, length, 2))
    def array(values, dtype):
        values = np.asarray(values, dtype=dtype)
        data.extend(struct.pack('<I', len(values))); data.extend(values.tobytes())
    for lod, (size, fixed, ids, poses, fractions) in enumerate(prepared):
        data.extend(struct.pack('<I', size)); array(fixed, '<u4'); array(ids, '<u4')
        data.extend(struct.pack('<I', len(poses)))
        for pose_index, (angle, knots) in enumerate(poses):
            source = recipe['lods'][lod]['poses'][pose_index]['referenceSource']
            pose_radius, pose_length, _ = reference(source)
            data.extend(struct.pack('<dddI', angle, pose_radius, pose_length, len(fractions)))
            for index, delta in enumerate(knots):
                data.extend(struct.pack('<d', fractions[index])); array(delta[ids], '<f8')
    data.extend(struct.pack('<Q', fnv(data)))
    if len(data) > 64*1024*1024:
        raise ValueError('Corrective exceeds native input bound')
    output.parent.mkdir(parents=True, exist_ok=True); output.write_bytes(data)
    proof = dict(schema='malemod.sewn-corrective/2', bindingSHA256=hashlib.sha256(binding).hexdigest(),
                 artifactSHA256=hashlib.sha256(data).hexdigest(), lods=proofs,
                 evaluation=recipe.get('evaluation', 'continuous-activation'),
                 nativeObserved=False, attachmentGatePassed=False)
    output.with_suffix(output.suffix+'.json').write_text(json.dumps(proof, indent=2))
    print(output, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['recipe', 'output', 'base']:
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    build(args.recipe, args.output, args.base)
