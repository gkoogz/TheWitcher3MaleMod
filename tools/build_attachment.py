"""Reproducible native attachment preparation; never installs into the game."""
from pathlib import Path
import shutil
import time
import uuid
from mod import (ROOT,settings,base_checkout,read_json,write_json,digest,inside,
                 export_resource,import_mesh,required_file)
from fit_attachment import fit
from verify_attachment import verify


def build_attachment():
    cfg=settings();lock=base_checkout(cfg)
    profile=read_json(ROOT/'characters/geralt-attachment.json')
    inputs=[ROOT/'characters/geralt-attachment.json',ROOT/'tools/fit_attachment.py',ROOT/'tools/wcc_fbx.py',
            ROOT/'tools/verify_attachment.py',ROOT/'tools/build_attachment.py']
    input_hashes={p:digest(p) for p in inputs}
    export=inside(ROOT,profile['nativeExport'])
    if not export.exists():export_resource(cfg,profile['nativeResource'],export,stock=True)
    torso=ROOT/'build/inspection/candidates/t_01_mg__body_hires.fbx'
    if not torso.exists():
        export_resource(cfg,'characters/models/geralt/body/model/t_01_mg__body_hires.w2mesh',torso,stock=True)
    job=ROOT/'build/attachment'/('fit-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
    job.mkdir(parents=True)
    fbx=job/'geralt-anatomy.fbx';fit_report=fit(fbx)
    resource=profile['nativeResource'];native=inside(ROOT/'generated/workspace',resource)
    old=None
    if native.exists():
        # Only replace an exact output of our recorded prior native import.
        known=[read_json(p) for p in (ROOT/'generated/imports').glob('*.json')]
        if not any(r['resource']==resource and r['outputSHA256']==digest(native) for r in known):
            raise RuntimeError('Native attachment has untracked edits; preserve them before rebuilding')
        old=job/'previous-native.w2mesh';shutil.copy2(native,old)
        if digest(old)!=digest(native):raise RuntimeError('Native backup failed')
        native.unlink()  # Exact verified, backed-up generated file within ROOT.
    try:
        import_mesh(cfg,fbx,resource)
        native_export=job/'native-roundtrip.fbx'
        export_resource(cfg,resource,native_export)
        native_report=job/'native-verification.json';verify(fbx,native_export,native_report)
    except Exception:
        # Preserve any failed output before restoring the prior owned resource.
        if native.exists():shutil.move(str(native),str(job/'failed-native.w2mesh'))
        if old is not None:shutil.copy2(old,native)
        raise
    if any(digest(p)!=h for p,h in input_hashes.items()):
        raise RuntimeError('Attachment inputs changed during native work; rebuild before packaging')
    paths=[*inputs,fbx,fbx.with_suffix('.xml'),
           fbx.with_suffix('.fit.json'),native,native_export,native_report]
    paths += [fbx.with_name(l['bindings']) for l in fit_report['lods']]
    record={'schemaVersion':1,'feature':'surface.rest-graft','baseCommit':lock['commit'],
            'nativeVerified':True,'observedGameplay':False,'nativeResource':resource,
            'fitReport':fbx.with_suffix('.fit.json').relative_to(ROOT).as_posix(),
            'nativeReport':native_report.relative_to(ROOT).as_posix(),
            'files':[{'path':p.relative_to(ROOT).as_posix(),'sha256':digest(p)} for p in paths]}
    write_json(ROOT/'generated/attachment.json',record)
    print('Native attachment prepared and verified; build/package is the next step.')
    return record


if __name__=='__main__':build_attachment()
