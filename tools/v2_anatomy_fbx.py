"""Preserve fitted geometry/skin while adding exact-UV native material states."""
import collections
import copy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from wcc_fbx import Document, Node, Property, triangles
from v2_skin_material import GRAPH


def prepare(source, donors, output, transport_faces=None):
    source, donors, output = map(Path, (source, donors, output))
    doc = Document(source)
    objects, connections = doc.root('Objects'), doc.root('Connections')
    next_id = max(int(o.values[0]) for o in objects.children if o.props and isinstance(o.values[0], int)) + 1
    reports = []
    if len(doc.meshes) != 2:
        raise ValueError('Expected the exact two fitted Geralt LODs')
    for lod, mesh in enumerate(doc.meshes):
        donor = np.load(donors / f'lod{lod}-material-donor.npz')
        before_points, before_faces = mesh.array('Vertices').copy(), triangles(mesh)
        groups = donor['materialGroup']
        if len(groups) != len(before_faces) or set(np.unique(groups)) != {0, 1}:
            raise ValueError('Material lineage differs from fitted faces')
        module_faces = before_faces[groups == 1]
        # Both state variants reference identical fitted vertices. Official
        # import creates its required section aliases; the solver runs once.
        extra = [] if transport_faces is None else [before_faces[int(transport_faces[str(lod)])]]
        if extra and groups[int(transport_faces[str(lod)])] != 1:
            raise ValueError('Transport triangle must belong to the source module')
        faces = np.vstack([before_faces, module_faces] + ([np.asarray(extra)] if extra else []))
        native = faces.copy()
        native[:, 2] = -native[:, 2] - 1
        mesh.set_array('PolygonVertexIndex', native)
        for materials in [n for n in mesh.children if n.name == 'LayerElementMaterial']:
            materials.set_array('Materials', np.concatenate([groups, np.full(len(module_faces) + len(extra), 2, dtype=groups.dtype)]))
        uv = next(n for n in mesh.children if n.name == 'LayerElementUV' and n.values == [0])
        if uv.child('MappingInformationType').values != ['ByVertice'] or uv.child('ReferenceInformationType').values != ['Direct']:
            raise ValueError('Unobserved fitted UV mapping')
        values = np.vstack([donor['bodyUV'], donor['moduleUV']]).copy()
        body_count = len(donor['bodyUV'])
        if len(values) * 3 != len(before_points):
            raise ValueError('Material donor vertex count differs')
        # Measured official import maps FBX (u,v) to runtime (u,1-v).
        # Body UVs are original FBX values; moduleUV is original runtime UV.
        values[body_count:, 1] = 1 - values[body_count:, 1]
        uv.set_array('UV', values)
        model_ids = [n.values[2] for n in connections.children if n.values[:2] == ['OO', mesh.values[0]]]
        if len(model_ids) != 1:
            raise ValueError('Unobserved native mesh/model link')
        model = model_ids[0]
        old_materials = [n.values[1] for n in connections.children if n.values[0] == 'OO' and n.values[2] == model
                         and any(o.name == 'Material' and o.values[0] == n.values[1] for o in objects.children)]
        if len(old_materials) != 1:
            raise ValueError('Expected one original native body material')
        template = next(o for o in objects.children if o.name == 'Material' and o.values[0] == old_materials[0])
        connections.children = [n for n in connections.children if n.values[:3] != ['OO', old_materials[0], model]]
        for label in ['Material0', f'NaturalLOD{lod}', f'ErectLOD{lod}']:
            if label == 'Material0':
                material_id = old_materials[0]
            else:
                node = copy.deepcopy(template)
                material_id = next_id
                next_id += 1
                node.props[0].value, node.props[0].raw = material_id, None
                node.props[1].value, node.props[1].raw = label + '\0\1Material', None
                objects.children.append(node)
            connections.children.append(Node('C', [Property('S', 'OO'), Property('L', material_id), Property('L', model)]))
        np.testing.assert_array_equal(mesh.array('Vertices'), before_points)
        np.testing.assert_array_equal(faces[:len(before_faces)], before_faces)
        np.testing.assert_array_equal(faces[len(before_faces):len(before_faces)+len(module_faces)], module_faces)
        np.testing.assert_array_equal(values[:body_count], donor['bodyUV'])
        reports.append(dict(lod=lod,vertices=len(before_points)//3,bodyFaces=int(np.sum(groups==0)),
                            canonicalModuleFaces=len(module_faces),stateCopies=2,
                            transportOnlyDuplicateFaces=len(extra),transportFace=None if not extra else int(transport_faces[str(lod)]),
                            positionSHA256=hashlib.sha256(before_points.tobytes()).hexdigest(),
                            originalTopologySHA256=hashlib.sha256(before_faces.tobytes()).hexdigest(),
                            runtimeModuleUVSHA256=hashlib.sha256(donor['moduleUV'].tobytes()).hexdigest()))
    # Material sidecars reference the verified stock/native texture resources.
    # Embedded editor preview images are unrelated to geometry or rendering;
    # omit their redundant 130MB payload in this fresh derived FBX only.
    remove = {o.values[0] for o in objects.children if o.name in ['Texture','Video']}
    objects.children = [o for o in objects.children if not (o.props and o.values[0] in remove)]
    connections.children = [n for n in connections.children if n.values[1] not in remove and n.values[2] not in remove]
    counts = collections.Counter(o.name for o in objects.children)
    definitions = doc.root('Definitions')
    definitions.child('Count').props[0].value = len(objects.children)
    definitions.child('Count').props[0].raw = None
    for node in definitions.children:
        if node.name == 'ObjectType':
            node.child('Count').props[0].value = counts[node.values[0]]
            node.child('Count').props[0].raw = None
    output.parent.mkdir(parents=True,exist_ok=True)
    doc.save(output)
    root = ET.Element('mesh')
    data = ET.SubElement(root,'mesh_data',autohideDistance='100.00',isTwoSided='false',useExtraStreams='true',mergeInGlobalShadowMesh='false',entityProxy='false')
    lods = ET.SubElement(data,'LODs')
    for distance in ['0.00','6.00']:
        ET.SubElement(lods,'LOD_info',distance=distance)
    mats = ET.SubElement(root,'materials')
    ET.SubElement(mats,'material',name='Material0',local='false',base='characters\\models\\common\\materials\\skin_body\\skin_body__mg_01.w2mi')
    for lod in range(2):
        for state, label in [('natural','Natural'),('erect','Erect')]:
            mat = ET.SubElement(mats,'material',name=f'{label}LOD{lod}',local='true',base=GRAPH.replace('/','\\'))
            for parameter,channel in [('Diffuse','diffuse'),('Normal','normal'),('Ambient','ambient'),('SpecularColor','specular')]:
                stem = f'lod{lod}-{state}-{channel}' if channel == 'diffuse' else f'lod{lod}-{channel}'
                ET.SubElement(mat,'param',name=parameter,type='handle:ITexture',value=f'characters\\malemod\\anatomy\\{stem}.xbm')
            for parameter,value in [('DetailPower',0),('DetailAlbedoPower',0),('VarianceOffset',1),('RSpecScale',0),('RSpecBase',1),('RSpecScale2',.2),('RSpecBase2',0)]:
                ET.SubElement(mat,'param',name=parameter,type='Float',value=str(value))
    ET.indent(root)
    ET.ElementTree(root).write(output.with_suffix('.xml'),encoding='utf-8',xml_declaration=True)
    result=dict(sourceSHA256=hashlib.sha256(source.read_bytes()).hexdigest(),outputSHA256=hashlib.sha256(output.read_bytes()).hexdigest(),
                geometryUnchanged=True,stockUVUnchanged=True,canonicalRuntimeUVRestored=True,stateSwitch='0=erect;1,2=natural',
                nativeCookRequired=True,nativeGameplayObserved=False,lods=reports)
    output.with_suffix('.material-states.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
