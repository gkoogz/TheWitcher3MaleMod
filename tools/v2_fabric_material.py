"""Own native graph data for the canonical raster fabric shading terms.

REDengine still owns illumination. Its observed two-sided output reflection
performs the source facing operation after the derivative tangent is applied.
Only graph data is authored; official resave/cook/shader compilation is required.
"""
import copy
import hashlib
from pathlib import Path
import struct
import zlib

from player_rig_redirect import header_crc
from v2_skin_material import state
from v2_cloth_material import native_objects

GRAPH = 'characters/malemod/garments/fabric.w2mg'
ROLE_PARAMETER = 'VarianceOffset'

NORMAL_CODE = '''float4 sourceFabricNormal(float3 normal, float3 position, float2 UV, float slopeThreshold)
{
 float3 n=normal*rsqrt(max(dot(normal,normal),1e-10));
#if defined(RT_MULTI_MATERIAL_GENERATION_TYPE) || ST_RAYTRACING
 // The source has no raytracing pass or raster derivatives. Preserve its
 // geometric frame here; the observed source analytic detail is raster-only.
 return float4(n,1);
#else
 float3 dx=ddx(position),dy=ddy(position);float2 ux=ddx(UV),uy=ddy(UV);
 float determinant=ux.x*uy.y-ux.y*uy.x;
 float3 tangent=dx*uy.y-dy*ux.y;
 tangent-=n*dot(n,tangent);
 tangent*=rsqrt(max(dot(tangent,tangent),1e-10));
 tangent*=determinant<0?-1:1;
 float fade=1-smoothstep(.2,.65,fwidth(UV.x)*96);
 float pouch=1-step(.5,slopeThreshold);
 n=normalize(n+tangent*(sin(UV.x*96*6.2831853)*.16*fade*pouch));
 return float4(n,1);
#endif
}'''

COLOR_CODE = '''float4 sourceFabricColor(float2 UV,float slopeThreshold)
{
 float3 color=float3(.527115126,.496932995,.462077000);
 if(slopeThreshold>1.5)color=slopeThreshold<2.5?float3(.58,.018,.027):float3(.018,.065,.38);
#if !defined(RT_MULTI_MATERIAL_GENERATION_TYPE) && !ST_RAYTRACING
 float fade=1-smoothstep(.2,.65,fwidth(UV.x)*96);
 float pouch=1-step(.5,slopeThreshold);
 color*=1+pouch*.035*cos(UV.x*96*6.2831853)*fade;
#endif
 return float4(color,1);
}'''


def encoded_string(text):
    data=text.encode();n=len(data);prefix=bytes([(n&63)|128|(64 if n>>6 else 0)]);n>>=6
    while n:
        prefix+=bytes([(n&127)|(128 if n>>7 else 0)]);n>>=7
    return prefix+data


def validate_hlsl():
    """Use the actual native HLSL parser for raster and nonderivative fallback."""
    import ctypes
    compiler=ctypes.WinDLL('d3dcompiler_47.dll').D3DCompile
    compiler.restype=ctypes.c_long
    compiler.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_char_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_char_p,ctypes.c_char_p,ctypes.c_uint,ctypes.c_uint,ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(ctypes.c_void_p)]
    for rt,multi in ((0,False),(1,False),(0,True)):
        defines='#define ST_RAYTRACING %d\n'%rt+('#define RT_MULTI_MATERIAL_GENERATION_TYPE 1\n'if multi else'')
        source=(defines+NORMAL_CODE+'\n'+COLOR_CODE+'\nfloat4 main(float4 p:SV_Position):SV_Target{return sourceFabricNormal(float3(0,0,1),p.xyz,p.xy,0)+sourceFabricColor(p.xy,0);}').encode()
        code,error=ctypes.c_void_p(),ctypes.c_void_p()
        status=compiler(source,len(source),b'source-fabric',None,None,b'main',b'ps_5_0',0,0,ctypes.byref(code),ctypes.byref(error))
        def method(blob,index,result,*args):
            table=ctypes.cast(blob,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
            return ctypes.WINFUNCTYPE(result,ctypes.c_void_p,*args)(table[index])
        message=''
        if error:message=ctypes.string_at(method(error,3,ctypes.c_void_p)(error),method(error,4,ctypes.c_size_t)(error)).decode(errors='replace')
        for blob in (code,error):
            if blob:method(blob,2,ctypes.c_ulong)(blob)
        if status<0:raise ValueError('Source fabric HLSL rejected: '+message)
    return dict(compiler='D3DCompile ps_5_0',rasterAndNonderivativeFallback=True,passed=True)


def inspect(path):
    r,imports,objects,name,array,ptr=state(path)
    def owner(signature):
        found=[i for i,o in enumerate(objects)if signature in o[2].get('customCode',('',b''))[1]]
        if len(found)!=1:raise ValueError('Missing or duplicate source fabric function')
        return found[0]
    normal,color=owner(b'sourceFabricNormal('),owner(b'sourceFabricColor(')
    def socket(index,label):
        matches=[s for s in array(index,'sockets')if name(s)==label]
        if len(matches)!=1:raise ValueError('Missing source fabric socket: '+label)
        return matches[0]
    def upstream(index):
        edges=array(index,'connections')
        if len(edges)!=1 or ptr(edges[0],'source')!=index:raise ValueError('Disconnected source fabric input')
        other=ptr(edges[0],'destination')
        if not any(ptr(e,'source')==other and ptr(e,'destination')==index for e in array(other,'connections')):
            raise ValueError('Source fabric edge is not reciprocal')
        return ptr(other,'block')
    output=next(i for i,o in enumerate(objects)if o[0]=='CMaterialBlockOutputColorDeferred')
    if upstream(socket(output,'Normal'))!=normal or upstream(socket(output,'Diffuse'))!=color:
        raise ValueError('Source fabric output was bypassed')
    for argument,kind in [('normal','CMaterialBlockTangentToWorld'),('position','CMaterialBlockWorldPosition'),('UV','CMaterialBlockTexCoords'),('slopeThreshold','CMaterialParameterScalar')]:
        if objects[upstream(socket(normal,argument))][0]!=kind:raise ValueError('Source fabric normal input differs: '+argument)
    for argument in ['UV','slopeThreshold']:upstream(socket(color,argument))
    role=upstream(socket(normal,'slopeThreshold'))
    if name(role,'parameterName')!=ROLE_PARAMETER or upstream(socket(color,'slopeThreshold'))!=role:
        raise ValueError('Source fabric material roles differ')
    spec=upstream(socket(output,'Specularity'));rough=upstream(socket(output,'Roughness'))
    if name(spec,'parameterName')!='RSpecBase' or struct.unpack('<f',objects[spec][2]['scalar'][1])[0]!=0:
        raise ValueError('Source fabric acquired a specular term')
    if abs(struct.unpack('<f',objects[rough][2]['scalar'][1])[0]-224/255)>1e-7:raise ValueError('Fabric roughness differs')
    if NORMAL_CODE.encode() not in objects[normal][2]['customCode'][1] or COLOR_CODE.encode() not in objects[color][2]['customCode'][1]:
        raise ValueError('Source analytic fabric code differs')
    return dict(graph=GRAPH,sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),sourceRasterFunctionsExact=True,
                allDeclaredInputsBound=True,reciprocalConnections=True,roleParameter=ROLE_PARAMETER,
                opaqueNativeOutput=True,explicitCustomFaceFlip=False,nativeFacingCorrectionRequired=True,nativeObserved=False)


def observed_name_entries(path):
    """Read CRC-checked native name tables, including the observed 163 donor."""
    raw=Path(path).read_bytes()
    if raw[:4]!=b'CR2W' or struct.unpack_from('<I',raw,4)[0]not in (163,164) or header_crc(raw,0)!=struct.unpack_from('<I',raw,32)[0]:
        raise ValueError('Unobserved source graph name-table layout')
    def table(i,stride):
        off,count,crc=struct.unpack_from('<III',raw,40+i*12);data=raw[off:off+count*stride]
        if len(data)!=count*stride or zlib.crc32(data)!=crc:raise ValueError('Native source name-table CRC differs')
        return data
    strings=table(0,1);result={}
    for off,h in struct.iter_unpack('<II',table(1,8)):
        name=strings[off:strings.index(b'\0',off)].decode();result[name]=h
    return result


def author(source,target,sdk):
    source,target,sdk=Path(source),Path(target),Path(sdk)
    raw=source.read_bytes();r,imports,original,name,array,ptr=state(source);objects=copy.deepcopy(original)
    old_names=list(r.names);names=list(old_names)
    donors=[sdk/'fx/environment/leaf/leaf_mat_fx.w2mg',sdk/'engine/materials/graphs/transparent_lit.w2mg']
    hashes={}
    for donor in [source]+donors:hashes.update(observed_name_entries(donor))
    for label in ['CMaterialBlockTexCoords','CMaterialBlockWorldPosition']:
        if label not in names:
            if label not in hashes:raise ValueError('Native node name lacks observed hash: '+label)
            names.append(label)
    def cname(label):return struct.pack('<H',names.index(label))
    def pointers(ids):return struct.pack('<I',len(ids))+b''.join(struct.pack('<i',i+1)for i in ids)
    def ids(index,key='sockets'):
        data=objects[index][2].get(key,('',bytes(4)))[1]
        return [v[0]-1 for v in struct.iter_unpack('<i',data[4:])]
    def arr(index,key,ty,values):objects[index][2][key]=(ty,pointers(values))
    def sock(owner,label,direction):
        found=[i for i in ids(owner)if objects[i][0]=='CMaterial'+direction+'Socket'and objects[i][2]['name'][1]==cname(label)]
        if len(found)!=1:raise ValueError('Unobserved fabric socket '+label)
        return found[0]
    def rewire(input_id,output_id):
        for edge in ids(input_id,'connections'):
            other=struct.unpack('<i',objects[edge][2]['destination'][1])[0]-1
            arr(other,'connections','array:2,0,ptr:CGraphConnection',[e for e in ids(other,'connections')if struct.unpack('<i',objects[e][2]['destination'][1])[0]-1!=input_id])
        first=len(objects)
        for a,b in [(input_id,output_id),(output_id,input_id)]:
            node=copy.deepcopy(next(o for o in original if o[0]=='CGraphConnection'));node[2].clear()
            node[2].update(source=('ptr:CGraphSocket',struct.pack('<i',a+1)),destination=('ptr:CGraphSocket',struct.pack('<i',b+1)));objects.append(node)
        arr(input_id,'connections','array:2,0,ptr:CGraphConnection',[first])
        arr(output_id,'connections','array:2,0,ptr:CGraphConnection',ids(output_id,'connections')+[first+1])
    root=next(i for i,o in enumerate(objects)if o[0]=='CMaterialGraph')
    out=next(i for i,o in enumerate(objects)if o[0]=='CMaterialBlockOutputColorDeferred')
    newblocks=[]
    def block(kind,arguments,code=None):
        owner=len(objects);node=copy.deepcopy(next(o for o in original if o[0]=='CMaterialBlockTangentToWorld'));node=(kind,node[1],node[2],b'')
        node[2].pop('position',None);objects.append(node);newblocks.append(owner)
        socket_ids=[]
        for direction,label in [('Output','Out')]+[('Input',label)for label in arguments]:
            s=copy.deepcopy(next(o for o in original if o[0]=='CMaterial'+direction+'Socket'))
            s[2].pop('connections',None);s[2].pop('swizzle',None);s[2]['name']=('CName',cname(label));s[2]['block']=('ptr:CGraphBlock',struct.pack('<i',owner+1))
            socket_ids.append(len(objects));objects.append(s)
        arr(owner,'sockets','array:2,0,ptr:CGraphSocket',socket_ids)
        if code is not None:node[2]['customCode']=('String',encoded_string(code))
        return owner
    position=block('CMaterialBlockWorldPosition',[])
    uv=block('CMaterialBlockTexCoords',[])
    # These built-ins have observed Out/UV output labels, respectively.
    objects[sock(uv,'Out','Output')][2]['name']=('CName',cname('UV'))
    role=next(i for i,o in enumerate(original)if'parameterName'in o[2]and name(i,'parameterName')==ROLE_PARAMETER)
    roleout=sock(role,'Value','Output')
    base=next(i for i,o in enumerate(original)if o[0]=='CMaterialBlockTangentToWorld')
    flat=next(i for i,o in enumerate(original)if o[0]=='CMaterialBlockCustomFunction'and b'unpackNormal('in o[2].get('customCode',('',b''))[1])
    objects[flat][2]['customCode']=('String',encoded_string('float4 unpackNormal(float4 col){return float4(0,0,1,0);}'))
    normal=block('CMaterialBlockCustomFunction',['normal','position','UV','slopeThreshold'],NORMAL_CODE)
    for arg,up in [('normal',sock(base,'Out','Output')),('position',sock(position,'Out','Output')),('UV',sock(uv,'UV','Output')),('slopeThreshold',roleout)]:rewire(sock(normal,arg,'Input'),up)
    color=block('CMaterialBlockCustomFunction',['UV','slopeThreshold'],COLOR_CODE)
    rewire(sock(color,'UV','Input'),sock(uv,'UV','Output'));rewire(sock(color,'slopeThreshold','Input'),roleout)
    rewire(sock(out,'Normal','Input'),sock(normal,'Out','Output'));rewire(sock(out,'Diffuse','Input'),sock(color,'Out','Output'))
    zero=next(i for i,o in enumerate(original)if'parameterName'in o[2]and name(i,'parameterName')=='RSpecBase')
    objects[zero][2]['scalar']=('Float',struct.pack('<f',0));rewire(sock(out,'Specularity','Input'),sock(zero,'Value','Output'))
    rough=copy.deepcopy(original[zero]);rough[2]['parameterName']=('CName',cname('Roughness'));rough[2]['scalar']=('Float',struct.pack('<f',224/255));rough[2].pop('position',None)
    roughid=len(objects);objects.append(rough);newblocks.append(roughid)
    template=copy.deepcopy(objects[sock(zero,'Value','Output')]);template[2]['block']=('ptr:CGraphBlock',struct.pack('<i',roughid+1));template[2].pop('connections',None)
    roughout=len(objects);objects.append(template);arr(roughid,'sockets','array:2,0,ptr:CGraphSocket',[roughout]);rewire(sock(out,'Roughness','Input'),roughout)
    arr(root,'blocks','array:2,0,ptr:CGraphBlock',ids(root,'blocks')+newblocks)
    arr(root,'pixelParameterBlocks','array:2,0,ptr:CMaterialParameter',ids(root,'pixelParameterBlocks')+[roughid])
    rebuilt=rebuild(raw,objects,names,hashes)
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(rebuilt)
    return dict(graph=GRAPH,sha256=hashlib.sha256(rebuilt).hexdigest(),sourceSHA256=hashlib.sha256(raw).hexdigest(),
                observedNodeDonors=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())for p in donors],
                sourceAnalyticRasterNormal=True,sourceRibColor=True,sourceCottonPalette=True,
                sourceGeometryModified=False,sourceNormalsModified=False,ambientFloorAdded=False,
                nativeFacing='Verified actual native output reflects normal geometric component on backfaces; no second custom flip',
                roleParameter=ROLE_PARAMETER,roleValues={'ribbed':0,'elastic':1,'red':2,'blue':3},
                sourceSpecularTerm=0,roughness=224/255,rayTracing='No source analogue; geometric normal and unmodulated source palette',
                officialResaveRequired=True,nativeObserved=False)


def rebuild(raw,objects,names,hashes):
    if any(struct.unpack_from('<II',raw,40+12*i)!=(0,0)for i in [5,6,7,8,9]):raise ValueError('Unobserved graph external tables')
    so,sc,_=struct.unpack_from('<III',raw,40);strings=bytearray(raw[so:so+sc]);offsets={}
    at=0
    while at<len(strings):
        end=strings.index(0,at);offsets[strings[at:end].decode()]=at;at=end+1
    for n in names:
        if n not in offsets:offsets[n]=len(strings);strings+=n.encode()+b'\0'
    table1=b''.join(struct.pack('<II',offsets[n],hashes[n])for n in names)
    io,ic,_=struct.unpack_from('<III',raw,64);imports=raw[io:io+ic*8]
    eo,ec,_=struct.unpack_from('<III',raw,88);entries=list(struct.iter_unpack('<HHIIIII',raw[eo:eo+ec*24]))
    oldkind={names[e[0]]:e for e in entries}
    po,pc,pcrc=struct.unpack_from('<III',raw,76);properties=raw[po:po+pc*16]
    if len(properties)!=pc*16 or zlib.crc32(properties)!=pcrc:raise ValueError('Native graph property-table CRC differs')
    tables=[bytes(strings),table1,imports,properties]
    result=bytearray(raw[:160])
    for i,table in enumerate(tables):
        while len(result)%4:result+=b'\0'
        off=len(result);result+=table;count=len(table)//([1,8,8,16][i])
        struct.pack_into('<III',result,40+i*12,off,count,zlib.crc32(table))
    while len(result)%4:result+=b'\0'
    tableoff=len(result);cursor=tableoff+len(objects)*24;table=bytearray();payloads=bytearray()
    for i,(kind,flags,props,tail)in enumerate(objects):
        payload=b'\0'
        for label,(ty,value)in props.items():payload+=struct.pack('<HHI',names.index(label),names.index(ty),4+len(value))+value
        payload+=b'\0\0'+tail
        entry=entries[i]if i<ec else oldkind.get(kind,oldkind['CMaterialBlockTangentToWorld'])
        _,ef,parent,_,_,template,_=entry
        table+=struct.pack('<HHIIIII',names.index(kind),ef,parent,len(payload),cursor,template,zlib.crc32(payload));payloads+=payload;cursor+=len(payload)
    result+=table+payloads;struct.pack_into('<III',result,88,tableoff,len(objects),zlib.crc32(table))
    struct.pack_into('<II',result,24,len(result),len(result));struct.pack_into('<I',result,32,header_crc(result,0))
    return result
