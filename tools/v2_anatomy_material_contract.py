"""Bind observed cooked section IDs to the canonical material state meanings."""
import json
from pathlib import Path
import struct
from mod import digest, write_json
from packed_mesh_format import CookedMesh
from v2_cloth_material import native_objects
from adopt_v2_clinical_carriers import material


def graph_detail_contract(imported, graph=None):
    """A .5 override requires a verified graph from this exact intake."""
    imported = Path(imported)
    suffix = Path('characters/models/geralt/body/model/l_01_mg__body.w2mesh')
    if graph is None and imported.parts[-len(suffix.parts):] == suffix.parts:
        candidate = imported.parents[len(suffix.parts)-1] / 'characters/malemod/anatomy/skin.w2mg'
        if candidate.is_file(): graph = candidate
    if graph is None:
        return None
    from v2_skin_material import inspect
    return inspect(Path(graph))


def validate_source_scalars(params, graph_proof):
    detail = graph_proof.get('stockSeamDetail') if graph_proof else None
    physical=bool(graph_proof and graph_proof.get('physicalVariant'))
    if physical:
        if (not graph_proof.get('normalComplete') or graph_proof.get('bakedAmbientActive')is not False
            or graph_proof.get('physicalWeightEncoding')!='COLOR0.R UNORM8; A255 preserved'):
            raise ValueError('Physical material proof is incomplete')
        if 'Ambient'in params:
            raise ValueError('Physical source instance retains an old baked Ambient override')
        from v2_physical_skin_material import MARKER,STOCK_DIFFUSE,STOCK_NORMAL
        for label,expected in [(MARKER,STOCK_DIFFUSE),('PhysicalStockNormal',STOCK_NORMAL)]:
            if label in params and params[label]!=expected:
                raise ValueError('Physical stock material dependency overridden: '+label)
    if detail:
        if detail.get('uvIndex') != 1 or detail.get('detailPower') != .5 or detail.get('detailTile') != [25,25] or detail.get('detailMaskInputs') != 3:
            raise ValueError('Stock seam detail graph proof differs')
        from v2_seam_detail_material import STOCK_AMBIENT, STOCK_DETAIL
        for label, expected in [('StockSeamAmbient',STOCK_AMBIENT),('DetailNormal',STOCK_DETAIL)]:
            if label in params and params[label] != expected:
                raise ValueError('Native instance overrides verified stock detail: '+label)
        if 'DetailTile' in params:
            raise ValueError('Stock seam DetailTile must inherit the verified graph vector')
    for key, value in [('DetailPower',.5 if detail else 0),('DetailAlbedoPower',0),('VarianceOffset',1),('RSpecScale',0),('RSpecBase',1),('RSpecScale2',struct.unpack('<f',struct.pack('<f',.2))[0]),('RSpecBase2',0)]:
        if params.get(key) != value:
            raise ValueError('Native material scalar differs: ' + key)
    return 'physical-stock-uv1'if physical else 'stock-seam-uv1' if detail else 'flat-source'


def names(blob):
    count = struct.unpack_from('<I', blob)[0]
    at, result = 4, []
    for _ in range(count):
        first = blob[at]
        at += 1
        if not first & 128:
            raise ValueError('Unobserved native material name encoding')
        n, shift, more = first & 63, 6, bool(first & 64)
        while more:
            b = blob[at]
            at += 1
            n |= (b & 127) << shift
            shift += 7
            more = bool(b & 128)
        raw = blob[at:at + n]
        if len(raw) != n:
            raise ValueError('Native material name leaves array')
        result.append(raw.decode('utf-8'))
        at += n
    if at != len(blob):
        raise ValueError('Native material names trailer differs')
    return result


def generate(cooked, imported, output, *, graph=None):
    cooked, imported, output = map(Path, (cooked, imported, output))
    detail_contract = graph_detail_contract(imported, graph)
    mesh = CookedMesh(cooked.read_bytes(), allow_multi_section=True)
    buffer = Path(str(cooked) + '.1.buffer')
    sections = mesh.skin_sections(buffer.read_bytes())
    ir, ii, io = native_objects(imported)
    cr, ci, co = native_objects(cooked)
    source_mesh = next(o for o in io if o[0] == 'CMesh')
    target_mesh = next(o for o in co if o[0] == 'CMesh')
    source_names = names(source_mesh[2]['materialNames'][1])
    if source_names != ['Material0', 'NaturalLOD0', 'ErectLOD0', 'NaturalLOD1', 'ErectLOD1']:
        raise ValueError('Official material import names differ')
    handles = target_mesh[2]['materials']
    if handles != source_mesh[2]['materials']:
        raise ValueError('Native cook changed section material handle identity')
    if source_mesh[2].get('mergeInGlobalShadowMesh') != ('Bool', b'\0') or target_mesh[2].get('mergeInGlobalShadowMesh') != ('Bool', b'\0'):
        raise ValueError('Owned lower shadow geometry merged into an unattributable buffer')
    values = handles[1]
    count = struct.unpack_from('<I', values)[0]
    if count != 5 or len(values) != 4 + count * 4:
        raise ValueError('Native material handle array differs')
    handles = struct.unpack('<5i', values[4:])
    if handles[0] >= 0 or ci[-handles[0]-1] != 'characters\\models\\common\\materials\\skin_body\\skin_body__mg_01.w2mi':
        raise ValueError('Stock body skin material changed')
    instances = []
    for index in range(1, 5):
        handle = handles[index]
        if handle <= 0 or handle > len(co) or co[handle-1][0] != 'CMaterialInstance':
            raise ValueError('Native state material is not an owned instance')
        obj = co[handle-1]
        base = struct.unpack('<i', obj[2]['baseMaterial'][1])[0]
        if base >= 0 or ci[-base-1] != 'characters\\malemod\\anatomy\\skin.w2mg':
            raise ValueError('Native source skin graph binding differs')
        params = material(cr, ci, [obj])
        lod = 0 if index < 3 else 1
        state = 'natural' if index in [1,3] else 'erect'
        texture_fields=[('Diffuse',f'lod{lod}-{state}-diffuse'),('Normal',f'lod{lod}-normal'),('SpecularColor',f'lod{lod}-specular')]
        if not(detail_contract and detail_contract.get('physicalVariant')):
            texture_fields.append(('Ambient',f'lod{lod}-ambient'))
        for key, stem in texture_fields:
            if params.get(key) != f'characters\\malemod\\anatomy\\{stem}.xbm':
                raise ValueError('Native material source map differs: ' + key)
        validate_source_scalars(params, detail_contract)
        instances.append(dict(nativeMaterial=index, name=source_names[index], parameters=params))
    rows = []
    for index, section in enumerate(sections):
        native = section['material']
        if native >= count:
            raise ValueError('Native section refers outside material handles')
        label = source_names[native]
        semantic = 0 if native == 0 else 1 if label.startswith('Natural') else 2
        if semantic and not label.endswith(str(section['lod'])):
            raise ValueError('Native section uses another LOD material')
        rows.append(dict(section=index,lod=section['lod'],nativeMaterial=native,semanticMaterial=semantic,name=label))
    if len(rows) != 6 or [(r['lod'],r['semanticMaterial'])for r in rows] != [(0,0),(0,1),(0,2),(1,0),(1,1),(1,2)]:
        raise ValueError('Native material state sections are incomplete')
    physical_fields=[]
    if detail_contract and detail_contract.get('physicalVariant'):
        raw=buffer.read_bytes()
        for row,section in zip(rows,sections):
            if not row['semanticMaterial']:continue
            start,count=section['extraOffset'],section['vertexCount']
            colors=[raw[start+i*8:start+i*8+4]for i in range(count)]
            if any(len(c)!=4 or c[3]!=255 for c in colors):
                raise ValueError('Physical R8 source changed native collapse alpha')
            low,high=min(c[0]for c in colors),max(c[0]for c in colors)
            if (low,high)!=(0,255):
                raise ValueError('Physical source section lacks original-source and stock endpoints')
            physical_fields.append(dict(section=row['section'],lod=row['lod'],material=row['semanticMaterial'],
                                        weightChannel='COLOR0.R UNORM8',minimum=low,maximum=high,alpha255=True))
    result = dict(schema='malemod.witcher-v2-material-contract/1',cookedMeshSHA256=digest(cooked),cookedBufferSHA256=digest(buffer),
                  importedMeshSHA256=digest(imported),sectionMaterials=rows,sections=sections,nativeInstances=instances,
                  mergeInGlobalShadowMesh=False,nativeGameplayObserved=False,
                  graphDetailContract=detail_contract,physicalSourceFields=physical_fields)
    write_json(output,result)
    return result
