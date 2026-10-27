"""Author an owned native skin graph from measured REDkit editor nodes.

Only graph data is edited. Official resave/cook regenerate native graph data;
cookmaterials must also compile its shader cache before runtime use. Stock graph
files and canonical shader code stay untouched.
"""
import copy
import hashlib
from pathlib import Path
import struct
import zlib
from player_rig_redirect import header_crc
from v2_cloth_material import native_objects
from packed_mesh_format import CookedMesh

GRAPH = 'characters/malemod/anatomy/skin.w2mg'


def instance_values(path):
    """Read the observed stock material159, retaining full table/export CRCs."""
    raw = Path(path).read_bytes()
    if raw[:4] != b'CR2W' or struct.unpack_from('<I', raw, 4)[0] != 159 or header_crc(raw, 0) != struct.unpack_from('<I', raw, 32)[0]:
        raise ValueError('Unobserved stock skin instance header')
    def table(i, stride):
        off, n, crc = struct.unpack_from('<III', raw, 40 + i * 12)
        size = n * stride
        if off < 160 or size > len(raw) - off:
            raise ValueError('Stock skin table leaves file')
        block = raw[off:off + size]
        if zlib.crc32(block) != crc:
            raise ValueError('Stock skin table CRC differs')
        return block
    strings = table(0, 1)
    def text(off):
        return strings[off:strings.index(b'\0', off)].decode('utf-8')
    names = [text(off) for off, _ in struct.iter_unpack('<II', table(1, 8))]
    imports = [text(off) for off, _, _ in struct.iter_unpack('<IHH', table(2, 8))]
    entries = list(struct.iter_unpack('<HHIIIII', table(4, 24)))
    if len(entries) != 1 or names[entries[0][0]] != 'CMaterialInstance':
        raise ValueError('Unobserved stock skin instance exports')
    _, _, _, size, off, _, crc = entries[0]
    blob = raw[off:off + size]
    if len(blob) != size or zlib.crc32(blob) != crc:
        raise ValueError('Stock skin export CRC differs')
    reader = CookedMesh.__new__(CookedMesh)
    reader.names = names
    _, tail = reader.object(blob)
    count, = struct.unpack_from('<I', tail)
    at, values = 4, {}
    for _ in range(count):
        size, name_id, ty_id = struct.unpack_from('<IHH', tail, at)
        value = tail[at + 8:at + size]
        if size < 8 or len(value) != size - 8:
            raise ValueError('Stock skin parameter bounds differ')
        name, ty = names[name_id], names[ty_id]
        if ty == 'Float':
            value = struct.unpack('<f', value)[0]
        elif ty == 'handle:ITexture':
            value = imports[-struct.unpack('<i', value)[0] - 1]
        elif ty in ['Color', 'Vector']:
            fields, rest = reader.object(value)
            if rest:
                raise ValueError('Stock skin vector trailer differs')
            value = {k: (t, v) for k, (t, v) in fields.items()}
        else:
            raise ValueError('Unobserved stock skin parameter type')
        values[name] = (ty, value)
        at += size
    if at != len(tail):
        raise ValueError('Stock skin parameter closure differs')
    return values


def state(path):
    reader, imports, objects = native_objects(path)
    def name(index, key='name'):
        kind, data = objects[index][2][key]
        if kind != 'CName' or len(data) != 2:
            raise ValueError('Unobserved skin graph name')
        return reader.names[struct.unpack('<H', data)[0]]
    def array(index, key):
        data = objects[index][2].get(key, ('', bytes(4)))[1]
        n = struct.unpack_from('<I', data)[0]
        if len(data) != 4 + n * 4:
            raise ValueError('Unobserved skin graph pointer array')
        ids = [v[0] - 1 for v in struct.iter_unpack('<i', data[4:])]
        if any(i < 0 or i >= len(objects) for i in ids):
            raise ValueError('Skin graph pointer leaves export table')
        return ids
    def ptr(index, key):
        data = objects[index][2][key][1]
        if len(data) != 4:
            raise ValueError('Unobserved skin graph pointer')
        i = struct.unpack('<i', data)[0] - 1
        if not 0 <= i < len(objects):
            raise ValueError('Skin graph pointer leaves exports')
        return i
    return reader, imports, objects, name, array, ptr


def validate_custom_functions(path):
    """Fast real HLSL syntax guard before expensive official graph/cook work."""
    import ctypes
    import os
    if os.name!='nt':raise RuntimeError('Native custom-function validation requires Windows')
    objects=state(path)[2];functions=[]
    for signature in [b'float4 sourceSpecular(',b'float4 sourceSubsurface(']:
        codes=[x[2].get('customCode',('',b''))[1] for x in objects if signature in x[2].get('customCode',('',b''))[1]]
        if len(codes)!=1:raise ValueError('Expected one source custom function')
        functions.append(codes[0][codes[0].index(signature):])
    source=b'\n'.join(functions)+b'\nfloat4 main(float4 p:SV_Position):SV_Target {return sourceSpecular(0,p,p)+sourceSubsurface(0,p,p);}'
    compiler=ctypes.WinDLL('d3dcompiler_47.dll').D3DCompile
    compiler.restype=ctypes.c_long
    compiler.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_char_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_char_p,ctypes.c_char_p,ctypes.c_uint,ctypes.c_uint,ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(ctypes.c_void_p)]
    code=ctypes.c_void_p();error=ctypes.c_void_p()
    result=compiler(source,len(source),b'source-skin-custom-functions',None,None,b'main',b'ps_5_0',0,0,ctypes.byref(code),ctypes.byref(error))
    def method(blob,index,result_type,*args):
        table=ctypes.cast(blob,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        return ctypes.WINFUNCTYPE(result_type,ctypes.c_void_p,*args)(table[index])
    message=''
    if error:
        data=method(error,3,ctypes.c_void_p)(error);size=method(error,4,ctypes.c_size_t)(error)
        message=ctypes.string_at(data,size).decode(errors='replace')
    for blob in [code,error]:
        if blob:method(blob,2,ctypes.c_ulong)(blob)
    if result<0:raise ValueError('Native HLSL custom-function compilation failed: '+message)
    return dict(compiler='D3DCompile ps_5_0',functions=2,passed=True)


def author(source, target):
    source, target = Path(source), Path(target)
    raw = source.read_bytes()
    r, imports, original, name, array, ptr = state(source)
    base_instance = source.parents[3] / 'characters/models/common/materials/base_materials/base_skin.w2mi'
    inherited = instance_values(base_instance)
    def encoded_object(fields):
        blob = b'\0'
        for key, (ty, value) in fields.items():
            blob += struct.pack('<HHI', r.names.index(key), r.names.index(ty), 4 + len(value)) + value
        return blob + b'\0\0'
    # A fresh graph otherwise inherits editor previews, not Geralt's actual
    # base skin. Copy the observed scalar/color/vector defaults explicitly.
    for i, node in enumerate(original):
        if 'parameterName' not in node[2]:
            continue
        label = name(i, 'parameterName')
        if label not in inherited:
            continue
        ty, value = inherited[label]
        if ty == 'Float' and node[0] == 'CMaterialParameterScalar':
            node[2]['scalar'] = ('Float', struct.pack('<f', value))
        elif ty in ['Color', 'Vector'] and node[0] == 'CMaterialParameter' + ty:
            node[2][ty.lower()] = (ty, encoded_object(value))
    default_normal = next(node[2]['texture'] for i, node in enumerate(original)
                          if node[0] == 'CMaterialParameterTexture' and name(i, 'parameterName') == 'Normal')
    for i, node in enumerate(original):
        if node[0] == 'CMaterialParameterTexture' and name(i, 'parameterName') == 'DetailNormal':
            # With DetailPower0, RNM still normalizes the detail Z component.
            # A missing/debug texture can reverse the normal even at zero XY
            # weight. An actual flat normal keeps this branch the identity.
            node[2]['texture'] = default_normal
    objects = copy.deepcopy(original)
    root = next(i for i, o in enumerate(original) if o[0] == 'CMaterialGraph')
    output = next(i for i, o in enumerate(original) if o[0] == 'CMaterialBlockOutputColorSkin')
    if original[root][2].get('canUseOnMorphMeshes') != ('Bool', b'\1'):
        raise ValueError('Source graph lacks observed native morph support')
    def pointers(ids):
        return struct.pack('<I', len(ids)) + b''.join(struct.pack('<i', i + 1) for i in ids)
    def set_array(index, key, ty, ids):
        objects[index][2][key] = (ty, pointers(ids))
    def current_array(index, key):
        data = objects[index][2].get(key, ('', bytes(4)))[1]
        return [v[0] - 1 for v in struct.iter_unpack('<i', data[4:])]
    def scalar_name(label):
        candidates = [i for i, o in enumerate(original) if 'parameterName' in o[2] and name(i, 'parameterName') == label]
        if len(candidates) != 1:
            raise ValueError('Ambiguous skin parameter ' + label)
        return candidates[0]
    def socket(owner, label, direction):
        matches = [i for i in array(owner, 'sockets') if original[i][0].startswith('CMaterial' + direction) and name(i) == label]
        if len(matches) != 1:
            raise ValueError('Ambiguous skin socket ' + label)
        return matches[0]
    def upstream(index):
        connections = array(index, 'connections')
        if len(connections) != 1 or ptr(connections[0], 'source') != index:
            raise ValueError('Unobserved reciprocal skin edge')
        return ptr(connections[0], 'destination')
    def rewire(input_id, output_id):
        for edge in current_array(input_id, 'connections'):
            other = struct.unpack('<i', objects[edge][2]['destination'][1])[0] - 1
            keep = [e for e in current_array(other, 'connections')
                    if struct.unpack('<i', objects[e][2]['destination'][1])[0] - 1 != input_id]
            set_array(other, 'connections', 'array:2,0,ptr:CGraphConnection', keep)
        first = len(objects)
        template = next(o for o in original if o[0] == 'CGraphConnection')
        for a, b in [(input_id, output_id), (output_id, input_id)]:
            node = copy.deepcopy(template)
            node[2].clear()
            node[2].update(source=('ptr:CGraphSocket', struct.pack('<i', a + 1)),
                           destination=('ptr:CGraphSocket', struct.pack('<i', b + 1)))
            objects.append(node)
        set_array(input_id, 'connections', 'array:2,0,ptr:CGraphConnection', [first])
        set_array(output_id, 'connections', 'array:2,0,ptr:CGraphConnection', current_array(output_id, 'connections') + [first + 1])
    def encoded_string(value):
        data = value.encode('utf-8')
        n = len(data)
        prefix = bytes([(n & 63) | 128 | (64 if n >> 6 else 0)])
        n >>= 6
        while n:
            prefix += bytes([(n & 127) | (128 if n >> 7 else 0)])
            n >>= 7
        return prefix + data
    def clone_block(owner):
        ids = [owner] + array(owner, 'sockets')
        mapping = {old: len(objects) + n for n, old in enumerate(ids)}
        for old in ids:
            node = copy.deepcopy(original[old])
            node[2].pop('position', None)
            node[2].pop('connections', None)
            if 'sockets' in node[2]:
                node[2]['sockets'] = (node[2]['sockets'][0], pointers([mapping[i] for i in array(old, 'sockets')]))
            if 'block' in node[2]:
                node[2]['block'] = (node[2]['block'][0], struct.pack('<i', mapping[ptr(old, 'block')] + 1))
            objects.append(node)
        return mapping

    # Clone the actual Normal texture parameter/sampler and its own sockets.
    # Texture coordinates remain the sampler's default UV0, matching source UV.
    normal = scalar_name('Normal')
    normal_out = socket(normal, 'Texture', 'Output')
    sample_input = upstream(normal_out)
    sampler = ptr(sample_input, 'block')
    if original[sampler][0] != 'CMaterialBlockSamplerTexture':
        raise ValueError('Native Normal is not sampled by the observed texture node')
    selected = {normal, sampler, *array(normal, 'sockets'), *array(sampler, 'sockets')}
    connections = set()
    for index in selected:
        for edge in array(index, 'connections'):
            if ptr(edge, 'source') in selected and ptr(edge, 'destination') in selected:
                connections.add(edge)
    selected |= connections
    mapping = {old: len(objects) + n for n, old in enumerate(sorted(selected))}
    for old in sorted(selected):
        node = copy.deepcopy(original[old])
        node[2].pop('position', None)
        for key, (ty, data) in list(node[2].items()):
            if key in ['sockets', 'connections']:
                ids = [i for i in array(old, key) if i in mapping]
                node[2][key] = (ty, pointers([mapping[i] for i in ids]))
            elif key in ['block', 'source', 'destination']:
                node[2][key] = (ty, struct.pack('<i', mapping[ptr(old, key)] + 1))
        objects.append(node)
    specular = scalar_name('SpecularColor')
    objects[specular][2].pop('parameterName')
    objects[mapping[normal]][2]['parameterName'] = ('CName', struct.pack('<H', r.names.index('SpecularColor')))
    spec_sample = mapping[socket(sampler, 'Color', 'Output')]
    custom = next(i for i, o in enumerate(original) if o[0] == 'CMaterialBlockCustomFunction'
                  and {name(s) for s in array(i, 'sockets')} == {'Out', 'offset', 'albedo', 'blendColor'})
    strength = clone_block(custom)
    objects[strength[custom]][2]['customCode'] = ('String', encoded_string(
        'float4 sourceSpecular( float offset, float4 albedo, float4 blendColor )\n'
        '{ float3 encoded = saturate(albedo.xyz);\n'
        '  float3 linRGB = lerp(encoded/12.92, pow((encoded+0.055)/1.055,2.4), step(0.04045,encoded));\n'
        '  return float4( linRGB * float3(1.0,1.5,2.0), albedo.w ); }'))
    rewire(strength[socket(custom, 'albedo', 'Input')], spec_sample)
    # The native custom-function exporter emits all declared arguments even
    # when HLSL optimizes them away. An unconnected float4 socket generates
    # float4(1), which DXC rejects. Bind the unused declared arguments to typed
    # native outputs rather than relying on that invalid editor default.
    rewire(strength[socket(custom, 'blendColor', 'Input')], spec_sample)
    rewire(strength[socket(custom, 'offset', 'Input')], socket(scalar_name('RSpecScale'), 'Value', 'Output'))
    strength_out = strength[socket(custom, 'Out', 'Output')]
    # Actual UE3 Texture/Texture2D defaults and the specular asset establish
    # SRGB=true. Preserve the original encoded source bytes, decode IEC sRGB
    # before authored Phong amplitude, then enter native linear specular data.
    gamma_input = upstream(socket(specular, 'Color', 'Output'))
    gamma = ptr(gamma_input, 'block')
    if original[gamma][0] != 'CMaterialBlockConvertGammaToLinear':
        raise ValueError('Unobserved native specular color conversion')
    for edge in array(socket(gamma, 'Out', 'Output'), 'connections'):
        rewire(ptr(edge, 'destination'), strength_out)
    # The canonical runtime binds its diffuse to the subsurface sampler too.
    # Native skin's SSS color data accepts the existing diffuse sample directly.
    data0 = socket(output, 'Data0', 'Input')
    pack = ptr(upstream(data0), 'block')
    if original[pack][0] != 'CMaterialBlockCustomFunction':
        raise ValueError('Unobserved native SSS color packing')
    sss = socket(pack, 'subsurfColor', 'Input')
    diffuse = scalar_name('Diffuse')
    diffuse_sampler = ptr(upstream(socket(diffuse, 'Texture', 'Output')), 'block')
    ambient = scalar_name('Ambient')
    ambient_sampler = ptr(upstream(socket(ambient, 'Texture', 'Output')), 'block')
    seam = socket(ambient_sampler, 'Blue', 'Output')
    sss_blend = clone_block(custom)
    objects[sss_blend[custom]][2]['customCode'] = ('String', encoded_string(
        'float4 sourceSubsurface( float offset, float4 albedo, float4 blendColor )\n'
        '{ float3 encoded = saturate(albedo.xyz);\n'
        '  float3 linRGB = lerp(encoded/12.92, pow((encoded+0.055)/1.055,2.4), step(0.04045,encoded));\n'
        '  return lerp( float4(linRGB,albedo.w), blendColor, saturate(offset) ); }'))
    rewire(sss_blend[socket(custom, 'albedo', 'Input')], socket(diffuse_sampler, 'Color', 'Output'))
    rewire(sss_blend[socket(custom, 'blendColor', 'Input')], upstream(sss))
    rewire(sss_blend[socket(custom, 'offset', 'Input')], seam)
    rewire(sss, sss_blend[socket(custom, 'Out', 'Output')])
    # Ambient.r carries seamWeight*stockAmbient.b. The original native second
    # lobe is retained only through that narrow transition, preserving stock
    # boundary response while the source anatomy uses its one healthy lobe.
    blue = socket(ambient_sampler, 'Blue', 'Output')
    power2 = socket(scalar_name('RSpecPower2'), 'Value', 'Output')
    matches = []
    for i, o in enumerate(original):
        if o[0] != 'CMaterialBlockMathPower':
            continue
        inputs = [s for s in array(i, 'sockets') if o and original[s][0].startswith('CMaterialInput')]
        if len(inputs) == 2 and all(array(s, 'connections') for s in inputs) and {upstream(s) for s in inputs} == {blue, power2}:
            matches.append(next(s for s in inputs if upstream(s) == blue))
    if len(matches) != 1:
        raise ValueError('Unobserved native second lobe mask')
    rewire(matches[0], socket(ambient_sampler, 'Red', 'Output'))
    set_array(root, 'blocks', 'array:2,0,ptr:CGraphBlock', array(root, 'blocks') +
              [mapping[normal], mapping[sampler], strength[custom], sss_blend[custom]])
    # Do not retain the old type declaration for the now texture-typed parameter.
    # Official resave recomputes the complete reachable parameter metadata.
    compiled = [i for i in array(root, 'pixelParameterBlocks') if i != specular]
    set_array(root, 'pixelParameterBlocks', 'array:2,0,ptr:CMaterialParameter', compiled + [mapping[normal]])

    def encode(props, tail):
        blob = b'\0'
        for key, (ty, value) in props.items():
            blob += struct.pack('<HHI', r.names.index(key), r.names.index(ty), 4 + len(value)) + value
        return blob + b'\0\0' + tail
    if any(struct.unpack_from('<II', raw, 40 + 12 * i) != (0, 0) for i in range(5, 10)):
        raise ValueError('Skin graph external buffers are unsupported')
    offset, count, _ = struct.unpack_from('<III', raw, 88)
    entries = list(struct.iter_unpack('<HHIIIII', raw[offset:offset + count * 24]))
    at = offset + len(objects) * 24
    table, data = bytearray(), bytearray()
    for i, node in enumerate(objects):
        payload = encode(node[2], node[3])
        e = entries[i] if i < count else next(e for e in entries if r.names[e[0]] == node[0])
        kind, flags, parent, _, _, template, _ = e
        table += struct.pack('<HHIIIII', kind, flags, parent, len(payload), at, template, zlib.crc32(payload))
        data += payload
        at += len(payload)
    rebuilt = bytearray(raw[:offset]) + table + data
    struct.pack_into('<III', rebuilt, 88, offset, len(objects), zlib.crc32(table))
    struct.pack_into('<II', rebuilt, 24, len(rebuilt), len(rebuilt))
    struct.pack_into('<I', rebuilt, 32, header_crc(rebuilt, 0))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(rebuilt)
    inspected = inspect(target)
    syntax=validate_custom_functions(target)
    return dict(inspected, sourceSHA256=hashlib.sha256(raw).hexdigest(), officialResaveRequired=True,
                inheritedStockInstanceSHA256=hashlib.sha256(base_instance.read_bytes()).hexdigest(),
                customFunctionSyntax=syntax,shaderPayloadEdited=False, canonicalGeometryEdited=False)


def inspect(path):
    r, imports, objects, name, array, ptr = state(path)
    root = next(i for i, o in enumerate(objects) if o[0] == 'CMaterialGraph')
    params = {}
    for index in array(root, 'pixelParameterBlocks'):
        label = name(index, 'parameterName')
        if label in params:
            raise ValueError('Duplicate compiled native skin parameter')
        params[label] = objects[index][0]
    if 'PhysicalStockDiffuse' in params:
        # Physical variants have their own complete structural guard. The
        # marker alone cannot enable missing normal or baked-mask branches.
        from v2_physical_skin_material import inspect as inspect_physical
        return inspect_physical(path,require_complete=True)
    if params.get('SpecularColor') != 'CMaterialParameterTexture':
        raise ValueError('Source spatial specular texture was flattened')
    for label in ['Diffuse', 'Normal', 'Ambient', 'DetailNormal']:
        if params.get(label) != 'CMaterialParameterTexture':
            raise ValueError('Native skin texture missing: ' + label)
    stock_detail = None
    if 'StockSeamAmbient' in params:
        if params['StockSeamAmbient'] != 'CMaterialParameterTexture':
            raise ValueError('Stock seam detail marker is not a texture parameter')
        from v2_seam_detail_material import inspect as inspect_stock_detail
        # Recognition is explicit and structural, including UV1, authentic
        # textures and all three native masks; a marker alone grants nothing.
        stock_detail = inspect_stock_detail(path)
    else:
        detail = next(i for i in array(root,'pixelParameterBlocks') if name(i,'parameterName')=='DetailNormal')
        handle = struct.unpack('<i',objects[detail][2]['texture'][1])[0]
        if handle>=0 or -handle>len(imports) or imports[-handle-1]!='engine\\textures\\editor\\normal.xbm':
            raise ValueError('Zero-weight detail normal is not the verified flat identity')
    outputs = [i for i, o in enumerate(objects) if o[0] == 'CMaterialBlockOutputColorSkin']
    if len(outputs) != 1:
        raise ValueError('Expected one native skin output graph')
    def input_socket(owner, label):
        matches = [s for s in array(owner, 'sockets')
                   if objects[s][0].startswith('CMaterialInput') and name(s) == label]
        if len(matches) != 1:
            raise ValueError('Missing native skin output input: ' + label)
        return matches[0]
    def dependencies(block, visited=None):
        visited = set() if visited is None else visited
        if block in visited:
            return set()
        visited.add(block)
        result = {block}
        for s in array(block, 'sockets'):
            if not objects[s][0].startswith('CMaterialInput'):
                continue
            edges = array(s, 'connections')
            if not edges:
                continue
            if len(edges) != 1 or ptr(edges[0], 'source') != s:
                raise ValueError('Native skin input edge direction differs')
            other = ptr(edges[0], 'destination')
            if not any(ptr(e, 'source') == other and ptr(e, 'destination') == s for e in array(other, 'connections')):
                raise ValueError('Native skin edge lacks reciprocal connection')
            result |= dependencies(ptr(other, 'block'), visited)
        return result
    def upstream_blocks(label):
        s = input_socket(outputs[0], label)
        edges = array(s, 'connections')
        if len(edges) != 1 or ptr(edges[0], 'source') != s:
            raise ValueError('Native skin output is disconnected: ' + label)
        return dependencies(ptr(ptr(edges[0], 'destination'), 'block'))
    def parameter_ids(ids):
        return {name(i, 'parameterName') for i in ids if 'parameterName' in objects[i][2]}
    spec = upstream_blocks('Specularity')
    sss = upstream_blocks('Data0')
    if not {'SpecularColor', 'Ambient'} <= parameter_ids(spec) or not {'Diffuse', 'Ambient', 'SSS_DetailColorBleed'} <= parameter_ids(sss):
        raise ValueError('Native skin source map connectivity differs')
    strength = [i for i in spec if b'sourceSpecular(' in objects[i][2].get('customCode', ('', b''))[1]]
    if len(strength) != 1:
        raise ValueError('Source specular channel strengths were disconnected')
    for argument in ['albedo','blendColor','offset']:
        if len(array(input_socket(strength[0],argument),'connections'))!=1:
            raise ValueError('Native custom function has an unbound declared argument')
    code = b''.join(objects[strength[0]][2]['customCode'][1].split())
    if b'linRGB*float3(1.0,1.5,2.0)' not in code:
        raise ValueError('Source specular authored strengths differ')
    decode=b'lerp(encoded/12.92,pow((encoded+0.055)/1.055,2.4),step(0.04045,encoded))'
    if decode not in code:
        raise ValueError('Source sRGB specular decode is missing or differs')
    strength_input = input_socket(strength[0], 'albedo')
    connection = array(strength_input, 'connections')
    if len(connection) != 1:
        raise ValueError('Source specular sampler is disconnected')
    sampled = ptr(ptr(connection[0], 'destination'), 'block')
    if objects[sampled][0] != 'CMaterialBlockSamplerTexture':
        raise ValueError('A new color conversion was added to source specular')
    if parameter_ids(dependencies(sampled)) != {'SpecularColor'}:
        raise ValueError('Source specular samples a different map')
    subsurface=[i for i in sss if b'sourceSubsurface(' in objects[i][2].get('customCode', ('', b''))[1]]
    if len(subsurface)!=1:
        raise ValueError('Source/native seam subsurface transition was disconnected')
    if decode not in b''.join(objects[subsurface[0]][2]['customCode'][1].split()):
        raise ValueError('Source sRGB subsurface decode is missing or differs')
    return dict(SHA256=hashlib.sha256(Path(path).read_bytes()).hexdigest(), graph=GRAPH,
                runtimeParameters=params, sourceSpecularIsTexture=True,
                diffuseFeedsNativeSSS=True, flatDetailNormal=stock_detail is None,
                detailMode='stock-seam-uv1' if stock_detail else 'flat-source', stockSeamDetail=stock_detail,
                specularStrength=[1,1.5,2],
                sourceSpecularSRGBDecoded=True,sourceSubsurfaceSRGBDecoded=True,
                sourceSRGBDecode='IEC piecewise: threshold .04045, /12.92 or ((x+.055)/1.055)^2.4',
                ambientChannels='r=seam*stockSpecMask,g=roughness,b=seam',
                nativeSecondLobeSeamOnly=True, nativeGameplayObserved=False)
