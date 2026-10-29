"""Bounded adapter diffuse sampling over measured canonical raphe atlas gaps.

Two extra samplers share the EXISTING Diffuse parameter, including native state
overrides. Only the physical diffuse input changes. Original texture files,
UV arrays, alpha, SSS, normal/specular paths and geometry remain untouched.
Authoring is offline; official resave/cook and native review remain required.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from v2_fabric_material import encoded_string

SCHEMA = 'malemod.raphe-diffuse-sampling/1'
ATLAS_SIZE = 4096
DONOR_INSET = 12
LEFT_KNOTS = ((592,2630,2630),(598,2618,2637),(600,2613,2644),
              (610,2590,2655),(620,2570,2666),(630,2547,2669),
              (640,2526,2674),(650,2509,2681),(660,2480,2682),
              (670,2455,2683),(680,2414,2685),(685,2393.5,2686))
RIGHT_KNOTS = ((590,3517,3517),(594,3510,3524),(598,3501,3530),
               (600,3499,3535),(610,3494,3554),(620,3483,3574),
               (630,3479,3590),(640,3476,3604),(650,3471,3622),
               (660,3470,3638),(670,3468,3654),(680,3466,3673),
               (690,3465,3696),(700,3463,3720),(704,3463,3730),
               (708,3463,3740))


def number(x):
    return format(float(x), '.9g') + ('.0' if float(x).is_integer() else '')


def edge_code(knots):
    lines = [f'if(y<={number(knots[0][0])}) edges=float2({number(knots[0][1])},{number(knots[0][2])});']
    for a,b in zip(knots,knots[1:]):
        lines.append(f'else if(y<={number(b[0])}) edges=lerp(float2({number(a[1])},{number(a[2])}),'
                     f'float2({number(b[1])},{number(b[2])}),saturate((y-{number(a[0])})/{number(b[0]-a[0])}));')
    lines.append(f'else edges=float2({number(knots[-1][1])},{number(knots[-1][2])});')
    return '\n'.join(lines)


def selected_edges(vertical=False):
    left = edge_code(LEFT_KNOTS)
    right = edge_code(RIGHT_KNOTS)
    if vertical:
        left += '\nvertical=smoothstep(590.0,594.0,y)*(1.0-smoothstep(681.0,685.0,y));'
        right += '\nvertical=smoothstep(588.0,592.0,y)*(1.0-smoothstep(704.0,708.0,y));'
    return 'if(p.x<3000.0){\n'+left+'\n}else{\n'+right+'\n}\n'


def uv_code(name, edge, displacement):
    return (f'float4 {name}(float2 UV)\n{{\n'
            'float2 p=UV.xy*4096.0-0.5; float y=p.y; float2 edges;\n'
            + selected_edges() + f'return float4((float2(edges.{edge}{displacement},y)+0.5)/4096.0,0.0,0.0);\n}}')


LEFT_UV_CODE = uv_code('rapheDiffuseLeftUV','x','-12.0')
RIGHT_UV_CODE = uv_code('rapheDiffuseRightUV','y','+12.0')
REPAIR_CODE = ('float4 rapheDiffuseRepair(float2 UV,float4 original,float4 left,float4 right)\n{\n'
               'float2 p=UV.xy*4096.0-0.5; float y=p.y; float2 edges; float vertical;\n'
               + selected_edges(vertical=True) +
               'float width=edges.y-edges.x;\n'
               'float mask=smoothstep(-6.0,-2.0,min(p.x-edges.x,edges.y-p.x))*smoothstep(0.0,8.0,width)*vertical;\n'
               'if(mask<=0.0)return original;\n'
               'float t=saturate((p.x-edges.x)/max(width,0.000001));\n'
               'float3 tissue=lerp(pow(max(left.xyz,0),2.2),pow(max(right.xyz,0),2.2),t);\n'
               'float3 corrected=lerp(pow(max(original.xyz,0),2.2),tissue,mask);\n'
               'return float4(pow(max(corrected,0),1.0/2.2),original.w);\n}')
CODES = {'rapheDiffuseLeftUV':LEFT_UV_CODE,'rapheDiffuseRightUV':RIGHT_UV_CODE,
         'rapheDiffuseRepair':REPAIR_CODE}


def sampling_reference(uv):
    """CPU reference in original runtime UV0, at texel centers."""
    import numpy as np
    uv=np.asarray(uv,dtype=float)
    p=uv*ATLAS_SIZE-.5
    left=p[...,0]<3000
    a=np.asarray(LEFT_KNOTS);b=np.asarray(RIGHT_KNOTS)
    lo=np.where(left,np.interp(p[...,1],a[:,0],a[:,1]),np.interp(p[...,1],b[:,0],b[:,1]))
    hi=np.where(left,np.interp(p[...,1],a[:,0],a[:,2]),np.interp(p[...,1],b[:,0],b[:,2]))
    def smooth(low,high,x):
        t=np.clip((x-low)/(high-low),0,1)
        return t*t*(3-2*t)
    vertical=np.where(left,smooth(590,594,p[...,1])*(1-smooth(681,685,p[...,1])),
                       smooth(588,592,p[...,1])*(1-smooth(704,708,p[...,1])))
    mask=smooth(-6,-2,np.minimum(p[...,0]-lo,hi-p[...,0]))*smooth(0,8,hi-lo)*vertical
    fraction=np.clip((p[...,0]-lo)/np.maximum(hi-lo,1e-6),0,1)
    tap_left=(np.stack([lo-DONOR_INSET,p[...,1]],axis=-1)+.5)/ATLAS_SIZE
    tap_right=(np.stack([hi+DONOR_INSET,p[...,1]],axis=-1)+.5)/ATLAS_SIZE
    return tap_left,tap_right,mask,fraction


def diffuse_reference(uv, original, left, right):
    import numpy as np
    original,left,right=map(lambda x:np.asarray(x,dtype=float),(original,left,right))
    _,_,mask,t=sampling_reference(uv)
    tissue=np.maximum(left[...,:3],0)**2.2*(1-t[...,None])+np.maximum(right[...,:3],0)**2.2*t[...,None]
    linear=np.maximum(original[...,:3],0)**2.2*(1-mask[...,None])+tissue*mask[...,None]
    rgb=np.maximum(linear,0)**(1/2.2)
    rgb=np.where((mask<=0)[...,None],original[...,:3],rgb)
    return np.concatenate([rgb,original[...,3,None]],axis=-1)


def validate_custom_functions():
    """Compile declared and observed native vector4 socket conventions."""
    import ctypes as C
    import re
    compile_=C.WinDLL('d3dcompiler_47.dll').D3DCompile
    compile_.restype=C.c_long
    compile_.argtypes=[C.c_void_p,C.c_size_t,C.c_char_p,C.c_void_p,C.c_void_p,C.c_char_p,C.c_char_p,C.c_uint,C.c_uint,C.POINTER(C.c_void_p),C.POINTER(C.c_void_p)]
    def method(blob,index,restype):
        table=C.cast(blob,C.POINTER(C.POINTER(C.c_void_p))).contents
        return C.WINFUNCTYPE(restype,C.c_void_p)(table[index])
    variants=[]
    for native in (False,True):
        sources=list(CODES.values())
        if native:
            sources=[re.sub(r'float[234]?\s+(rapheDiffuse\w+)\(',r'float4 \1(',code).replace('float2 UV','float4 UV')for code in sources]
        source='\n'.join(sources)
        source+='\nTexture2D<float4> diffuseTexture:register(t0); SamplerState diffuseSampler:register(s0);'
        source+='\nfloat4 main(float4 p:SV_Position,float2 UV:TEXCOORD0):SV_Target {'
        source+='float4 a=diffuseTexture.Sample(diffuseSampler,UV);'
        uv='float4(UV,0.0,0.0)'if native else'UV'
        source+='float4 l=diffuseTexture.Sample(diffuseSampler,rapheDiffuseLeftUV('+uv+').xy);'
        source+='float4 r=diffuseTexture.Sample(diffuseSampler,rapheDiffuseRightUV('+uv+').xy);'
        source+='return rapheDiffuseRepair('+uv+',a,l,r);}'
        data=source.encode();code,error=C.c_void_p(),C.c_void_p()
        result=compile_(data,len(data),b'raphe-diffuse-functions',None,None,b'main',b'ps_5_0',0,0,C.byref(code),C.byref(error))
        message=''
        if error:
            message=C.string_at(method(error,3,C.c_void_p)(error),method(error,4,C.c_size_t)(error)).decode(errors='replace')
        for blob in [code,error]:
            if blob:method(blob,2,C.c_ulong)(blob)
        if result<0:
            raise ValueError('Raphe diffuse HLSL syntax failed (native vector4='+str(native)+'): '+message)
        variants.append(dict(nativeVector4Sockets=native,sourceSHA256=hashlib.sha256(data).hexdigest()))
    return dict(passed=True,compiler='D3DCompile ps_5_0',deviceCreated=False,variants=variants)


def texture_samplers(g, parameter):
    out=g.socket(parameter,'Texture')
    return [g.ptr(socket,'block') for socket in g.destinations(out)]


def is_uv0(g, output):
    node=g.ptr(output,'block')
    return (g.objects[node][0]=='CMaterialBlockTexCoords'
            and g.objects[node][2].get('coordinatesIndex',('Int32',bytes(4)))==('Int32',bytes(4)))


def original_diffuse_sampler(g):
    candidates=[]
    for node in texture_samplers(g,g.parameter('Diffuse')):
        if g.objects[node][0]!='CMaterialBlockSamplerTexture':
            raise ValueError('Diffuse texture has a non-sampler consumer')
        socket=g.socket(node,'UV')
        if not g.ids(socket,'connections') or is_uv0(g,g.upstream(socket)):
            candidates.append(node)
    if len(candidates)!=1:
        raise ValueError('Expected exactly one original UV0 Diffuse sampler')
    return candidates[0]


def inspect_graph(g):
    """Strict standalone wiring validation; historical graphs remain explicit."""
    marked=[i for i,o in enumerate(g.objects) if b'rapheDiffuse' in o[2].get('customCode',('',b''))[1]]
    if not marked:
        return dict(rapheDiffuseRepair=False)
    nodes={}
    for name,code in CODES.items():
        found=[i for i in marked if g.objects[i][2].get('customCode')==('String',encoded_string(code))]
        if len(found)!=1:
            raise ValueError('Missing or altered raphe diffuse function: '+name)
        nodes[name]=found[0]
    if len(marked)!=3:
        raise ValueError('Unexpected raphe diffuse function or partial variant')
    output=next(i for i,o in enumerate(g.objects) if o[0]=='CMaterialBlockOutputColorSkin')
    if not set(nodes.values()).issubset(g.dependencies(output)):
        raise ValueError('Raphe diffuse repair is disconnected from skin output')
    raw=original_diffuse_sampler(g)
    parameter=g.parameter('Diffuse')
    samplers=texture_samplers(g,parameter)
    if len(samplers)!=3 or len(set(samplers))!=3:
        raise ValueError('Raphe diffuse requires exactly three same-state Diffuse samplers')
    repair=nodes['rapheDiffuseRepair']
    uv=g.upstream(g.socket(repair,'UV'))
    if not is_uv0(g,uv):
        raise ValueError('Raphe diffuse does not read original untiled UV0')
    raw_uv=g.socket(raw,'UV')
    if g.ids(raw_uv,'connections') and g.upstream(raw_uv)!=uv:
        raise ValueError('Raphe diffuse changed the original UV0 source')
    if g.upstream(g.socket(repair,'original'))!=g.socket(raw,'Color'):
        raise ValueError('Raphe diffuse lost the original source sample')
    taps={}
    for argument,name in [('left','rapheDiffuseLeftUV'),('right','rapheDiffuseRightUV')]:
        node=nodes[name]
        if g.upstream(g.socket(node,'UV'))!=uv:
            raise ValueError('Raphe diffuse donor uses different source UV0')
        tap=g.ptr(g.upstream(g.socket(repair,argument)),'block')
        if tap==raw or tap not in samplers:
            raise ValueError('Raphe diffuse donor lost same-state Diffuse parameter')
        if g.upstream(g.socket(tap,'UV'))!=g.socket(node,'Out'):
            raise ValueError('Raphe diffuse donor does not use measured edge UV')
        if g.destinations(g.socket(node,'Out'))!=[g.socket(tap,'UV')]:
            raise ValueError('Raphe diffuse donor UV has an unexpected consumer')
        if g.destinations(g.socket(tap,'Color'))!=[g.socket(repair,argument)]:
            raise ValueError('Raphe diffuse donor color leaks to another channel')
        if any(g.destinations(g.socket(tap,c))for c in ['Red','Green','Blue','Alpha']):
            raise ValueError('Raphe diffuse donor leaks scalar channels')
        taps[argument]=tap
    if len(set(taps.values()))!=2:
        raise ValueError('Raphe diffuse donor taps are not independent')
    physical=[i for i,o in enumerate(g.objects) if b'physicalSkinDiffuse('in o[2].get('customCode',('',b''))[1]]
    if len(physical)!=1 or g.destinations(g.socket(repair,'Out'))!=[g.socket(physical[0],'albedo')]:
        raise ValueError('Raphe diffuse repair bypasses physical diffuse or leaks to other channels')
    return dict(rapheDiffuseRepair=True,originalSampler=raw,rawOutput=g.socket(raw,'Color'),
                repairOutput=g.socket(repair,'Out'),repairOriginalInput=g.socket(repair,'original'),
                repairNode=repair,uvOutput=uv,nodes=nodes,tapSamplers=taps,
                mask='measured piecewise UV0 atlas gaps; full plateau 2px outside; feather to 6px outside',
                originalTextureParameter='Diffuse',donorInsetPixels=DONOR_INSET,
                originalAlphaPreserved=True,otherMaterialChannelsChanged=False)


def build(source):
    from v2_physical_skin_material import PhysicalGraph
    from v2_skin_color_match import DIFFUSE_CODE as BODY_DIFFUSE,SSS_CODE as BODY_SSS
    g=PhysicalGraph(source)
    if inspect_graph(g)['rapheDiffuseRepair']:
        raise ValueError('Source already has a raphe diffuse repair')
    for code in [BODY_DIFFUSE,BODY_SSS]:
        if sum(o[2].get('customCode')==('String',encoded_string(code))for o in g.objects)!=1:
            raise ValueError('Raphe repair requires the complete body-color03 graph')
    g.new_blocks=[]
    raw=original_diffuse_sampler(g)
    parameter=g.parameter('Diffuse')
    uv_socket=g.socket(raw,'UV')
    if g.ids(uv_socket,'connections'):
        uv=g.upstream(uv_socket)
    else:
        candidates=[i for i,o in enumerate(g.objects) if o[0]=='CMaterialBlockTexCoords'
                    and o[2].get('coordinatesIndex',('Int32',bytes(4)))==('Int32',bytes(4))]
        if len(candidates)!=1:
            raise ValueError('Expected one observed original UV0 coordinates node')
        uv=g.socket(candidates[0],'UV')
    if not is_uv0(g,uv):
        raise ValueError('Original source diffuse must use native UV0')
    before_functions=[o[2]['customCode']for o in g.objects if 'customCode'in o[2]]
    taps={}
    for argument,code in [('left',LEFT_UV_CODE),('right',RIGHT_UV_CODE)]:
        _,donor_uv=g.custom(code,dict(UV=uv))
        sampler=g.clone(raw)
        g.rewire(g.socket(sampler,'Texture'),g.socket(parameter,'Texture'))
        g.rewire(g.socket(sampler,'UV'),donor_uv)
        g.new_blocks.append(sampler)
        taps[argument]=g.socket(sampler,'Color')
    _,repaired=g.custom(REPAIR_CODE,dict(UV=uv,original=g.socket(raw,'Color'),**taps))
    physical=next(i for i,o in enumerate(g.objects) if b'physicalSkinDiffuse('in o[2].get('customCode',('',b''))[1])
    if g.upstream(g.socket(physical,'albedo'))!=g.socket(raw,'Color'):
        raise ValueError('Source body-color diffuse route differs')
    g.rewire(g.socket(physical,'albedo'),repaired)
    root=next(i for i,o in enumerate(g.objects) if o[0]=='CMaterialGraph')
    g.array(root,'blocks',g.ids(root,'blocks')+g.new_blocks)
    if [o[2]['customCode']for o in g.objects if 'customCode'in o[2]][:len(before_functions)]!=before_functions:
        raise ValueError('An existing native/source function changed')
    proof=inspect_graph(g)
    return g,proof


def author(source, job):
    from mod import ROOT
    from v2_physical_skin_material import GRAPH,inspect
    source,job=Path(source),Path(job)
    if job.exists() or not job.resolve().is_relative_to((ROOT/'v2/build/materials').resolve()):
        raise ValueError('Use a fresh owned raphe material job')
    previous=inspect(source)
    if not all(previous.get(k)for k in ['bodyMatchedColor','bodyMatchedReflectance','normalComplete']):
        raise ValueError('Raphe repair requires the complete inspected body-color03 graph')
    graph,inspection=build(source)
    target=job/'build/intake'/GRAPH
    target.parent.mkdir(parents=True)
    target.write_bytes(graph.rebuild())
    # Also validate a serialized roundtrip; official native resave remains separate.
    from v2_physical_skin_material import PhysicalGraph,inspect
    inspect_graph(PhysicalGraph(target))
    native_inspection=inspect(target)
    proof=dict(schema=SCHEMA,source=str(source),sourceSHA256=hashlib.sha256(source.read_bytes()).hexdigest(),
               graph=str(target),inspection=native_inspection,rapheInspection=inspection,
               graphSHA256=hashlib.sha256(target.read_bytes()).hexdigest(),
               codeSHA256={k:hashlib.sha256(encoded_string(v)).hexdigest()for k,v in CODES.items()},
               atlasSize=ATLAS_SIZE,leftKnots=LEFT_KNOTS,rightKnots=RIGHT_KNOTS,
               originalDiffuseSamplerUnchanged=True,sameStateDiffuseParameterShared=True,
               sourceMapsChanged=False,geometryChanged=False,UVArraysChanged=False,
               originalCustomFunctionsUnchanged=True,normalReflectanceSSSFunctionsChanged=False,
               officialResaveRequired=True,nativeCompiled=False,nativeGameplayObserved=False,staged=False)
    (job/'graph-authored.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
    return proof


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--job',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(author(args.source,args.job),indent=2))
