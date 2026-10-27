"""Plan or explicitly import eight original source maps into a fresh private job."""
import argparse,json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import xml.etree.ElementTree as ET
import mod
from mod import ROOT,digest,read_json,write_json
from build_v2_anatomy_material import complete_depot,texture_properties


def plan(textures,job):
    textures,job=Path(textures).resolve(),Path(job).resolve();proof=read_json(textures)
    if proof.get('schema')!='malemod.original-canonical-source-textures/1'or proof.get('seamPainted')or proof.get('colorGraded'):raise ValueError('Exact ungraded original source texture proof required')
    if job.exists()or not job.is_relative_to((ROOT/'v2/build/materials').resolve()):raise ValueError('Use a fresh owned native texture import job')
    rows=[dict(row,lod=lod['lod'])for lod in proof['lods']for row in lod['files']]
    if len(rows)!=8 or {(r['lod'],r['role'])for r in rows}!={(lod,role)for lod in(0,1)for role in('NaturalDiffuse','ErectDiffuse','SourceSpec','Normal')}:raise ValueError('Eight exact source map inputs required')
    for row in rows:
        if digest(row['path'])!=row['sha256']:raise ValueError('Original source TGA changed')
        row['textureGroup']='V2AnatomyNormalRGB'if row['role']=='Normal'else'V2AnatomyColor'
        row['target']=str(job/'build/intake/characters/malemod/anatomy'/Path(row['path']).with_suffix('.xbm').name)
    return rows


def run(textures,job):
    textures,job=Path(textures).resolve(),Path(job).resolve();rows=plan(textures,job);job.mkdir(parents=True)
    cfg=mod.settings();cfg['depot']=complete_depot(cfg)
    cfg['wcc']=ROOT/'v2/build/materials/anatomy-01/build/shaders-05/runtime/bin/x64_RedKit/wcc_lite.exe'
    groups=ET.fromstring((cfg['depot']/'engine/textures/texturegroups.xml').read_bytes())
    for name in('V2AnatomyColor','V2AnatomyNormalRGB'):
        if any(g.attrib.get('name')==name for g in groups):raise ValueError('Preserve unexpected original-source texture group collision')
        node=ET.SubElement(groups,'group',name=name)
        for key,value in(('compression','TCM_QualityColor'),('maxsize','4096'),('resizable','0'),('category','Characters')):ET.SubElement(node,key,value=value)
    encoded=ET.tostring(groups,encoding='utf-8',xml_declaration=True);original_root=mod.ROOT;mod.ROOT=job
    try:
        def one(row):
            source=Path(row['path']);target=Path(row['target']);target.parent.mkdir(parents=True,exist_ok=True)
            scratch=job/'build/imports'/source.stem;config=scratch/'engine/textures/texturegroups.xml';config.parent.mkdir(parents=True);config.write_bytes(encoded)
            command=mod.run_wcc(cfg,'import',['-depot=local','-file='+str(source),'-out='+str(target),'-texturegroup='+row['textureGroup']],scratch,'original-'+source.stem)
            properties=texture_properties(target)
            if properties['compression']!='TCM_QualityColor'or properties['textureGroup']!=row['textureGroup']:raise ValueError('Native import changed original RGB channel packing')
            if digest(source)!=row['sha256']:raise ValueError('Original source input changed during native import')
            result=dict(row,path=str(target),SHA256=digest(target),sourceTGA=str(source),sourceTGASHA256=row['sha256'],properties=properties,command=command)
            write_json(job/'build/imports'/(source.stem+'.json'),result);return result
        with ThreadPoolExecutor(max_workers=2)as pool:results=list(pool.map(one,rows))
    finally:mod.ROOT=original_root
    proof=dict(schema='malemod.original-source-native-imports/1',textures=str(textures),texturesSHA256=digest(textures),files=results,
        nativeImported=True,allOriginalInputsUnchanged=True,RGBQualityColorPacking=True,cooked=False,globallyAdopted=False)
    write_json(job/'imports.json',proof);return proof


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--textures',type=Path,required=True);p.add_argument('--job',type=Path,required=True)
    p.add_argument('--run',action='store_true',help='Only after primary explicitly grants the native import lease')
    a=p.parse_args();print(json.dumps(run(a.textures,a.job)if a.run else dict(nativeImportPerformed=False,files=plan(a.textures,a.job)),indent=2))
