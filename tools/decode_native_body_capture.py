"""Decode a captured 28-byte DX12 stream through its measured render contract.

Upload positions are resource-normalized coordinates, not metres. The returned
positions are the deformed pre-skinning mesh; this does not reconstruct the
game's skeletal pose, morph shader, camera, or a native screenshot.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

import numpy as np
from review_collar_integrity import VERTEX, contract

UPLOAD = np.dtype([('position', '<f4', 3), ('bones', '<u4'),
                   ('weights', '<u4'), ('normal', '<u4'), ('tangent', '<u4')])


def decode(capture, render, expected_upload_hash=None):
    capture, render = Path(capture), Path(render)
    payload = capture.read_bytes()
    if len(payload) % UPLOAD.itemsize:
        raise ValueError('Truncated native upload')
    fnv = 14695981039346656037
    for byte in payload:
        fnv = ((fnv ^ byte) * 1099511628211) & 0xffffffffffffffff
    if expected_upload_hash is not None and fnv != int(expected_upload_hash, 16):
        raise ValueError('Capture differs from the completed native upload hash')
    layouts = contract(render)  # Validates version, topology extent and EOF.
    raw = render.read_bytes()
    at = 240
    palette = struct.unpack_from('<I', raw, at)[0]
    at += 4 + palette * 132
    count = struct.unpack_from('<I', raw, at)[0]
    at += 4
    resources = []
    for _ in range(count):
        values = struct.unpack_from('<5I6f', raw, at)
        at += 44
        scale, bias = np.array(values[5:8]), np.array(values[8:11])
        if not np.isfinite(np.r_[scale, bias]).all() or np.any(scale <= 0):
            raise ValueError('Invalid observed resource calibration')
        resources.append((scale, bias, values[2], values[3]))
    at += 4  # LOD count, already validated by contract().
    vertices = np.frombuffer(payload, UPLOAD)
    expected_count = sum(lod['n'] for lod in layouts)
    if len(vertices) != expected_count or not np.isfinite(vertices['position']).all():
        raise ValueError('Capture topology differs from the render contract')
    result = np.zeros(expected_count, VERTEX)
    result['weights'] = vertices['weights']
    for attribute in ('normal', 'tangent'):
        word = vertices[attribute]
        result[attribute] = np.column_stack([
            ((word >> (10 * axis)) & 1023) / 1023. * 2 - 1 for axis in range(3)])
    result['sign'] = np.where(vertices['tangent'] >> 30 == 0, -1, 1)
    waist = {}
    for lod in layouts:
        at += 36
        reference, boundaries = [], []
        for _ in range(lod['n']):
            reference.append(struct.unpack_from('<3d', raw, at + 88))
            boundaries.append(struct.unpack_from('<I', raw, at + 128)[0])
            at += 156
        faces = struct.unpack_from('<I', raw, at)[0]
        at += 4 + faces * 12
        seams = struct.unpack_from('<I', raw, at)[0]
        at += 4 + seams * 20
        scale, bias, first_palette, palette_count = resources[lod['resource']]
        reference = np.asarray(reference)
        words = np.rint((reference - bias) / scale * 65535)
        if np.any((words < 0) | (words > 65535)):
            raise ValueError('Reference is outside its observed UNORM range')
        encoded = words.astype(np.float32) / np.float32(65535)
        selection = slice(lod['first'], lod['first'] + lod['n'])
        result['position'][selection] = (reference.astype(np.float32)
            + (vertices['position'][selection] - encoded) * scale)
        result['reference'][selection] = reference
        # Retain the actual upload's remapping, expressed in the global palette
        # expected by SourceRenderVertex, rather than restoring authored bones.
        bone_word = vertices['bones'][selection]
        global_word = np.zeros(lod['n'], dtype=np.uint32)
        for slot in range(4):
            local = (bone_word >> (8 * slot)) & 255
            if np.any(local >= palette_count) or np.any(local + first_palette > 255):
                raise ValueError('Captured bone index leaves its resource palette')
            global_word |= (local + first_palette) << (8 * slot)
        result['bones'][selection] = global_word
        for index, boundary in enumerate(boundaries):
            if boundary:
                waist.setdefault((lod['lod'], boundary), []).append(
                    result['position'][lod['first'] + index])
    if at != len(raw):
        raise ValueError('Native decoder did not consume the render contract')
    gaps = {}
    for (lod, _), points in waist.items():
        gap = float(np.linalg.norm(np.asarray(points) - points[0], axis=1).max())
        gaps[lod] = max(gaps.get(lod, 0.), gap)
    report = dict(captureSHA256=hashlib.sha256(payload).hexdigest(),
                  renderSHA256=hashlib.sha256(raw).hexdigest(),
                  uploadFNV64=f'{fnv:016x}', uploadHashVerified=expected_upload_hash is not None,
                  vertexCount=len(result), preSkinning=True,
                  sharedWaistAliasMaxGapMetres=gaps)
    return result, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('render', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--upload-fnv64')
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix('.json').exists():
        raise ValueError('Preserve existing decoded evidence; choose a new output')
    vertices, report = decode(args.capture, args.render, args.upload_fnv64)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    vertices.tofile(args.output)
    args.output.with_suffix('.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == '__main__':
    main()
