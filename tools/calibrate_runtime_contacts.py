"""Measure the adapter collision primitives from verified Geralt stock body data."""
import json,numpy as np
from pathlib import Path
from scipy.optimize import least_squares
from mod import ROOT,read_json,write_json,digest,settings,base_checkout

def calibrate():
    path=ROOT/'characters/geralt-runtime-bindings.json';profile=read_json(path)
    binding=ROOT/profile['lods'][0]['binding']
    if digest(binding)!=profile['lods'][0]['bindingSHA256']:raise ValueError('Verified stock donor geometry differs')
    data=np.load(binding);points=data['body_original_points']/100.0
    # Central lower pelvis, bounded by the actual retained stock surface. The
    # shared source law uses one capsule, so fit that primitive rather than
    # claiming an exact convex hull or introducing a different collision law.
    selected=np.flatnonzero((abs(points[:,0])<=.06)&(points[:,2]>=.83)&(points[:,2]<=1.08))
    p=points[selected];zlo=float(p[:,2].min());zhi=float(p[:,2].max())
    def residual(x):
        radius=x[2];a=np.array([0.,x[0],zlo+radius]);b=np.array([0.,x[1],zhi-radius]);axis=b-a
        t=np.clip((p-a)@axis/(axis@axis),0,1)
        return np.linalg.norm(p-(a+t[:,None]*axis),axis=1)-radius
    fit=least_squares(residual,[-.045,-.025,.09],bounds=([-.1,-.1,.04],[.03,.04,(zhi-zlo)*.499]),loss='soft_l1',f_scale=.008)
    if not fit.success or len(selected)<100:raise ValueError('Measured pelvic primitive fit failed')
    radius=float(fit.x[2]);native=np.array([[0.,fit.x[0],zlo+radius],[0.,fit.x[1],zhi-radius]])
    c=profile['coordinateCalibration'];basis=np.array(c['basis']);scale=c['nativeUnitsPerSourceUnit']
    source=(native-np.array(c['targetRootNative']))@basis/scale+np.array(c['sourceRoot'])
    restored=np.array(c['targetRootNative'])+(source-np.array(c['sourceRoot']))@basis.T*scale
    if not np.allclose(restored,native,rtol=0,atol=1e-12):raise ValueError('Collider coordinate round trip failed')
    capsule=dict(nativeBindEndpoints=native.tolist(),radiusNative=radius,sourceEndpoints=source.tolist(),radiusSource=radius/scale,
        method='robust central stock pelvic surface capsule fit with measured vertical extent; same shared capsule primitive',
        sampleCount=len(selected),surfaceResidualNativePercentiles=np.percentile(abs(residual(fit.x)),[50,90,95,100]).tolist(),
        sourceBinding=profile['lods'][0]['binding'],sourceBindingSHA256=digest(binding),selectedStockDonorIndices=selected.tolist(),
        fitRecipeSHA256=digest(Path(__file__)),primitiveApproximation=True)
    profile['contacts']['pelvisCapsule']=capsule;profile['contacts']['pelvisStatus']='measured native primitive; collision quality remains a gameplay gate'
    profile['contacts']['livePoseSampling']='observed actor-local pelvis and both thigh endpoints; native script bridge'
    profile['baseCommit']=base_checkout(settings())['commit'];write_json(path,profile)
    out=ROOT/'build/full-runtime/geralt-contact-calibration.json';write_json(out,dict(profileSHA256=digest(path),capsule=capsule,sourceGeometryModified=False))
    print(json.dumps({k:v for k,v in capsule.items() if k!='selectedStockDonorIndices'},indent=2))
if __name__=='__main__':calibrate()
