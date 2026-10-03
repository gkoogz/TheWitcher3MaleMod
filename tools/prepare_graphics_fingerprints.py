"""Fingerprint only the exact owned cooked .31 anatomy resource family.

Generated hashes/prefixes stay in ignored build output. No live game reads.
"""
import argparse,hashlib,struct
from pathlib import Path
from packed_mesh_format import CookedMesh
from mod import ROOT,read_json,write_json,digest

COOKED=ROOT/'build/motion/player-stack-138649950289/package-cfb0915d89d2/cooked/characters/malemod/body'


def prepare(output,cooked=None,upper=None,clinical=None):
    output=(ROOT/output).resolve()
    if not output.is_relative_to(ROOT/'build'):raise ValueError('Expected an owned ignored output')
    records=[];sources=[]
    body=Path(cooked).absolute() if cooked else COOKED
    paths=[body/'geralt_motion.w2mesh',*sorted((body/'overall_overall-stable-layout').glob('*.w2mesh'))]
    if len(paths)!=12:raise ValueError('Expected the neutral plus all eleven Overall resources')
    if upper:paths.append(Path(upper).absolute())
    fluid_paths=[]
    if clinical:
        fluid_paths=[Path(clinical).absolute()/(k+'.w2mesh') for k in ['opaque','clear']]
        paths.extend(fluid_paths)
    for path in paths:
        fluid=path in fluid_paths
        mesh=CookedMesh(path.read_bytes(),allow_rigid=fluid);buffer=Path(str(path)+'.1.buffer');raw=buffer.read_bytes()
        if fluid and mesh.palette:raise ValueError('Fluid carrier unexpectedly has a skin palette')
        chunks=mesh.get(mesh.cooked,'renderChunks','array:47,0,Uint8')
        # DataBuffer serialized length prefix is verified against the old dump.
        count=6 if fluid and path.stem=='opaque' else 2
        if len(chunks)!=5+37*count or struct.unpack_from('<I',chunks)[0]!=1+37*count or chunks[4]!=count:raise ValueError('Unobserved packed render chunks')
        chunks=chunks[4:]
        vertex_size=struct.unpack('<I',mesh.get(mesh.cooked,'vertexBufferSize','Uint32'))[0]
        index_offset=struct.unpack('<I',mesh.get(mesh.cooked,'indexBufferOffset','Uint32'))[0]
        index_size=struct.unpack('<I',mesh.get(mesh.cooked,'indexBufferSize','Uint32'))[0]
        if vertex_size>index_offset or index_offset+index_size!=len(raw):raise ValueError('Unexpected owned native buffer bounds')
        blocks=[('all',0,len(raw)),('vertices',0,vertex_size),('indices',index_offset,index_size)]
        for lod in range(2):
            chunk=chunks[1+37*lod:1+37*(lod+1)];n=struct.unpack_from('<H',chunk,27)[0]
            for slot,stride in enumerate([8 if fluid else 16,4,8,8]):blocks.append((f'lod{lod}_stream{slot}',struct.unpack_from('<I',chunk,1+4*slot)[0],n*stride))
        for label,offset,size in blocks:
            data=raw[offset:offset+size]
            if len(data)!=size or size<32:raise ValueError('Fingerprint stream leaves owned buffer')
            name=('fluid_'+path.stem if fluid else 'upper' if upper and path==Path(upper).absolute() else path.stem)+'_'+label;records.append(struct.pack('<IH',size,len(name))+data[:32]+hashlib.sha256(data).digest()+name.encode('ascii'))
        sources.append(dict(resource=path.relative_to(ROOT).as_posix(),meshSHA256=digest(path),bufferSHA256=digest(buffer)))
    baseline=read_json(ROOT/'local/installation.json')
    packet=b'MMGPH01\0'+struct.pack('<I',len(records))+b''.join(records)
    output.mkdir(parents=True,exist_ok=True);(output/'graphics-owned-fingerprints.bin').write_bytes(packet)
    write_json(output/'graphics-owned-fingerprints.json',dict(contractVersion=1,records=len(records),sources=sources,
        recipeSHA256=digest(Path(__file__)),readerSHA256=digest(ROOT/'tools/packed_mesh_format.py'),
        packetSHA256=digest(output/'graphics-owned-fingerprints.bin'),installedBundleHashes=[f for f in baseline['files'] if f['path'].endswith('.bundle')],
        observedGameResource=False,capturedGameData=False))
    print('Prepared',len(records),'owned resource stream fingerprints')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--cooked',type=Path);p.add_argument('--upper',type=Path);p.add_argument('--clinical',type=Path);a=p.parse_args();prepare(a.output,a.cooked,a.upper,a.clinical)
