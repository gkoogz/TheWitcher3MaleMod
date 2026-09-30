"""Conservative REDengine cage calibration, not a shared physics solver.

Lengths use the measured native rest frame. Zero-distance source joints stay
kinematic. Native `dampening` retains velocity; higher values decay more slowly.
"""
import numpy as np
from prepare_motion import scalar, array


def apply_profile(resource, names, worlds):
    dyng=resource['_chunks']['CDyngResource #0']['_vars']
    all_names=[x['_value'] for x in dyng['nodeNames']['_elements']]
    if names!=['mm_shaft_%02d'%i for i in range(8)]+['mm_scrotum_l','mm_scrotum_r']:
        raise ValueError('Unexpected authored cage')
    ids=[all_names.index(n) for n in names]
    points=np.asarray(worlds,dtype=float)[:,:3,3]
    if points.shape!=(10,3) or not np.isfinite(points).all():raise ValueError('Invalid rest frame')
    distances=[0.]*len(all_names)
    # All limits are smaller than neighboring segment lengths. This prevents
    # the 0.4.0 tip envelope (0.12) from folding 0.0375-long segments over.
    caps=[0.,.003,.005,.007,.009,.011,.013,.015,.006,.006]
    shortest=float(np.linalg.norm(np.diff(points[:8],axis=0),axis=1).min())
    if shortest<=0:raise ValueError('Collapsed native chain')
    for i,index in enumerate(ids):distances[index]=min(caps[i],shortest*.4)
    dyng['nodeDistances']=array('array:2,0,Float',[scalar('Float',v) for v in distances])
    # Match the observed pendant's zero stiffness; don't equate this legacy
    # native field with the Base stiffness control without a calibrated law.
    dyng['nodeStifnesses']=array('array:2,0,Float',[scalar('Float',0.) for _ in all_names])
    pairs=[(i,i+span) for span in (1,2) for i in range(8-span)]
    for key,values in {
        'linkAs':[ids[a] for a,b in pairs], 'linkBs':[ids[b] for a,b in pairs],
        'linkTypes':[0]*len(pairs),
        'linkLengths':[float(np.linalg.norm(points[a]-points[b])) for a,b in pairs]
    }.items():
        kind=dyng[key]['_elements'][0]['_type']
        dyng[key]['_elements']=[scalar(kind,v) for v in values]
    return {'profile':'bounded-native-v2','maximumDisplacement':max(distances),
            'shortestShaftSegment':shortest,'links':len(pairs),
            'stockJointsKinematic':True,'observedStableGameplay':False}
