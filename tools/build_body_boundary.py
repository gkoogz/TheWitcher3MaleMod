"""Cook the authored separate body resources and source material atlas.

Preserves the installed player entity/skeleton/graph. No install is performed.
All native material handles are verified with official resource dumps.
"""
import argparse,shutil,sys
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image
from mod import ROOT,settings,base_checkout,run_wcc,write_json,digest,build,verify_package,read_json


def verified_material(record, channel, base_commit, stock_hash, source_hash, native_hash):
    """Reuse only a material whose generation receipt matches its inputs.

    An XBM left by an interrupted or earlier build is not evidence that the
    current diffuse correction was imported. Keep the original receipt rather
    than assigning today's source hashes to yesterday's native bytes.
    """
    if record.get('baseCommit') != base_commit:
        raise ValueError('Cached material belongs to a different Base revision; use a fresh body job')
    rows = [r for r in record.get('materials', []) if r.get('channel') == channel]
    if len(rows) != 1:
        raise ValueError('Cached material has no unique generation receipt: '+channel)
    row = rows[0]
    expected = dict(stockSHA256=stock_hash, sourceSHA256=source_hash, nativeSHA256=native_hash)
    if any(row.get(k) != v for k, v in expected.items()):
        raise ValueError('Cached material input/output hash changed: '+channel)
    if not row.get('atlasSHA256'):
        raise ValueError('Cached material receipt lacks the authored atlas hash: '+channel)
    return dict(row, reusedNativeImport=True)


def material_policy(channel):
    # Measured from Geralt's actual diffuse/normal XBM resources and the
    # installed REDkit texturegroups.xml. Color compression is not a valid
    # tangent-normal encoding: import without this flag defaults WorldDiffuse.
    return ('CharacterNormal','TCM_Normals') if channel=='normal' else ('CharacterDiffuse','TCM_DXTNoAlpha')


def character_ambient(image, seam_uv):
    """Transfer the actual skin shader's packed material channels.

    pbr_skin's Ambient is R=detail mask, G=roughness, B=specularity;
    it is not an ambient-occlusion multiplier. White is not neutral.
    There is no equivalent packed map in the extracted source, so use the
    measured character attachment material rather than relabeling specular.
    """
    import numpy as np
    from malemod_base.skin_match import sample
    samples=sample(image,seam_uv)
    rgb=np.floor(np.median(samples,axis=0)+.5).astype(np.uint8)
    return Image.new('RGBA',image.size,tuple(int(v) for v in rgb)+(255,)),dict(
        method='median measured character seam packed-material channels',
        channels=dict(R='detail mask',G='roughness',B='specularity'),
        packedRGB=rgb.tolist(),sampleCount=len(samples))


def verify_texture_metadata(xml, group, compression):
    root=ET.parse(xml).getroot()
    properties=root.find(".//object[@class='CBitmapTexture']/properties")
    if properties is None:raise ValueError('Native texture dump lacks CBitmapTexture')
    values={p.attrib['name']:(p.text or '').strip() for p in properties.findall('prop')}
    if values.get('textureGroup')!=group or values.get('compression')!=compression:
        raise ValueError('Native texture group/compression differs from the measured character material')
    return dict(textureGroup=group,compression=compression,nativeMetadataVerified=True,width=int(values['width']),height=int(values['height']))


def prepare(job):
    job=Path(job).absolute();cfg=settings();pin=base_checkout(cfg);sys.path.insert(0,str(cfg['base']))
    from malemod_base.material_atlas import compose_tiles,bake_repeat
    from malemod_base.skin_match import sample,match
    from wcc_fbx import Document
    import numpy as np
    from scipy.sparse import csr_matrix
    if not job.is_relative_to(ROOT/'build') or not (job/'manifest.json').exists():raise ValueError('Use an authored boundary job')
    workspace=job/'intake';workspace.mkdir(exist_ok=True)
    sources=[
      ('diffuse',ROOT/'build/probe/geralt_lower.fbm/body_01_mg__geralt_d01.tga',cfg['base']/'assets/materials/wolverine/R14-skin-natural.dds'),
      ('normal',ROOT/'build/probe/geralt_lower.fbm/body_01_mg__geralt_n01.tga',cfg['base']/'assets/materials/wolverine/SharedBody-normal.dds'),
      ('ambient',ROOT/'build/jobs/texture-export-calibration/body-ambient.tga',None)]
    receipt_path=job/'material-imports.json'
    previous=read_json(receipt_path) if receipt_path.exists() else {}
    materials=[]
    for name,stock,source in sources:
        group,compression=material_policy(name)
        output=workspace/'characters/malemod/materials'/('body_'+name+'.xbm');output.parent.mkdir(parents=True,exist_ok=True)
        if output.exists():
            row=verified_material(previous,name,pin['commit'],digest(stock),digest(source) if source else None,digest(output))
            if row.get('textureGroup')!=group or row.get('compression')!=compression or not row.get('nativeMetadataVerified'):
                raise ValueError('Cached texture lacks the verified character encoding; use a fresh body job')
            if name=='diffuse':
                correction_path=job/'skin-match.json'
                if not correction_path.exists():raise ValueError('Cached diffuse lacks its skin-match receipt')
                correction=read_json(correction_path)
                if correction.get('sourceSHA256')!=digest(source) or correction.get('targetSHA256')!=digest(stock) or correction.get('method')!='median seam samples, linear RGB multiplicative correction':
                    raise ValueError('Cached diffuse skin-match inputs differ')
                if row.get('skinMatchSHA256') and row['skinMatchSHA256']!=digest(correction_path):
                    raise ValueError('Cached diffuse correction receipt changed')
            if name=='ambient':
                calibration=job/'ambient-match.json'
                if not calibration.exists() or row.get('ambientMatchSHA256')!=digest(calibration):
                    raise ValueError('Cached Ambient lacks the skin shader packed-channel calibration')
            materials.append(row)
            continue
        left=Image.open(stock).convert('RGBA')
        if source:
            right=Image.open(source).convert('RGBA')
            if name=='normal':right=bake_repeat(right,16) # source SetPixelShaderConstantF sampler scale
            if name=='diffuse':
                bank=__import__('json').loads((ROOT/'build/overall/overall-stable-layout/overall.json').read_text())
                binding=np.load(ROOT/bank['fit'].rsplit('/',1)[0]/'geralt-anatomy-lod0.bindings.npz')
                mesh=Document(ROOT/bank['cage']/'geralt-motion.fbx').meshes[0]
                uv=next(l for l in mesh.children if l.name=='LayerElementUV' and l.values[0]==0).array('UV').reshape(-1,2)
                ml=csr_matrix((binding['module_lineage_data'],binding['module_lineage_indices'],binding['module_lineage_indptr']),shape=tuple(binding['module_lineage_shape']))
                body=len(uv)-ml.shape[0];native_uv=uv[binding['body_seam']].copy();native_uv[:,1]=1-native_uv[:,1]
                source_uv=(ml@binding['original_module_uv'])[binding['module_seam']-body]
                right,correction=match(right,sample(right,source_uv),sample(left,native_uv))
                write_json(job/'skin-match.json',dict(**correction,sourceSampleUV=source_uv.tolist(),targetSampleUV=native_uv.tolist(),sourceSHA256=digest(source),targetSHA256=digest(stock)))
        else:
            correction=read_json(job/'skin-match.json')
            right,calibration=character_ambient(left,correction['targetSampleUV'])
            write_json(job/'ambient-match.json',dict(**calibration,targetSHA256=digest(stock),
                targetSampleUV=correction['targetSampleUV'],
                shader='engine/materials/graphs/pbr_skin.w2mg'))
        atlas=compose_tiles([left,right]);tga=job/('atlas-'+name+'.tga');atlas.save(tga)
        record=run_wcc(cfg,'import',['-depot=local','-file='+str(tga),'-out='+str(output),'-texturegroup='+group],workspace,'import-atlas-'+name)
        materials.append(dict(channel=name,stockSHA256=digest(stock),sourceSHA256=digest(source) if source else None,atlasSHA256=digest(tga),nativeSHA256=digest(output),resolution=list(atlas.size),command=record))
        metadata_record=run_wcc(cfg,'dumpfile',['-file='+str(output),'-out=\\\\?\\'],workspace,'verify-atlas-'+name)
        dump=Path(str(output)+'.xml')
        materials[-1].update(verify_texture_metadata(dump,group,compression))
        materials[-1]['nativeMetadataCommand']=metadata_record
        materials[-1]['nativeMetadataDumpSHA256']=digest(dump)
        dump.unlink()
        if name=='diffuse':materials[-1]['skinMatchSHA256']=digest(job/'skin-match.json')
        if name=='ambient':materials[-1]['ambientMatchSHA256']=digest(job/'ambient-match.json')
        # Persist provenance after each successful import so an interrupted
        # build can resume without silently accepting an unverified XBM.
        complete={r['channel']:r for r in previous.get('materials',[]) if previous.get('baseCommit')==pin['commit']}
        complete.update({r['channel']:r for r in materials})
        write_json(receipt_path,dict(baseCommit=pin['commit'],materials=list(complete.values()),nativeHandleVerified=False,observedGameplay=False))
        # Remove only the exact, just-authored uncompressed intermediate after
        # hashing it. Native asset remains in the isolated intake.
        tga.unlink();atlas.close();left.close();right.close()
    targets=[('lower','characters/malemod/body/geralt_motion.w2mesh'),('upper','characters/models/geralt/body/model/t_01_mg__body_hires.w2mesh')]
    for label,resource in targets:
        output=workspace/resource;output.parent.mkdir(parents=True,exist_ok=True)
        if not output.exists():run_wcc(cfg,'import',['-depot=local','-file='+str(job/(label+'.fbx')),'-out='+str(output)],workspace,'import-'+label)
        record=run_wcc(cfg,'dumpfile',['-file='+str(output),'-out=\\\\?\\'],workspace,'material-'+label)
        text=Path(str(output)+'.xml').read_text()
        for name in ['diffuse','normal','ambient']:
            if 'body_'+name+'.xbm' not in text:raise ValueError('Native import lost material handle '+name)
    # The existing graph's eleven carrier meshes must have exactly the same
    # layout. The complete Base surface now owns all slider deformation.
    neutral=workspace/targets[0][1]
    for value in [1,10,20,30,40,50,60,70,80,90,100]:
        target=workspace/'characters/malemod/body/overall_overall-stable-layout'/('overall_'+str(value)+'.w2mesh')
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(neutral,target)
    # Official diagnostic XML is not an authored game resource.
    for label,resource in targets:Path(str(workspace/resource)+'.xml').unlink()
    write_json(job/'material-imports.json',dict(baseCommit=pin['commit'],materials=materials,nativeHandleVerified=True,observedGameplay=False))
    package=build(cfg,dict(name='modMaleModBodyBoundary',version='0.4.32-body-boundary',platform='pc',cacheBuilders=['textures'],scope='Shared waist on separate body resources; source material atlas; full native runtime required'),workspace)
    manifest=verify_package(package);cooked=next(a.removeprefix('-outdir=') for r in manifest['nativeCommands'] if r['command']=='cook' for a in r['args'] if a.startswith('-outdir='))
    write_json(job/'package.json',dict(directory=package.relative_to(ROOT).as_posix(),cooked=cooked))
    return package


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('job',type=Path);prepare(p.parse_args().job)
