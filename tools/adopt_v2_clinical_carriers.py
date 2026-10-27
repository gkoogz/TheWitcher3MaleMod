"""Adopt only the retained rigid clinical materials, preserving their native bytes.

No anatomy, garment mechanics, or v1 numerical runtime is copied. The current
canonical simulation supplies every replacement vertex. This recipe checks the
actual official-unbundled CR2W resources and their measured GPU buffer hashes.
"""
import argparse,hashlib,json,shutil,struct
from pathlib import Path
from mod import ROOT,digest,write_json
from packed_mesh_format import CookedMesh,decode_render_chunks
from v2_cloth_material import native_objects


def records(path):
    data=Path(path).read_bytes()
    if data[:8]!=b'MMGPH01\0':raise ValueError('Unobserved fingerprint header')
    at=12;out={}
    for _ in range(struct.unpack_from('<I',data,8)[0]):
        start=at;size,length=struct.unpack_from('<IH',data,at);at+=70
        label=data[at:at+length].decode('ascii');at+=length
        if label in out:raise ValueError('Duplicate fingerprint label')
        out[label]=data[start:at]
    if at!=len(data):raise ValueError('Fingerprint trailer differs')
    return out


def record(label,data):
    label=label.encode('ascii')
    return struct.pack('<IH',len(data),len(label))+data[:32]+hashlib.sha256(data).digest()+label


def material(reader,imports,objects):
    entry=next(x for x in objects if x[0]=='CMaterialInstance');tail=entry[3]
    count=struct.unpack_from('<I',tail)[0];at=4;result={}
    for _ in range(count):
        size,name,kind=struct.unpack_from('<IHH',tail,at)
        if size!=12:raise ValueError('Unobserved clinical material parameter size')
        name,kind=reader.names[name],reader.names[kind];value=tail[at+8:at+12];at+=size
        if kind=='handle:ITexture':value=imports[-struct.unpack('<i',value)[0]-1]
        elif kind=='Float':value=struct.unpack('<f',value)[0]
        else:raise ValueError('Unobserved clinical material parameter')
        result[name]=value
    if at!=len(tail):raise ValueError('Unobserved clinical material trailer')
    return result


def adopt(source,unpacked,output,binding):
    source,unpacked,output,binding=[Path(x).absolute() for x in (source,unpacked,output,binding)]
    owned=ROOT/'v2/build'
    if not output.is_relative_to(owned) or not binding.is_relative_to(owned) or output.exists():raise ValueError('Use fresh owned v2 outputs')
    native=source/'bin/x64_dx12/malemod-native';package=source/'Mods/modMaleModClinical'
    root=unpacked/'characters/malemod/clinical'
    expected={'carrier.w2ent','clear.w2mesh','clear.w2mesh.1.buffer','opaque.w2mesh','opaque.w2mesh.1.buffer','white.xbm','flat.xbm','opacity.xbm'}
    if {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}!=expected:raise ValueError('Clinical unbundle resources differ')
    textures=[]
    for name,group,compression in [('white','CharacterDiffuse','TCM_DXTNoAlpha'),('flat','CharacterNormal','TCM_Normals'),('opacity','CharacterDiffuseWithAlpha','TCM_DXTAlpha')]:
        path=root/(name+'.xbm');reader,imports,objects=native_objects(path);obj=objects[0]
        if imports or len(objects)!=1 or obj[0]!='CBitmapTexture':raise ValueError('Unobserved clinical texture')
        names={k:reader.names[struct.unpack('<H',obj[2][k][1])[0]]for k in ['compression','textureGroup']}
        if names!={'compression':compression,'textureGroup':group}:raise ValueError('Clinical texture encoding differs')
        if any(struct.unpack('<I',obj[2][k][1])[0]!=256 for k in ['width','height']):raise ValueError('Clinical texture dimensions differ')
        textures.append(dict(name=name,sha256=digest(path),**names))
    original=records(native/'graphics-owned-fingerprints.bin');fingerprints={};packet=bytearray(b'MMFLD001');resources=[]
    for kind,graph,diffuse,chunks_expected in [('opaque','pbr_std','white',6),('clear','transparent_lit_vert','opacity',2)]:
        path=root/(kind+'.w2mesh');reader,imports,objects=native_objects(path)
        expected_imports=['engine\\materials\\graphs\\'+graph+'.w2mg','characters\\malemod\\clinical\\'+diffuse+'.xbm','characters\\malemod\\clinical\\flat.xbm']
        if imports!=expected_imports:raise ValueError('Native clinical material graph differs')
        params=material(reader,imports,objects)
        expected_params={'Diffuse':imports[1],'Normal':imports[2],'RSpecScale':1.,'RSpecBase':struct.unpack('<f',struct.pack('<f',.65))[0]}if kind=='opaque'else {'Diffuse':imports[1],'Normal':imports[2],'Opacity':1.}
        # pbr_std's serialized first numeric parameter is RSpecScale, rather
        # than the transparent graph's Opacity. Keep the observed native fields.
        if params!=expected_params:raise ValueError('Native clinical material parameters differ: '+repr(params))
        mesh=CookedMesh(path.read_bytes(),allow_rigid=True);raw=Path(str(path)+'.1.buffer').read_bytes()
        word=lambda key:struct.unpack('<I',mesh.get(mesh.cooked,key,'Uint32'))[0]
        vertex_bytes,index_offset,index_bytes=[word(k)for k in ['vertexBufferSize','indexBufferOffset','indexBufferSize']]
        chunks=decode_render_chunks(mesh.get(mesh.cooked,'renderChunks','array:47,0,Uint8'))
        if mesh.palette or len(chunks)!=chunks_expected or index_bytes!=384 or tuple(mesh.scale[:3])!=(256.,)*3 or tuple(mesh.offset[:3])!=(-128.,)*3:raise ValueError('Unobserved native rigid dimensions')
        packet+=struct.pack('<6fI',*mesh.scale[:3],*mesh.offset[:3],index_bytes)
        for label,data in [('all',raw),('vertices',raw[:vertex_bytes]),('indices',raw[index_offset:index_offset+index_bytes])]:
            label='fluid_'+kind+'_'+label;fingerprints[label]=record(label,data)
        for lod,chunk in enumerate(chunks[:2]):
            n=struct.unpack_from('<H',chunk,27)[0]
            if n!=192:raise ValueError('Unobserved native carrier vertex count')
            for slot,stride in enumerate([8,4,8,8]):
                offset=struct.unpack_from('<I',chunk,1+4*slot)[0];label=f'fluid_{kind}_lod{lod}_stream{slot}';fingerprints[label]=record(label,raw[offset:offset+n*stride])
        resources.append(dict(kind=kind,meshSHA256=digest(path),bufferSHA256=digest(Path(str(path)+'.1.buffer')),scale=mesh.scale,offset=mesh.offset,indexBytes=index_bytes,renderChunks=len(chunks),parameters=params,graph=imports[0]))
    if packet!=(native/'clinical.render').read_bytes():raise ValueError('Measured native clinical render contract differs from retained contract')
    if fingerprints!={k:v for k,v in original.items()if k.startswith('fluid_')}:raise ValueError('Measured buffer fingerprints differ from retained identity')
    output.mkdir(parents=True);shutil.copytree(package,output/'native-assets/Mods/modMaleModClinical')
    (output/'clinical.render').write_bytes(packet)
    fragment=b'MMGPH01\0'+struct.pack('<I',len(fingerprints))+b''.join(fingerprints.values());(output/'clinical-fingerprints.bin').write_bytes(fragment)
    current=records(binding/'graphics-owned-fingerprints.bin');merged={k:v for k,v in current.items()if not k.startswith('fluid_')};merged.update(fingerprints)
    fp=binding/'graphics-owned-fingerprints.bin';fp.write_bytes(b'MMGPH01\0'+struct.pack('<I',len(merged))+b''.join(merged.values()));(binding/'clinical.render').write_bytes(packet)
    files=[dict(path=p.relative_to(output/'native-assets').as_posix(),sha256=digest(p),bytes=p.stat().st_size)for p in sorted((output/'native-assets').rglob('*'))if p.is_file()]
    receipt=dict(schema='malemod.witcher-v2-clinical-carriers/1',source=str(source),unpacked=str(unpacked),recipeSHA256=digest(Path(__file__)),nativeCarrierFiles=files,resources=resources,textures=textures,renderContractSHA256=digest(output/'clinical.render'),fingerprintFragmentSHA256=digest(output/'clinical-fingerprints.bin'),mergedFingerprintSHA256=digest(fp),fingerprintCount=len(fingerprints),nativeRecooked=False,sourceNumericalRuntimeCopied=False,observedV2Gameplay=False,sourceCmToNativeMeters=.01,phasePresentation=dict(clearFlowOpacity=.14,clearAlphaSource='native Diffuse.a sampled at UV.x texel centers',opaqueFlowGraph='pbr_std',depositOpacity='source density/fade times phase opacity'))
    write_json(output/'clinical-carrier-binding.json',receipt);write_json(binding/'clinical-carrier-binding.json',receipt)
    print('Verified actual retained rigid clinical resources and adopted',len(fingerprints),'measured fingerprints; gameplay acceptance pending')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['source','unpacked','output','binding']:p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();adopt(a.source,a.unpacked,a.output,a.binding)
