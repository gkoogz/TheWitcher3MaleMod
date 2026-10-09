"""Prepare recorded Geralt bind endpoints for the calibrated offline probe."""
import argparse,struct,math
from pathlib import Path
from mod import ROOT,read_json,digest,write_json

def prepare(profile,output):
    output=Path(output).resolve();profile=Path(profile)
    if not output.is_relative_to((ROOT/'build').resolve()) or output.exists():
        raise ValueError('Use a fresh owned fixture directory')
    path=ROOT/'characters/geralt-runtime-bindings.json';j=read_json(path)
    proof=read_json(ROOT/'build/full-runtime/geralt-contact-calibration.json')
    if proof['profileSHA256']!=digest(path) or proof['capsule']!=j['contacts']['pelvisCapsule']:
        raise ValueError('Measured contact provenance differs')
    raw=profile.read_bytes();c=j['coordinateCalibration'];contacts=j['contacts'];pelvis=contacts['pelvisCapsule']
    values=[x for row in c['basis'] for x in row]+c['sourceRoot']+c['targetRootNative']+[c['nativeUnitsPerSourceUnit']]
    expected=struct.pack('<16d',*values)
    contact=struct.pack('<I2f7f',1,*[t['radiusSource'] for t in contacts['thighs']],*[x for row in pelvis['sourceEndpoints'] for x in row],pelvis['radiusSource'])
    if len(raw)!=472 or raw[:8]!=b'MMRUN001' or raw[176:304]!=expected or raw[432:]!=contact:
        raise ValueError('Runtime profile does not contain these measured coordinates and contacts')
    points=[p for thigh in contacts['thighs'] for p in thigh['nativeBindEndpoints']]
    if len(points)!=4 or any(len(p)!=3 or not all(math.isfinite(x) for x in p) for p in points):
        raise ValueError('Incomplete measured thigh endpoints')
    output.mkdir(parents=True)
    packet=output/'bind-endpoints.bin';packet.write_bytes(b'MMBIND01'+struct.pack('<12d',*[x for p in points for x in p]))
    write_json(output/'manifest.json',dict(schema='malemod.measured-bind-contact-probe/1',
        characterProfileSHA256=digest(path),runtimeProfileSHA256=digest(profile),
        recipeSHA256=digest(Path(__file__)),packetSHA256=digest(packet),
        measuredNativeBindEndpoints=points,animatedLivePose=False,installed=False,nativeGameplay=False))
    return packet

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);args=p.parse_args();print(prepare(args.profile,args.output))
