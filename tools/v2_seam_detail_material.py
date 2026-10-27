"""Author a fresh seam-only stock-detail graph; official resave/cook required.

UV0, source textures, geometry and native RNM/distance/roughness/SpecAA laws stay
unchanged. UV1 is supplied separately and must equal stock UV0 at the weld.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import struct
import zlib

from packed_mesh_format import CookedMesh
from player_rig_redirect import header_crc
from v2_skin_material import GRAPH, state
from v2_fabric_material import observed_name_entries

STOCK_AMBIENT = 'characters\\models\\geralt\\body\\model\\body_01_mg__geralt_a01.xbm'
STOCK_DETAIL = 'characters\\models\\common\\textures\\detailmaps_pbr\\detailmap_skin_02.xbm'
PARAMETER = 'StockSeamAmbient'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def native_name_hash(text):
    # Verified against every nonempty name in the closed native source graph.
    if not text:
        return 0
    value = 2166136261
    for byte in text.encode('utf-8') + b'\0':
        value = ((value ^ byte) * 16777619) & 0xffffffff
    return value


def uv1_contract(sdk):
    """Read the real SDK163 UV1 property, with table/export CRC checks."""
    path = Path(sdk) / 'engine/materials/graphs/grid_vat.w2mg'
    raw = path.read_bytes()
    if raw[:4] != b'CR2W' or struct.unpack_from('<I', raw, 4)[0] != 163 or header_crc(raw, 0) != struct.unpack_from('<I', raw, 32)[0]:
        raise ValueError('Unobserved SDK UV1 donor header')
    def table(index, stride):
        offset, count, crc = struct.unpack_from('<III', raw, 40 + index * 12)
        data = raw[offset:offset + count * stride]
        if offset < 160 or len(data) != count * stride or zlib.crc32(data) != crc:
            raise ValueError('SDK UV1 donor table CRC/bounds differ')
        return data
    strings = table(0, 1)
    reader = CookedMesh.__new__(CookedMesh)
    reader.names = [strings[offset:strings.index(b'\0', offset)].decode() for offset, _ in struct.iter_unpack('<II', table(1, 8))]
    matches = []
    for index, entry in enumerate(struct.iter_unpack('<HHIIIII', table(4, 24))):
        kind, _, _, length, offset, _, crc = entry
        data = raw[offset:offset + length]
        if offset < 160 or len(data) != length or zlib.crc32(data) != crc:
            raise ValueError('SDK UV1 donor export CRC/bounds differ')
        properties, _ = reader.object(data)
        if reader.names[kind] == 'CMaterialBlockTexCoords' and properties.get('coordinatesIndex') == ('Int32', struct.pack('<i', 1)):
            matches.append(index)
    if len(matches) != 1:
        raise ValueError('Expected one observed SDK UV1 node')
    return dict(path=str(path), SHA256=digest(path), version=163, export=matches[0],
                node='CMaterialBlockTexCoords', property='coordinatesIndex', type='Int32', bytes='01000000')


class Graph:
    def __init__(self, path):
        self.path = Path(path)
        self.raw = self.path.read_bytes()
        reader, imports, objects, _, _, _ = state(path)
        self.reader, self.names = reader, list(reader.names)
        self.imports, self.objects = list(imports), copy.deepcopy(objects)

    def name(self, node, key='name'):
        ty, value = self.objects[node][2][key]
        if ty != 'CName' or len(value) != 2:
            raise ValueError('Unobserved graph name')
        return self.names[struct.unpack('<H', value)[0]]

    def ids(self, node, key='sockets'):
        data = self.objects[node][2].get(key, ('', bytes(4)))[1]
        count, = struct.unpack_from('<I', data)
        if len(data) != 4 + count * 4:
            raise ValueError('Invalid graph pointer array')
        return [value[0] - 1 for value in struct.iter_unpack('<i', data[4:])]

    def ptr(self, node, key):
        return struct.unpack('<i', self.objects[node][2][key][1])[0] - 1

    def array(self, node, key, ids):
        ty = {'sockets':'array:2,0,ptr:CGraphSocket', 'connections':'array:2,0,ptr:CGraphConnection',
              'blocks':'array:2,0,ptr:CGraphBlock', 'pixelParameterBlocks':'array:2,0,ptr:CMaterialParameter'}[key]
        self.objects[node][2][key] = (ty, struct.pack('<I', len(ids)) + b''.join(struct.pack('<i', i + 1) for i in ids))

    def parameter(self, label):
        ids = [i for i, o in enumerate(self.objects) if 'parameterName' in o[2] and self.name(i, 'parameterName') == label]
        if len(ids) != 1:
            raise ValueError('Ambiguous graph parameter ' + label)
        return ids[0]

    def socket(self, node, label):
        ids = [i for i in self.ids(node) if self.name(i) == label]
        if len(ids) != 1:
            raise ValueError('Ambiguous graph socket ' + label)
        return ids[0]

    def upstream(self, socket):
        edges = self.ids(socket, 'connections')
        if len(edges) != 1 or self.ptr(edges[0], 'source') != socket:
            raise ValueError('Missing or ambiguous graph input')
        other = self.ptr(edges[0], 'destination')
        if not any(self.ptr(e, 'source') == other and self.ptr(e, 'destination') == socket for e in self.ids(other, 'connections')):
            raise ValueError('Missing reciprocal graph edge')
        return other

    def sampler(self, parameter):
        outputs = self.ids(self.socket(parameter, 'Texture'), 'connections')
        if len(outputs) != 1:
            raise ValueError('Ambiguous texture sampler')
        node = self.ptr(self.ptr(outputs[0], 'destination'), 'block')
        if self.objects[node][0] != 'CMaterialBlockSamplerTexture':
            raise ValueError('Texture does not feed the observed sampler')
        return node

    def clone(self, owner):
        selected = [owner] + self.ids(owner)
        mapping = {old: len(self.objects) + n for n, old in enumerate(selected)}
        for old in selected:
            node = copy.deepcopy(self.objects[old])
            node[2].pop('position', None)
            node[2].pop('connections', None)
            if 'sockets' in node[2]:
                node[2]['sockets'] = (node[2]['sockets'][0], struct.pack('<I', len(self.ids(old))) + b''.join(struct.pack('<i', mapping[s] + 1) for s in self.ids(old)))
            if 'block' in node[2]:
                node[2]['block'] = (node[2]['block'][0], struct.pack('<i', mapping[self.ptr(old, 'block')] + 1))
            self.objects.append(node)
        return mapping[owner]

    def rewire(self, input_id, output_id):
        for edge in self.ids(input_id, 'connections'):
            other = self.ptr(edge, 'destination')
            self.array(other, 'connections', [e for e in self.ids(other, 'connections') if self.ptr(e, 'destination') != input_id])
        first = len(self.objects)
        template = next(o for o in self.objects if o[0] == 'CGraphConnection')
        for a, b in [(input_id, output_id), (output_id, input_id)]:
            node = copy.deepcopy(template)
            node[2].clear()
            node[2].update(source=('ptr:CGraphSocket', struct.pack('<i', a + 1)), destination=('ptr:CGraphSocket', struct.pack('<i', b + 1)))
            self.objects.append(node)
        self.array(input_id, 'connections', [first])
        self.array(output_id, 'connections', self.ids(output_id, 'connections') + [first + 1])

    def texture(self, parameter, path):
        if path not in self.imports:
            self.imports.append(path)
        self.objects[parameter][2]['texture'] = ('handle:ITexture', struct.pack('<i', -self.imports.index(path) - 1))

    def texture_path(self, parameter):
        handle, = struct.unpack('<i', self.objects[parameter][2]['texture'][1])
        if handle >= 0 or -handle > len(self.imports):
            raise ValueError('Texture handle leaves import table')
        return self.imports[-handle - 1]

    def rebuild(self):
        raw, names = self.raw, self.names
        hashes = observed_name_entries(self.path)
        if any(native_name_hash(name) != value for name, value in hashes.items()):
            raise ValueError('Native name-hash convention differs')
        if any(struct.unpack_from('<II', raw, 40 + i * 12) != (0, 0) for i in range(5, 10)):
            raise ValueError('Graph external tables are unsupported')
        so, count, _ = struct.unpack_from('<III', raw, 40)
        strings = bytearray(raw[so:so + count]); offsets = {}; at = 0
        while at < len(strings):
            end = strings.index(0, at); offsets[strings[at:end].decode()] = at; at = end + 1
        for name in names + self.imports:
            if name not in offsets:
                offsets[name] = len(strings); strings += name.encode() + b'\0'
        name_table = b''.join(struct.pack('<II', offsets[n], hashes.get(n, native_name_hash(n))) for n in names)
        io, ic, _ = struct.unpack_from('<III', raw, 64)
        old_imports = list(struct.iter_unpack('<IHH', raw[io:io + ic * 8]))
        if not old_imports or any(kind != names.index('CBitmapTexture') or flags != 0 for _, kind, flags in old_imports):
            raise ValueError('Unobserved graph texture import kind')
        imports = b''.join(struct.pack('<IHH', offsets[path], names.index('CBitmapTexture'), 0) for path in self.imports)
        po, pc, crc = struct.unpack_from('<III', raw, 76); properties = raw[po:po + pc * 16]
        if len(properties) != pc * 16 or zlib.crc32(properties) != crc:
            raise ValueError('Graph property-table CRC differs')
        eo, ec, _ = struct.unpack_from('<III', raw, 88); entries = list(struct.iter_unpack('<HHIIIII', raw[eo:eo + ec * 24])); by_kind = {names[e[0]]:e for e in entries}
        result = bytearray(raw[:160])
        for i, table in enumerate([bytes(strings), name_table, imports, properties]):
            while len(result) % 4: result += b'\0'
            offset = len(result); result += table
            struct.pack_into('<III', result, 40 + i * 12, offset, len(table) // [1,8,8,16][i], zlib.crc32(table))
        while len(result) % 4: result += b'\0'
        offset = len(result); cursor = offset + len(self.objects) * 24; table = bytearray(); data = bytearray()
        for i, (kind, _, props, tail) in enumerate(self.objects):
            payload = b'\0'
            for label, (ty, value) in props.items():
                payload += struct.pack('<HHI', names.index(label), names.index(ty), 4 + len(value)) + value
            payload += b'\0\0' + tail
            # A derived graph may add a built-in class whose exact native
            # export header was observed in a separate, CRC-checked donor.
            # Legacy callers have no extra headers and retain strict lookup.
            header = entries[i] if i < ec else by_kind.get(kind)
            if header is None:
                header = getattr(self, 'extra_export_headers', {}).get(kind)
                if header is None:
                    raise ValueError('New graph class lacks observed native header: '+kind)
            _, flags, parent, _, _, template, _ = header
            table += struct.pack('<HHIIIII', names.index(kind), flags, parent, len(payload), cursor, template, zlib.crc32(payload)); data += payload; cursor += len(payload)
        result += table + data
        struct.pack_into('<III', result, 88, offset, len(self.objects), zlib.crc32(table))
        struct.pack_into('<II', result, 24, len(result), len(result)); struct.pack_into('<I', result, 32, header_crc(result, 0))
        return result


def inspect(path):
    g = Graph(path)
    stock, ambient, detail = [g.parameter(p) for p in [PARAMETER, 'Ambient', 'DetailNormal']]
    if g.texture_path(stock) != STOCK_AMBIENT or g.texture_path(detail) != STOCK_DETAIL:
        raise ValueError('Stock seam texture dependency differs')
    sampler, current, detail_sampler = g.sampler(stock), g.sampler(ambient), g.sampler(detail)
    uv = g.upstream(g.socket(sampler, 'UV')); uv_node = g.ptr(uv, 'block')
    if g.objects[uv_node][0] != 'CMaterialBlockTexCoords' or g.objects[uv_node][2].get('coordinatesIndex') != ('Int32', struct.pack('<i', 1)):
        raise ValueError('Stock seam mask is not sampled at untiled UV1')
    tile = g.ptr(g.upstream(g.socket(detail_sampler, 'UV')), 'block')
    if g.objects[tile][0] != 'CMaterialBlockMathMultiply' or g.upstream(g.socket(tile, 'A')) != uv or g.ptr(g.upstream(g.socket(tile, 'B')), 'block') != g.parameter('DetailTile'):
        raise ValueError('Detail sampler lost UV1 times native DetailTile')
    vector, _ = g.reader.object(g.objects[g.parameter('DetailTile')][2]['vector'][1])
    if any(vector[k] != ('Float', struct.pack('<f', 25)) for k in ['X','Y']):
        raise ValueError('Stock detail tile differs')
    if g.objects[g.parameter('DetailPower')][2].get('scalar') != ('Float', struct.pack('<f', .5)):
        raise ValueError('Stock detail power differs')
    red, blue = g.socket(sampler, 'Red'), g.socket(current, 'Blue')
    masks = []
    for i, obj in enumerate(g.objects):
        if obj[0] != 'CMaterialBlockMathMultiply': continue
        if not g.ids(g.socket(i, 'A'), 'connections') or not g.ids(g.socket(i, 'B'), 'connections'): continue
        if g.upstream(g.socket(i, 'A')) == red and g.upstream(g.socket(i, 'B')) == blue:
            masks.append(i)
    if len(masks) != 1: raise ValueError('Detail mask is not stockR(UV1) times seamWeight')
    out = g.socket(masks[0], 'Out')
    destinations = [g.ptr(e, 'destination') for e in g.ids(out, 'connections')]
    if len(destinations) != 3 or sorted(g.name(s) for s in destinations) != ['cutoff','cutoff','tMask']:
        raise ValueError('Expected only the original three native detail mask inputs')
    if any(g.upstream(s) != out for s in destinations): raise ValueError('Detail mask connection is not reciprocal')
    if any(g.ptr(s, 'block') == masks[0] for e in g.ids(g.socket(current, 'Red'), 'connections') for s in [g.ptr(e, 'destination')]):
        raise ValueError('Native source second-lobe mask was repurposed')
    for signature in [b'sourceSpecular(',b'sourceSubsurface(',b'sourceSeamAntiLight(']:
        if len([o for o in g.objects if signature in o[2].get('customCode',('',b''))[1]]) != 1:
            raise ValueError('Source material branch missing')
    return dict(graph=GRAPH, SHA256=digest(path), uvIndex=1, detailPower=.5, detailTile=[25,25],
                detailMask='StockSeamAmbient.R(UV1)*Ambient.B', detailMaskInputs=3,
                stockAmbient=STOCK_AMBIENT, detailNormal=STOCK_DETAIL, officialResaveRequired=True,
                nativeGameplayObserved=False)


def author(source, job, sdk):
    source, job, sdk = Path(source).absolute(), Path(job).absolute(), Path(sdk).absolute()
    if job.exists(): raise ValueError('Choose a fresh candidate directory')
    evidence = uv1_contract(sdk); g = Graph(source); original = copy.deepcopy(g.objects)
    for label in ['coordinatesIndex','Int32',PARAMETER]:
        if label not in g.names: g.names.append(label)
    root = next(i for i, o in enumerate(g.objects) if o[0] == 'CMaterialGraph')
    ambient = g.parameter('Ambient'); ambient_sampler = g.sampler(ambient)
    detail = g.parameter('DetailNormal'); detail_sampler = g.sampler(detail)
    tile = g.ptr(g.upstream(g.socket(detail_sampler, 'UV')), 'block')
    uv0 = g.ptr(g.upstream(g.socket(tile, 'A')), 'block')
    uv1 = g.clone(uv0); g.objects[uv1][2]['coordinatesIndex'] = ('Int32', struct.pack('<i', 1)); uv_out = g.socket(uv1, 'UV')
    stock = g.clone(ambient); g.objects[stock][2]['parameterName'] = ('CName', struct.pack('<H', g.names.index(PARAMETER))); g.texture(stock, STOCK_AMBIENT)
    sampler = g.clone(ambient_sampler); g.rewire(g.socket(sampler, 'Texture'), g.socket(stock, 'Texture')); g.rewire(g.socket(sampler, 'UV'), uv_out)
    multiply = next(i for i, o in enumerate(original) if o[0] == 'CMaterialBlockMathMultiply')
    mask = g.clone(multiply); g.rewire(g.socket(mask, 'A'), g.socket(sampler, 'Red')); g.rewire(g.socket(mask, 'B'), g.socket(ambient_sampler, 'Blue'))
    destinations = [g.ptr(e, 'destination') for e in g.ids(g.socket(ambient_sampler, 'Red'), 'connections')]
    detail_inputs = [s for s in destinations if g.name(s) in ['cutoff','tMask'] and g.objects[g.ptr(s, 'block')][0] == 'CMaterialBlockCustomFunction']
    if len(detail_inputs) != 3: raise ValueError('Unobserved native detail mask branches')
    for socket in detail_inputs: g.rewire(socket, g.socket(mask, 'Out'))
    g.rewire(g.socket(tile, 'A'), uv_out); g.texture(detail, STOCK_DETAIL)
    g.objects[g.parameter('DetailPower')][2]['scalar'] = ('Float', struct.pack('<f', .5))
    props, tail = g.reader.object(g.objects[g.parameter('DetailTile')][2]['vector'][1]); props['X'] = props['Y'] = ('Float', struct.pack('<f', 25)); blob = b'\0'
    for label, (ty, value) in props.items(): blob += struct.pack('<HHI', g.names.index(label), g.names.index(ty), 4 + len(value)) + value
    g.objects[g.parameter('DetailTile')][2]['vector'] = ('Vector', blob + b'\0\0' + tail)
    g.array(root, 'blocks', g.ids(root, 'blocks') + [uv1,stock,sampler,mask]); g.array(root, 'pixelParameterBlocks', g.ids(root, 'pixelParameterBlocks') + [stock])
    # Preserve every existing function and the original compiled shader bytes.
    for i, obj in enumerate(original):
        if 'customCode' in obj[2] and obj[2]['customCode'] != g.objects[i][2]['customCode']:
            raise ValueError('Native/source function arithmetic changed')
    if original[root][3] != g.objects[root][3]: raise ValueError('Compiled shader payload was patched')
    target = job / 'build/intake' / GRAPH; target.parent.mkdir(parents=True); target.write_bytes(g.rebuild())
    proof = dict(schema='malemod.seam-stock-detail-graph/1', source=str(source), sourceSHA256=digest(source),
                 SDKUV1=evidence, graph=str(target), inspection=inspect(target),
                 sourceCustomFunctionsByteIdentical=True, nativeShaderPayloadUnchanged=True,
                 originalUV0NodeUnchanged=original[uv0] == g.objects[uv0], sourceTexturesChanged=False,
                 geometryChanged=False, nativeCompiled=False, cooked=False, staged=False)
    # Removing one outgoing UV0 edge is the only topology edit to that node's
    # original output socket; its class/properties and all UV0 samplers remain.
    proof['originalUV0NodeUnchanged'] = original[uv0] == g.objects[uv0]
    (job/'graph-authored.json').write_text(json.dumps(proof, indent=2)+'\n')
    return proof


def resave(job):
    """Compile only this graph using the exact owned native WCC runtime."""
    import mod
    from build_v2_anatomy_material import complete_depot
    job = Path(job).absolute()
    root = Path(__file__).resolve().parents[1]
    if not job.resolve().is_relative_to((root/'v2/build/materials').resolve()):
        raise ValueError('Graph resave must remain in an owned material job')
    graph = job/'build/intake'/GRAPH
    authored = json.loads((job/'graph-authored.json').read_text())
    if authored['inspection']['SHA256'] != digest(graph) or (job/'graph-compiled.json').exists():
        raise ValueError('Graph changed or was already resaved')
    shutil.copy2(graph, job/'authored-skin.w2mg')
    before = Graph(graph)
    cfg = mod.settings()
    isolated = root/'v2/build/materials/anatomy-01/build/shaders-05/runtime/bin/x64_RedKit/wcc_lite.exe'
    if digest(isolated) != digest(cfg['wcc']):
        raise ValueError('Owned WCC differs from the exact SDK compiler')
    cfg['wcc'] = isolated
    cfg['depot'] = complete_depot(cfg)
    scratch = job/'build/resave-temp'; scratch.mkdir(parents=True)
    previous = mod.ROOT; mod.ROOT = job
    try:
        command = mod.run_wcc(cfg, 'resave', ['-tmpdir='+str(scratch), '-path='+str(Path(GRAPH).parent),
                              '-ext=w2mg', '-nosourcecontrol', '-ignorefileversion'], job/'build/intake', 'stock-seam-detail-graph')
    finally:
        mod.ROOT = previous
    args = command['args']; compiled = Path(args[args.index('-uncookDir')+1])/GRAPH
    inspection = inspect(compiled)
    after = Graph(compiled)
    old_payload = next(o[3] for o in before.objects if o[0] == 'CMaterialGraph')
    new_payload = next(o[3] for o in after.objects if o[0] == 'CMaterialGraph')
    if old_payload == new_payload:
        raise ValueError('Official resave did not refresh compiled graph payload')
    old_functions = sorted(o[2]['customCode'][1] for o in before.objects if 'customCode' in o[2])
    new_functions = sorted(o[2]['customCode'][1] for o in after.objects if 'customCode' in o[2])
    if old_functions != new_functions:
        raise ValueError('Official resave changed original material function source')
    shutil.copy2(compiled, graph)
    proof = dict(nativeCompiled=True, SHA256=digest(graph), path=str(graph), command=command,
                 authoredSHA256=authored['inspection']['SHA256'], inspection=inspection,
                 compiledPayloadChanged=True, originalFunctionSourcesByteIdentical=True,
                 sourceTexturesChanged=False, geometryChanged=False, staged=False)
    (job/'graph-compiled.json').write_text(json.dumps(proof, indent=2)+'\n')
    return proof


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--source',type=Path); parser.add_argument('--job',type=Path,required=True); parser.add_argument('--sdk',type=Path); parser.add_argument('--resave',action='store_true')
    args=parser.parse_args()
    if not args.resave and (args.source is None or args.sdk is None): parser.error('Authoring requires --source and --sdk')
    print(json.dumps(resave(args.job) if args.resave else author(args.source,args.job,args.sdk),indent=2))
