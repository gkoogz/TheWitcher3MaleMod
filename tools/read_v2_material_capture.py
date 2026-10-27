"""Decode exact native target bytes, preserving slot numbers and stored values.

No slot is labelled albedo/normal/specular until the captured PS establishes it.
UNORM_SRGB views remain stored encoded values here; no implicit gamma operation.
"""
import argparse,json
from pathlib import Path
import numpy as np
from PIL import Image

def small_float(value,mantissa):
    value=np.asarray(value,np.uint32);exponent=value>>mantissa;fraction=value&((1<<mantissa)-1)
    result=np.ldexp(1+fraction.astype(float)/(1<<mantissa),exponent.astype(int)-15)
    return np.where(exponent==0,np.ldexp(fraction.astype(float),1-15-mantissa),np.where(exponent==31,np.where(fraction,np.nan,np.inf),result))

def load_target(root,target):
    root=Path(root).resolve();path=(root/target['file']).resolve()
    if not path.is_relative_to(root):raise ValueError('Capture target escapes its metadata directory')
    data=path.read_bytes();w,h=int(target['width']),int(target['height']);pitch=int(target['rowPitch']);offset=int(target['offset']);fmt=int(target['viewFormat'])
    if len(data)!=target['bytes'] or not(0<w<=4096 and 0<h<=2160):raise ValueError('Capture byte size or dimensions differ')
    if fmt in [28,29,87,91]:
        packed=np.ndarray((h,w,4),np.uint8,buffer=data,offset=offset,strides=(pitch,4,1));result=packed.astype(float)/255
        if fmt in [87,91]:result=result[:,:,[2,1,0,3]]
        return result
    if fmt==10:return np.ndarray((h,w,4),'<f2',buffer=data,offset=offset,strides=(pitch,8,2)).astype(float)
    if fmt==2:return np.ndarray((h,w,4),'<f4',buffer=data,offset=offset,strides=(pitch,16,4)).astype(float)
    if fmt==24:
        packed=np.ndarray((h,w),'<u4',buffer=data,offset=offset,strides=(pitch,4));return np.stack([(packed&1023)/1023,((packed>>10)&1023)/1023,((packed>>20)&1023)/1023,(packed>>30)/3],axis=-1)
    if fmt==26:
        packed=np.ndarray((h,w),'<u4',buffer=data,offset=offset,strides=(pitch,4));return np.stack([small_float(packed&2047,6),small_float((packed>>11)&2047,6),small_float(packed>>22,5),np.ones_like(packed,float)],axis=-1)
    raise ValueError('Unsupported observed native view format '+str(fmt))

def inspect(metadata,output):
    metadata=Path(metadata).resolve();output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False);info=json.loads(metadata.read_text());reports=[]
    if info.get('schema')!='malemod.native-material-capture/1' or len(info.get('targets',[]))!=5 or info.get('completeFrame') is not False:raise ValueError('Expected bounded native five-target draw capture')
    for target in info['targets']:
        pixels=load_target(metadata.parent,target);slot=target['slot'];finite=np.isfinite(pixels);reports.append(dict(slot=slot,format=target['viewFormat'],minimum=np.nanmin(pixels,axis=(0,1)).tolist(),maximum=np.nanmax(pixels,axis=(0,1)).tolist(),finite=bool(finite.all())))
        # Raw channel views, never a reconstructed lit image. A neutral range
        # is used solely for display; exact values remain in the native bins.
        rgba=np.uint8(np.clip(np.nan_to_num(pixels,nan=0,posinf=1,neginf=0),0,1)*255+.5)
        Image.fromarray(rgba[:,:,:3]).save(output/f'rt{slot}-rgb-stored.png')
        for channel,name in enumerate('rgba'):Image.fromarray(rgba[:,:,channel]).save(output/f'rt{slot}-{name}-stored.png')
    report=dict(metadata=str(metadata),interpretation='Stored target channels; no implicit gamma, normal decode, lighting reconstruction or slot semantics',targets=reports);(output/'channels.json').write_text(json.dumps(report,indent=2)+'\n');return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('metadata',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();print(json.dumps(inspect(a.metadata,a.output),indent=2))
