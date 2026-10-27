"""Alias-free material-frame normal transport, before the original native RNM.

Source/stock encoded endpoints pass through exactly. This explicitly defines
the interior fit frame; it does not claim an original stock world frame there.
"""
import numpy as np

NORMAL_CODE = '''float4 physicalSkinNormalTransport(float4 sourceEncoded,float4 stockEncoded,float weight,float3 position,float2 UV,float3 nativeT,float3 nativeB,float3 nativeN)
{
 float w=isfinite(weight)?saturate(weight):0;
#if defined(RT_MULTI_MATERIAL_GENERATION_TYPE) || ST_RAYTRACING
 if(w<=0)return sourceEncoded;
 if(w>=1)return stockEncoded;
 return lerp(sourceEncoded,stockEncoded,w);
#else
 // All raster derivatives execute before any endpoint or validity branch.
 float3 px=ddx(position.xyz),py=ddy(position.xyz);
 float2 ux=ddx(UV.xy),uy=ddy(UV.xy);
 if(w<=0)return sourceEncoded;
 if(w>=1)return stockEncoded;
 float4 fallback=lerp(sourceEncoded,stockEncoded,w);
 float3 T=nativeT.xyz,B=nativeB.xyz,N=nativeN.xyz;
 float n2=dot(N,N),t2=dot(T,T),b2=dot(B,B);
 float det=dot(T,cross(B,N));
 float uvdet=ux.x*uy.y-ux.y*uy.x;
 float uvscale=dot(ux,ux)*dot(uy,uy);
 if(!all(isfinite(float4(n2,t2,b2,det)))||n2<=0||t2<=0||b2<=0||det*det<=n2*t2*b2*1e-12
    ||!isfinite(uvdet)||!isfinite(uvscale)||uvscale<=0||uvdet*uvdet<=uvscale*1e-12)
  return fallback;
 float3 nh=N*rsqrt(n2);
 float3 tu=(px*uy.y-py*ux.y)/uvdet;
 float3 bv=(py*ux.x-px*uy.x)/uvdet;
 tu-=nh*dot(nh,tu);
 float tu2=dot(tu,tu);
 if(!all(isfinite(tu))||!all(isfinite(bv))||!isfinite(tu2)||tu2<=0)return fallback;
 tu*=rsqrt(tu2);
 float handed=dot(cross(tu,bv),nh);
 if(!isfinite(handed)||handed==0)return fallback;
 float3 bu=cross(nh,tu)*(handed<0?-1:1);
 float3 s=sourceEncoded.xyz*2-1,k=stockEncoded.xyz*2-1;
 // Both material frames have the identical raw native geometric-N column.
 float3 derived=tu*k.x+bu*k.y+N*k.z;
 float3 original=T*k.x+B*k.y+N*k.z;
 float3 stockWorld=lerp(derived,original,w);
 float3 sourceWorld=T*s.x+B*s.y+N*s.z;
 float3 combined=lerp(sourceWorld,stockWorld,w);
 float3 ts=float3(dot(cross(B,N),combined),dot(cross(N,T),combined),dot(cross(T,B),combined))/det;
 if(!all(isfinite(ts)))return fallback;
 return float4(ts*.5+.5,lerp(sourceEncoded.w,stockEncoded.w,w));
#endif
}'''


def reference(source,stock,weight,position_dx,position_dy,uv_dx,uv_dy,native,rt=False,dtype=np.float64):
    """Scalar/batched reference using the same branches and conditioning law."""
    source,stock=np.asarray(source,dtype=dtype),np.asarray(stock,dtype=dtype)
    native=np.asarray(native,dtype=dtype);shape=np.broadcast_shapes(source.shape[:-1],stock.shape[:-1],native.shape[:-2],np.shape(weight))
    source=np.broadcast_to(source,shape+(4,)).copy();stock=np.broadcast_to(stock,shape+(4,))
    native=np.broadcast_to(native,shape+(3,3));weight=np.broadcast_to(weight,shape)
    w=np.where(np.isfinite(weight),np.clip(weight,0,1),0).astype(dtype)
    fallback=source*(1-w[...,None])+stock*w[...,None];out=fallback.copy()
    if not rt:
        dx=np.broadcast_to(np.asarray(position_dx,dtype=dtype),shape+(3,));dy=np.broadcast_to(np.asarray(position_dy,dtype=dtype),shape+(3,));ux=np.broadcast_to(np.asarray(uv_dx,dtype=dtype),shape+(2,));uy=np.broadcast_to(np.asarray(uv_dy,dtype=dtype),shape+(2,))
        for index in np.ndindex(shape):
            if not 0<w[index]<1:continue
            T,B,N=native[index].T;n2=np.dot(N,N);t2=np.dot(T,T);b2=np.dot(B,B);det=np.dot(T,np.cross(B,N));ud=ux[index][0]*uy[index][1]-ux[index][1]*uy[index][0];scale=np.dot(ux[index],ux[index])*np.dot(uy[index],uy[index])
            if not np.isfinite([n2,t2,b2,det,ud,scale]).all()or min(n2,t2,b2,scale)<=0 or det*det<=n2*t2*b2*1e-12 or ud*ud<=scale*1e-12:continue
            nh=N/np.sqrt(n2);tu=(dx[index]*uy[index][1]-dy[index]*ux[index][1])/ud;bv=(dy[index]*ux[index][0]-dx[index]*uy[index][0])/ud;tu-=nh*np.dot(nh,tu);tu2=np.dot(tu,tu)
            if not np.isfinite(tu).all()or not np.isfinite(bv).all()or not np.isfinite(tu2)or tu2<=0:continue
            tu/=np.sqrt(tu2);hand=np.dot(np.cross(tu,bv),nh)
            if not np.isfinite(hand)or hand==0:continue
            bu=np.cross(nh,tu)*(-1 if hand<0 else 1);s=source[index][:3]*2-1;k=stock[index][:3]*2-1
            derived=tu*k[0]+bu*k[1]+N*k[2];original=T*k[0]+B*k[1]+N*k[2];source_world=T*s[0]+B*s[1]+N*s[2]
            combined=source_world*(1-w[index])+(derived*(1-w[index])+original*w[index])*w[index]
            ts=np.asarray([np.dot(np.cross(B,N),combined),np.dot(np.cross(N,T),combined),np.dot(np.cross(T,B),combined)])/det
            if np.isfinite(ts).all():out[index][:3]=ts*.5+.5
    out=np.where((w<=0)[...,None],source,np.where((w>=1)[...,None],stock,out))
    return out
