"""Cook the authored separate body resources and source material atlas.

Preserves the installed player entity/skeleton/graph. No install is performed.
All native material handles are verified with official resource dumps.
"""
import argparse,shutil,sys
from pathlib import Path
from PIL import Image
from mod import ROOT,settings,base_checkout,run_wcc,write_json,digest,build,verify_package


def prepare(job):
    job=Path(job).absolute();cfg=settings();pin=base_checkout(cfg);sys.path.insert(0,str(cfg['base']))
    from malemod_base.material_atlas import compose_tiles,bake_repeat
    if not job.is_relative_to(ROOT/'build') or not (job/'manifest.json').exists():raise ValueError('Use an authored boundary job')
    workspace=job/'intake';workspace.mkdir(exist_ok=True)
    sources=[
      ('diffuse',ROOT/'build/probe/geralt_lower.fbm/body_01_mg__geralt_d01.tga',cfg['base']/'assets/materials/wolverine/R14-skin-natural.dds'),
      ('normal',ROOT/'build/probe/geralt_lower.fbm/body_01_mg__geralt_n01.tga',cfg['base']/'assets/materials/wolverine/SharedBody-normal.dds'),
      ('ambient',ROOT/'build/jobs/texture-export-calibration/body-ambient.tga',None)]
    materials=[]
    for name,stock,source in sources:
        output=workspace/'characters/malemod/materials'/('body_'+name+'.xbm');output.parent.mkdir(parents=True,exist_ok=True)
        if output.exists():
            with Image.open(stock) as image:resolution=[image.width*2,image.height]
            materials.append(dict(channel=name,stockSHA256=digest(stock),sourceSHA256=digest(source) if source else None,nativeSHA256=digest(output),resolution=resolution,reusedNativeImport=True,sourceSamplerRepeat=16 if name=='normal' else 1,anatomyAmbientPolicy='neutral white AO' if name=='ambient' else None))
            continue
        left=Image.open(stock).convert('RGBA')
        if source:
            right=Image.open(source).convert('RGBA')
            if name=='normal':right=bake_repeat(right,16) # source SetPixelShaderConstantF sampler scale
        else:
            right=Image.new('RGBA',left.size,(255,255,255,255)) # explicit neutral AO; not the source specular texture
        atlas=compose_tiles([left,right]);tga=job/('atlas-'+name+'.tga');atlas.save(tga)
        record=run_wcc(cfg,'import',['-depot=local','-file='+str(tga),'-out='+str(output)],workspace,'import-atlas-'+name)
        materials.append(dict(channel=name,stockSHA256=digest(stock),sourceSHA256=digest(source) if source else None,atlasSHA256=digest(tga),nativeSHA256=digest(output),resolution=list(atlas.size),command=record))
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
