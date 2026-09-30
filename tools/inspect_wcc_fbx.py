"""Read raw mesh arrays from WCC's binary FBX exports for asset discovery.

Requires numpy. This narrowly inspects observed WCC exports; it does not evaluate
FBX transforms, skin deformation, animation or textures, or import a character.
"""
import argparse
from pathlib import Path
import struct
import zlib

import numpy as np


def inspect(path):
    data = Path(path).read_bytes()
    if data[:23] != b'Kaydara FBX Binary  \x00\x1a\x00':
        raise ValueError('Expected a binary WCC FBX export')
    version = struct.unpack_from('<I', data, 23)[0]
    header, header_size = ('<QQQB', 25) if version >= 7500 else ('<IIIB', 13)
    scalar = {'Y': 'h', 'C': '?', 'I': 'i', 'F': 'f', 'D': 'd', 'L': 'q'}
    arrays = {'f': '<f4', 'd': '<f8', 'i': '<i4', 'l': '<i8', 'b': 'u1', 'c': 'i1'}

    def node(position):
        end, count, property_bytes, name_length = struct.unpack_from(header, data, position)
        if not end:
            return None, position + header_size
        if not position < end <= len(data):
            raise ValueError('Invalid FBX node bounds')
        name = data[position + header_size:position + header_size + name_length].decode()
        position += header_size + name_length
        properties_end = position + property_bytes
        properties = []
        for _ in range(count):
            tag = chr(data[position])
            position += 1
            if tag in scalar:
                fmt = '<' + scalar[tag]
                value = struct.unpack_from(fmt, data, position)[0]
                position += struct.calcsize(fmt)
            elif tag in ('S', 'R'):
                length = struct.unpack_from('<I', data, position)[0]
                position += 4
                value = data[position:position + length].decode(errors='replace') if tag == 'S' else None
                position += length
            elif tag in arrays:
                length, encoding, size = struct.unpack_from('<III', data, position)
                position += 12
                if encoding not in (0, 1):
                    raise ValueError('Unknown FBX array encoding')
                raw = data[position:position + size]
                position += size
                value = np.frombuffer(zlib.decompress(raw) if encoding else raw, dtype=arrays[tag]).copy()
                if len(value) != length:
                    raise ValueError('FBX array length mismatch')
            else:
                raise ValueError('Unsupported FBX property: ' + tag)
            properties.append(value)
        if position != properties_end:
            raise ValueError('FBX property boundary mismatch')
        children = []
        while position < end - header_size:
            child, position = node(position)
            if child:
                children.append(child)
        return {'name': name, 'properties': properties, 'children': children}, end

    position, roots = 27, []
    while position + header_size <= len(data):
        item, position = node(position)
        if not item:
            break
        roots.append(item)
    objects = next(n for n in roots if n['name'] == 'Objects')['children']
    meshes = []
    for item in objects:
        if item['name'] != 'Geometry' or item['properties'][-1] != 'Mesh':
            continue
        children = {c['name']: c for c in item['children']}
        vertices = children['Vertices']['properties'][0].reshape(-1, 3)
        indices = children['PolygonVertexIndex']['properties'][0]
        faces, polygon = [], []
        for index in indices:
            polygon.append(int(index) if index >= 0 else -int(index) - 1)
            if index < 0:
                faces.extend([polygon[0], polygon[j], polygon[j + 1]] for j in range(1, len(polygon) - 1))
                polygon = []
        triangles = np.array(faces, dtype=np.int32)
        if polygon or triangles.min() < 0 or triangles.max() >= len(vertices):
            raise ValueError('Invalid polygon indices')
        meshes.append({'vertices': vertices, 'triangles': triangles})
    models = [n['properties'][1].split('\x00')[0] for n in objects if n['name'] == 'Model']
    materials = [n['properties'][1].split('\x00')[0] for n in objects if n['name'] == 'Material']
    return version, meshes, models, materials


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fbx', type=Path)
    args = parser.parse_args()
    version, meshes, models, materials = inspect(args.fbx)
    print('FBX version:', version, '| models:', len(models), '| materials:', materials)
    for index, mesh in enumerate(meshes):
        v, f = mesh['vertices'], mesh['triangles']
        print('Geometry', index, '| vertices:', len(v), '| triangles:', len(f),
              '| bounds:', v.min(axis=0).tolist(), v.max(axis=0).tolist())
