"""Offline coupled-domain verification on actual fitted Geralt bindings.

The synthetic expansion is a seam/boundary stress fixture, not the actual
source Raphe guide or a generated in-game slider. No cook/install occurs.
"""
import json
from pathlib import Path
import sys
import time
import uuid
import numpy as np
from mod import ROOT, settings, base_checkout, digest, write_json


def main():
    cfg=settings();pin=base_checkout(cfg);sys.path.insert(0,str(cfg['base']))
    from malemod_base.graft import boundary_loops,topology_ids
    from malemod_base.graft_collar import GraftCollar
    from malemod_base.collar import CollarFrame
    fit_path=ROOT/'build/attachment/fit-20260930-075013-7ae7f2/geralt-anatomy.fit.json'
    fit=json.loads(fit_path.read_text(encoding='utf-8'))
    profile=json.loads((ROOT/'characters/geralt-attachment.json').read_text(encoding='utf-8'))
    basis=np.asarray(profile['basis']);scale=fit['sourceToFBXScale']
    source_root=np.asarray(fit['sourceRoot']);target_root=np.asarray(profile['targetRoot'])
    job=ROOT/'build/pelvic-domain'/uuid.uuid4().hex[:12];job.mkdir(parents=True)
    rows=[]
    for lod in fit['lods']:
        binding=fit_path.parent/lod['bindings']
        if digest(binding)!=lod['bindingsSHA256']:raise ValueError('Fitted binding changed')
        with np.load(binding,allow_pickle=False) as b:
            # Undo the measured fit, not the different anatomical shaft anchor.
            points=(b['points']-target_root)@basis/scale+source_root
            _,stock_alias=topology_ids(b['body_original_points'],1e-5)
            stock_loops=boundary_loops(stock_alias[b['body_original_faces']])
            protected=np.flatnonzero(np.isin(stock_alias,np.concatenate(stock_loops)))
            domain=GraftCollar(points,b['faces'],b['body_seam'],b['module_seam'],
                              b['body_edge_donors'],protected,1e-5/scale)
            for radius in [2.9,4.5,7.62]:
                # Explicit source-unit fixture dimensions. These are NOT a
                # recovered logical frame from Wolverine's omitted live data.
                frame=CollarFrame((9,0,84.3),(1,0,0),(0,0,1),radius,30.,1.)
                start=time.perf_counter();plan=domain.prepare(frame)
                factor_seconds=time.perf_counter()-start
                target=points.copy();target[:,1]+=np.sign(points[:,1])*plan.mask[domain.aliases]*.5
                start=time.perf_counter();out,fraction=domain.solve_checked(target,frame,.025)
                solve_seconds=time.perf_counter()-start
                seam=float(np.max(np.linalg.norm(out[b['body_seam']]-out[b['module_seam']],axis=1)))
                lock=float(np.max(np.linalg.norm(out[protected]-points[protected],axis=1)))
                if seam>1e-10 or lock>1e-10:raise RuntimeError('Seam or body-part boundary drift')
                before=points[b['faces']];after=out[b['faces']]
                normal=lambda p:np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0])
                old_normal=normal(before);new_normal=normal(after)
                ratios=np.sum(old_normal*new_normal,axis=1)/np.sum(old_normal*old_normal,axis=1)
                inverted=int(np.count_nonzero(ratios<=0))
                donors=b['body_edge_donors'];a=donors[:,0].astype(int);c=donors[:,1].astype(int);w=donors[:,2,None]
                donor_error=float(np.max(np.linalg.norm(out[b['body_seam']]-(out[a]*(1-w)+out[c]*w),axis=1)))
                if donor_error>1e-10 or ratios.min()<.025-1e-9:
                    raise RuntimeError('Original edge donor or continuous area bound failed')
                row={'lod':lod['lod'],'probeRadiusSourceUnits':radius,'renderVertices':len(points),
                     'canonicalVertices':len(domain.unique),'activeMasters':len(plan.free),
                     'originalEdgeConstraints':len(domain.seams),'protectedBoundaryVertices':len(protected),
                     'maximumSeamError':seam,'maximumPartBoundaryDrift':lock,'invertedTriangles':inverted,
                     'acceptedCorrectionFraction':fraction,'requestedShapeAccuracyVerified':False,
                     'minimumProjectedAreaRatio':float(ratios.min()),'maximumOriginalDonorError':donor_error,
                     'factorSecondsOffline':factor_seconds,'solveSecondsOffline':solve_seconds,
                     'sourceBindingSHA256':digest(binding)}
                rows.append(row)
    report={'fixture':'synthetic lateral target on actual fitted Geralt topology',
            'fitReportSHA256':digest(fit_path),'baseCommit':pin['commit'],
            'rows':rows,'nativeOutputVerified':False,'observedGameplay':False,'installed':False,
            'limitations':['synthetic targets, not reconstructed Raphe guide or full source rest shape',
                           'bounded synthetic correction does not establish requested shape accuracy',
                           'no native deformation bridge or independent physics controls']}
    write_json(job/'report.json',report);print(json.dumps(report,indent=2))
    return report


if __name__=='__main__':main()
