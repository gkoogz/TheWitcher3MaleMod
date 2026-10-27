"""Import rigid native material carriers for the canonical runtime garment.

The actual garment mesh comes from canonical Meridian each frame. These small
SDK-box carriers supply native material passes and measured draw ownership only.
"""
import argparse,collections,hashlib,json,shutil,struct,sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
from PIL import Image
import mod
from mod import ROOT,digest,read_json,write_json
from wcc_fbx import Document
from v2_cloth_material import native_objects
NATIVE_GRAPH='engine/materials/graphs/pbr_std.w2mg'

KINDS=('ribbed','elastic','red','blue')


def adopt(job,binding=None,package_info=None):
    descriptor=Path(package_info)if package_info is not None else job/'package.json'
    info=read_json(descriptor);package=Path(info['directory']);mod.verify_package(package)
    cooked=Path(info['cooked']);graph=info.get('graph',NATIVE_GRAPH);out=Path(binding)if binding is not None else ROOT/'v2/build/runtime-binding';records=[];packet=bytearray(b'MMCLT001')
    for kind in KINDS:
        p=cooked/'characters/malemod/garments'/(kind+'.w2mesh');reader,imports,objects=native_objects(p)
        mesh=next(x[2]for x in objects if x[0]=='CMesh');reader.cooked=reader.object(reader.get(mesh,'cookedData','SMeshCookedData'))[0]
        scale=reader.vector('quantizationScale')[:3];bias=reader.vector('quantizationOffset')[:3];word=lambda key:struct.unpack('<I',reader.get(reader.cooked,key,'Uint32'))[0]
        raw=Path(str(p)+'.1.buffer').read_bytes();vbytes=word('vertexBufferSize');io=word('indexBufferOffset');ib=word('indexBufferSize')
        if graph.replace('/','\\')not in imports:raise ValueError('Cooked material graph import differs')
        packet+=struct.pack('<6fI',*scale,*bias,ib)
        for suffix,data in [('all',raw),('vertices',raw[:vbytes]),('indices',raw[io:io+ib])]:
            label=('garment_'+kind+'_'+suffix).encode();records.append(struct.pack('<IH',len(data),len(label))+data[:32]+hashlib.sha256(data).digest()+label)
    (out/'garment.render').write_bytes(packet)
    fp=out/'graphics-owned-fingerprints.bin';data=fp.read_bytes();at=12;retained=[]
    for _ in range(struct.unpack_from('<I',data,8)[0]):
        start=at;size,length=struct.unpack_from('<IH',data,at);at+=70;label=data[at:at+length].decode();at+=length
        if not label.startswith('garment_'):retained.append(data[start:at])
    fp.write_bytes(b'MMGPH01\0'+struct.pack('<I',len(retained)+len(records))+b''.join(retained+records))
    write_json(out/'carrier-binding.json',dict(schema='malemod.witcher-v2-carrier-binding/1',package=str(package),packageManifestSHA256=digest(package/'build-manifest.json'),graph=graph,fingerprintsSHA256=digest(fp),garmentRenderSHA256=digest(out/'garment.render'),actualGarmentTopologyIsCanonical=True,nativeAppearancePassed=False))
    print('Adopted measured native carrier contract:',out/'garment.render')


def build():
    cfg=mod.settings();cfg['depot']=cfg['redkit']/'r4data';cfg['base']=ROOT.parent/'Work/dependencies/base-wolverine';job=ROOT/'v2/build/materials/carriers-07'
    if job.exists():raise ValueError('Use a fresh carrier job; adoption alone is available with --adopt-existing')
    intake=job/'build/intake';assets=intake/'characters/malemod/garments';assets.mkdir(parents=True)
    graph=cfg['depot']/NATIVE_GRAPH
    template=ROOT/'v2/build/materials/build/rigid-carrier.fbx';prior=mod.ROOT;mod.ROOT=job
    try:
        textures=[];y,x=np.mgrid[:256,:256];phase=x/256*2*np.pi*96
        linear=[(.527115126,.496932995,.462077),(.527115126,.496932995,.462077),(.58,.018,.027),(.018,.065,.38)]
        tasks=[]
        for k,kind in enumerate(KINDS):
            c=np.asarray(linear[k])*.35;srgb=np.where(c<=.0031308,c*12.92,1.055*c**(1/2.4)-.055);weave=1-.012*(.5+.5*np.cos(phase))
            rgb=np.uint8(np.clip(srgb[None,None,:]*weave[:,:,None]*255+.5,0,255));image=job/(kind+'.tga');Image.fromarray(rgb,'RGB').save(image)
            slope=.16 if k==0 else .018;nx=-slope*np.sin(phase);ny=-.008*np.sin(y/256*2*np.pi*128);nz=np.sqrt(1-nx*nx-ny*ny);normal=np.uint8(np.clip(np.stack([nx,ny,nz],axis=-1)*127.5+127.5,0,255));rgba=np.concatenate([normal,np.full((256,256,1),224,np.uint8)],axis=-1);normal_image=job/(kind+'-normal.tga');Image.fromarray(rgba,'RGBA').save(normal_image)
            # Measured pbr_std graph connects the sampled alpha directly to
            # Roughness. The texture-group name alone does not define shading.
            # Preserve the measured rough native normal map; calibrate only
            # the target engine's diffuse response to keep cotton below clipping.
            native_normal=ROOT/'v2/build/materials/carriers-06/build/intake/characters/malemod/garments'/(kind+'-normal.xbm')
            shutil.copy2(native_normal,assets/native_normal.name)
            tasks.append((kind,'diffuse',image,assets/(kind+'.xbm'),'CharacterDiffuse'))
        def import_texture(task):
            kind,channel,source,target,group=task;command=mod.run_wcc(cfg,'import',['-depot=local','-file='+str(source),'-out='+str(target),'-texturegroup='+group],job/'build/import-workspaces'/(kind+'-'+channel),'v2-fabric-'+kind+'-'+channel)
            return dict(kind=kind,channel=channel,sourceSHA256=digest(source),nativeSHA256=digest(target),command=command)
        with ThreadPoolExecutor(max_workers=2)as pool:textures=list(pool.map(import_texture,tasks))
        imports=[]
        for k,kind in enumerate(KINDS):
            document=Document(template);objects=document.root('Objects');connections=document.root('Connections')
            collision=next(o.values[0]for o in document.meshes if o.values[1].startswith('CCollisionShapeBox'))
            collision_model=next(n.values[2]for n in connections.children if n.values[:2]==['OO',collision])
            remove={o.values[0]for o in objects.children if o.name in ['Deformer','Pose','Texture','Video']or o.values[0]in [collision,collision_model]or o.name=='Material'and o.values[1].startswith('wood_solid')}
            objects.children=[o for o in objects.children if o.values[0]not in remove];connections.children=[n for n in connections.children if n.values[1]not in remove and n.values[2]not in remove]
            mesh=document.meshes[0];points=mesh.array('Vertices').reshape(-1,3);points=points*6;points[0,1]+=(k+1)*.9;mesh.set_array('Vertices',points)
            material=next(o for o in objects.children if o.name=='Material');material.props[1].value='Material0\0\1Material';material.props[1].raw=None
            counts=collections.Counter(o.name for o in objects.children)
            definitions=document.root('Definitions');definitions.child('Count').props[0].value=len(objects.children);definitions.child('Count').props[0].raw=None
            for node in definitions.children:
                if node.name=='ObjectType':node.child('Count').props[0].value=counts[node.values[0]];node.child('Count').props[0].raw=None
            fbx=job/(kind+'.fbx');document.save(fbx)
            fbx.with_suffix('.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><mesh><mesh_data autohideDistance="500.00" isTwoSided="true" useExtraStreams="true" mergeInGlobalShadowMesh="false" entityProxy="false"><LODs><LOD_info distance="0.00"/></LODs></mesh_data><materials><material name="Material0" local="true" base="'+NATIVE_GRAPH.replace('/','\\')+'"><param name="Diffuse" type="handle:ITexture" value="characters\\malemod\\garments\\'+kind+'.xbm"/><param name="Normal" type="handle:ITexture" value="characters\\malemod\\garments\\'+kind+'-normal.xbm"/><param name="wetness_switch" type="Float" value="0.0"/><param name="VarianceOffset" type="Float" value="1.0"/><param name="RSpecScale" type="Float" value="0.0"/><param name="RSpecBase" type="Float" value="0.1"/></material></materials></mesh>')
            target=assets/(kind+'.w2mesh');command=mod.run_wcc(cfg,'import',['-depot=local','-file='+str(fbx),'-out='+str(target)],intake,'v2-import-'+kind);imports.append(dict(kind=kind,sourceSHA256=digest(fbx),nativeSHA256=digest(target),command=command))
        lock=read_json(ROOT/'dependencies/base.lock.json');lock['commit']='47023a7f53d794cff84f2f423ba6a7d1fb98ec0f';write_json(job/'dependencies/base.lock.json',lock)
        project=dict(name='mod000000V2Fabric',version='2.0.0-carrier-preview',platform='pc',cacheBuilders=['textures'],reuseReadOnlyDepot=True,scope='V2 canonical-fabric draw carriers, fully reimported with their native material')
        package=mod.build(cfg,project,intake);manifest=read_json(package/'build-manifest.json');cook=next(c for c in manifest['nativeCommands']if c['command']=='cook');cooked=Path(next(a.split('=',1)[1]for a in cook['args']if a.startswith('-outdir=')))
        write_json(job/'package.json',dict(directory=str(package),cooked=str(cooked),sourceSDKBoxSHA256=digest(template),graphSHA256=digest(graph),textures=textures,meshImports=imports,nativeObserved=False));adopt(job)
    finally:mod.ROOT=prior


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--adopt-existing',action='store_true');a=p.parse_args();adopt(ROOT/'v2/build/materials/carriers-07')if a.adopt_existing else build()
