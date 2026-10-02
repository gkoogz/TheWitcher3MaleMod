"""Hash installed shader inputs and prepare an ignored two-LOD SDK test packet.

No SDK source, native geometry or palette data is copied into tracked files.
"""
import argparse,json,struct
from pathlib import Path
from mod import ROOT,digest,write_json
from packed_mesh_format import CookedMesh

SDK=Path('E:/SteamLibrary/steamapps/common/The Witcher 3 REDkit/bin/shaders/include')
FILES=['vertexFactory.fx','vertexFactoryMeshSkinned.fx','include_computeRTData.fx','globalConstantsVS.fx','common.fx']

def prepare(output):
    mesh=ROOT/'build/motion/player-stack-138649950289/package-cfb0915d89d2/cooked/characters/malemod/body/geralt_motion.w2mesh'
    parsed=CookedMesh(mesh.read_bytes());buffer=Path(str(mesh)+'.1.buffer');data=buffer.read_bytes()
    chunks=parsed.get(parsed.cooked,'renderChunks','array:47,0,Uint8')
    if len(chunks)<4 or struct.unpack_from('<I',chunks)[0]!=len(chunks)-4:raise ValueError('Native byte array length differs')
    chunks=chunks[4:]
    if len(chunks)!=75 or chunks[0]!=2:raise ValueError('Unexpected two-LOD render chunk layout')
    vertices=[];counts=[]
    for lod in range(2):
        chunk=chunks[1+37*lod:1+37*(lod+1)]
        offsets=[struct.unpack_from('<I',chunk,1+4*i)[0] for i in range(4)]
        count=struct.unpack_from('<H',chunk,27)[0];counts.append(count)
        if any(o+s*count>len(data) for o,s in zip(offsets,[16,4,8,8])):raise ValueError('Stream outside owned buffer')
        vertices.extend(data[offsets[0]+16*i:offsets[0]+16*(i+1)]+data[offsets[2]+8*i:offsets[2]+8*(i+1)] for i in range(count))
    output.mkdir(parents=True,exist_ok=True)
    packet=output/'owned.skin'
    packet.write_bytes(b'MMSKIN01'+struct.pack('<6fII',*parsed.scale[:3],*parsed.offset[:3],len(parsed.palette),len(vertices))+b''.join(vertices))
    manifest=dict(recipeSHA256=digest(Path(__file__)),conversionSHA256=digest(ROOT/'native/skin_output.hpp'),oracleSHA256=digest(ROOT/'native/skin_sdk_test.cpp'),
                  sdkFiles=[dict(path=str(SDK/f),sha256=digest(SDK/f)) for f in FILES],meshSHA256=digest(mesh),bufferSHA256=digest(buffer),
                  packetSHA256=digest(packet),lodVertexCounts=counts,vertices=len(vertices),paletteSize=len(parsed.palette),
                  shaderNormalizesWeights=True,shaderSkinBufferSlot=0,frequentConstantBufferSlot=2,
                  quantizationScaleByteOffset=128,quantizationOffsetByteOffset=144,skinningDataByteOffset=176,
                  nativeVertexOutput=False,observedGameplay=False)
    write_json(output/'manifest.json',manifest);print(json.dumps(manifest,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);prepare(p.parse_args().output)
