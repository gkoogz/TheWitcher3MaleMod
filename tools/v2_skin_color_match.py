"""Measured Geralt color adaptation; retain original source diffuse texels.

This upgrades the body-reflectance variant only. Gains are calibrated once from
natural source UV0 and stock target UV1 using observed WCC half packing and the
unchanged native pow2.2 diffuse path. The same gains retain mechanical-state
color differences. Native SSS follows its existing stock color branch.
"""
import argparse
import hashlib
import json
from pathlib import Path

from v2_fabric_material import encoded_string

SOURCE_LINEAR_REFERENCE = (.31633809397978996, .1247409453870513, .05659902117247641)
TARGET_LINEAR_REFERENCE = (.2866294871698493, .16931861009324786, .173439036332135)
LINEAR_GAINS = (.9060859018394457, 1.3573619276964686, 3.064346922248133)
DONOR_SHA256 = '9517a60a74bf967f5ca3c3265757583eeedb7d94d14ea3fff16a0e44c9674971'
TARGET_UV1_SHA256 = '96e579155c705a60c4780b8491b311350214f84c323f9f9875943cf15376c066'
STOCK_DIFFUSE_SHA256 = '249384b04b38fb98522039de2843706bc22ab6eba207cdbe81267c1d7466e5a2'
SOURCE_TGA_SHA256 = {'NaturalDiffuse': 'ac15a825a50d7006b4f4a54f22f89909e85a4bc3ac1810d72bebfa9d13aa8de2',
                     'ErectDiffuse': 'cbf17deda0ef5d8879b998cde0ac2f16c7b9da4798bd11e6fad7e867ee6a8c44'}
SOURCE_DDS_SHA256 = {'NaturalDiffuse': '70ab81655d2e264c30f955b1a3772ca005841cbcc5fb00ea4040c2bbce71449f',
                     'ErectDiffuse': 'df565b3b277ae873703ab06955c653d8e6b36c287c75eaaa132012bc6d25b452'}

DIFFUSE_CODE = ('float4 physicalSkinDiffuse(float offset,float4 albedo,float4 blendColor)\n'
                '{ float3 s=pow(saturate(albedo.xyz),2.2)*float3('
                + ','.join(format(x, '.17g') for x in LINEAR_GAINS) + '); '
                'float3 t=pow(saturate(blendColor.xyz),2.2); '
                'return float4(pow(max(lerp(s,t,saturate(offset)),0),1.0/2.2),'
                'lerp(albedo.w,blendColor.w,saturate(offset))); }')
SSS_CODE = ('float4 sourceSubsurface(float offset,float4 albedo,float4 blendColor)\n'
            '{ return blendColor; }')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def diffuse_reference(source, stock, weight):
    import numpy as np
    s = np.clip(np.asarray(source, dtype=float), 0, 1) ** 2.2 * np.asarray(LINEAR_GAINS)
    t = np.clip(np.asarray(stock, dtype=float), 0, 1) ** 2.2
    w = np.clip(np.asarray(weight, dtype=float), 0, 1)[..., None]
    return np.maximum(s * (1 - w) + t * w, 0) ** (1/2.2)


def calibration(donor, target_uv1, stock_diffuse, original_maps):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter
    from bake_v2_skin_textures import sample
    from prepare_v2_target_uv1 import runtime_half
    donor, target_uv1, stock_diffuse, original_maps = map(Path, (donor, target_uv1, stock_diffuse, original_maps))
    for path, expected in [(donor, DONOR_SHA256), (target_uv1, TARGET_UV1_SHA256), (stock_diffuse, STOCK_DIFFUSE_SHA256)]:
        if digest(path) != expected:
            raise ValueError('Body-color calibration requires exact canonical inputs: ' + str(path))
    maps = json.loads(original_maps.read_text())
    if maps.get('schema') != 'malemod.original-canonical-source-textures/1':
        raise ValueError('Original source texture receipt required')
    rows = {row['role']: row for row in maps['lods'][0]['files'] if row['role'] in SOURCE_TGA_SHA256}
    if set(rows) != set(SOURCE_TGA_SHA256):
        raise ValueError('Natural and erect original maps are both required')
    for role, row in rows.items():
        if (row['sha256'] != SOURCE_TGA_SHA256[role] or digest(row['path']) != row['sha256']
                or row['sourceDDSSHA256'] != SOURCE_DDS_SHA256[role]
                or digest(row['sourceDDS']) != row['sourceDDSSHA256']
                or not row.get('originalChannelBytesUnchanged')
                or row['decodedPixelsSHA256'] != row['originalDecodedPixelsSHA256']):
            raise ValueError('Original source diffuse provenance differs')
    data, field = np.load(donor), np.load(target_uv1)
    fbx0 = data['moduleUV'].copy()
    fbx0[:, 1] = 1 - fbx0[:, 1]
    uv0 = runtime_half(fbx0).view('<f2').astype(float)
    uv1 = runtime_half(field['moduleUV1FBX']).view('<f2').astype(float)
    interior = data['seamBlend'] == 0
    if int(interior.sum()) != 15683:
        raise ValueError('Reference physical interior changed')
    stock = sample(np.asarray(Image.open(stock_diffuse).convert('RGB')), uv1) / 255
    target_reference = np.median(stock[interior] ** 2.2, axis=0)

    # Conservative base-level footprint: all actual source UV triangles plus
    # two pixels of gutter. This does not claim coverage of every native mip.
    mask = Image.new('L', (4096, 4096))
    draw = ImageDraw.Draw(mask)
    xy = uv0 * 4096 - .5
    for ids in data['moduleFaces']:
        draw.polygon([tuple(p) for p in xy[ids]], fill=255)
    covered = np.asarray(mask.filter(ImageFilter.MaxFilter(5))) > 0
    reports = []
    source_reference = None
    for role in ['NaturalDiffuse', 'ErectDiffuse']:
        row = rows[role]
        image = np.asarray(Image.open(row['path']).convert('RGB'))
        colors = sample(image, uv0) / 255
        if role == 'NaturalDiffuse':
            source_reference = np.median(colors[interior] ** 2.2, axis=0)
            np.testing.assert_allclose(source_reference, SOURCE_LINEAR_REFERENCE, rtol=0, atol=1e-13)
            np.testing.assert_allclose(target_reference, TARGET_LINEAR_REFERENCE, rtol=0, atol=1e-13)
            np.testing.assert_allclose(target_reference/source_reference, LINEAR_GAINS, rtol=0, atol=1e-13)
        adapted = (image[covered].astype(float)/255) ** 2.2 * np.asarray(LINEAR_GAINS)
        reports.append(dict(role=role, sourceTGA=row['path'], sourceTGASHA256=row['sha256'],
                            sourceDDSSHA256=row['sourceDDSSHA256'], fixedNaturalReference=True,
                            linearMinimum=adapted.min(axis=0).tolist(), linearMaximum=adapted.max(axis=0).tolist(),
                            channelsBelowZero=int((adapted < 0).sum()), channelsAboveOne=int((adapted > 1).sum()),
                            nativeSampleMedian=(np.median(colors[interior] ** 2.2, axis=0)*np.asarray(LINEAR_GAINS)).tolist()))
    return dict(donor=str(donor), donorSHA256=digest(donor), targetUV1=str(target_uv1), targetUV1SHA256=digest(target_uv1),
                stockDiffuse=str(stock_diffuse), stockDiffuseSHA256=digest(stock_diffuse),
                originalMapsReceipt=str(original_maps), originalMapsReceiptSHA256=digest(original_maps),
                sampling='Bilinear wrap at texel centers; observed WCC float32-to-half truncation; physical seamBlend==0',
                rows=int(interior.sum()), sourceNaturalLinearReference=source_reference.tolist(),
                stockLinearReference=target_reference.tolist(), linearGains=list(LINEAR_GAINS),
                footprintLOD=0, footprintMip=0, conservativeFootprintTexels=int(covered.sum()), gutterPixels=2,
                higherMipClippingUnobserved=True, unusedAtlasTexelsMayExceedOne=True, states=reports)


def author(source, job, donor, target_uv1, stock_diffuse, original_maps):
    from mod import ROOT
    from v2_physical_skin_material import PhysicalGraph, GRAPH, inspect
    source, job = Path(source), Path(job)
    if job.exists() or not job.resolve().is_relative_to((ROOT/'v2/build/materials').resolve()):
        raise ValueError('Use a fresh owned body-color job')
    before = inspect(source)
    if not before.get('bodyMatchedReflectance') or before.get('bodyMatchedColor'):
        raise ValueError('Upgrade requires the complete body-reflectance variant only')
    reference = calibration(donor, target_uv1, stock_diffuse, original_maps)
    graph = PhysicalGraph(source)
    changes = []
    for signature, code in [('physicalSkinDiffuse(', DIFFUSE_CODE), ('sourceSubsurface(', SSS_CODE)]:
        nodes = [i for i, row in enumerate(graph.objects) if signature.encode() in row[2].get('customCode', ('', b''))[1]]
        if len(nodes) != 1:
            raise ValueError('Expected one body-color channel: ' + signature)
        node = nodes[0]
        changes.append(dict(node=node, function=signature, beforeSHA256=hashlib.sha256(graph.objects[node][2]['customCode'][1]).hexdigest(),
                            afterSHA256=hashlib.sha256(encoded_string(code)).hexdigest()))
        graph.objects[node][2]['customCode'] = ('String', encoded_string(code))
    target = job/'build/intake'/GRAPH
    target.parent.mkdir(parents=True)
    target.write_bytes(graph.rebuild())
    proof = dict(schema='malemod.body-matched-skin-color/1', source=str(source), sourceSHA256=digest(source),
                 graph=str(target), inspection=inspect(target), calibration=reference, changedFunctions=changes,
                 sourceMapsChanged=False, geometryChanged=False, normalReflectanceFunctionsChanged=False,
                 nativeSSSLaw='Existing native SSS_DetailColorBleed.Color times itself; complete RGBA preserved',
                 nativeShaderPayloadUnchanged=True, officialResaveRequired=True, nativeCompiled=False,
                 nativeGameplayObserved=False, staged=False)
    (job/'graph-authored.json').write_text(json.dumps(proof, indent=2)+'\n', encoding='utf-8')
    return proof


if __name__ == '__main__':
    from mod import ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--job', type=Path, required=True)
    parser.add_argument('--donor', type=Path, default=ROOT/'v2/build/materials/source-anatomy-01/lod0-material-donor.npz')
    parser.add_argument('--target-uv1', type=Path, default=ROOT/'v2/build/materials/physical-skin-field-01/lod0-target-uv1.npz')
    parser.add_argument('--stock-diffuse', type=Path, default=ROOT/'v2/build/native-fit-02/build/depot-bb7d8c28a8c3/characters/models/geralt/body/model/body_01_mg__geralt_d01.tga')
    parser.add_argument('--original-maps', type=Path, default=ROOT/'v2/build/materials/original-source-maps-01/textures.json')
    args = parser.parse_args()
    print(json.dumps(author(args.source, args.job, args.donor, args.target_uv1, args.stock_diffuse, args.original_maps), indent=2))
