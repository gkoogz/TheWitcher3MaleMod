"""Read the observed native embedded world/group ownership, without rewriting.

The property terminators and group buffer order are measured from native REDkit
OnSerialize routines and the pinned diagnostic CR2W schema. This checks object
ownership independently of XML, which omits custom serialization tails.
"""
import struct
import zlib
from player_rig_redirect import header_crc


def inspect_layers(raw, expected_floor):
    if len(raw) < 160 or raw[:4] != b'CR2W' or struct.unpack_from('<I', raw, 4)[0] not in (159, 163, 164):
        raise ValueError('Unobserved world container')
    if header_crc(raw, 0) != struct.unpack_from('<I', raw, 32)[0]:
        raise ValueError('World header CRC differs')
    def table(index, stride):
        at, count, crc = struct.unpack_from('<III', raw, 40 + 12 * index)
        if at < 160 or count * stride > len(raw) - at:
            raise ValueError('World table bounds differ')
        data = raw[at:at + count * stride]
        if zlib.crc32(data) != crc:
            raise ValueError('World table CRC differs')
        return data
    strings = table(0, 1)
    def pool(at):
        if at >= len(strings):
            raise ValueError('World string offset leaves pool')
        end = strings.find(b'\0', at)
        if end < 0:
            raise ValueError('World string is unterminated')
        return strings[at:end].decode('utf-8')
    names = [pool(at) for at, _ in struct.iter_unpack('<II', table(1, 8))]
    objects = []
    for kind, flags, parent, size, at, template, crc in struct.iter_unpack('<HHIIIII', table(4, 24)):
        if kind >= len(names) or size > len(raw) - at:
            raise ValueError('World export bounds differ')
        data = raw[at:at + size]
        if zlib.crc32(data) != crc:
            raise ValueError('World export flags/CRC differ')
        if names[kind] not in ('CGameWorld', 'CLayerGroup', 'CLayerInfo'):
            objects.append(dict(kind=names[kind], properties={}, tail=b''))
            continue
        if not data or data[0] != 0:
            raise ValueError('World ownership export flags differ')
        cursor = 1
        properties = {}
        while cursor + 2 <= len(data):
            name = struct.unpack_from('<H', data, cursor)[0]
            if not name:
                cursor += 2
                break
            if cursor + 8 > len(data):
                raise ValueError('World property truncated')
            name, propkind, length = struct.unpack_from('<HHI', data, cursor)
            if name >= len(names) or propkind >= len(names) or length < 4 or 4 + length > len(data) - cursor or names[name] in properties:
                raise ValueError('World property bounds/type/repetition differ')
            properties[names[name]] = (names[propkind], data[cursor + 8:cursor + 4 + length])
            cursor += 4 + length
        else:
            raise ValueError('Missing world property terminator')
        objects.append(dict(kind=names[kind], properties=properties, tail=data[cursor:]))
    def reference(value, cls):
        if value <= 0 or value > len(objects) or objects[value - 1]['kind'] != cls:
            raise ValueError('Native internal ownership is NULL/wrong class/out of bounds')
        return objects[value - 1]
    worlds = [o for o in objects if o['kind'] == 'CGameWorld']
    if len(worlds) != 1:
        raise ValueError('Expected one game world')
    world = worlds[0]
    embedded = world['properties'].get('hasEmbeddedLayerInfos')
    if embedded != ('Bool', b'\x01') or len(world['tail']) != 4:
        raise ValueError('Cooked world lacks a native embedded root')
    root_id = struct.unpack('<i', world['tail'])[0]
    reference(root_id, 'CLayerGroup')
    world_id = objects.index(world) + 1
    floor_ids = []
    visited = set()
    def vlq(data, cursor):
        if cursor >= len(data):
            raise ValueError('Truncated layer count')
        first = data[cursor]; cursor += 1
        value = first & 63; next_byte = first & 64; shift = 6
        while next_byte:
            if cursor >= len(data) or shift > 27:
                raise ValueError('Invalid layer count continuation')
            byte = data[cursor]; cursor += 1
            value |= (byte & 127) << shift; shift += 7; next_byte = byte & 128
        if first & 128 and value:
            raise ValueError('Negative native layer count')
        return value, cursor
    def read_string(prop):
        if prop[0] != 'String' or not prop[1]:
            raise ValueError('Layer depot path type differs')
        data = prop[1]; first = data[0]; cursor = 1; length = first & 63
        if first & 64:
            if len(data) < 2:
                raise ValueError('Truncated layer path count')
            length += 64 * data[1]; cursor += 1
        width = 1 if first & 128 else 2
        if cursor + width * length != len(data):
            raise ValueError('Native layer path bounds differ')
        return data[cursor:].decode('latin-1' if width == 1 else 'utf-16-le').replace('\\', '/').lower()
    def walk(group_id, expected_parent):
        if group_id in visited:
            raise ValueError('Duplicate/cyclic native layer ownership')
        visited.add(group_id)
        group = reference(group_id, 'CLayerGroup')
        if group['properties'].get('hasEmbeddedLayerInfos') != ('Bool', b'\x01'):
            raise ValueError('Native group is not embedded')
        data = group['tail']
        if len(data) < 10:
            raise ValueError('Native group tail truncated')
        owner, parent = struct.unpack_from('<ii', data)
        if owner != world_id or parent != expected_parent:
            raise ValueError('Native group world/parent ownership differs')
        cursor = 8
        count, cursor = vlq(data, cursor)
        if count > len(objects) or cursor + 4 * count > len(data):
            raise ValueError('Native subgroup count/bounds differ')
        children = list(struct.unpack_from('<' + 'i' * count, data, cursor))
        cursor += 4 * count
        count, cursor = vlq(data, cursor)
        if count > len(objects) or cursor + 4 * count != len(data):
            raise ValueError('Native layer info count/bounds differ')
        infos = list(struct.unpack_from('<' + 'i' * count, data, cursor))
        for info_id in infos:
            info = reference(info_id, 'CLayerInfo')
            if info['properties'].get('hasEmbeddedLayerInfo') != ('Bool', b'\x01') or info['tail'] != struct.pack('<i', group_id):
                raise ValueError('Native layer info parent ownership differs')
            if read_string(info['properties']['depotFilePath']) == expected_floor.replace('\\', '/').lower():
                floor_ids.append(info_id)
        for child in children:
            walk(child, group_id)
    walk(root_id, 0)
    if len(floor_ids) != 1:
        raise ValueError('Native root must own exactly one expected floor')
    return dict(schema='malemod.native-layer-ownership/1', worldExport=world_id,
                rootExport=root_id, groupExports=sorted(visited), floorInfoExport=floor_ids[0],
                floor=expected_floor, worldParentRootAndFloorLinksVerified=True)
