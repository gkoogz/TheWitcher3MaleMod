"""Own grey studio carriers; official resave/cook, no installation."""
import argparse,copy,json,shutil,struct,subprocess,uuid,zlib
from pathlib import Path
from mod import ROOT,settings,digest,write_json,run_wcc,build
from packed_mesh_format import CookedMesh
from player_rig_redirect import header_crc
from prepare_motion import scalar,array
from prepare_iteration_world import transform

def grey_mesh(source,target):
    # Measured SDK editor box 162: preserve all mesh/collision/UV bytes.
    raw=bytearray(source.read_bytes())
    if struct.unpack_from('<I',raw,4)[0]!=162:raise ValueError('Expected measured SDK box 162')
    at,n,_=struct.unpack_from('<III',raw,40);pool=raw[at:at+n]
    at,n,_=struct.unpack_from('<III',raw,52)
    r=CookedMesh.__new__(CookedMesh)
    r.names=[pool[o:pool.index(0,o)].decode() for o,h in struct.iter_unpack('<II',raw[at:at+8*n])]
    table,n,_=struct.unpack_from('<III',raw,88);changed=[]
    for i in range(n):
        kind,flags,parent,size,offset,template,crc=struct.unpack_from('<HHIIIII',raw,table+24*i)
        if r.names[kind]!='CMaterialInstance':continue
        props,tail=r.object(raw[offset:offset+size]);begin=offset+size-len(tail);count=struct.unpack_from('<I',tail)[0];p=4
        for j in range(count):
            length,name,ty=struct.unpack_from('<IHH',tail,p);key=r.names[name]
            if key=='VarianceColor':
                color,end=r.object(tail[p+8:p+length])
                if end or set(color)!={'Red','Green','Blue','Alpha'}:raise ValueError('Unmeasured color representation')
                q=p+9
                while q<p+length-2:
                    cn,ct,cl=struct.unpack_from('<HHI',tail,q)
                    if cl!=5:raise ValueError('Unexpected byte color')
                    raw[begin+q+8]=255 if r.names[cn]=='Alpha' else 145;q+=9
                changed.append(key)
            elif key=='VarianceOffset':
                if length!=12:raise ValueError('Unexpected variance scalar')
                struct.pack_into('<f',raw,begin+p+8,0);changed.append(key)
            p+=length
        struct.pack_into('<I',raw,table+24*i+20,zlib.crc32(raw[offset:offset+size]))
    if changed!=['VarianceColor','VarianceOffset']:raise ValueError('SDK box material changed')
    struct.pack_into('<I',raw,96,zlib.crc32(raw[table:table+24*n]));struct.pack_into('<I',raw,32,header_crc(raw,0))
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    return dict(source=str(source),sourceSHA256=digest(source),SHA256=digest(target),color=[145,145,145,255],varianceOffset=0,geometryUnchanged=True)

def prepare():
    cfg=settings();job=ROOT/'build/iteration-storage'/('grey-platform-'+uuid.uuid4().hex[:12]);w=job/'workspace';w.mkdir(parents=True)
    baseline=ROOT/'recipes/iteration-floor-template.json'
    converter=ROOT/'build/research/wkit-current/MaleModCR2W.exe';proof=json.loads((converter.parent/'toolchain.json').read_text())
    if digest(converter)!=proof['executableSHA256']:raise ValueError('Authoring converter changed')
    if digest(converter.parent/'WolvenKit.CR2W.dll')!=proof['librarySHA256']:raise ValueError('Authoring library changed')
    paths=[]
    for name,scale in [('transient_floor',(32,32,.5)),('wall',(32,.5,12)),('walk_target',None)]:
        data=json.loads(baseline.read_text());chunks=data['_chunks'];entity=chunks['CEntity #1']['_vars'];entity['name']=scalar('String','Iteration '+name)
        if scale is None:
            entity['Components']=array('array:0,0,ptr:CComponent',[]);del chunks['CStaticMeshComponent #2']
        else:chunks['CStaticMeshComponent #2']['_vars']['transform']=transform(scale=scale)
        source=job/(name+'.json');write_json(source,data);target=w/'levels/malemod_iteration'/(name+'.w2ent');target.parent.mkdir(parents=True,exist_ok=True)
        result=subprocess.run([str(converter),'import',str(source),str(target)],capture_output=True,text=True)
        if result.returncode:raise RuntimeError(result.stderr)
        paths.append(target.relative_to(w).as_posix())
    mesh=w/'levels/malemod_iteration/floor.w2mesh';material=grey_mesh(cfg['redkit']/'r4data/engine/meshes/editor/box.w2mesh',mesh);paths.append(mesh.relative_to(w).as_posix())
    environment_source=cfg['redkit']/'r4data/environment/definitions/test_environments/env_shader_standard_neutral.env'
    environment=w/'levels/malemod_iteration/studio.env'
    shutil.copy2(environment_source,environment);paths.append(environment.relative_to(w).as_posix())
    report=dict(material=material,environmentSource=str(environment_source),environmentSourceSHA256=digest(environment_source),converterSHA256=digest(converter),native=[])
    write_json(job/'authoring.json',report)
    record=run_wcc(cfg,'resave',['-tmpdir='+str(job/'resave-tmp'),'-path=levels\\malemod_iteration','-nosourcecontrol','-ignorefileversion'],w,'grey-platform-resave');report['native'].append(record)
    depot=Path(record['args'][record['args'].index('-uncookDir')+1])
    for path in paths:shutil.copy2(depot/path,w/path)
    package=build(cfg,dict(name='modMaleModIteration',version='0.1.1',platform='pc',cacheBuilders=['physics'],reuseReadOnlyDepot=True,scope='Neutral grey transient studio'),w)
    manifest=json.loads((package/'build-manifest.json').read_text());pack=next(c for c in manifest['nativeCommands']if c['command']=='pack');intake=Path(next(a[5:]for a in pack['args']if a.startswith('-dir=')))
    commands=[]
    for path in paths:
        output=job/'readback'/Path(path).name;output.parent.mkdir(exist_ok=True);shutil.copy2(intake/path,output)
        commands.append(run_wcc(cfg,'dumpfile',['-file='+str(output),'-out=\\\\?\\'],w,'grey-platform-readback',existing_depot=depot))
    import xml.etree.ElementTree as ET
    template=ET.parse(str(job/'readback/transient_floor.w2ent')+'.xml');meshrefs=template.findall('.//prop[@name="mesh"]/resource')
    if len(meshrefs)!=1 or meshrefs[0].get('path').replace('\\','/')!='levels/malemod_iteration/floor.w2mesh':raise ValueError('Own floor reference differs')
    env_dump=ET.parse(str(job/'readback/studio.env')+'.xml')
    if len(env_dump.findall('.//object[@class="CEnvironmentDefinition"]'))!=1:raise ValueError('Own studio environment did not survive cooking')
    links=dict(schema='malemod.iteration-transient-native-links/1',label='cooked',templateClassVerified=bool(template.findall('.//object[@class="CEntityTemplate"]')),staticMeshVerified=bool(template.findall('.//object[@class="CStaticMeshComponent"]')),ownMeshHardReferenceVerified=True,bootstrapMode='stock-q002-transient-platform',worldReplaced=False,resources=[dict(path=p,sha256=digest(intake/p))for p in paths],commands=commands)
    receipt=job/'native-links-cooked.json';write_json(receipt,links)
    report.update(package=str(package),nativeLinks=str(receipt));write_json(job/'authoring.json',report)
    write_json(package.with_name(package.name+'.iteration-native-proof.json'),dict(schema='malemod.iteration-transient-platform/1',buildManifestSHA256=digest(package/'build-manifest.json'),nativeLinksReceipt=str(receipt),nativeLinksReceiptSHA256=digest(receipt)))
    print(package,flush=True)
    return package

if __name__=='__main__':argparse.ArgumentParser(description=__doc__).parse_args();prepare()
