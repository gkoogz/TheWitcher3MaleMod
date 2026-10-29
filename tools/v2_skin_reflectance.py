"""Body-matched native skin reflectance; source maps and geometry stay intact.

UE3's colored Phong amplitude is not a physical dielectric F0. Keep its spatial
detail as an achromatic modulation, centered on the measured original anatomy,
and use Geralt's actual native F0, roughness and second lobe. This is an explicit
REDengine lighting adaptation, not a change to canonical Wolverine lighting.
"""
import argparse
import hashlib
import json
from pathlib import Path

from v2_fabric_material import encoded_string

REFERENCE_LUMINANCE = 0.042994450549721924
LUMINANCE_WEIGHTS = (.2126, .7152, .0722)
REFERENCE_DONOR_SHA256 = '9517a60a74bf967f5ca3c3265757583eeedb7d94d14ea3fff16a0e44c9674971'
REFERENCE_SPECULAR_SHA256 = '51f2625a6bc680433d1fbd21a66b29476fbf7209636df0618c53e1eaaf25780c'

SPECULAR_CODE = ('float4 physicalSkinSpecular(float offset,float4 albedo,float4 blendColor)\n'
                '{ float3 e=saturate(albedo.xyz); '
                'float3 s=lerp(e/12.92,pow((e+0.055)/1.055,2.4),step(0.04045,e)); '
                'float detail=dot(s,float3(0.2126,0.7152,0.0722))/'
                + format(REFERENCE_LUMINANCE, '.17g') + '; '
                'float3 stock=pow(float3(239.0,241.0,255.0)/255.0,2.2)*0.25*blendColor.b; '
                'return float4(stock*lerp(detail,1.0,saturate(offset)),albedo.w); }')
AMBIENT_CODE = ('float4 physicalSkinAmbient(float offset,float4 albedo,float4 blendColor)\n'
               '{ return float4(albedo.b,albedo.g,saturate(offset),1); }')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def specular_reference(encoded, stock_ambient, weight):
    """Independent CPU response for endpoint/chroma/detail checks."""
    import numpy as np
    e = np.clip(np.asarray(encoded, dtype=float), 0, 1)
    linear = np.where(e <= .04045, e / 12.92, ((e + .055) / 1.055) ** 2.4)
    detail = linear @ np.asarray(LUMINANCE_WEIGHTS) / REFERENCE_LUMINANCE
    ambient = np.asarray(stock_ambient, dtype=float)
    w = np.clip(np.asarray(weight, dtype=float), 0, 1)
    stock = np.power(np.asarray([239, 241, 255]) / 255, 2.2) * .25 * ambient[..., 2, None]
    return stock * (detail * (1 - w) + w)[..., None]


def calibration(donor, specular):
    """Reproduce the fixed reference from hash-pinned physical interior rows.

    Sampling is original UV0, bilinear wrap at texel centers. Decode IEC sRGB
    before Rec.709 luminance; take the median of rows with physical blend zero.
    This is a texture-detail normalization, never a fitted brightness slider.
    """
    import numpy as np
    from PIL import Image
    from bake_v2_skin_textures import sample
    donor, specular = Path(donor), Path(specular)
    if digest(donor) != REFERENCE_DONOR_SHA256 or digest(specular) != REFERENCE_SPECULAR_SHA256:
        raise ValueError('Body-reflectance calibration requires exact canonical inputs')
    data = np.load(donor)
    encoded = sample(np.asarray(Image.open(specular).convert('RGB')), data['moduleUV']) / 255
    linear = np.where(encoded <= .04045, encoded / 12.92, ((encoded + .055) / 1.055) ** 2.4)
    interior = data['seamBlend'] == 0
    luminance = linear @ np.asarray(LUMINANCE_WEIGHTS)
    actual = float(np.median(luminance[interior]))
    if int(interior.sum()) != 15683 or abs(actual - REFERENCE_LUMINANCE) > 1e-13:
        raise ValueError('Canonical interior specular reference changed')
    return dict(donor=str(donor), donorSHA256=digest(donor), specular=str(specular),
                specularSHA256=digest(specular), rows=int(interior.sum()),
                scalar='Rec.709 luminance after IEC sRGB decode',
                sampling='Original UV0; bilinear wrap at texel centers; seamBlend==0',
                referenceLuminance=actual, spatialDetailRange=[float(luminance[interior].min()/actual),
                                                            float(luminance[interior].max()/actual)])


def author(source, job, donor, specular):
    from mod import ROOT
    from v2_physical_skin_material import PhysicalGraph, GRAPH, inspect
    source, job = Path(source), Path(job)
    if not job.resolve().is_relative_to((ROOT / 'v2/build/materials').resolve()):
        raise ValueError('Reflectance job must remain in owned material workspace')
    target = job / 'build/intake' / GRAPH
    if job.exists():
        raise ValueError('Use a fresh reflectance job; historical materials stay intact')
    previous = inspect(source)
    if previous.get('bodyMatchedReflectance'):
        raise ValueError('Source is already body-matched')
    reference = calibration(donor, specular)
    graph = PhysicalGraph(source)
    changes = []
    for signature, code in [('physicalSkinSpecular(', SPECULAR_CODE), ('physicalSkinAmbient(', AMBIENT_CODE)]:
        nodes = [i for i, row in enumerate(graph.objects) if signature.encode() in row[2].get('customCode', ('', b''))[1]]
        if len(nodes) != 1:
            raise ValueError('Missing unique physical skin channel: ' + signature)
        node = nodes[0]
        changes.append(dict(node=node, function=signature, beforeSHA256=hashlib.sha256(graph.objects[node][2]['customCode'][1]).hexdigest(),
                            afterSHA256=hashlib.sha256(encoded_string(code)).hexdigest()))
        graph.objects[node][2]['customCode'] = ('String', encoded_string(code))
    target.parent.mkdir(parents=True)
    target.write_bytes(graph.rebuild())
    proof = dict(schema='malemod.body-matched-skin-reflectance/1', source=str(source), sourceSHA256=digest(source),
                 graph=str(target), inspection=inspect(target), calibration=reference, changedFunctions=changes,
                 geometryChanged=False, sourceMapsChanged=False, normalDiffuseSSSFunctionsChanged=False,
                 nativeFunctionsChanged=False, nativeShaderPayloadUnchanged=True, officialResaveRequired=True,
                 nativeCompiled=False, nativeGameplayObserved=False, staged=False)
    (job / 'graph-authored.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
    return proof


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['source', 'job', 'donor', 'specular']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(author(args.source, args.job, args.donor, args.specular), indent=2))
