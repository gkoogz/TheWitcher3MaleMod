"""Audit the selected skin correction and authored cross-resource radial graft.

This verifies the actual asset receipts and sparse lineage, not gameplay or
native shading. Cooked conversion and the live body_render_test remain separate
gates. No game or shared source assets are modified.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.sparse import csr_matrix

from mod import ROOT, settings, read_json, digest, write_json
from build_body_boundary import verified_material,material_policy,character_ambient


def verify(job, output=None):
    # Some owned build jobs use a configured workspace junction to the fast
    # build volume. Read through that view, just as the authoring/cooking tools
    # do; no input paths are mutated by this audit.
    job=Path(job).absolute()
    if not job.is_relative_to(ROOT/'build'):
        raise ValueError('Audit only an owned body build job')
    cfg=settings();sys.path.insert(0,str(cfg['base']))
    from malemod_base.skin_match import linear, encoded, sample
    geometry=read_json(job/'manifest.json')
    receipt=read_json(job/'material-imports.json')
    pin=read_json(ROOT/'dependencies/base.lock.json')['commit']
    paths={
        'diffuse':(ROOT/'build/probe/geralt_lower.fbm/body_01_mg__geralt_d01.tga',cfg['base']/'assets/materials/wolverine/R14-skin-natural.dds'),
        'normal':(ROOT/'build/probe/geralt_lower.fbm/body_01_mg__geralt_n01.tga',cfg['base']/'assets/materials/wolverine/SharedBody-normal.dds'),
        'ambient':(ROOT/'build/jobs/texture-export-calibration/body-ambient.tga',None),
    }
    for channel,(stock,source) in paths.items():
        native=job/'intake/characters/malemod/materials'/('body_'+channel+'.xbm')
        row=verified_material(receipt,channel,pin,digest(stock),digest(source) if source else None,digest(native))
        group,compression=material_policy(channel)
        if row.get('textureGroup')!=group or row.get('compression')!=compression or not row.get('nativeMetadataVerified'):
            raise ValueError('Imported texture lacks measured character group/encoding: '+channel)
    correction=read_json(job/'skin-match.json')
    ambient_calibration=read_json(job/'ambient-match.json')
    ambient_row=next(row for row in receipt['materials'] if row['channel']=='ambient')
    if ambient_row.get('ambientMatchSHA256')!=digest(job/'ambient-match.json'):
        raise ValueError('Native packed Ambient lacks its generation receipt')
    ambient_stock=paths['ambient'][0]
    with Image.open(ambient_stock) as image:
        _,expected_calibration=character_ambient(image,correction['targetSampleUV'])
    if any(ambient_calibration.get(k)!=v for k,v in expected_calibration.items()) or ambient_calibration.get('targetSHA256')!=digest(ambient_stock):
        raise ValueError('Native skin packed-material calibration differs from measured stock seam')
    stock,source=paths['diffuse']
    if correction['sourceSHA256']!=digest(source) or correction['targetSHA256']!=digest(stock):
        raise ValueError('Skin correction inputs differ from imported texture inputs')
    with Image.open(source) as source_image, Image.open(stock) as target_image:
        s=sample(source_image,correction['sourceSampleUV'])
        t=sample(target_image,correction['targetSampleUV'])
    sm,tm=np.median(linear(s),axis=0),np.median(linear(t),axis=0)
    gain=np.asarray(correction['linearRGBGain'])
    if not np.allclose(gain,tm/sm,rtol=0,atol=1e-12):
        raise ValueError('Stored diffuse correction differs from the measured seam samples')
    corrected=encoded(linear(s)*gain)
    before=float(np.linalg.norm(np.median(s,axis=0)-np.median(t,axis=0)))
    after=float(np.linalg.norm(np.median(corrected,axis=0)-np.median(t,axis=0)))
    if after>1.5 or after>=before:
        raise ValueError('Diffuse correction does not match measured seam color')

    canonical=np.load(job/'waist.npz')['points']
    parts=[];waist_weights=None
    for i,row in enumerate(geometry['parts']):
        data=np.load(job/('part%d.npz'%i));points=data['points'];faces=data['faces']
        lineage=csr_matrix((data['lineage_data'],data['lineage_indices'],data['lineage_indptr']),shape=tuple(data['lineage_shape']))
        if len(points)!=row['vertices'] or lineage.shape[0]!=len(points):
            raise ValueError('Authored topology differs from its sparse lineage')
        if not np.allclose(np.asarray(lineage.sum(1)).ravel(),1,rtol=0,atol=1e-10) or np.any(lineage.data < -1e-12):
            raise ValueError('Refinement lost convex source attribute donors')
        if not np.array_equal(points[data['waist']],canonical):
            raise ValueError('The separate native resource/LOD does not share the canonical waist')
        weights=data['weights'][data['waist']]
        if waist_weights is None:waist_weights=weights
        elif not np.array_equal(weights,waist_weights):
            raise ValueError('Canonical skin field differs across a resource/LOD')
        triangle=points[faces]
        areas=np.linalg.norm(np.cross(triangle[:,1]-triangle[:,0],triangle[:,2]-triangle[:,0]),axis=1)
        if np.any(~np.isfinite(areas)) or np.any(areas<=1e-12):
            raise ValueError('Authored ramp contains a collapsed triangle')
        if i<2:
            donors=data['body_edge_donors'];a=donors[:,0].astype(int);b=donors[:,1].astype(int);u=donors[:,2,None]
            expected=points[a]*(1-u)+points[b]*u
            for key in ['body_seam','module_seam']:
                if not np.allclose(points[data[key]],expected,rtol=0,atol=1e-9):
                    raise ValueError('Anatomical graft no longer satisfies its original edge donor')
        parts.append(dict(resource=row['resource'],lod=row['lod'],vertices=len(points),minimumTwiceAreaFBXSquared=float(areas.min()),lineageVerified=True))
    # Inspect actual cooked UV0 against the authored FBX, including native
    # half-float rounding and WCC's V flip. This catches a source-island or
    # convention error which matching the pre-import samples cannot detect.
    from wcc_fbx import Document
    selection=read_json(ROOT/'build/full-runtime/current-install.json')
    render=ROOT/selection['render'];uv_errors=[]
    document=Document(job/'lower.fbx')
    for lod,mesh in enumerate(document.meshes):
        native=np.load(render/'inspection-lower'/('lod%d.npz'%lod))
        layer=next(l for l in mesh.children if l.name=='LayerElementUV' and l.values[0]==0)
        authored=layer.array('UV').reshape(-1,2).copy();authored[:,1]=1-authored[:,1]
        expected=authored[native['nearestAuthored']]
        error=float(np.abs(native['uv']-expected).max())
        if error>1/2048.:raise ValueError('Actual native UV0 differs from authored atlas convention')
        module=native['nearestAuthored']>=int(np.load(job/('part%d.npz'%lod))['bodyCount'])
        if np.any(native['uv'][module,0]<.5):raise ValueError('Native anatomy samples the Geralt atlas tile')
        uv_errors.append(error)
    report=dict(baseCommit=pin,bodyJob=job.relative_to(ROOT).as_posix(),seamSamples=len(s),linearRGBGain=gain.tolist(),medianRGBErrorBefore=before,medianRGBErrorAfter=after,packedMaterialChannelsVerified=True,packedMaterialRGB=ambient_calibration['packedRGB'],commonWaistSamples=len(canonical),parts=parts,nativeMaterialInputHashesVerified=True,nativeTextureGroupAndEncodingVerified=True,nativeAtlasUVMaximumErrors=uv_errors,nativeConversionVerified=False,observedGameplay=False)
    if output:
        output=Path(output).resolve()
        if not output.is_relative_to(ROOT/'build'):raise ValueError('Audit output must remain in owned build')
        write_json(output,report)
    print('PASS:',len(s),'measured seam color samples; median RGB error',before,'->',after,';',len(canonical),'exact waist positions/skin fields across four parts; sparse lineage and attachment edge donors retained')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--job',type=Path,required=True);p.add_argument('--output',type=Path)
    a=p.parse_args();verify(a.job,a.output)
