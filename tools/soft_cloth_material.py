"""Author and inspect the supported forward-lit, 95% covering cloth graph.

The input is an owned copy of REDkit transparent_lit, upgraded by official
resave to CR2W 164. No stock depot files or compiled shader bytes are patched.
An official resave is required after this structural edit.
"""
from pathlib import Path
import copy, hashlib, struct, zlib
from prepare_garment_carrier import native_objects
from player_rig_redirect import header_crc

GRAPH='characters/malemod/garments/cloth_soft.w2mg'

def _graph(path):
    reader, imports, objects = native_objects(path)
    def name(props, key='name'):
        data=props[key][1]
        if len(data)!=2: raise ValueError('Unsupported graph name width')
        return reader.names[struct.unpack('<H',data)[0]]
    def ptr(props,key):
        data=props[key][1]
        if len(data)!=4: raise ValueError('Unsupported graph pointer width')
        i=struct.unpack('<i',data)[0]-1
        if not 0<=i<len(objects): raise ValueError('Graph pointer leaves exports')
        return i
    def array(props,key):
        data=props.get(key,('',struct.pack('<I',0)))[1]
        n=struct.unpack_from('<I',data)[0]
        if len(data)!=4+n*4: raise ValueError('Unsupported graph array width')
        result=[x[0]-1 for x in struct.iter_unpack('<i',data[4:])]
        if any(not 0<=i<len(objects) for i in result): raise ValueError('Graph array leaves exports')
        return result
    return reader, imports, objects, name, ptr, array

def inspect(path):
    r,imports,o,name,ptr,array=_graph(path)
    roots=[i for i,v in enumerate(o) if v[0]=='CMaterialGraph']
    outputs=[i for i,v in enumerate(o) if v[0]=='CMaterialBlockOutputColor']
    lights=[i for i,v in enumerate(o) if v[0]=='CMaterialBlockForwardLight']
    if len(roots)!=1 or len(outputs)!=1 or len(lights)!=1: raise ValueError('Expected one supported forward cloth graph')
    root,output,light=roots[0],outputs[0],lights[0]
    def enum(p,key): return r.names[struct.unpack('<H',p[key][1])[0]]
    if enum(o[root][2],'sortGroup')!='RSG_Transparent' or enum(o[root][2],'blendMode')!='RBM_AlphaBlend' or enum(o[output][2],'blendMode')!='RBM_AlphaBlend': raise ValueError('Cloth needs the actual alpha-blending graph path')
    def input_socket(owner,slot):
        ids=[i for i in array(o[owner][2],'sockets') if o[i][0].startswith('CMaterialInput') and name(o[i][2])==slot]
        if len(ids)!=1: raise ValueError('Missing authoritative cloth input '+slot)
        return ids[0]
    def upstream(socket):
        edges=array(o[socket][2],'connections')
        if len(edges)!=1: raise ValueError('Cloth input needs one edge')
        c=o[edges[0]][2];a,b=ptr(c,'source'),ptr(c,'destination')
        if a!=socket: raise ValueError('Cloth input edge direction differs')
        if not any(ptr(o[e][2],'source')==b and ptr(o[e][2],'destination')==a for e in array(o[b][2],'connections')): raise ValueError('Cloth edge lacks its reciprocal')
        return ptr(o[b][2],'block')
    result=dict(graph=GRAPH,sortGroup='RSG_Transparent',blendMode='RBM_AlphaBlend',nativeShaderOverride=False)
    for owner,slot,expected in [(output,'Opacity',.95),(light,'Roughness',.88),(light,'Specularity',.015)]:
        i=upstream(input_socket(owner,slot));kind,_,p,_=o[i]
        if kind!='CMaterialParameterScalar' or 'scalar' not in p: raise ValueError('Cloth optical output must have an authoritative scalar')
        value=struct.unpack('<f',p['scalar'][1])[0]
        if abs(value-expected)>1e-7: raise ValueError('Cloth optical scalar differs: '+slot)
        result[slot]=dict(exportOrdinal=i+1,value=value)
    parameters={name(v[2],'parameterName'):i for i,v in enumerate(o) if v[0].startswith('CMaterialParameter') and 'parameterName' in v[2]}
    for slot in ['Diffuse','Normal']:
        if slot not in parameters: raise ValueError('Missing supported cloth texture '+slot)
    for slot in ['TextureRefraction','ShapeRefraction','ReflectionPower']:
        if slot not in parameters or struct.unpack('<f',o[parameters[slot]][2]['scalar'][1])[0]!=0: raise ValueError('Fabric must not use a glass/reflection distortion: '+slot)
    def dependencies(block,visited=None):
        visited=set()if visited is None else visited
        if block in visited:return set()
        visited.add(block);result={block}
        for socket in array(o[block][2],'sockets'):
            if o[socket][0].startswith('CMaterialInput') and array(o[socket][2],'connections'):
                result.update(dependencies(upstream(socket),visited))
        return result
    if parameters['Normal'] not in dependencies(upstream(input_socket(light,'WorldNormal'))): raise ValueError('Forward cloth lighting lost the supported Normal sampler path')
    if parameters['Diffuse'] not in dependencies(upstream(input_socket(light,'Albedo'))): raise ValueError('Forward cloth lighting lost the supported Diffuse sampler path')
    result['normalFeedsForwardLight']=True
    result['diffuseFeedsForwardLight']=True
    compiled=array(o[root][2],'pixelParameterBlocks')
    result['compiledNormal']=parameters['Normal'] in compiled
    result['compiledDiffuse']=parameters['Diffuse'] in compiled
    if not result['compiledNormal'] or not result['compiledDiffuse']:raise ValueError('Native cloth compiler metadata lost a required texture parameter')
    result['pixelParameterCount']=len(compiled)
    result['SHA256']=hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return result

def author(source,target):
    source,target=Path(source),Path(target)
    raw=source.read_bytes();r,imports,o,name,ptr,array=_graph(source)
    objects=copy.deepcopy(o);root=next(i for i,v in enumerate(o) if v[0]=='CMaterialGraph');output=next(i for i,v in enumerate(o) if v[0]=='CMaterialBlockOutputColor');light=next(i for i,v in enumerate(o) if v[0]=='CMaterialBlockForwardLight')
    def pointers(values): return struct.pack('<I',len(values))+b''.join(struct.pack('<i',v+1)for v in values)
    def setprop(i,key,ty,value): objects[i][2][key]=(ty,value)
    def constant(value):
        template=next(v for v in o if v[0]=='CMaterialParameterScalar' and 'scalar' in v[2] and 'parameterName' not in v[2]);block=copy.deepcopy(template);block[2].pop('position',None)
        socket=copy.deepcopy(next(v for v in o if v[0]=='CMaterialOutputSocket'));socket[2].pop('position',None);socket[2].pop('connections',None)
        bi=len(objects);si=bi+1;block[2]['scalar']=('Float',struct.pack('<f',value));block[2]['sockets']=('array:2,0,ptr:CGraphSocket',pointers([si]));socket[2]['block']=('ptr:CGraphBlock',struct.pack('<i',bi+1));socket[2]['name']=('CName',struct.pack('<H',r.names.index('Value')))
        objects.extend([block,socket]);blocks=[x[0]-1 for x in struct.iter_unpack('<i',objects[root][2]['blocks'][1][4:])];setprop(root,'blocks','array:2,0,ptr:CGraphBlock',pointers(blocks+[bi]));return si
    def rewire(owner,slot,out):
        si=next(i for i in array(o[owner][2],'sockets')if name(o[i][2])==slot)
        for old in array(o[si][2],'connections'):
            cp=o[old][2];a,b=ptr(cp,'source'),ptr(cp,'destination');other=b if a==si else a
            kept=[e for e in array(objects[other][2],'connections')if not (ptr(o[e][2],'source')==other and ptr(o[e][2],'destination')==si)]
            setprop(other,'connections','array:2,0,ptr:CGraphConnection',pointers(kept))
        template=next(v for v in o if v[0]=='CGraphConnection');first=len(objects)
        for a,b in [(si,out),(out,si)]:
            c=copy.deepcopy(template);c[2].clear();c[2].update({'source':('ptr:CGraphSocket',struct.pack('<i',a+1)),'destination':('ptr:CGraphSocket',struct.pack('<i',b+1))});objects.append(c)
        setprop(si,'connections','array:2,0,ptr:CGraphConnection',pointers([first]));setprop(out,'connections','array:2,0,ptr:CGraphConnection',pointers([first+1]))
    for owner,slot,value in [(output,'Opacity',.95),(light,'Roughness',.88),(light,'Specularity',.015)]: rewire(owner,slot,constant(value))
    for i,v in enumerate(objects):
        if v[0]=='CMaterialParameterScalar' and 'parameterName'in v[2] and name(v[2],'parameterName')in ['TextureRefraction','ShapeRefraction','ReflectionPower']:setprop(i,'scalar','Float',struct.pack('<f',0))
    def encode(props,tail):
        blob=b'\0'
        for key,(ty,value)in props.items():blob+=struct.pack('<HHI',r.names.index(key),r.names.index(ty),4+len(value))+value
        return blob+b'\0\0'+tail
    if any(struct.unpack_from('<II',raw,40+12*i)!=(0,0)for i in range(5,10)):raise ValueError('Soft graph with external buffers is unsupported')
    offset,count,_=struct.unpack_from('<III',raw,88)
    entries=list(struct.iter_unpack('<HHIIIII',raw[offset:offset+count*24]));payloads=[encode(v[2],v[3])for v in objects]
    at=offset+len(objects)*24;table=bytearray();data=bytearray()
    for i,(v,payload)in enumerate(zip(objects,payloads)):
        e=entries[i]if i<count else next(e for e in entries if r.names[e[0]]==v[0]);kind,flags,parent,_,_,template,_=e
        table+=struct.pack('<HHIIIII',kind,flags,parent,len(payload),at,template,zlib.crc32(payload));data+=payload;at+=len(payload)
    rebuilt=bytearray(raw[:offset])+table+data;struct.pack_into('<III',rebuilt,88,offset,len(objects),zlib.crc32(table));struct.pack_into('<II',rebuilt,24,len(rebuilt),len(rebuilt));struct.pack_into('<I',rebuilt,32,header_crc(rebuilt,0))
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(rebuilt);proof=inspect(target);proof.update(sourceSHA256=hashlib.sha256(raw).hexdigest(),officialResaveRequired=True,stockUntouched=True);return proof

def inspect_cooked(path, source, compiler_receipt):
    """Validate stripped runtime metadata against official compiled authoring.

    Unnamed optical constants are checked in the compiled authoring graph;
    they are not presented as editable scalars in the stripped runtime graph.
    """
    import json
    source_proof=inspect(source)
    receipt=json.loads(Path(compiler_receipt).read_text())
    sr,si,so,sname,_,sarray=_graph(source)
    cr,ci,co,cname,_,carray=_graph(path)
    def root(objects):
        ids=[i for i,v in enumerate(objects) if v[0]=='CMaterialGraph']
        if len(ids)!=1:raise ValueError('Expected one native cloth runtime graph')
        return ids[0]
    sroot,croot=root(so),root(co)
    if not receipt.get('nativeCompiled') or not receipt.get('compiledPayloadChanged') or receipt.get('SHA256')!=source_proof['SHA256'] or receipt.get('compiledPayloadAfterSHA256')!=hashlib.sha256(so[sroot][3]).hexdigest() or receipt.get('command',{}).get('exitCode')!=0:
        raise ValueError('Compiled cloth authoring receipt does not bind the source')
    if co[croot][1]!=8192 or any(v[0].startswith('CMaterialBlock') for v in co):raise ValueError('Unsupported cooked cloth graph shape')
    for key,expected in [('sortGroup','RSG_Transparent'),('blendMode','RBM_AlphaBlend')]:
        if cname(co[croot][2],key)!=expected:raise ValueError('Cooked cloth lost alpha blending')
    for key in ['pixelParamBlockSize','canUseOnDestruction','canUseOnApex','canUseOnSkinnedInstancing','canUseOnMorph','canOverrideMasked','isAccumulativelyRefracted']:
        if so[sroot][2].get(key)!=co[croot][2].get(key):raise ValueError('Cooked cloth metadata differs: '+key)
    def parameters(r,imports,objects,naming,array,root_id):
        result=[]
        ids=array(objects[root_id][2],'pixelParameterBlocks')
        for i in ids:
            kind,_,p,_=objects[i];name=naming(p,'parameterName')
            if kind=='CMaterialParameterScalar':value=struct.unpack('<f',p.get('scalar',('Float',b'\0'*4))[1])[0]
            elif kind=='CMaterialParameterColor':
                color,tail=r.object(p['color'][1])
                if tail:raise ValueError('Unexpected native cloth color tail')
                value={k:dict(type=t,value=b.hex())for k,(t,b)in color.items()}
            elif kind=='CMaterialParameterTexture':
                index=struct.unpack('<i',p['texture'][1])[0]
                if index>=0 or -index>len(imports):raise ValueError('Cloth texture leaves native import table')
                value=imports[-index-1]
            else:raise ValueError('Unsupported cloth runtime parameter')
            result.append(dict(name=name,kind=kind,value=value))
        tail=objects[root_id][3];count=tail[0] if tail else 0;end=1+4*count
        if count!=9 or len(ids)!=count or len(tail)<end+5 or tail[end]!=128:raise ValueError('Unsupported compiled cloth parameter payload')
        layout=[]
        for at in range(1,end,4):
            ty,offset,n=struct.unpack_from('<BBH',tail,at)
            if n>=len(r.names):raise ValueError('Runtime parameter name leaves native table')
            layout.append(dict(type=ty,offset=offset,name=r.names[n]))
        if [v['name']for v in layout]!=[v['name']for v in result]:raise ValueError('Compiled cloth parameter order differs')
        return result,layout,struct.unpack_from('<I',tail,end+1)[0]
    sp,sl,sc=parameters(sr,si,so,sname,sarray,sroot)
    cp,cl,cc=parameters(cr,ci,co,cname,carray,croot)
    if sp!=cp or sl!=cl:raise ValueError('Cooking changed actual cloth runtime parameters')
    if [v['name']for v in cp].count('Normal')!=1 or [v['name']for v in cp].count('Diffuse')!=1:raise ValueError('Cooked cloth lost texture lighting parameters')
    return dict(**{k:v for k,v in source_proof.items() if k!='SHA256'},SHA256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        authoredGraphSHA256=source_proof['SHA256'],compilerReceiptSHA256=hashlib.sha256(Path(compiler_receipt).read_bytes()).hexdigest(),
        opticalConstantsEvidence='official-compiled-authoring-graph',cookedOpticalScalarsPresent=False,
        runtimeParameters=cp,runtimeParameterLayout=cl,sourceEncodedShaderCount=sc,cookedEncodedShaderCount=cc,
        editorNodesStripped=True,nativeMaterialObserved=False)
