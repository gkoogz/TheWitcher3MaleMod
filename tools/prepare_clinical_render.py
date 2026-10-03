"""Validate the cooked rigid carriers and write their native draw contract."""
import argparse,struct
from pathlib import Path
from mod import ROOT,read_json,write_json,digest,settings,base_checkout,verify_package
from packed_mesh_format import CookedMesh

def verify_materials(job):
    job=Path(job).absolute();receipt=read_json(job/'authoring.json')
    rows={r['name']:r for r in receipt.get('textures',[])}
    for name,group,compression in [('white','CharacterDiffuse','TCM_DXTNoAlpha'),('flat','CharacterNormal','TCM_Normals')]:
        row=rows.get(name,{})
        if row.get('textureGroup')!=group or row.get('compression')!=compression or not row.get('nativeMetadataVerified') or not row.get('nativeMetadataDumpSHA256'):
            raise ValueError('Clinical texture lacks measured native group/encoding: '+name)
        native=job/'intake/characters/malemod/clinical'/(name+'.xbm')
        if digest(native)!=row['nativeSHA256']:raise ValueError('Clinical imported texture differs from official metadata proof: '+name)
    return receipt['textures']

def prepare(job,output):
    job,output=[Path(p).absolute() for p in [job,output]]
    if not job.is_relative_to(ROOT/'build') or not output.is_relative_to(ROOT/'build') or output.exists():raise ValueError('Use fresh owned build output')
    textures=verify_materials(job)
    pin=base_checkout(settings())['commit'];package=read_json(job/'package.json');manifest=verify_package(ROOT/package['directory'])
    if manifest['baseCommit']!=pin:raise ValueError('Clinical cook pin differs')
    cooked=Path(package['cooked'])/'characters/malemod/clinical';blob=b'MMFLD001';rows=[]
    for kind in ['opaque','clear']:
        path=cooked/(kind+'.w2mesh');mesh=CookedMesh(path.read_bytes(),allow_rigid=True)
        chunks=mesh.get(mesh.cooked,'renderChunks','array:47,0,Uint8')
        count=6 if kind=='opaque' else 2
        if mesh.palette or len(chunks)!=5+37*count or chunks[4]!=count:raise ValueError('Unobserved rigid native carrier')
        size=struct.unpack('<I',mesh.get(mesh.cooked,'indexBufferSize','Uint32'))[0]
        if size!=384:raise ValueError('Native carrier index layout differs')
        blob+=struct.pack('<6fI',*mesh.scale[:3],*mesh.offset[:3],size)
        rows.append(dict(kind=kind,path=path.relative_to(ROOT).as_posix(),meshSHA256=digest(path),bufferSHA256=digest(Path(str(path)+'.1.buffer')),scale=mesh.scale,offset=mesh.offset,indexBytes=size))
    output.mkdir();packet=output/'clinical.render';packet.write_bytes(blob)
    write_json(output/'manifest.json',dict(baseCommit=pin,packetSHA256=digest(packet),resources=rows,package=package['directory'],cookRoot=package['cooked'],authoring=job.relative_to(ROOT).as_posix(),authoringSHA256=digest(job/'authoring.json'),textures=textures,recipeSHA256=digest(Path(__file__)),bakeSHA256=read_json(settings()['base']/'provenance/clinical.json')['bakeSHA256'],nativeCooked=True,observedGameplay=False))
    print('Prepared rigid clinical contract:',output)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--job',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();prepare(a.job,a.output)
