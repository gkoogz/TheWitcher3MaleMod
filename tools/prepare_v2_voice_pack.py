"""Stage reviewed, ID-addressed recordings; never synthesize or install audio."""
import argparse,json,shutil,time,wave
from pathlib import Path,PurePosixPath
from mod import ROOT,digest,read_json,write_json
from install_v2 import target

def prepare(delivery,audio_root):
    profile=read_json(ROOT/'v2/voice-profile.json');data=read_json(delivery);root=Path(audio_root).resolve()
    lock=read_json(ROOT/'v2/voice-pipeline.lock.json');core=(ROOT/lock['coreRoot']).resolve()
    if lock.get('schema')!='malemod.voice-pipeline-lock/1':raise ValueError('Unknown voice pipeline revision lock')
    for relative,sha in lock['files'].items():
        if digest(target(core,relative))!=sha:raise ValueError('Pinned Core voice pipeline changed')
    if data.get('catalogSHA256')!=digest(core/'profiles/voice-lines.json')or data.get('scriptSHA256')!=digest(ROOT/profile['script']):
        raise ValueError('Approved voice delivery uses a different script or catalog revision')
    if data.get('schema')!='malemod.voice-delivery/1'or data.get('character_id')!=profile['character_id']or not data.get('ready'):
        raise ValueError('Expected a complete approved character voice delivery')
    bindings=profile['bindings'];clips=data['clips']
    if len(clips)!=len(bindings)or{r['line_id']for r in clips}!=set(bindings):raise ValueError('Approved delivery differs from permanent voice IDs')
    rows=[]
    for row in clips:
        target(Path('owned-pack'),bindings[row['line_id']])
        relative=PurePosixPath(row['recording'])
        if relative.is_absolute()or '..'in relative.parts or '\\'in row['recording']or ':'in row['recording']:raise ValueError('Unsafe recording path')
        p=root/relative
        if p.is_symlink()or not p.resolve().is_relative_to(root)or digest(p)!=row['sha256']:raise ValueError('Approved recording changed')
        with wave.open(str(p),'rb')as w:
            if (w.getnchannels(),w.getframerate(),w.getsampwidth(),w.getcomptype())!=(1,44100,2,'NONE')or w.getnframes()<1 or len(w.readframes(w.getnframes()))!=w.getnframes()*2:raise ValueError('Unsupported or truncated PCM')
        rows.append(dict(path=bindings[row['line_id']],source=str(p),sha256=row['sha256'],line_id=row['line_id']))
    config=Path('C:/Games/X-Men Origins Wolverine/Binaries/TeachingFluid.ini')
    rows.append(dict(path='TeachingFluid.ini',source=str(config),sha256=digest(config)))
    job=ROOT/'v2/build/voice-packs'/('prepared-'+str(time.time_ns()));job.mkdir(parents=True,exist_ok=False)
    for row in rows:
        dest=target(job,row['path']);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(row['source'],dest)
        if digest(dest)!=row['sha256']:raise ValueError('Voice staging copy changed')
    manifest=job/'manifest.json';write_json(manifest,dict(schema='malemod.witcher-voice-pack/1',root=str(job.resolve()),character_id=profile['character_id'],
        delivery=str(Path(delivery).resolve()),deliverySHA256=digest(delivery),profileSHA256=digest(ROOT/'v2/voice-profile.json'),files=rows,installed=False))
    write_json(ROOT/'local/v2-voice-pack.json',dict(manifest=str(manifest),sha256=digest(manifest)))
    return manifest
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--delivery',type=Path,required=True);p.add_argument('--audio-root',type=Path,required=True);a=p.parse_args()
    print(prepare(a.delivery,a.audio_root))
