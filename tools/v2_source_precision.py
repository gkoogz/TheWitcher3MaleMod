"""Restore authored B04 anatomy-interior float baselines after native cooking.

Native uint16 cooking may merge sub-texel source corners. The dynamic renderer
already consumes floats, so retain the authoritative fitted baseline for source
interior rows. Stock body, shared seam, skinning, lighting and donor bytes stay
exact. This never alters the canonical source solver or the cooked allocation.
"""
import argparse
import collections
import hashlib
import json
import struct
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix
from scipy.spatial import cKDTree

from packed_mesh_format import CookedMesh


def sha(data):
    return hashlib.sha256(data).hexdigest()


def parse_b04(data):
    if data[:8] != b'MMV2B04\0' or struct.unpack_from('<I', data, 8)[0] != 2:
        raise ValueError('Source precision restoration requires a two-resource B04 binding')
    sources = struct.unpack_from('<I', data, 72)[0]
    cursor = 76 + sources * 12 * 3
    resources = []
    for part in range(2):
        count = struct.unpack_from('<I', data, cursor)[0]
        scale = np.asarray(struct.unpack_from('<3f', data, cursor + 20), np.float32)
        bias = np.asarray(struct.unpack_from('<3f', data, cursor + 32), np.float32)
        if not 0 < count <= 100000 or not np.isfinite(scale).all() or np.any(scale <= 0):
            raise ValueError('Invalid native precision resource bounds')
        cursor += 20 + 24 + 32
        sections = struct.unpack_from('<I', data, cursor)[0]
        cursor += 4
        if not 2 <= sections <= 16:
            raise ValueError('Invalid native precision section count')
        table = np.frombuffer(data, '<u4', sections * 10, cursor).reshape(-1, 10).copy()
        cursor += sections * 40
        bones = struct.unpack_from('<I', data, cursor)[0]
        cursor += 4 + bones * 68
        resources.append(dict(part=part, count=count, scale=scale, bias=bias,
                              sections=table, rowoffset=cursor))
        cursor += count * 52
    if cursor != len(data):
        raise ValueError('Truncated or trailing B04 precision data')
    return resources


def face_key(tri):
    return min(tuple(np.roll(tri, k)) for k in range(3))


def match_source_rows(points, uv, faces, authored, authored_uv, authored_faces):
    """Use original half-UV plus proximity, resolving close aliases by topology."""
    words = np.asarray(authored_uv, '<f2').view('<u2').reshape(-1, 2)
    table = collections.defaultdict(list)
    for i, pair in enumerate(words):
        table[tuple(pair)].append(i)
    observed = np.asarray(uv, '<f2').view('<u2').reshape(-1, 2)
    tree = cKDTree(authored)
    domains = []
    fallback = 0
    for point, pair in zip(points, observed):
        ids = [i for i in table.get(tuple(pair), [])
               if np.linalg.norm(authored[i] - point) <= 3e-5]
        if not ids:
            ids = [i for i in tree.query_ball_point(point, 3e-5)
                   if np.max(abs(words[i].astype(int) - pair.astype(int))) <= 1]
            fallback += 1
        if not ids:
            raise ValueError('Native source row has no UV/position donor within 3e-5 metres')
        domains.append(ids)
    initial = collections.Counter(map(len, domains))
    mapping = np.asarray([ids[0] if len(ids) == 1 else -1 for ids in domains])
    authored_keys = {face_key(t) for t in authored_faces}
    incident = [[] for _ in points]
    for i, tri in enumerate(faces):
        for v in tri:
            incident[v].append(i)
    changed = True
    while changed:
        changed = False
        for v in np.flatnonzero(mapping < 0):
            allowed = []
            for option in domains[v]:
                valid = True
                for face in incident[v]:
                    tri = faces[face]
                    mapped = mapping[tri].copy()
                    mapped[tri == v] = option
                    if np.all(mapped >= 0) and face_key(mapped) not in authored_keys:
                        valid = False
                        break
                if valid:
                    allowed.append(option)
            if not allowed:
                raise ValueError('Native source topology excludes every matching donor')
            domains[v] = allowed
            if len(allowed) == 1:
                mapping[v] = allowed[0]
                changed = True
    equivalent = 0
    for v in np.flatnonzero(mapping < 0):
        if not np.all(authored[domains[v]] == authored[domains[v][0]]):
            raise ValueError('Non-equivalent source positions remain ambiguous')
        mapping[v] = domains[v][0]
        equivalent += 1
    # Every physical triangle must preserve the authored orientation. Counts
    # may contain one identical Erect transport duplicate, checked by caller.
    actual = collections.Counter(face_key(mapping[t]) for t in faces)
    expected = collections.Counter(face_key(t) for t in authored_faces)
    if expected - actual or any(k not in expected for k in actual):
        raise ValueError('Native source topology omits or changes authored faces')
    return mapping, dict(oneHalfULPFallbackRows=fallback,
                         topologyResolvedRows=sum(v for k, v in initial.items() if k > 1) - equivalent,
                         equivalentAliases=equivalent,
                         extraIdenticalTriangles=sum((actual - expected).values()))


def restore_payload(original, fit_directory, cooked_path):
    """Return guarded replacement bytes and provenance; never write inputs."""
    fit_directory, cooked_path = Path(fit_directory), Path(cooked_path)
    data = bytearray(original)
    resources = parse_b04(data)
    mesh_bytes = cooked_path.read_bytes()
    buffer_bytes = Path(str(cooked_path) + '.1.buffer').read_bytes()
    mesh = CookedMesh(mesh_bytes, allow_multi_section=True)
    sections = mesh.skin_sections(buffer_bytes)
    if len(sections) != len(resources[0]['sections']):
        raise ValueError('Precision binding does not match native material sections')
    index_offset = struct.unpack('<I', mesh.get(mesh.cooked, 'indexBufferOffset', 'Uint32'))[0]
    allowed = np.zeros(len(data), bool)
    reports = []
    protected = sum(r['count'] for r in resources)
    resource = resources[0]
    rows = np.frombuffer(data, '<f4', resource['count'] * 13, resource['rowoffset']).reshape(-1, 13)
    for section_index, (native, section) in enumerate(zip(sections, resource['sections'])):
        lod, material, first, count = map(int, section[:4])
        if (lod, first, count) != (native['lod'], native['firstVertex'], native['vertexCount']):
            raise ValueError('Precision binding/native section identity differs')
        keys = ('positionOffset', 'uvOffset', 'lightingOffset', 'extraOffset', 'indexFirst', 'indexCount')
        if tuple(map(int, section[4:])) != tuple(native[k] for k in keys):
            raise ValueError('Precision binding/native section streams differ')
        if not material:
            continue
        if material not in (1, 2) or lod not in (0, 1):
            raise ValueError('Unobserved precision material semantic')
        fit_path = fit_directory / ('lod%d.npz' % lod)
        with np.load(fit_path) as archive:
            fit = {k: archive[k] for k in archive.files}
        body_count = int(fit['bodyCount'])
        authored = fit['points'][body_count:] * .01
        lineage = csr_matrix((fit['module_data'], fit['module_indices'], fit['module_indptr']), shape=fit['module_shape'])
        authored_uv = lineage @ fit['moduleOriginalUV']
        authored_faces = fit['faces'][np.all(fit['faces'] >= body_count, axis=1)] - body_count
        quant = np.frombuffer(buffer_bytes, '<u2', count * 8, native['positionOffset']).reshape(-1, 8)[:, :3]
        points = quant.astype(float) / 65535 * np.asarray(mesh.scale[:3]) + np.asarray(mesh.offset[:3])
        uv = np.frombuffer(buffer_bytes, '<f2', count * 2, native['uvOffset']).reshape(-1, 2)
        faces = np.frombuffer(buffer_bytes, '<u2', native['indexCount'], index_offset + native['indexFirst'] * 2).reshape(-1, 3)[:, [0, 2, 1]]
        ids, info = match_source_rows(points, uv, faces, authored, authored_uv, authored_faces)
        if info['extraIdenticalTriangles'] != int(material == 2):
            raise ValueError('Only the single observed Erect transport duplicate is allowed')
        seam = cKDTree(fit['points'][fit['seamBody']] * .01).query(authored[ids])[0] <= 1e-8
        selected = np.flatnonzero(~seam)
        before = rows[first + selected, :3].copy()
        rows[first + selected, :3] = np.asarray((authored[ids[selected]] - resource['bias']) / resource['scale'], np.float32)
        correction = np.linalg.norm(rows[first + selected, :3] * resource['scale'] + resource['bias'] - (before * resource['scale'] + resource['bias']), axis=1)
        if not np.isfinite(correction).all() or correction.max(initial=0) > 3e-5:
            raise ValueError('Source precision correction exceeds 3e-5 metres')
        for row in first + selected:
            start = resource['rowoffset'] + int(row) * 52
            allowed[start:start + 12] = True
        protected -= len(selected)
        reports.append(dict(section=section_index, lod=lod, semanticMaterial=material,
                            fitSHA256=sha(fit_path.read_bytes()), restoredInteriorRows=len(selected),
                            protectedSharedSeamRows=int(seam.sum()), maximumCorrectionMeters=float(correction.max(initial=0)), **info))
    if len(reports) != 4:
        raise ValueError('Both source states in both LODs are required')
    if np.any((np.frombuffer(original, 'u1') != np.frombuffer(data, 'u1')) & ~allowed):
        raise ValueError('Precision restoration changed protected or non-position bytes')
    result = bytes(data)
    report = dict(schema='malemod.witcher-v2-source-precision/1', rawBindingSHA256=sha(original),
                  bindingSHA256=sha(result), cookedMeshSHA256=sha(mesh_bytes), cookedBufferSHA256=sha(buffer_bytes),
                  stockBodyAndSharedSeamRowsByteIdentical=True, nonPositionBytesByteIdentical=True,
                  protectedRows=protected, sections=reports, sourceNumericsModified=False,
                  nativeObserved=False, attachmentGatePassed=False)
    return result, report


def restore_binding(binding_path, fit_directory, cooked_path, receipt_path):
    binding_path, receipt_path = Path(binding_path), Path(receipt_path)
    result, report = restore_payload(binding_path.read_bytes(), fit_directory, cooked_path)
    # All validation finishes before the generated binding is replaced.
    binding_path.write_bytes(result)
    receipt_path.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binding', type=Path, required=True)
    parser.add_argument('--fit', type=Path, required=True)
    parser.add_argument('--cooked', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(restore_binding(args.binding, args.fit, args.cooked, args.receipt), indent=2))
