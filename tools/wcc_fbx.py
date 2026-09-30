"""Narrow, lossless binary FBX editing for observed official WCC mesh exports.

Unknown properties and embedded resources retain their original encoded bytes.
This is not a general FBX transform evaluator. Native import/export validates
the resulting rig; we never synthesize skeleton transforms or bone names.
"""
from dataclasses import dataclass, field
from pathlib import Path
import struct
import zlib
import numpy as np


@dataclass
class Property:
    tag: str
    value: object
    raw: bytes = None

    def encode(self):
        if self.raw is not None:
            return self.raw
        if self.tag in 'fdilbc':
            dtype = {'f':'<f4','d':'<f8','i':'<i4','l':'<i8','b':'u1','c':'i1'}[self.tag]
            a = np.asarray(self.value, dtype=dtype).reshape(-1)
            compressed = zlib.compress(a.tobytes())
            return self.tag.encode() + struct.pack('<III', len(a), 1, len(compressed)) + compressed
        raise ValueError('Only array mutations are supported')


@dataclass
class Node:
    name: str
    props: list = field(default_factory=list)
    children: list = field(default_factory=list)
    sentinel: bool = False

    @property
    def values(self):
        return [p.value for p in self.props]

    def child(self, name):
        found = [n for n in self.children if n.name == name]
        if len(found) != 1:
            raise ValueError(f'Expected one {name} in {self.name}, found {len(found)}')
        return found[0]

    def array(self, name):
        return self.child(name).props[0].value

    def set_array(self, name, values):
        prop = self.child(name).props[0]
        prop.value = np.asarray(values).reshape(-1)
        prop.raw = None


class Document:
    def __init__(self, path):
        data = Path(path).read_bytes()
        if data[:23] != b'Kaydara FBX Binary  \x00\x1a\x00':
            raise ValueError('Expected binary FBX')
        self.version = struct.unpack_from('<I', data, 23)[0]
        self.fmt, self.size = ('<QQQB',25) if self.version >= 7500 else ('<IIIB',13)
        self.prefix = data[:27]
        scalar = {'Y':'h','C':'?','I':'i','F':'f','D':'d','L':'q'}
        arrays = {'f':'<f4','d':'<f8','i':'<i4','l':'<i8','b':'u1','c':'i1'}

        def parse(pos):
            end, count, propbytes, namelen = struct.unpack_from(self.fmt, data, pos)
            if end == 0:
                if data[pos:pos+self.size] != bytes(self.size):
                    raise ValueError('Invalid FBX sentinel')
                return None, pos + self.size
            if not pos < end <= len(data):
                raise ValueError('Invalid node offset')
            name = data[pos+self.size:pos+self.size+namelen].decode()
            pos += self.size + namelen
            prop_end = pos + propbytes
            props = []
            for _ in range(count):
                start = pos; tag = chr(data[pos]); pos += 1
                if tag in scalar:
                    fmt = '<' + scalar[tag]
                    value = struct.unpack_from(fmt,data,pos)[0];pos += struct.calcsize(fmt)
                elif tag in ('S','R'):
                    length = struct.unpack_from('<I',data,pos)[0];pos += 4
                    value = data[pos:pos+length]
                    if tag == 'S': value = value.decode()
                    pos += length
                elif tag in arrays:
                    length, encoding, size = struct.unpack_from('<III',data,pos);pos += 12
                    raw = data[pos:pos+size];pos += size
                    if encoding not in (0,1): raise ValueError('Unknown array encoding')
                    value = np.frombuffer(zlib.decompress(raw) if encoding else raw,dtype=arrays[tag]).copy()
                    if len(value) != length: raise ValueError('Array length mismatch')
                else: raise ValueError('Unsupported FBX property: ' + tag)
                props.append(Property(tag,value,data[start:pos]))
            if pos != prop_end: raise ValueError('Property boundary mismatch')
            children, sentinel = [], False
            while pos < end:
                child,pos = parse(pos)
                if child is None:
                    sentinel = True
                    if pos != end: raise ValueError('Early node sentinel')
                else: children.append(child)
            return Node(name,props,children,sentinel),end

        pos,self.nodes = 27,[]
        while True:
            node,pos = parse(pos)
            if node is None: break
            self.nodes.append(node)
        # Footer begins with a fixed 16-byte identifier followed by alignment
        # padding, then the version and fixed suffix. Realign after mutations.
        tail = data[pos:]
        marker = struct.pack('<I',self.version)
        version_pos = tail.find(marker,16,64)
        if version_pos < 0: raise ValueError('Unrecognized FBX footer')
        self.footer_id = tail[:16]
        self.footer_suffix = tail[version_pos:]
        self.original_footer = tail
        self.original_footer_offset = pos

    def root(self, name):
        return next(n for n in self.nodes if n.name == name)

    @property
    def objects(self): return self.root('Objects').children

    @property
    def meshes(self):
        return [n for n in self.objects if n.name == 'Geometry' and n.values[-1] == 'Mesh']

    def save(self,path):
        def encode(node,pos):
            name = node.name.encode()
            properties = b''.join(p.encode() for p in node.props)
            cursor = pos+self.size+len(name)+len(properties)
            children = []
            for child in node.children:
                raw = encode(child,cursor);children.append(raw);cursor += len(raw)
            if node.sentinel: children.append(bytes(self.size));cursor += self.size
            return struct.pack(self.fmt,cursor,len(node.props),len(properties),len(name))+name+properties+b''.join(children)
        output = bytearray(self.prefix)
        for node in self.nodes: output.extend(encode(node,len(output)))
        output.extend(bytes(self.size))
        if len(output) == self.original_footer_offset:
            output.extend(self.original_footer)
        else:
            # Preserve the source's footer-version alignment modulo 16.
            original_version = self.original_footer_offset + len(self.original_footer)-len(self.footer_suffix)
            padding = (original_version-(len(output)+16)) % 16
            output.extend(self.footer_id+bytes(padding)+self.footer_suffix)
        Path(path).write_bytes(output)

    def skin(self,mesh):
        objects = {n.values[0]:n for n in self.objects}
        connections = [n.values for n in self.root('Connections').children]
        skin = [objects[c[1]] for c in connections if c[0]=='OO' and c[2]==mesh.values[0]
                and objects.get(c[1],Node('')).name=='Deformer']
        if len(skin)!=1 or skin[0].values[-1]!='Skin': raise ValueError('Expected one skin')
        result=[]
        for c in connections:
            if c[0]!='OO' or c[2]!=skin[0].values[0]: continue
            cluster=objects[c[1]]
            links=[objects[x[1]] for x in connections if x[0]=='OO' and x[2]==cluster.values[0]
                   and objects.get(x[1],Node('')).name=='Model']
            if len(links)!=1: raise ValueError('Ambiguous cluster bone')
            result.append((links[0].values[1].split('\x00')[0],cluster))
        return result


def triangles(mesh):
    indices=mesh.array('PolygonVertexIndex').reshape(-1,3).copy()
    if np.any(indices[:,:2]<0) or np.any(indices[:,2]>=0):
        raise ValueError('Expected triangulated native geometry')
    indices[:,2]=-indices[:,2]-1
    return indices
