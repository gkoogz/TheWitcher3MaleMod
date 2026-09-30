"""REDengine dangle rest frames: X points to the single skeletal child.

The native EvaluateTransforms routine aims X at that child even at rest. An
identity-frame cage therefore changes the skin pose before any motion occurs.
This convention belongs to the REDengine adapter, not Base's cage geometry.
"""
import numpy as np


def orient_chain(worlds, count=8):
    result=np.asarray(worlds,dtype=float).copy()
    for i in range(count-1):
        x=result[i+1,:3,3]-result[i,:3,3]
        length=np.linalg.norm(x)
        if not np.isfinite(length) or length<1e-8:raise ValueError('Collapsed native joint interval')
        x/=length
        reference=np.array([1.,0.,0.])
        if abs(np.dot(reference,x))>.95:reference=np.array([0.,0.,1.])
        y=reference-x*np.dot(reference,x);y/=np.linalg.norm(y)
        z=np.cross(x,y)
        result[i,:3,:3]=np.column_stack([x,y,z])
    result[count-1,:3,:3]=result[count-2,:3,:3]
    return result


def verify_rest_axes(worlds,count=8,tolerance=1e-6):
    w=np.asarray(worlds,dtype=float)
    directions=np.diff(w[:count,:3,3],axis=0)
    directions/=np.linalg.norm(directions,axis=1)[:,None]
    error=float(np.max(np.linalg.norm(w[:count-1,:3,0]-directions,axis=1)))
    if not np.isfinite(error) or error>tolerance:raise ValueError('Native solver would rotate the rest skin')
    np.testing.assert_allclose(np.linalg.det(w[:count,:3,:3]),1.,atol=1e-6)
    return {'nativeChildAxis':'positive X','maximumRestAxisError':error,'restAxisVerified':True}
