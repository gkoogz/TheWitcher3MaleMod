"""Import/cook four owned lit garment carriers, using the measured rigid ABI."""
import argparse,copy,hashlib,json,shutil,struct,subprocess,zlib
from pathlib import Path
import numpy as np
from PIL import Image
from mod import ROOT,settings,run_wcc,write_json,digest,build,verify_package,base_checkout
from prepare_motion import scalar,reference,array,vector
from wcc_fbx import Document
from packed_mesh_format import CookedMesh
from player_rig_redirect import header_crc
from build_body_boundary import verify_texture_metadata

KINDS=('ribbed','elastic','red','blue')
DRY_GRAPH='characters/malemod/garments/cloth_dry.w2mg'
ROUGHNESS_ALPHA=224 # Supported normal/gloss storage; dry cloth uses a direct roughness constant.

def cloth_normal(kind):
    y,x=np.mgrid[:512,:512]
    amplitude=.065 if kind=='ribbed' else .018
    nx=-amplitude*np.sin(x/512*2*np.pi*128)
    ny=-.008*np.sin(y/512*2*np.pi*256)
    nz=np.sqrt(1-nx*nx-ny*ny)
    rgba=np.empty((512,512,4),dtype=np.uint8)
    rgba[...,:3]=np.uint8(np.clip(np.floor((np.stack((nx,ny,nz),axis=-1)*.5+.5)*255+.5),0,255))
    rgba[...,3]=ROUGHNESS_ALPHA
    return rgba

def native_objects(path):
    """Read only the observed native 164 tables, checking bounds and CRCs."""
    raw=Path(path).read_bytes()
    if len(raw)<160 or raw[:4]!=b'CR2W' or struct.unpack_from('<I',raw,4)[0]!=164 or header_crc(raw,0)!=struct.unpack_from('<I',raw,32)[0]:raise ValueError('Unobserved material/texture header')
    def table(index,stride):
        offset,count,crc=struct.unpack_from('<III',raw,40+index*12);size=count*stride
        if not count and not offset and not crc:return b''
        if offset<160 or size>len(raw)-offset:raise ValueError('Native table leaves resource')
        block=raw[offset:offset+size]
        if zlib.crc32(block)!=crc:raise ValueError('Native table CRC differs')
        return block
    strings=table(0,1)
    def text(offset):
        end=strings.find(b'\0',offset)
        if offset>=len(strings) or end<offset:raise ValueError('Native text leaves string table')
        return strings[offset:end].decode('utf-8')
    reader=CookedMesh.__new__(CookedMesh);reader.names=[text(offset) for offset,_ in struct.iter_unpack('<II',table(1,8))]
    imports=[text(offset) for offset,kind,flags in struct.iter_unpack('<IHH',table(2,8))]
    objects=[]
    for kind,flags,parent,size,offset,template,crc in struct.iter_unpack('<HHIIIII',table(4,24)):
        if kind>=len(reader.names) or offset<160 or size>len(raw)-offset:raise ValueError('Native export leaves resource')
        data=raw[offset:offset+size]
        if zlib.crc32(data)!=crc:raise ValueError('Native export CRC differs')
        properties,tail=reader.object(data);objects.append((reader.names[kind],flags,properties,tail))
    return reader,imports,objects

def dry_graph_constants(path):
    reader,imports,objects=native_objects(path)
    if any('Wetness' in kind for kind,_,_,_ in objects):raise ValueError('Dry cloth graph must not contain automatic wetness blocks')
    def pointer(props,name):
        value=struct.unpack('<i',props[name][1])[0]-1
        if value<0 or value>=len(objects):raise ValueError('Graph pointer leaves native exports')
        return value
    def array(props,name):
        data=props[name][1];count=struct.unpack_from('<I',data)[0]
        if len(data)!=4+4*count:raise ValueError('Native graph pointer array differs')
        result=[v[0]-1 for v in struct.iter_unpack('<i',data[4:])]
        if any(v<0 or v>=len(objects) for v in result):raise ValueError('Native graph array leaves exports')
        return result
    outputs=[o for o in objects if o[0]=='CMaterialBlockOutputColorDeferred']
    if len(outputs)!=1:raise ValueError('Dry cloth graph must have one deferred output')
    result={}
    for socket in array(outputs[0][2],'sockets'):
        props=objects[socket][2];name=reader.names[struct.unpack('<H',props['name'][1])[0]]
        if name not in ['Roughness','Specularity']:continue
        connections=array(props,'connections')
        if len(connections)!=1:raise ValueError('Dry cloth output must have one authoritative connection')
        connection=objects[connections[0]][2];a,b=pointer(connection,'source'),pointer(connection,'destination')
        if socket not in [a,b]:raise ValueError('Dry cloth connection does not reference output')
        owner=pointer(objects[b if a==socket else a][2],'block');kind,_,props,_=objects[owner]
        if kind!='CMaterialParameterScalar' or 'parameterName' in props:raise ValueError('Dry cloth output must use an unnamed scalar constant')
        result[name]=(owner,struct.unpack('<f',CookedMesh.get(props,'scalar','Float'))[0])
    if set(result)!={'Roughness','Specularity'}:raise ValueError('Missing authoritative dry cloth constants')
    return result

def connect_dry_normal(path):
    """Connect the supported tangent-to-world normal output in an owned graph."""
    path=Path(path);raw=path.read_bytes();reader,_,objects=native_objects(path)
    def pointers(props):
        data=props['sockets'][1];count=struct.unpack_from('<I',data)[0]
        if len(data)!=4+count*4:raise ValueError('Unobserved graph socket array')
        return [x[0]-1 for x in struct.iter_unpack('<i',data[4:])]
    output=[o for o in objects if o[0]=='CMaterialBlockOutputColorDeferred']
    tangent=[o for o in objects if o[0]=='CMaterialBlockTangentToWorld']
    if len(output)!=1 or len(tangent)!=1:raise ValueError('Unobserved dry cloth normal blocks')
    normals=[i for i in pointers(output[0][2]) if reader.names[struct.unpack('<H',objects[i][2]['name'][1])[0]]=='Normal']
    tangents=[i for i in pointers(tangent[0][2]) if objects[i][0]=='CMaterialOutputSocket']
    if len(normals)!=1 or len(tangents)!=1:raise ValueError('Unobserved dry cloth normal sockets')
    input_,output_=normals[0],tangents[0]
    if objects[input_][2].get('connections',('',struct.pack('<I',0)))[1]!=struct.pack('<I',0) or 'connections' in objects[output_][2]:raise ValueError('Stock dry normal connection baseline changed')
    exports_offset,exports_count,_=struct.unpack_from('<III',raw,40+4*12)
    if any(struct.unpack_from('<II',raw,40+12*i)!=(0,0) for i in range(5,10)):raise ValueError('Graph with external native buffers is unsupported')
    exports=list(struct.iter_unpack('<HHIIIII',raw[exports_offset:exports_offset+exports_count*24]))
    if len(exports)!=len(objects):raise ValueError('Native graph export count differs')
    def encode(props,tail):
        blob=b'\0'
        for name,(kind,value) in props.items():blob+=struct.pack('<HHI',reader.names.index(name),reader.names.index(kind),4+len(value))+value
        return blob+b'\0\0'+tail
    payloads=[raw[e[4]:e[4]+e[3]] for e in exports]
    for offset,index in enumerate([input_,output_]):
        kind,flags,props,tail=objects[index];props=dict(props);props['connections']=('array:2,0,ptr:CGraphConnection',struct.pack('<Ii',1,exports_count+offset+1));payloads[index]=encode(props,tail)
    connection=next(e for e in exports if reader.names[e[0]]=='CGraphConnection')
    for source,destination in [(input_,output_),(output_,input_)]:
        props={'source':('ptr:CGraphSocket',struct.pack('<i',source+1)),'destination':('ptr:CGraphSocket',struct.pack('<i',destination+1))}
        payloads.append(encode(props,b''));exports.append((connection[0],connection[1],connection[2],0,0,connection[5],0))
    rebuilt=bytearray(raw[:exports_offset]);table_end=exports_offset+24*len(exports);at=table_end;table=bytearray();data=bytearray()
    for entry,payload in zip(exports,payloads):
        kind,flags,parent,_,_,template,_=entry;table+=struct.pack('<HHIIIII',kind,flags,parent,len(payload),at,template,zlib.crc32(payload));data+=payload;at+=len(payload)
    rebuilt+=table+data
    struct.pack_into('<III',rebuilt,40+4*12,exports_offset,len(exports),zlib.crc32(table))
    struct.pack_into('<II',rebuilt,24,len(rebuilt),len(rebuilt));struct.pack_into('<I',rebuilt,32,header_crc(rebuilt,0));path.write_bytes(rebuilt)
    native_objects(path) # All rewritten native export/table/header CRCs must pass.


def dry_graph_normal_path(path):
    """Require the actual reciprocal Normal edge and existing sampler chain."""
    reader,_,objects=native_objects(path)
    def ptr(value):
        if len(value)!=4:raise ValueError('Native graph pointer width differs')
        i=struct.unpack('<i',value)[0]-1
        if i<0 or i>=len(objects):raise ValueError('Native graph pointer leaves exports')
        return i
    def links(props,name):
        data=props.get(name,('',struct.pack('<I',0)))[1]
        count=struct.unpack_from('<I',data)[0]
        if len(data)!=4+count*4:raise ValueError('Native graph array width differs')
        return [ptr(data[i:i+4]) for i in range(4,len(data),4)]
    def name(props,key='name'):
        payload=props[key][1]
        if len(payload)!=2:raise ValueError('Native graph name width differs')
        return reader.names[struct.unpack('<H',payload)[0]]
    def upstream(socket):
        edges=links(objects[socket][2],'connections')
        if len(edges)!=1:raise ValueError('Normal chain requires one authoritative input edge')
        c=objects[edges[0]]
        if c[0]!='CGraphConnection':raise ValueError('Normal edge is not a graph connection')
        a,b=ptr(c[2]['source'][1]),ptr(c[2]['destination'][1])
        if a!=socket:raise ValueError('Normal input edge direction differs')
        reciprocal=links(objects[b][2],'connections')
        if not any(objects[e][0]=='CGraphConnection' and
                   ptr(objects[e][2]['source'][1])==b and
                   ptr(objects[e][2]['destination'][1])==a for e in reciprocal):
            raise ValueError('Normal edge lacks its reciprocal output connection')
        return ptr(objects[b][2]['block'][1])
    outputs=[i for i,o in enumerate(objects) if o[0]=='CMaterialBlockOutputColorDeferred']
    if len(outputs)!=1:raise ValueError('Expected one deferred output')
    sockets=[i for i in links(objects[outputs[0]][2],'sockets') if name(objects[i][2])=='Normal']
    if len(sockets)!=1:raise ValueError('Deferred Normal socket differs')
    chain=[];owner=upstream(sockets[0]);seen=set()
    for expected in ['CMaterialBlockTangentToWorld','CMaterialBlockCustomFunction','CMaterialBlockSamplerTexture','CMaterialParameterTexture']:
        if owner in seen or objects[owner][0]!=expected:raise ValueError('Unsupported dry cloth Normal chain')
        seen.add(owner);props=objects[owner][2];chain.append(dict(exportOrdinal=owner+1,kind=expected))
        if expected=='CMaterialParameterTexture':
            if name(props,'parameterName')!='Normal':raise ValueError('Normal chain uses the wrong texture parameter')
        else:
            inputs=[i for i in links(props,'sockets') if objects[i][0].startswith('CMaterialInput') and links(objects[i][2],'connections')]
            if len(inputs)!=1:raise ValueError('Unsupported connected Normal chain inputs')
            owner=upstream(inputs[0])
    return chain


def compiled_dry_normal(path):
    """Check native compiler metadata exposes the connected Normal parameter."""
    reader,_,objects=native_objects(path)
    roots=[o for o in objects if o[0]=='CMaterialGraph']
    if len(roots)!=1:raise ValueError('Expected one native material graph root')
    data=roots[0][2]['pixelParameterBlocks'][1];count=struct.unpack_from('<I',data)[0]
    if len(data)!=4+4*count:raise ValueError('Compiled pixel parameter array differs')
    indices=[x[0]-1 for x in struct.iter_unpack('<i',data[4:])]
    if any(i<0 or i>=len(objects) for i in indices):raise ValueError('Compiled parameter leaves native exports')
    normal=[]
    for i in indices:
        kind,_,props,_=objects[i]
        if kind=='CMaterialParameterTexture' and 'parameterName' in props:
            value=props['parameterName'][1]
            if len(value)!=2:raise ValueError('Compiled texture parameter name width differs')
            if reader.names[struct.unpack('<H',value)[0]]=='Normal':normal.append(i+1)
    if len(normal)!=1:raise ValueError('Native compiler metadata does not expose Normal')
    return dict(pixelParameterCount=count,normalExportOrdinal=normal[0])


def resave_dry_graph(cfg,workspace,job):
    """Refresh owned graph caches with the official, locally scoped resaver."""
    workspace,job=Path(workspace).absolute(),Path(job).absolute();graph=workspace/DRY_GRAPH
    if not workspace.is_relative_to(ROOT/'build') or not job.is_relative_to(ROOT/'build'):raise ValueError('Graph resave requires owned build paths')
    candidates=list(graph.parent.glob('*.w2mg'))
    if candidates!=[graph]:raise ValueError('Graph resave scope must contain only the owned cloth graph')
    before=digest(graph);before_tail=native_objects(graph)[2][0][3];temp=job/'graph-resave-tmp';temp.mkdir(exist_ok=True)
    command=run_wcc(cfg,'resave',['-tmpdir='+str(temp),'-path='+str(Path(DRY_GRAPH).parent),'-ext=w2mg','-nosourcecontrol','-ignorefileversion'],workspace,'resave-owned-cloth-material')
    args=command['args'];depot=Path(args[args.index('-uncookDir')+1]);output=depot/DRY_GRAPH
    constants=dry_graph_constants(output);normal_path=dry_graph_normal_path(output);compiled=compiled_dry_normal(output)
    if any(abs(constants[n][1]-v)>1e-7 for n,v in [('Roughness',.88),('Specularity',.015)]):raise ValueError('Official material resave changed authoritative cloth outputs')
    after_tail=native_objects(output)[2][0][3]
    shutil.copy2(output,graph)
    return dict(command=command,sourceSHA256=before,nativeSHA256=digest(graph),compiledPayloadBeforeSHA256=hashlib.sha256(before_tail).hexdigest(),compiledPayloadAfterSHA256=hashlib.sha256(after_tail).hexdigest(),constants=constants,normalPath=normal_path,compiled=compiled)


def author_dry_graph(source,target):
    """Adapt supported native graph nodes without touching the stock depot."""
    source,target=Path(source),Path(target)
    roles=dry_graph_constants(source);raw=bytearray(source.read_bytes());original=bytes(raw);allowed=set();edits=[]
    table,count,_=struct.unpack_from('<III',raw,40+4*12)
    reader,_,_=native_objects(source)
    for name,expected,value in [('Roughness',.1,.88),('Specularity',.2,.015)]:
        ordinal,old=roles[name]
        if abs(old-expected)>1e-7:raise ValueError('Stock dry graph baseline changed')
        entry=table+ordinal*24;kind,flags,parent,size,position,template,crc=struct.unpack_from('<HHIIIII',raw,entry);at=position+1
        found=False
        while at+8<=position+size:
            key,type_,length=struct.unpack_from('<HHI',raw,at)
            if not key:break
            if length<4 or at+4+length>position+size:raise ValueError('Graph scalar property leaves export')
            if reader.names[key]=='scalar':
                if reader.names[type_]!='Float' or length!=8:raise ValueError('Graph scalar encoding differs')
                struct.pack_into('<f',raw,at+8,value);allowed.update(range(at+8,at+12));found=True;break
            at+=4+length
        if not found:raise ValueError('Authoritative graph constant lacks serialized scalar')
        struct.pack_into('<I',raw,entry+20,zlib.crc32(raw[position:position+size]));allowed.update(range(entry+20,entry+24));edits.append(dict(role=name,exportOrdinal=ordinal+1,before=old,after=value))
    struct.pack_into('<I',raw,40+4*12+8,zlib.crc32(raw[table:table+count*24]));allowed.update(range(40+4*12+8,40+4*12+12))
    struct.pack_into('<I',raw,32,header_crc(raw,0));allowed.update(range(32,36))
    if any(a!=b and i not in allowed for i,(a,b) in enumerate(zip(original,raw))):raise ValueError('Graph adaptation altered unrelated bytes')
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    connect_dry_normal(target)
    actual=dry_graph_constants(target)
    if any(abs(actual[name][1]-value)>1e-7 for name,value in [('Roughness',.88),('Specularity',.015)]):raise ValueError('Dry graph adaptation failed native roundtrip')
    return dict(sourceSHA256=digest(source),nativeSHA256=digest(target),edits=edits,normalConnected=True,normalPath=dry_graph_normal_path(target),stockUntouched=True,nativeNodesPreserved=True)

def verify_material(path,kind,expected_graph=DRY_GRAPH):
    reader,imports,objects=native_objects(path)
    materials=[o for o in objects if o[0]=='CMaterialInstance']
    if len(materials)!=1:raise ValueError('Expected one owned cloth material')
    _,_,props,tail=materials[0]
    def handle(payload):
        index=-struct.unpack('<i',payload)[0]-1
        if index<0 or index>=len(imports):raise ValueError('Material handle leaves imports')
        return imports[index].replace('\\','/')
    graph=handle(CookedMesh.get(props,'baseMaterial','handle:IMaterial'))
    if graph!=expected_graph:raise ValueError('Unsupported cloth material graph')
    count=struct.unpack_from('<I',tail)[0];at=4;params={}
    for _ in range(count):
        if at+8>len(tail):raise ValueError('Truncated native material parameter')
        size,name,type_=struct.unpack_from('<IHH',tail,at)
        if size!=12 or name>=len(reader.names) or type_>=len(reader.names) or at+size>len(tail):raise ValueError('Unobserved cloth parameter encoding')
        key,typ=reader.names[name],reader.names[type_];payload=tail[at+8:at+size]
        if key in {'Diffuse','Normal'} and typ!='handle:ITexture' or key=='Opacity' and typ!='Float':raise ValueError('Cloth parameter type differs: '+key)
        if key in params:raise ValueError('Duplicate cloth parameter')
        params[key]=handle(payload) if typ=='handle:ITexture' else struct.unpack('<f',payload)[0] if typ=='Float' else None
        at+=size
    expected={'Diffuse':f'characters/malemod/garments/{kind}.xbm','Normal':f'characters/malemod/garments/{kind}-normal.xbm'}
    if expected_graph=='characters/malemod/garments/cloth_soft.w2mg':expected['Opacity']=.95
    if at!=len(tail) or set(params)!=set(expected):raise ValueError('Cloth parameters differ from authored graph contract')
    for key,value in expected.items():
        if (params[key]!=value if isinstance(value,str) else abs(params[key]-value)>1e-7):raise ValueError('Native cloth parameter differs: '+key)
    return dict(graph=graph,parameters=params,meshSHA256=digest(path))

def verify_normal_encoding(path,*,cooked):
    reader,imports,objects=native_objects(path)
    textures=[o for o in objects if o[0]=='CBitmapTexture']
    if len(textures)!=1:raise ValueError('Expected one owned normal texture')
    _,flags,props,tail=textures[0]
    for key,typ,value in [('compression','ETextureCompression','TCM_NormalsGloss'),('textureGroup','CName','CharacterNormalmapGloss')]:
        payload=CookedMesh.get(props,key,typ)
        if len(payload)!=2 or reader.names[struct.unpack('<H',payload)[0]]!=value:raise ValueError('Native normal encoding differs')
    if bool(flags&8192)!=cooked:raise ValueError('Native texture cook flags differ')
    if len(tail)<8:raise ValueError('Truncated native texture tail')
    _,count=struct.unpack_from('<II',tail);at=8;mips=[];data=[]
    if count!=10:raise ValueError('Expected ten owned 512 normal mip levels')
    for level in range(count):
        if at+12>len(tail):raise ValueError('Truncated native mip record')
        width,height,pitch=struct.unpack_from('<III',tail,at);at+=12
        if width!=max(4,512>>level) or height!=width or pitch!=width*4:raise ValueError('Native normal mip ABI differs')
        size=max(1,(width+3)//4)**2*16;mips.append(size)
        if not cooked:
            actual=struct.unpack_from('<I',tail,at)[0];at+=4
            if actual!=size or actual>len(tail)-at:raise ValueError('Native BC3 mip size differs')
            data.append(tail[at:at+size]);at+=size
    if cooked:
        first=CookedMesh.get(props,'residentMipIndex','Uint8')[0]
        size=struct.unpack_from('<I',tail,at)[0];at+=8
        if first>=count or size!=sum(mips[first:]) or size>len(tail)-at:raise ValueError('Cooked resident BC3 size differs')
        data.append(tail[at:at+size]);at+=size
    else:
        size=struct.unpack_from('<I',tail,at)[0];at+=4
        if size:raise ValueError('Uncooked normal unexpectedly has resident payload')
    if at!=len(tail):raise ValueError('Native normal tail length differs')
    minimum=255;maximum=0;blocks=0
    for blob in data:
        for offset in range(0,len(blob),16):
            a,b=blob[offset:offset+2]
            palette=[a,b]+([( (7-i)*a+i*b)//7 for i in range(1,7)] if a>b else [((5-i)*a+i*b)//5 for i in range(1,5)]+[0,255])
            indices=int.from_bytes(blob[offset+2:offset+8],'little')
            values=[palette[(indices>>(3*i))&7] for i in range(16)]
            minimum=min(minimum,min(values));maximum=max(maximum,max(values));blocks+=1
    if minimum!=ROUGHNESS_ALPHA or maximum!=ROUGHNESS_ALPHA:raise ValueError('Native BC3 roughness alpha was not preserved')
    return dict(nativeSHA256=digest(path),cooked=cooked,decodedBC3Blocks=blocks,minimumAlpha=minimum,maximumAlpha=maximum,scope='resident mip chain' if cooked else 'all imported mip levels')

def author(job,source,*,resume=False):
    job,source=Path(job).absolute(),Path(source).absolute()
    if not job.is_relative_to(ROOT/'build') or (job.exists() and not resume) or not source.is_relative_to(ROOT/'build'):raise ValueError('Use fresh owned output, or explicitly resume its verified imports')
    job.mkdir(parents=True,exist_ok=resume);workspace=job/'intake';workspace.mkdir(exist_ok=resume);cfg=settings();cfg['depot']=cfg['redkit']/'r4data'
    def imported(options,target,label):
        if resume and target.is_file():
            for receipt in sorted((ROOT/'build/logs').glob('*.json'),reverse=True):
                r=json.loads(receipt.read_text(encoding='utf-8'))
                if r.get('command')=='import' and r.get('exitCode')==0 and all(o in r.get('args',[]) for o in options):
                    return r
            raise ValueError('Existing native output has no matching successful import receipt: '+str(target))
        return run_wcc(cfg,'import',options,workspace,label)
    converter=ROOT/'build/research/wkit-current/MaleModCR2W.exe';entity_file=source/'intake/characters/malemod/clinical/carrier.w2ent'
    raw=job/'entity-source.json'
    if not (resume and raw.is_file()):subprocess.run([str(converter),'export',str(entity_file),str(raw)],capture_output=True,check=True)
    entity=json.loads(raw.read_text())
    dry_graph=workspace/DRY_GRAPH;graph_proof=author_dry_graph(cfg['depot']/'engine/materials/graphs/pbr_std_no_wetness.w2mg',dry_graph)
    graph_proof['officialResave']=resave_dry_graph(cfg,workspace,job)
    resources=[];textures=[]
    for k,kind in enumerate(KINDS):
        y,x=np.mgrid[:512,:512];rib=.018*np.cos(x/512*2*np.pi*128)+.004*np.cos(y/512*2*np.pi*256)
        color=np.array(((.94,.94,.94),(.96,.96,.96),(.62,.035,.045),(.035,.09,.45))[k]);pixels=np.uint8(np.clip((color+rib[...,None])*255,0,255))
        image=job/(kind+'.tga');Image.fromarray(pixels).save(image);target=workspace/'characters/malemod/garments'/(kind+'.xbm')
        command=imported(['-depot=local','-file='+str(image),'-out='+str(target),'-texturegroup=CharacterDiffuse'],target,'import-garment-'+kind)
        run_wcc(cfg,'dumpfile',['-file='+str(target),'-out=\\\\?\\'],workspace,'verify-garment-'+kind);dump=Path(str(target)+'.xml');meta=verify_texture_metadata(dump,'CharacterDiffuse','TCM_DXTNoAlpha')
        textures.append(dict(kind=kind,channel='diffuse',sourceSHA256=digest(image),nativeSHA256=digest(target),nativeMetadataDumpSHA256=digest(dump),command=command,**meta));dump.unlink()
        normal_image=job/(kind+'-normal.tga');Image.fromarray(cloth_normal(kind),'RGBA').save(normal_image)
        normal_target=workspace/'characters/malemod/garments'/(kind+'-normal.xbm')
        normal_command=imported(['-depot=local','-file='+str(normal_image),'-out='+str(normal_target),'-texturegroup=CharacterNormalmapGloss'],normal_target,'import-garment-normal-'+kind)
        run_wcc(cfg,'dumpfile',['-file='+str(normal_target),'-out=\\\\?\\'],workspace,'verify-garment-normal-'+kind)
        normal_dump=Path(str(normal_target)+'.xml');normal_meta=verify_texture_metadata(normal_dump,'CharacterNormalmapGloss','TCM_NormalsGloss')
        textures.append(dict(kind=kind,channel='normal-roughness',sourceSHA256=digest(normal_image),sourceRoughnessAlpha=ROUGHNESS_ALPHA/255,nativeSHA256=digest(normal_target),nativeMetadataDumpSHA256=digest(normal_dump),command=normal_command,**normal_meta));normal_dump.unlink()
        document=Document(ROOT/'build/clinical-carrier-native-2/opaque.fbx')
        rng=np.random.default_rng(74219+k)
        for m in document.meshes:
            dummy=rng.uniform(-12800,12800,(192,3));dummy[:2]=[[-12800]*3,[12800]*3];m.set_array('Vertices',dummy)
        fbx=job/(kind+'.fbx');document.save(fbx)
        fbx.with_suffix('.xml').write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<mesh><mesh_data autohideDistance="500.00" isTwoSided="true" useExtraStreams="true" mergeInGlobalShadowMesh="false" entityProxy="false"><LODs><LOD_info distance="0.00"/><LOD_info distance="250.00"/></LODs></mesh_data><materials><material name="Material0" local="true" base="characters\\malemod\\garments\\cloth_dry.w2mg"><param name="Diffuse" type="handle:ITexture" value="characters\\malemod\\garments\\{kind}.xbm"/><param name="Normal" type="handle:ITexture" value="characters\\malemod\\garments\\{kind}-normal.xbm"/></material></materials></mesh>''')
        mesh=workspace/'characters/malemod/garments'/(kind+'.w2mesh');resources.append(dict(kind=kind,command=imported(['-depot=local','-file='+str(fbx),'-out='+str(mesh)],mesh,'import-garment-mesh-'+kind)))
    def edit(r):
        chunks=r['_chunks'];prefix=r['_extension'];entity_key=next(k for k,v in chunks.items() if v['_type']=='CEntity');owner=chunks[entity_key]
        template=copy.deepcopy(next(v for v in chunks.values() if v['_type']=='CMeshComponent'))
        chunks={k:v for k,v in chunks.items() if v['_type']!='CMeshComponent'}
        keys=[]
        for kind in KINDS:
            key=prefix+'CMeshComponent #'+str(len(chunks));c=copy.deepcopy(template);c['_key']=key;c['_parentKey']=entity_key;c['_vars']['name']=scalar('String','MaleModGarment'+kind)
            c['_vars']['mesh']['_vars']['_depotPath']['_value']='characters\\malemod\\garments\\'+kind+'.w2mesh';chunks[key]=c;keys.append(key)
        owner['_vars']['Components']=array('array:0,0,ptr:CComponent',[reference('ptr:CComponent',k) for k in keys]);owner['_vars']['name']=scalar('String','MaleModGarmentCarrier');r['_chunks']=chunks
        for chunk in list(chunks.values()):
            for v in chunk['_vars'].values():
                if v.get('_type')=='CR2W':edit(v)
    edit(entity);recipe=job/'entity.json';write_json(recipe,entity);output=workspace/'characters/malemod/garments/carrier.w2ent';subprocess.run([str(converter),'import',str(recipe),str(output)],capture_output=True,check=True)
    write_json(job/'authoring.json',dict(recipeSHA256=digest(Path(__file__)),sourceCarrierSHA256=digest(entity_file),resources=resources,textures=textures,materialPresentation=dict(graph=DRY_GRAPH,roughnessSource='authoritative native output scalar',roughness=.88,specularity=.015,automaticWetness=False,graphProof=graph_proof),entitySHA256=digest(output),nativeCooked=False,observedGameplay=False))
def cook(job):
    job=Path(job).absolute();cfg=settings();cfg['depot']=cfg['redkit']/'r4data';package=build(cfg,dict(name='modMaleModGarments',version='0.5.1',platform='pc',cacheBuilders=['textures'],scope='Owned optional shared garment carriers'),job/'intake');finalize_package(job,package)

def finalize_package(job,package):
    job=Path(job).absolute();package=Path(package).absolute();m=verify_package(package)
    authoring=json.loads((job/'authoring.json').read_text());graph=authoring['materialPresentation']['graph']
    native_input=Path(next(a.removeprefix('-mod=') for r in m['nativeCommands'] if r['command']=='cook' for a in r['args'] if a.startswith('-mod=')))
    for src in (job/'intake').rglob('*'):
        if src.is_file() and src.suffix in {'.w2mg','.w2mesh','.w2ent','.xbm','.buffer'}:
            native=native_input/src.relative_to(job/'intake')
            if not native.is_file() or digest(src)!=digest(native):raise ValueError('Finalization source differs from actual native cook input: '+str(src))
    cooked=Path(next(a.removeprefix('-outdir=') for r in m['nativeCommands'] if r['command']=='cook' for a in r['args'] if a.startswith('-outdir=')))
    blob=b'MMCLT001';rows=[];material_proof=[]
    for kind in KINDS:
        path=cooked/'characters/malemod/garments'/(kind+'.w2mesh');mesh=CookedMesh(path.read_bytes(),allow_rigid=True);size=struct.unpack('<I',mesh.get(mesh.cooked,'indexBufferSize','Uint32'))[0]
        if mesh.palette or size!=384:raise ValueError('Garment rigid ABI differs')
        material_proof.append(dict(kind=kind,material=verify_material(path,kind,graph),importedNormal=verify_normal_encoding(job/'intake/characters/malemod/garments'/(kind+'-normal.xbm'),cooked=False),cookedNormal=verify_normal_encoding(cooked/'characters/malemod/garments'/(kind+'-normal.xbm'),cooked=True)))
        blob+=struct.pack('<6fI',*mesh.scale[:3],*mesh.offset[:3],size);rows.append(dict(kind=kind,meshSHA256=digest(path),bufferSHA256=digest(Path(str(path)+'.1.buffer')),scale=mesh.scale,offset=mesh.offset,indexBytes=size))
    if graph==DRY_GRAPH:
        graph_constants=dry_graph_constants(cooked/graph)
        if any(abs(graph_constants[name][1]-value)>1e-7 for name,value in [('Roughness',.88),('Specularity',.015)]):raise ValueError('Cooked dry graph constants differ')
        optical=dict(cookedGraphConstants=graph_constants,cookedNormalPath=dry_graph_normal_path(cooked/graph),compiledNormal=compiled_dry_normal(cooked/graph))
    else:
        from soft_cloth_material import GRAPH,inspect_cooked
        if graph!=GRAPH:raise ValueError('Unsupported authored garment optical contract')
        optical=inspect_cooked(cooked/graph,job/'intake'/graph,job/'graph-resave-final.json')
        if not optical['compiledNormal'] or not optical['compiledDiffuse']:raise ValueError('Cooked forward cloth lost texture parameters')
    write_json(job/'material-proof.json',dict(cookedGraphSHA256=digest(cooked/graph),opticalContract=optical,validatorRecipeSHA256=digest(Path(__file__)),resources=material_proof,normalRoundtripReference='build/probe/garment-gloss-encoding/proof.json',highMipTextureCacheDecoded=False,observedGameplay=False))
    packet=job/'garment.render';packet.write_bytes(blob);write_json(job/'package.json',dict(baseCommit=m['baseCommit'],directory=package.relative_to(ROOT).as_posix(),cooked=str(cooked),packetSHA256=digest(packet),resources=rows,observedGameplay=False))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('job',type=Path);p.add_argument('--source',type=Path);p.add_argument('--cook',action='store_true');p.add_argument('--finalize-package',type=Path);a=p.parse_args();finalize_package(a.job,a.finalize_package) if a.finalize_package else cook(a.job) if a.cook else author(a.job,a.source)
