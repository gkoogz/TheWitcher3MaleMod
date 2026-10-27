"""Original canonical texture inputs, with no UV-space seam baking or grading."""
import argparse,hashlib,json,shutil
from pathlib import Path
import numpy as np
from PIL import Image
from mod import ROOT,digest,read_json,write_json
from prepare_v2_skin_donor import EXPECTED


def converted_normal(rgb):
    value=np.asarray(rgb,dtype=np.float32)/255.;value=value*2;value[...,:2]-=1
    value=value/np.maximum(np.linalg.norm(value,axis=-1,keepdims=True),1e-20)
    value=value/np.maximum(np.linalg.norm(value,axis=-1,keepdims=True),1e-20)
    return np.uint8(np.clip((value*.5+.5)*255+.5,0,255))


def prepare(output,donor_receipt):
    output,donor_receipt=Path(output).resolve(),Path(donor_receipt).resolve()
    if output.exists()or not output.is_relative_to((ROOT/'v2/build/materials').resolve()):raise ValueError('Use a fresh owned raw-source texture job')
    donor=read_json(donor_receipt);sources={r['name']:r for r in donor['maps']}
    if set(sources)!=set(EXPECTED):raise ValueError('Original canonical texture inventory differs')
    for name,expected in EXPECTED.items():
        source=Path(sources[name]['path'])
        if sources[name]['sha256']!=expected or digest(source)!=expected:raise ValueError('Original canonical DDS changed: '+name)
        with Image.open(source)as image:
            if image.size!=(4096,4096)or image.mode!='RGBA':raise ValueError('Original source resolution/channels differ')
    output.mkdir(parents=True);rows={0:[],1:[]}
    for role,stem,name,mode in [('NaturalDiffuse','natural-diffuse','R14-skin-natural.dds','RGBA'),
        ('ErectDiffuse','erect-diffuse','R14-skin-erect.dds','RGBA'),('SourceSpec','specular','SharedBody-specular.dds','RGB'),
        ('Normal','normal','SharedBody-normal.dds','RGB')]:
        source=Path(sources[name]['path'])
        with Image.open(source)as image:original=np.asarray(image.convert(mode)).copy()
        pixels=converted_normal(original)if role=='Normal'else original
        target=output/('lod0-'+stem+'.tga');Image.fromarray(pixels,mode).save(target)
        with Image.open(target)as image:
            actual=np.asarray(image);assert image.mode==mode and image.size==(4096,4096)
            if not np.array_equal(actual,pixels):raise ValueError('TGA changed original texture channel bytes')
        pixel_sha=hashlib.sha256(pixels.tobytes()).hexdigest();original_sha=hashlib.sha256(original.tobytes()).hexdigest()
        for lod in(0,1):
            path=output/(f'lod{lod}-'+stem+'.tga')
            if lod:shutil.copy2(target,path)
            rows[lod].append(dict(role=role,path=str(path),sha256=digest(path),mode=mode,width=4096,height=4096,
                decodedPixelsSHA256=pixel_sha,originalDecodedPixelsSHA256=original_sha,sourceDDS=str(source),sourceDDSSHA256=EXPECTED[name],
                originalChannelBytesUnchanged=role!='Normal',normalConversionOnly=role=='Normal'))
        del original,pixels
    proof=dict(schema='malemod.original-canonical-source-textures/1',donorReceipt=str(donor_receipt),donorReceiptSHA256=digest(donor_receipt),
        sourceDDSInventory=[sources[name]for name in sorted(sources)],lods=[dict(lod=i,files=rows[i])for i in(0,1)],
        sourceDiffuseRGBAUnchanged=True,sourceSpecularRGBUnchanged=True,resampled=False,colorGraded=False,seamPainted=False,
        normalConversion='normalize(2R-1,2G-1,2B), then original native RGB encode round(clamp((normalize(n)*.5+.5)*255)); float32',
        normalReferenceImplementation='bake_v2_skin_textures.source_normal + encode_normal',normalReferenceSHA256=digest(ROOT/'tools/bake_v2_skin_textures.py'),
        nativeNormalPacking='RGB TCM_QualityColor; do not import as BC5 normal-map encoding',nativeImported=False,cooked=False,globallyAdopted=False)
    write_json(output/'textures.json',proof);return proof


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--donor-receipt',type=Path,default=ROOT/'v2/build/materials/source-anatomy-01/donor.json')
    a=p.parse_args();print(json.dumps(prepare(a.output,a.donor_receipt),indent=2))
