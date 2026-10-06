"""One session's cheap studio shadow setting, with exact preference restoration."""
from pathlib import Path
import shutil
from mod import digest,read_json,write_json

def begin(path,job,option='ScreenShadows'):
    path=Path(path).resolve();job=Path(job).resolve()
    job.mkdir(parents=True,exist_ok=False)
    original=path.read_bytes()
    # This measured renderer option is stored in the user's DX12 profile.
    # Change only its byte value; preserve encoding, whitespace and all else.
    if option not in ('ScreenShadows','SSREnabled','StudioCascadeRanges','SSAOEnabled'):
        raise ValueError('Unmeasured renderer option')
    if option=='StudioCascadeRanges':
        import re
        updated=original
        for index in range(4):
            pattern=rb'(?m)^CascadeShadowDistanceScale'+str(index).encode()+rb'=[^\r\n]+'
            updated,count=re.subn(pattern,b'CascadeShadowDistanceScale'+str(index).encode()+b'=0.0001',updated)
            if count!=1:raise ValueError('Expected one measured cascade range per index')
        backup=job/'original.settings';backup.write_bytes(original)
        value=dict(path=str(path),backup=str(backup),originalSHA256=digest(backup),
                   temporarySHA256=__import__('hashlib').sha256(updated).hexdigest(),
                   option=option,temporaryValue=0.0001)
        receipt=job/'receipt.json';write_json(receipt,value)
        path.write_bytes(updated)
        if digest(path)!=value['temporarySHA256']:raise ValueError('Temporary studio settings differ')
        return receipt
    needle=(option+('=3' if option=='SSAOEnabled' else '=true')).encode()
    if original.count(needle)!=1:
        raise ValueError('Expected measured DX12 screen shadow option')
    updated=original.replace(needle,(option+('=0' if option=='SSAOEnabled' else '=false')).encode(),1)
    backup=job/'original.settings';backup.write_bytes(original)
    value=dict(path=str(path),backup=str(backup),originalSHA256=digest(backup),
               temporarySHA256=__import__('hashlib').sha256(updated).hexdigest(),
               option=option,temporaryValue=0 if option=='SSAOEnabled' else False)
    receipt=job/'receipt.json';write_json(receipt,value)
    path.write_bytes(updated)
    if digest(path)!=value['temporarySHA256']:raise ValueError('Temporary studio settings differ')
    return receipt

def restore(receipt):
    receipt=Path(receipt).resolve();r=read_json(receipt)
    path=Path(r['path']);backup=Path(r['backup'])
    if digest(backup)!=r['originalSHA256']:raise ValueError('Original preferences backup differs')
    # Restore the exact pre-launch file after the owned game has exited. Keep a
    # diagnostic copy if the engine wrote updated preferences during its exit.
    if digest(path)!=r['temporarySHA256']:
        shutil.copy2(path,receipt.parent/'engine-written.settings')
    shutil.copy2(backup,path)
    if digest(path)!=r['originalSHA256']:raise ValueError('Original preferences not restored')
    r['originalPreferencesRestored']=True;write_json(receipt,r)
    return r
