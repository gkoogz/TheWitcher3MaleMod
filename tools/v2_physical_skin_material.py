"""Alias-free physical skin graph authoring. No WCC, staging or native launch.

The old atlas mask cannot represent a physical field because distinct native
vertices have identical UV0 and different intended weights. This variant reads
a separately verified physical field, keeps source UV0, and samples stock UV1.
Normal transport is an explicit builder contract, never an assumed angle law.
"""
import copy
import hashlib
import json
import re
from pathlib import Path
import struct

from v2_seam_detail_material import Graph, GRAPH, STOCK_AMBIENT, STOCK_DETAIL, native_name_hash
from v2_fabric_material import encoded_string

STOCK_DIFFUSE = 'characters\\models\\geralt\\body\\model\\body_01_mg__geralt_d01.xbm'
STOCK_NORMAL = 'characters\\models\\geralt\\body\\model\\body_01_mg__geralt_n01.xbm'
MARKER = 'PhysicalStockDiffuse'
SCHEMA = 'malemod.physical-skin-graph/1'
SOURCE_ROUGHNESS = (2 / 17) ** .25
DECODE = ('float3 e=saturate(albedo.xyz); '
          'float3 s=lerp(e/12.92,pow((e+0.055)/1.055,2.4),step(0.04045,e)); ')

# Native stock diffuse/specular use pow(2.2), while the source assets inherit
# UE3 SRGB=true. Encode the mixed linear diffuse for the unchanged native
# pow(2.2) input node. Both endpoint conventions are explicit.
DIFFUSE_CODE = ('float4 physicalSkinDiffuse(float offset,float4 albedo,float4 blendColor)\n'
                '{ float3 s=pow(saturate(albedo.xyz),2.2); float3 t=pow(saturate(blendColor.xyz),2.2); '
                'return float4(pow(max(lerp(s,t,saturate(offset)),0),1.0/2.2),'
                'lerp(albedo.w,blendColor.w,saturate(offset))); }')
SPECULAR_CODE = ('float4 physicalSkinSpecular(float offset,float4 albedo,float4 blendColor)\n'
                 '{ ' + DECODE + 'float3 source=s*float3(1.0,1.5,2.0); '
                 'float3 stock=pow(float3(239.0,241.0,255.0)/255.0,2.2)*0.25*blendColor.b; '
                 'return float4(lerp(source,stock,saturate(offset)),albedo.w); }')
AMBIENT_CODE = ('float4 physicalSkinAmbient(float offset,float4 albedo,float4 blendColor)\n'
                '{ float w=saturate(offset); return float4(w*albedo.b,'
                'lerp(' + format(SOURCE_ROUGHNESS, '.17g') + ',albedo.g,w),w,1); }')
LEGACY_COLOR_CODE = ('float4 physicalSkinLegacyColor(float offset,float4 albedo,float4 blendColor)\n'
                     '{ return float4(1,albedo.g,albedo.b,1); }')
ONE_CODE = ('float physicalSkinLegacyOne(float offset,float4 albedo,float4 blendColor)\n'
            '{ return 1; }')
WEIGHT_CODE = ('float physicalSkinDecodeWeight(float offset,float4 albedo,float4 blendColor)\n'
               '{ return saturate(albedo.r); }')
# Exact native/source function exports from the closed UV1-03 source graph
# SHA2fe888c754103954db7fe1cf7863d5c8c18bb38a54eb9227c7764aa46a8b4c7a.
# Official resave preserves these source bytes; changing graph wiring is not
# permission to replace native RNM, detail, roughness, distance or SSS laws.
NATIVE_FUNCTIONS = {
 'customColoring':'297650a3a5a5dfc70d394c8289364ad964d373a7661c40d09f54d926cfe7c5eb',
 'roughDiffBlend':'1bfe31acd51822f0f3fac9e9257103acd5625b30a8723eb8b5452bfb31bccab8',
 'roughBlend':'573be72866f55fbbcfb53a97f975600d8d05269a1ddf1a9a299b9e45a944b223',
 'sourceSeamAntiLight':'38e60b7cd6c760e95af57d18f6e7f20d9dcfa1fc1aeda17357d7388de0589478',
 'skinSpecMod':'2e9f11fbf80ce5590daea870b0676970851c6f1f73b97b2ad1f654387d4b5401',
 'unpackNormal':'283878d79e6e8f881eb38ed95959e307031f6db391fc5eeca2e1324e92c17bf1',
 'normBlend':'1211eae3263aa97f3344999c2d0a34d9a065f14b3dd6dc3c50ad28fe2ac68473',
 'unpackNormal_':'91a9dfd2ff79d1bb7617308cea383acf9dae45088941b2d3e5b8816d22262d35',
 'simpleDistanceBlend':'7b881645f74564e275a2d6d1486ff5f788b0e3e746552fa87d040bb5fca765f2',
 'detailRoughnessBlend':'a25622da4f1783229c0670f2d38a8a9fb5a41a431c8e9304141f3007283fb5e8',
 'sourceSubsurface':'9c4fcb06291273bfa8fef8b4d6cb313a90df7ddebdb4afb2d1c65df770fa88ec',
 'MergeData0':'76205aae80517ebee8e1af28aa17007b02f47b515b02f97376979e704433d30a',
 'skinWrap':'88e76fdfd7215e8dedfa4dfcb04faecb22684884f0717fa6c06dfe0842bb0f18'}


class PhysicalGraph(Graph):
    def add_name(self, name):
        if name not in self.names:
            self.names.append(name)
        return struct.pack('<H', self.names.index(name))

    def custom(self, code, inputs):
        """Clone observed generic native sockets; every HLSL argument is bound."""
        template = next(i for i, o in enumerate(self.objects)
                        if o[0] == 'CMaterialBlockCustomFunction'
                        and any(s in o[2].get('customCode', ('', b''))[1]
                                for s in [b'sourceSpecular(',b'physicalSkinSpecular(']))
        node = self.clone(template)
        old = self.ids(node)
        out = self.socket(node, 'Out')
        input_template = next(s for s in old if self.name(s) != 'Out')
        sockets = [out]
        for name, upstream in inputs.items():
            socket = len(self.objects)
            obj = copy.deepcopy(self.objects[input_template])
            obj[2].pop('connections', None)
            obj[2]['block'] = ('ptr:CGraphBlock', struct.pack('<i', node + 1))
            obj[2]['name'] = ('CName', self.add_name(name))
            self.objects.append(obj)
            sockets.append(socket)
            self.rewire(socket, upstream)
        self.array(node, 'sockets', sockets)
        self.objects[node][2]['customCode'] = ('String', encoded_string(code))
        self.new_blocks.append(node)
        return node, out

    def destinations(self, output):
        return [self.ptr(e, 'destination') for e in self.ids(output, 'connections')]

    def replace_output(self, old, new, destinations=None):
        for socket in self.destinations(old) if destinations is None else destinations:
            self.rewire(socket, new)

    def clone_texture(self, label, path, uv):
        old = self.parameter('Normal')
        parameter = self.clone(old)
        self.objects[parameter][2]['parameterName'] = ('CName', self.add_name(label))
        self.texture(parameter, path)
        sampler = self.clone(self.sampler(old))
        self.rewire(self.socket(sampler, 'Texture'), self.socket(parameter, 'Texture'))
        self.rewire(self.socket(sampler, 'UV'), uv)
        self.new_blocks.extend([parameter, sampler])
        self.new_parameters.append(parameter)
        return parameter, sampler

    def dependencies(self, node, seen=None):
        seen = set() if seen is None else seen
        if node in seen:
            return set()
        seen.add(node)
        result = {node}
        for socket in self.ids(node):
            if self.objects[socket][0].startswith('CMaterialInput') and self.ids(socket, 'connections'):
                result |= self.dependencies(self.ptr(self.upstream(socket), 'block'), seen)
        return result

    def raw_native_basis(self, weight):
        """Linear TangentToWorld at unit axes exposes actual VS interpolants."""
        basis={}
        template=next(i for i,o in enumerate(self.objects)if o[0]=='CMaterialBlockTangentToWorld')
        for label,vector in [('nativeT','1,0,0,0'),('nativeB','0,1,0,0'),('nativeN','0,0,1,0')]:
            code=f'float4 physicalSkinAxis{label}(float offset,float4 albedo,float4 blendColor){{return float4({vector});}}'
            raw=next(i for i,o in enumerate(self.objects)if o[0]=='CMaterialBlockVertexColor')
            color=self.socket(raw,'Color')
            _,constant=self.custom(code,dict(offset=weight,albedo=color,blendColor=color))
            node=self.clone(template)
            self.rewire(self.socket(node,'Normal'),constant)
            self.new_blocks.append(node)
            basis[label]=self.socket(node,'Out')
        return basis

    def world_position(self, donor):
        """Observe the real donor class/header, create native Out socket only."""
        donor=Path(donor)
        dg=Graph(donor)
        ids=[i for i,o in enumerate(dg.objects)if o[0]=='CMaterialBlockWorldPosition']
        if len(ids)!=1 or [dg.name(s)for s in dg.ids(ids[0])]!=['Out']:
            raise ValueError('World-position donor differs from observed native built-in')
        off,count,_=struct.unpack_from('<III',dg.raw,88)
        header=struct.unpack_from('<HHIIIII',dg.raw,off+ids[0]*24)
        if header[1]!=0 or header[2]!=1 or header[5]!=0:
            raise ValueError('World-position native export ownership differs')
        from v2_fabric_material import observed_name_entries
        if observed_name_entries(donor).get('CMaterialBlockWorldPosition')!=native_name_hash('CMaterialBlockWorldPosition'):
            raise ValueError('World-position class lacks matching native name hash')
        self.add_name('CMaterialBlockWorldPosition')
        self.extra_export_headers=getattr(self,'extra_export_headers',{})
        self.extra_export_headers['CMaterialBlockWorldPosition']=header
        template=next(i for i,o in enumerate(self.objects)if o[0]=='CMaterialBlockTangentToWorld')
        old=self.objects[template]
        node=len(self.objects)
        self.objects.append(('CMaterialBlockWorldPosition',old[1],{},b''))
        out=len(self.objects)
        socket=copy.deepcopy(self.objects[self.socket(template,'Out')])
        socket[2].pop('connections',None)
        socket[2]['block']=('ptr:CGraphBlock',struct.pack('<i',node+1))
        self.objects.append(socket)
        self.array(node,'sockets',[out])
        self.new_blocks.append(node)
        return out,dict(path=str(donor),SHA256=hashlib.sha256(dg.raw).hexdigest(),export=ids[0],
                        node='CMaterialBlockWorldPosition',exportHeader=list(header))


def build(source, weight_builder, normal_builder=None):
    """Return a draft graph. Missing normal transport remains explicitly blocked.

    weight_builder(g,rawColor) must return (scalarOutput, proof). normal_builder
    receives the exact stock/source/normal graph context and returns a proof.
    These are trusted local functions, not code loaded from external metadata.
    """
    g = PhysicalGraph(source)
    g.new_blocks, g.new_parameters = [], []
    root = next(i for i, o in enumerate(g.objects) if o[0] == 'CMaterialGraph')
    original_functions = {i:o[2]['customCode'] for i,o in enumerate(g.objects) if 'customCode' in o[2]}
    ambient = g.sampler(g.parameter('Ambient'))
    old_ambient_destinations = {channel:g.destinations(g.socket(ambient,channel))
                                for channel in ['Color','Red','Green','Blue','Alpha']}
    stock_ambient = g.sampler(g.parameter('StockSeamAmbient'))
    uv1 = g.upstream(g.socket(stock_ambient, 'UV'))
    uvnode = g.ptr(uv1, 'block')
    if g.objects[uvnode][2].get('coordinatesIndex') != ('Int32',struct.pack('<i',1)):
        raise ValueError('Physical stock samplers require observed untiled UV1')
    stock_diffuse_param, stock_diffuse = g.clone_texture(MARKER, STOCK_DIFFUSE, uv1)
    _, stock_normal = g.clone_texture('PhysicalStockNormal', STOCK_NORMAL, uv1)
    raw_node = g.clone(next(i for i,o in enumerate(g.objects) if o[0]=='CMaterialBlockVertexColor'))
    g.new_blocks.append(raw_node)
    raw_color = g.socket(raw_node, 'Color')
    weight, weight_proof = weight_builder(g, raw_color)
    if not isinstance(weight_proof, dict) or not weight_proof.get('encoding'):
        raise ValueError('Physical weight encoding must be explicit')

    # Legacy vertex-color consumers keep their original G/B semantics. R/A
    # carried no authored variation before this variant and are forced to one.
    _, legacy = g.custom(LEGACY_COLOR_CODE, dict(offset=weight,albedo=raw_color,blendColor=raw_color))
    _, one = g.custom(ONE_CODE, dict(offset=weight,albedo=raw_color,blendColor=raw_color))
    legacy_routes = []
    for node,obj in enumerate(g.objects[:raw_node]):
        if obj[0] != 'CMaterialBlockVertexColor':
            continue
        for channel,new in [('Color',legacy),('Red',one),('Alpha',one)]:
            old = g.socket(node,channel)
            destinations = g.destinations(old)
            legacy_routes.extend(destinations)
            g.replace_output(old,new,destinations)
    # The native factory can read A before material graph code. Packing is
    # therefore R8 only; A255 and the original native capability stay intact.
    # Physical R8 leaves A255 unchanged. Every old vertex shader was audited:
    # none uses R for position; the original collapse capability is preserved.
    g.objects[root][2]['canUseOnCollapsableObjects'] = ('Bool',b'\1')

    stock_color = g.socket(stock_ambient,'Color')
    _, virtual = g.custom(AMBIENT_CODE, dict(offset=weight,albedo=stock_color,blendColor=stock_color))
    virtual_outputs = {'Color':virtual}
    for channel,field in [('Red','r'),('Green','g'),('Blue','b'),('Alpha','a')]:
        code = (f'float physicalSkinAmbient{channel}(float offset,float4 albedo,float4 blendColor)\n'
                f'{{ return albedo.{field}; }}')
        _, virtual_outputs[channel] = g.custom(code,dict(offset=weight,albedo=virtual,blendColor=virtual))
    for channel,destinations in old_ambient_destinations.items():
        g.replace_output(g.socket(ambient,channel),virtual_outputs[channel],destinations)

    diffuse = g.sampler(g.parameter('Diffuse'))
    raw_diffuse = g.socket(diffuse,'Color')
    old_diffuse_destinations = g.destinations(raw_diffuse)
    _, blended_diffuse = g.custom(DIFFUSE_CODE,dict(offset=weight,albedo=raw_diffuse,
                                                  blendColor=g.socket(stock_diffuse,'Color')))
    # The SSS branch must decode the original source image, not the newly
    # native-encoded mixed diffuse. Its stock target already uses native SSS.
    sss = next(i for i,o in enumerate(g.objects) if b'sourceSubsurface(' in o[2].get('customCode',('',b''))[1])
    raw_sss = g.socket(sss,'albedo')
    for destination in old_diffuse_destinations:
        if destination != raw_sss:
            g.rewire(destination,blended_diffuse)
    g.rewire(g.socket(sss,'offset'),weight)
    specular = next(i for i,o in enumerate(g.objects) if b'sourceSpecular(' in o[2].get('customCode',('',b''))[1])
    g.objects[specular][2]['customCode'] = ('String',encoded_string(SPECULAR_CODE))
    g.rewire(g.socket(specular,'offset'),weight)
    g.rewire(g.socket(specular,'blendColor'),stock_color)

    ctx = dict(root=root,rawColor=raw_color,rawVertexColorNode=raw_node,weight=weight,uv1=uv1,
               sourceNormalSampler=g.sampler(g.parameter('Normal')),stockNormalSampler=stock_normal,
               detailNormalSampler=g.sampler(g.parameter('DetailNormal')),virtualAmbient=virtual_outputs,
               stockAmbientSampler=stock_ambient)
    normal = normal_builder(g,ctx) if normal_builder is not None else dict(complete=False,reason='Measured normal transport contract pending')
    g.array(root,'blocks',g.ids(root,'blocks')+g.new_blocks)
    g.array(root,'pixelParameterBlocks',g.ids(root,'pixelParameterBlocks')+g.new_parameters)
    # Preserve every original native RNM/detail/distance/roughness law. Only
    # the explicitly source-specific specular function changes arithmetic.
    for i,code in original_functions.items():
        if i != specular and g.objects[i][2].get('customCode') != code:
            raise ValueError('Original native/source material arithmetic changed')
    outputs = [i for i,o in enumerate(g.objects) if o[0]=='CMaterialBlockOutputColorSkin']
    active = g.dependencies(outputs[0])
    if ambient in active or g.parameter('Ambient') in active:
        raise ValueError('A UV0-baked Ambient branch remains active')
    if stock_diffuse not in active or specular not in active or sss not in active:
        raise ValueError('Physical material lost a required color branch')
    return g,dict(schema=SCHEMA,sourceSHA256=hashlib.sha256(Path(source).read_bytes()).hexdigest(),
                  physicalWeight=weight_proof,normalTransport=normal,normalComplete=normal.get('complete') is True,
                  bakedAmbientActive=False,legacyR_AForcedOne=True,legacyRoutes=len(legacy_routes),
                  nativeObjectCollapse=True,physicalAlphaPreserved=True,originalNativeFunctionsPreserved=True,geometryChanged=False,
                  nativeCompiled=False,cooked=False,staged=False,nativeGameplayObserved=False)


def r8_weight(g,raw_color):
    _,out=g.custom(WEIGHT_CODE,dict(offset=g.socket(g.parameter('VarianceOffset'),'Value'),
                                  albedo=raw_color,blendColor=raw_color))
    return out,dict(encoding='COLOR0.R UNORM8 physical seam weight',alpha=255,
                    greenBlueUnchanged=True,weld=255,outsideSupport=0)


def normal_transport(donor):
    """Bind the separately verified mathematical helper before native RNM."""
    def attach(g,ctx):
        from v2_physical_skin_normal import NORMAL_CODE
        raw=g.socket(ctx['sourceNormalSampler'],'Color')
        destinations=g.destinations(raw)
        if len(destinations)!=1:
            raise ValueError('Original source normal has unexpected consumers')
        unpack=g.ptr(destinations[0],'block')
        if g.objects[unpack][0]!='CMaterialBlockCustomFunction' or b'unpackNormal'not in g.objects[unpack][2].get('customCode',('',b''))[1]:
            raise ValueError('Normal transport is not immediately before native unpack/RNM')
        basis=g.raw_native_basis(ctx['weight'])
        position,provenance=g.world_position(donor)
        node,out=g.custom(NORMAL_CODE,dict(sourceEncoded=raw,
            stockEncoded=g.socket(ctx['stockNormalSampler'],'Color'),weight=ctx['weight'],
            position=position,UV=ctx['uv1'],**basis))
        g.rewire(destinations[0],out)
        return dict(complete=True,helper='v2_physical_skin_normal.NORMAL_CODE',
                    codeSHA256=hashlib.sha256(NORMAL_CODE.encode()).hexdigest(),
                    beforeNativeUnpack=unpack,normalNode=node,worldPositionProvenance=provenance,
                    rawBasis='Three observed linear TangentToWorld(unitAxis) nodes; no frame normalization',
                    nativeRNMRunsOnce=True,rayTracing='Observed RT_MULTI_MATERIAL_GENERATION_TYPE or ST_RAYTRACING finite native-TS blend')
    return attach


def author(source,job,world_position_donor,original_maps):
    """Author only. Official compilation is a separate root-authorized step."""
    source,job,world_position_donor,original_maps=map(Path,(source,job,world_position_donor,original_maps))
    target=job/'build/intake'/GRAPH
    if target.exists()or(job/'graph-authored.json').exists():
        raise ValueError('Physical graph authoring must not overwrite an existing candidate')
    maps=json.loads(original_maps.read_text())
    if maps.get('schema')!='malemod.original-canonical-source-textures/1':
        raise ValueError('Expected closed original source map receipt')
    for lod in maps['lods']:
        if len(lod['files'])!=4:raise ValueError('Physical graph requires four original maps per LOD')
        for row in lod['files']:
            if hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()!=row['sha256']:
                raise ValueError('Original source map changed')
    g,proof=build(source,r8_weight,normal_transport(world_position_donor))
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(g.rebuild())
    proof.update(graph=str(target),inspection=inspect(target),
                 originalSourceMaps=dict(path=str(original_maps),SHA256=hashlib.sha256(original_maps.read_bytes()).hexdigest()),
                 nativeShaderPayloadUnchanged=True,officialResaveRequired=True)
    (job/'graph-authored.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof


def validate_custom_functions(*, body_matched=False, body_color_matched=False, raphe_diffuse=False):
    """Bounded actual compiler syntax check; no device or native game process."""
    import ctypes
    from v2_physical_skin_normal import NORMAL_CODE
    specular,ambient,diffuse=SPECULAR_CODE,AMBIENT_CODE,DIFFUSE_CODE
    if body_matched:
        from v2_skin_reflectance import SPECULAR_CODE as specular,AMBIENT_CODE as ambient
    extra=''
    if body_color_matched:
        if not body_matched:raise ValueError('Body-color adaptation requires body-matched reflectance')
        from v2_skin_color_match import DIFFUSE_CODE as diffuse,SSS_CODE
        extra=SSS_CODE
    if raphe_diffuse:
        if not body_color_matched:raise ValueError('Raphe diffuse repair requires complete body color')
        from v2_raphe_diffuse import CODES
        extra+='\n'+'\n'.join(CODES.values())
    source='\n'.join([diffuse,specular,ambient,LEGACY_COLOR_CODE,ONE_CODE,WEIGHT_CODE,NORMAL_CODE,extra])
    source+='\nfloat4 main(float4 p:SV_Position):SV_Target { float w=physicalSkinDecodeWeight(p.x,p,p); return physicalSkinDiffuse(w,p,p)+physicalSkinSpecular(w,p,p)+physicalSkinAmbient(w,p,p)+physicalSkinLegacyColor(w,p,p)+physicalSkinNormalTransport(p,p,w,p.xyz,p.xy,float3(1,0,0),float3(0,1,0),float3(0,0,1)); }'
    data=source.encode()
    compile_=ctypes.WinDLL('d3dcompiler_47.dll').D3DCompile
    compile_.restype=ctypes.c_long
    compile_.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_char_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_char_p,ctypes.c_char_p,ctypes.c_uint,ctypes.c_uint,ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(ctypes.c_void_p)]
    code,error=ctypes.c_void_p(),ctypes.c_void_p()
    result=compile_(data,len(data),b'physical-skin-graph-functions',None,None,b'main',b'ps_5_0',0,0,ctypes.byref(code),ctypes.byref(error))
    def method(blob,index,ret,*args):
        table=ctypes.cast(blob,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        return ctypes.WINFUNCTYPE(ret,ctypes.c_void_p,*args)(table[index])
    message=''
    if error:
        message=ctypes.string_at(method(error,3,ctypes.c_void_p)(error),method(error,4,ctypes.c_size_t)(error)).decode(errors='replace')
    for blob in [code,error]:
        if blob:method(blob,2,ctypes.c_ulong)(blob)
    if result<0:raise ValueError('Physical skin HLSL syntax failed: '+message)
    return dict(compiler='D3DCompile ps_5_0',sourceSHA256=hashlib.sha256(data).hexdigest(),passed=True,deviceCreated=False)


def resave(job):
    """Official graph compilation. Caller must hold the root WCC grant."""
    import shutil
    import mod
    from build_v2_anatomy_material import complete_depot
    job=Path(job).absolute()
    if not job.resolve().is_relative_to((mod.ROOT/'v2/build/materials').resolve()):
        raise ValueError('Physical resave must remain in the owned material workspace')
    graph=job/'build/intake'/GRAPH
    authored=json.loads((job/'graph-authored.json').read_text())
    if hashlib.sha256(graph.read_bytes()).hexdigest()!=authored['inspection']['SHA256']or(job/'graph-compiled.json').exists():
        raise ValueError('Physical graph changed or already compiled')
    before=PhysicalGraph(graph);inspection=inspect(graph)
    syntax=validate_custom_functions(body_matched=inspection.get('bodyMatchedReflectance',False),
                                     body_color_matched=inspection.get('bodyMatchedColor',False),
                                     raphe_diffuse=inspection.get('rapheDiffuseRepair',False))
    if inspection.get('rapheDiffuseRepair'):
        from v2_raphe_diffuse import validate_custom_functions as validate_raphe
        syntax['rapheSampling']=validate_raphe()
    shutil.copy2(graph,job/'authored-skin.w2mg')
    cfg=mod.settings();cfg['depot']=complete_depot(cfg)
    isolated=mod.ROOT/'v2/build/materials/anatomy-01/build/shaders-05/runtime/bin/x64_RedKit/wcc_lite.exe'
    if hashlib.sha256(isolated.read_bytes()).digest()!=hashlib.sha256(Path(cfg['wcc']).read_bytes()).digest():
        raise ValueError('Physical WCC differs from the verified SDK executable')
    cfg['wcc']=isolated
    scratch=job/'build/resave-temp';scratch.mkdir(parents=True)
    prior=mod.ROOT;mod.ROOT=job
    try:
        command=mod.run_wcc(cfg,'resave',['-tmpdir='+str(scratch),'-path='+str(Path(GRAPH).parent),
                            '-ext=w2mg','-nosourcecontrol','-ignorefileversion'],job/'build/intake','physical-skin-graph')
    finally:mod.ROOT=prior
    args=command['args'];compiled=Path(args[args.index('-uncookDir')+1])/GRAPH
    inspection=inspect(compiled);after=PhysicalGraph(compiled)
    old=next(o[3]for o in before.objects if o[0]=='CMaterialGraph')
    new=next(o[3]for o in after.objects if o[0]=='CMaterialGraph')
    if old==new:raise ValueError('Official physical graph payload did not change')
    if sorted(o[2]['customCode']for o in before.objects if'customCode'in o[2])!=sorted(o[2]['customCode']for o in after.objects if'customCode'in o[2]):
        raise ValueError('Official graph resave changed function sources')
    shutil.copy2(compiled,graph)
    proof=dict(nativeCompiled=True,SHA256=hashlib.sha256(graph.read_bytes()).hexdigest(),path=str(graph),command=command,
               authoredSHA256=authored['inspection']['SHA256'],inspection=inspection,customFunctionSyntax=syntax,
               compiledPayloadChanged=True,sourceFunctionsByteIdentical=True,geometryChanged=False,staged=False)
    (job/'graph-compiled.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof


def inspect(path, require_complete=True):
    """Strict physical variant dispatch. A marker alone never grants adoption."""
    g=PhysicalGraph(path)
    root=next(i for i,o in enumerate(g.objects) if o[0]=='CMaterialGraph')
    output=next(i for i,o in enumerate(g.objects) if o[0]=='CMaterialBlockOutputColorSkin')
    active=g.dependencies(output)
    from v2_skin_color_match import DIFFUSE_CODE as body_diffuse,SSS_CODE as body_sss,LINEAR_GAINS
    body_color=any(o[2].get('customCode')==('String',encoded_string(body_diffuse))for o in g.objects)
    from v2_raphe_diffuse import inspect_graph as inspect_raphe
    raphe=inspect_raphe(g)
    if raphe['rapheDiffuseRepair'] and not body_color:
        raise ValueError('Raphe diffuse repair requires complete body-color adaptation')
    functions={}
    for obj in g.objects:
        if 'customCode'not in obj[2]:continue
        raw=obj[2]['customCode'][1]
        match=re.search(rb'float[234]?\s+(\w+)\s*\(',raw)
        if match:
            label=match[1].decode()
            if label in functions:raise ValueError('Duplicate native material function: '+label)
            functions[label]=hashlib.sha256(raw).hexdigest()
    expected_functions=dict(NATIVE_FUNCTIONS)
    if body_color:
        expected_functions['sourceSubsurface']=hashlib.sha256(encoded_string(body_sss)).hexdigest()
    if any(functions.get(label)!=expected for label,expected in expected_functions.items()):
        raise ValueError('Original native material function source changed')
    if g.objects[root][2].get('canUseOnCollapsableObjects')!=('Bool',b'\1'):
        raise ValueError('Physical R8 variant changed native collapse capability')
    for label,texture in [(MARKER,STOCK_DIFFUSE),('PhysicalStockNormal',STOCK_NORMAL),('StockSeamAmbient',STOCK_AMBIENT)]:
        parameter=g.parameter(label);sampler=g.sampler(parameter)
        if g.texture_path(parameter)!=texture:raise ValueError('Wrong physical stock dependency: '+label)
        uv=g.ptr(g.upstream(g.socket(sampler,'UV')),'block')
        if g.objects[uv][0]!='CMaterialBlockTexCoords' or g.objects[uv][2].get('coordinatesIndex')!=('Int32',struct.pack('<i',1)):
            raise ValueError('Physical stock dependency does not use untiled UV1')
    if g.parameter('Ambient')in active or g.sampler(g.parameter('Ambient'))in active:
        raise ValueError('Old UV0-baked Ambient still reaches native output')
    # Historical source-Phong candidates remain strictly inspectable. The
    # body-matched adaptation is a separately recognized pair of exact sources;
    # mixed/partially edited channel variants cannot be adopted.
    from v2_skin_reflectance import SPECULAR_CODE as body_specular,AMBIENT_CODE as body_ambient
    body_matched=any(o[2].get('customCode')==('String',encoded_string(body_specular))for o in g.objects)
    if body_color and not body_matched:
        raise ValueError('Body-color adaptation requires complete body-matched reflectance')
    signatures=[('physicalSkinDiffuse(',body_diffuse if body_color else DIFFUSE_CODE),
                ('physicalSkinSpecular(',body_specular if body_matched else SPECULAR_CODE),
                ('physicalSkinAmbient(',body_ambient if body_matched else AMBIENT_CODE)]
    nodes={}
    for signature,code in signatures:
        found=[i for i in active if signature.encode()in g.objects[i][2].get('customCode',('',b''))[1]]
        if len(found)!=1 or g.objects[found[0]][2]['customCode']!=('String',encoded_string(code)):
            raise ValueError('Missing or altered physical material function: '+signature)
        nodes[signature]=found[0]
    legacy=[i for i,o in enumerate(g.objects) if b'physicalSkinLegacyColor('in o[2].get('customCode',('',b''))[1]]
    if len(legacy)!=1 or g.objects[legacy[0]][2]['customCode']!=('String',encoded_string(LEGACY_COLOR_CODE)):
        raise ValueError('Legacy color R/A values are not protected')
    diffuse=raphe['originalSampler'] if raphe['rapheDiffuseRepair'] else g.sampler(g.parameter('Diffuse'))
    # Unconnected native sampler UV is the observed UV0 default.
    if g.ids(g.socket(diffuse,'UV'),'connections'):
        uv0=g.ptr(g.upstream(g.socket(diffuse,'UV')),'block')
        if g.objects[uv0][0]!='CMaterialBlockTexCoords' or g.objects[uv0][2].get('coordinatesIndex',('Int32',bytes(4)))!=('Int32',bytes(4)):
            raise ValueError('Original source diffuse coordinates are no longer UV0')
    expected_diffuse=raphe['repairOutput'] if raphe['rapheDiffuseRepair'] else g.socket(diffuse,'Color')
    if g.upstream(g.socket(nodes['physicalSkinDiffuse('],'albedo'))!=expected_diffuse:
        raise ValueError('Physical source diffuse lost its verified UV0 route')
    stock=g.sampler(g.parameter(MARKER))
    if g.upstream(g.socket(nodes['physicalSkinDiffuse('],'blendColor'))!=g.socket(stock,'Color'):
        raise ValueError('Physical source diffuse lacks stock UV1 target')
    weight=g.upstream(g.socket(nodes['physicalSkinDiffuse('],'offset'))
    if any(g.upstream(g.socket(nodes[label],'offset'))!=weight
           for label in ['physicalSkinSpecular(','physicalSkinAmbient(']):
        raise ValueError('Physical channels use inconsistent geometric weights')
    sss=[i for i in active if b'sourceSubsurface('in g.objects[i][2].get('customCode',('',b''))[1]]
    if len(sss)!=1 or g.upstream(g.socket(sss[0],'offset'))!=weight or g.upstream(g.socket(sss[0],'albedo'))!=g.socket(diffuse,'Color'):
        raise ValueError('Physical SSS lost original source decode or geometric weight')
    if body_color:
        # Native stock SSS is the detail-bleed color multiplied by itself;
        # preserve that actual branch, including alpha. It is independent of
        # diffuse. Do not replace it with a guessed albedo-dependent law.
        blend=g.ptr(g.upstream(g.socket(sss[0],'blendColor')),'block')
        if g.objects[blend][0]!='CMaterialBlockMathMultiply':
            raise ValueError('Body-color SSS lost native detail-bleed multiply')
        expected=g.socket(g.parameter('SSS_DetailColorBleed'),'Color')
        if any(g.upstream(g.socket(blend,c))!=expected for c in ['A','B']):
            raise ValueError('Body-color SSS no longer follows actual native detail-bleed color')
    diffuse_destination=raphe['repairOriginalInput'] if raphe['rapheDiffuseRepair'] else g.socket(nodes['physicalSkinDiffuse('],'albedo')
    if set(g.destinations(g.socket(diffuse,'Color')))!={g.socket(sss[0],'albedo'),diffuse_destination}:
        raise ValueError('An original diffuse channel bypasses the physical blend')
    if g.objects[g.parameter('DetailPower')][2].get('scalar')!=('Float',struct.pack('<f',.5)):
        raise ValueError('Physical skin lost native stock detail strength')
    detail=g.sampler(g.parameter('DetailNormal'))
    if g.texture_path(g.parameter('DetailNormal'))!=STOCK_DETAIL:
        raise ValueError('Physical skin lost authentic stock detail texture')
    tile=g.ptr(g.upstream(g.socket(detail,'UV')),'block')
    if g.objects[tile][0]!='CMaterialBlockMathMultiply':
        raise ValueError('Physical detail UV no longer uses native tile multiply')
    uv=g.ptr(g.upstream(g.socket(tile,'A')),'block')
    if g.objects[uv][0]!='CMaterialBlockTexCoords' or g.objects[uv][2].get('coordinatesIndex')!=('Int32',struct.pack('<i',1)):
        raise ValueError('Physical detail no longer samples target UV1')
    values,_=g.reader.object(g.objects[g.parameter('DetailTile')][2]['vector'][1])
    if any(values[key]!=('Float',struct.pack('<f',25))for key in ['X','Y']):
        raise ValueError('Physical detail tiling differs from native stock')
    old=g.sampler(g.parameter('Ambient'))
    if any(g.destinations(g.socket(old,c)) for c in ['Color','Red','Green','Blue','Alpha']):
        raise ValueError('Baked Ambient sampler still has channel consumers')
    normal=[i for i in active if b'physicalSkinNormalTransport('in g.objects[i][2].get('customCode',('',b''))[1]]
    if require_complete and len(normal)!=1:
        raise ValueError('Physical material normal transport remains incomplete')
    if normal:
        from v2_physical_skin_normal import NORMAL_CODE
        node=normal[0]
        if len(normal)!=1 or g.objects[node][2]['customCode']!=('String',encoded_string(NORMAL_CODE)):
            raise ValueError('Physical normal transport differs from the proved helper')
        for argument,label in [('sourceEncoded','Normal'),('stockEncoded','PhysicalStockNormal')]:
            if g.upstream(g.socket(node,argument))!=g.socket(g.sampler(g.parameter(label)),'Color'):
                raise ValueError('Physical normal uses a different encoded source: '+argument)
        if g.upstream(g.socket(node,'weight'))!=weight:
            raise ValueError('Physical normal weight differs from other material channels')
        if g.upstream(g.socket(node,'UV'))!=g.upstream(g.socket(stock,'UV')):
            raise ValueError('Normal cotangents are not derived from the stock UV1 chart')
        if g.objects[g.ptr(g.upstream(g.socket(node,'position')),'block')][0]!='CMaterialBlockWorldPosition':
            raise ValueError('Normal cotangents lack observed native world position')
        for argument,vector in [('nativeT','1,0,0,0'),('nativeB','0,1,0,0'),('nativeN','0,0,1,0')]:
            basis=g.ptr(g.upstream(g.socket(node,argument)),'block')
            if g.objects[basis][0]!='CMaterialBlockTangentToWorld':
                raise ValueError('Normal basis is not a raw native linear basis')
            constant=g.ptr(g.upstream(g.socket(basis,'Normal')),'block')
            code=f'float4 physicalSkinAxis{argument}(float offset,float4 albedo,float4 blendColor){{return float4({vector});}}'
            if g.objects[constant][2].get('customCode')!=('String',encoded_string(code)):
                raise ValueError('Physical normal raw basis axis differs')
        destinations=g.destinations(g.socket(node,'Out'))
        if len(destinations)!=1 or b'unpackNormal'not in g.objects[g.ptr(destinations[0],'block')][2].get('customCode',('',b''))[1]:
            raise ValueError('Physical normal bypassed the single native unpack/RNM path')
    weight_node=g.ptr(weight,'block')
    if g.objects[weight_node][2].get('customCode')!=('String',encoded_string(WEIGHT_CODE)):
        if require_complete:raise ValueError('Physical weight is not the approved R8-only decoder')
    else:
        raw=g.ptr(g.upstream(g.socket(weight_node,'albedo')),'block')
        if g.objects[raw][0]!='CMaterialBlockVertexColor':
            raise ValueError('Physical weight does not read actual native vertex color')
    params={g.name(i,'parameterName'):g.objects[i][0]for i in g.ids(root,'pixelParameterBlocks')if'parameterName'in g.objects[i][2]}
    return dict(schema=SCHEMA,SHA256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                physicalVariant=True,normalComplete=len(normal)==1,bakedAmbientActive=False,
                sourceUV0Preserved=True,targetUVIndex=1,nativeObjectCollapse=True,physicalAlphaPreserved=True,
                diffuseSourceDecode='Preserved native pow2.2',diffuseStockDecode='Native pow2.2',
                specularStrength=None if body_matched else [1,1.5,2],sourceRoughness=None if body_matched else SOURCE_ROUGHNESS,
                bodyMatchedReflectance=body_matched,
                bodyMatchedColor=body_color,rapheDiffuseRepair=raphe['rapheDiffuseRepair'],
                rapheDiffuseScope=({key:raphe[key]for key in ['mask','originalTextureParameter','donorInsetPixels','originalAlphaPreserved','otherMaterialChannelsChanged']}if raphe['rapheDiffuseRepair']else None),
                diffuseLinearGains=list(LINEAR_GAINS)if body_color else[1,1,1],
                subsurfaceMode='native-stock-detail-bleed-color'if body_color else'legacy-source-color-interior',
                reflectanceMode='native-stock-F0-roughness-second-lobe-with-normalized-source-detail'if body_matched else'legacy-source-Phong-amplitude',
                runtimeParameters=params,physicalWeightEncoding='COLOR0.R UNORM8; A255 preserved',
                stockSeamDetail=dict(uvIndex=1,detailPower=.5,detailTile=[25,25],detailMaskInputs=3,
                                     detailMask='StockSeamAmbient.R(UV1)*physicalWeight'),
                detailMode='physical-stock-uv1',flatDetailNormal=False,
                sourceSpecularSRGBDecoded=True,sourceSubsurfaceSRGBDecoded=not body_color,
                subsurfaceInputDecode='native stock Color times Color'if body_color else'IEC sRGB source diffuse',
                nativeGameplayObserved=False)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    for option in ['source','job','world-position-donor','original-maps']:
        p.add_argument('--'+option,type=Path,required=option=='job')
    p.add_argument('--resave',action='store_true')
    args=p.parse_args()
    if not args.resave and any(x is None for x in [args.source,args.world_position_donor,args.original_maps]):
        p.error('Authoring requires source, world-position donor and original-map receipt')
    print(json.dumps(resave(args.job)if args.resave else author(args.source,args.job,args.world_position_donor,args.original_maps),indent=2))
