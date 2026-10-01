"""Extract only the two shipped player templates through official WCC.

The selection bundle retains the game's compressed payloads and entry metadata;
only its container offsets/lengths change. No SDK source entities are substituted
for game-cooked entities. All extracted data and receipts stay in ignored build/.
"""
import struct
import uuid
import zlib
from pathlib import Path
from mod import ROOT, settings, digest, write_json, run_wcc, required_file

PATHS=('gameplay/templates/characters/player/player.w2ent',
       'characters/player_entities/geralt/geralt_player.w2ent')


def extract(cfg):
    # This exact collision was also observed on untouched SDK Geralt. Keep the
    # narrowly calibrated assertion, and reject every other new diagnostic.
    from player_stack import verify_stock_template_baseline, STOCK_BASELINE
    baseline=verify_stock_template_baseline(cfg,STOCK_BASELINE)
    source=cfg['game']/'content/content0/bundles/startup.bundle'
    job=ROOT/'build/probe'/('shipped-player-'+uuid.uuid4().hex[:12]);job.mkdir(parents=True)
    bundles=job/'bundles';bundles.mkdir()
    entries=[];payloads=[];checks=[];offset=32+304*len(PATHS)
    with source.open('rb') as stream:
        header=bytearray(stream.read(32))
        table_size=struct.unpack_from('<I',header,16)[0]
        if (header[:8]!=b'POTATO70' or table_size%304 or
            struct.unpack_from('<Q',header,8)[0]!=source.stat().st_size or
            struct.unpack_from('<H',header,20)[0]!=5 or
            struct.unpack_from('<I',header,22)[0]!=32+table_size):
            raise ValueError('Uncalibrated shipped bundle header')
        table=stream.read(table_size)
        for path in PATHS:
            name=path.replace('/','\\').encode()+b'\0'
            matches=[i for i in range(0,table_size,304) if table[i:i+len(name)]==name]
            if len(matches)!=1:raise ValueError('Shipped player entry missing or duplicated')
            entry=bytearray(table[matches[0]:matches[0]+304])
            position,size,compressed,crc,compression=struct.unpack_from('<QIIII',entry,272)
            if compression!=1 or position<32+table_size or position+compressed>source.stat().st_size:
                raise ValueError('Uncalibrated player payload')
            stream.seek(position);payload=stream.read(compressed);decoded=zlib.decompress(payload)
            if len(decoded)!=size or zlib.crc32(decoded)!=crc:raise ValueError('Shipped player CRC mismatch')
            struct.pack_into('<Q',entry,272,offset);offset+=len(payload)
            entries.append(entry);payloads.append(payload);checks.append((path,decoded))
    struct.pack_into('<Q',header,8,offset);struct.pack_into('<I',header,16,304*len(PATHS))
    struct.pack_into('<I',header,22,32+304*len(PATHS))
    selected=bundles/'selected.bundle';selected.write_bytes(header+b''.join(entries)+b''.join(payloads))
    output=job/'unpacked'
    native=run_wcc(cfg,'unbundle',['-dir='+str(bundles),'-outdir='+str(output)],job/'workspace','shipped-player-unbundle')
    records=[]
    for path,decoded in checks:
        target=required_file(output/path)
        if target.read_bytes()!=decoded:raise ValueError('Official unbundle differs from CRC-checked payload')
        native_dump=run_wcc(cfg,'dumpfile',['-file='+str(target),'-out=\\\\?\\'],job/'workspace','inspect-shipped-player',baseline_asserts=baseline)
        dump=required_file(Path(str(target)+'.xml'))
        data=target.read_bytes();headers=[];start=0
        while True:
            start=data.find(b'CR2W',start)
            if start<0:break
            headers.append(start);start+=4
        records.append(dict(path=path,source=target.relative_to(ROOT).as_posix(),sourceSHA256=digest(target),
            sourceNativeDump=dump.relative_to(ROOT).as_posix(),sourceNativeDumpSHA256=digest(dump),
            embeddedHeaderCount=len(headers),nativeDump=native_dump))
    receipt=dict(sourceBundle=str(source),sourceBundleSHA256=digest(source),
        selectionBundleSHA256=digest(selected),nativeUnbundle=native,resources=records)
    write_json(job/'shipped-player.json',receipt)
    return job/'shipped-player.json'


if __name__=='__main__':print(extract(settings()))
