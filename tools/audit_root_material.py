"""Audit the actual packed native corner attributes at a dual-chart root seam."""
from pathlib import Path
import argparse,json
import numpy as np
from scipy.spatial import cKDTree

def audit(prefix):
    prefix=str(prefix)
    v=np.fromfile(prefix+'-native-attributes.bin',dtype=[('p','<f8',3),('n','<u4'),('t','<u4'),('uv','<f2',2)])
    s=np.fromfile(prefix+'-native-secondary.bin',dtype=[('uv','<f2',2),('color','<u4')])
    if len(v)!=len(s) or not len(v):raise ValueError('Missing paired packed attribute exports')
    weight=s['color']>>24
    pairs=[]
    for a,b in cKDTree(v['p']).query_pairs(1e-6):
        if weight[a]==0 and weight[b]==255:pairs.append((a,b))
        elif weight[b]==0 and weight[a]==255:pairs.append((b,a))
    if not pairs:raise ValueError('No outer ramp/body corner pairs')
    a,b=np.array(pairs).T
    checks=dict(secondaryUVMatchesBody=bool(np.array_equal(s['uv'][a],v['uv'][b])),
                packedNormalsIdentical=bool(np.array_equal(v['n'][a],v['n'][b])),
                packedTangentsAndHandednessIdentical=bool(np.array_equal(v['t'][a],v['t'][b])),
                stockColorChannelsIdentical=bool(np.array_equal(s['color'][a]&0xffffff,s['color'][b]&0xffffff)))
    result=dict(pairs=len(pairs),checks=checks,passed=all(checks.values()),nativeObserved=False,
                limitation='Verifies packed outer boundary continuity; not rendered interior continuity or gameplay acceptance.')
    Path(prefix+'-root-material-audit.json').write_text(json.dumps(result,indent=2))
    if not result['passed']:raise ValueError(result)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('prefix',type=Path);a=p.parse_args();print(json.dumps(audit(a.prefix),indent=2))
