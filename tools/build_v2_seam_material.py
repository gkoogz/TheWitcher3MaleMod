"""Fresh texture/graph-only seam candidate, preserving all geometry and UVs."""
import argparse,copy,struct,shutil,json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import mod
from mod import ROOT,digest,read_json,write_json
from build_v2_anatomy_material import complete_depot,texture_properties
from v2_skin_material import GRAPH,state,inspect
from v2_fabric_material import rebuild,observed_name_entries,encoded_string

CODE='''float sourceSeamAntiLight(float offset,float4 albedo,float4 blendColor)
{ return offset*(1-saturate(albedo.b)); }'''

def seam_graph(source,target):
 raw=source.read_bytes();r,im,original,name,array,ptr=state(source);objects=copy.deepcopy(original)
 def ids(i,key):
  data=objects[i][2].get(key,('',b'\0\0\0\0'))[1];n,=struct.unpack_from('<I',data)
  return [struct.unpack_from('<i',data,4+j*4)[0]-1 for j in range(n)]
 def arr(i,key,values):objects[i][2][key]=('array:2,0,ptr:CGraphSocket'if key=='sockets'else'array:2,0,ptr:CGraphConnection'if key=='connections'else'array:2,0,ptr:CGraphBlock',struct.pack('<I',len(values))+b''.join(struct.pack('<i',v+1)for v in values))
 def socket(i,label):return next(s for s in array(i,'sockets')if name(s)==label)
 anti=next(i for i,o in enumerate(original)if'parameterName'in o[2]and name(i,'parameterName')=='AntiLightbleedScale')
 antiout=socket(anti,'Value');destinations=[ptr(e,'destination')for e in array(antiout,'connections')]
 ambient=next(i for i,o in enumerate(original)if'parameterName'in o[2]and name(i,'parameterName')=='Ambient')
 sampler=ptr(ptr(array(socket(ambient,'Texture'),'connections')[0],'destination'),'block');color=socket(sampler,'Color')
 template=next(i for i,o in enumerate(original)if o[0]=='CMaterialBlockCustomFunction'and b'sourceSpecular('in o[2].get('customCode',('',b''))[1])
 selected=[template]+array(template,'sockets');mapping={i:len(objects)+j for j,i in enumerate(selected)}
 for old in selected:
  node=copy.deepcopy(original[old]);node[2].pop('connections',None);node[2].pop('position',None)
  if 'sockets'in node[2]:node[2]['sockets']=('array:2,0,ptr:CGraphSocket',struct.pack('<I',len(array(old,'sockets')))+b''.join(struct.pack('<i',mapping[x]+1)for x in array(old,'sockets')))
  if 'block'in node[2]:node[2]['block']=('ptr:CGraphBlock',struct.pack('<i',mapping[ptr(old,'block')]+1))
  objects.append(node)
 objects[mapping[template]][2]['customCode']=('String',encoded_string(CODE))
 def rewire(input_id,output_id):
  for edge in ids(input_id,'connections'):
   other=struct.unpack('<i',objects[edge][2]['destination'][1])[0]-1
   arr(other,'connections',[e for e in ids(other,'connections')if struct.unpack('<i',objects[e][2]['destination'][1])[0]-1!=input_id])
  first=len(objects)
  for a,b in [(input_id,output_id),(output_id,input_id)]:
   node=copy.deepcopy(next(o for o in original if o[0]=='CGraphConnection'));node[2].clear();node[2].update(source=('ptr:CGraphSocket',struct.pack('<i',a+1)),destination=('ptr:CGraphSocket',struct.pack('<i',b+1)));objects.append(node)
  arr(input_id,'connections',[first]);arr(output_id,'connections',ids(output_id,'connections')+[first+1])
 for dest in destinations:rewire(dest,mapping[socket(template,'Out')])
 for arg,up in [('offset',antiout),('albedo',color),('blendColor',color)]:rewire(mapping[socket(template,arg)],up)
 root=next(i for i,o in enumerate(original)if o[0]=='CMaterialGraph');arr(root,'blocks',ids(root,'blocks')+[mapping[template]])
 hashes=observed_name_entries(source);target.write_bytes(rebuild(raw,objects,r.names,hashes));inspect(target)
 return dict(sourceSHA256=digest(source),SHA256=digest(target),seamAntiLightbleedScale='original*(1-seamWeight), exactstock0 atedge; original1 outside',geometryChanged=False,UVChanged=False)

def prepare(job,textures,source_job,compiled_graph_job=None):
 job=Path(job).absolute();source_job=Path(source_job).absolute()
 if job.exists()or not job.resolve().is_relative_to((ROOT/'v2/build/materials').resolve()):raise ValueError('Use a fresh owned seam job')
 proof=read_json(source_job/'intake.json');mod.copy_tree(source_job/'build/intake',job/'build/intake')
 for p in ['graph-compiled.json','graph-authored.json']:shutil.copy2(source_job/p,job/p)
 cfg=mod.settings();cfg['depot']=complete_depot(cfg);cfg['wcc']=ROOT/'v2/build/materials/anatomy-01/build/shaders-05/runtime/bin/x64_RedKit/wcc_lite.exe'
 graph=job/'build/intake'/GRAPH;graph_proof=seam_graph(source_job/'build/intake'/GRAPH,graph);write_json(job/'graph-authored.json',graph_proof);before_payload=state(graph)[2][0][3]
 bake=read_json(textures)
 if not bake.get('boundarySamplerConstraint'):raise ValueError('Sharededge sampler constraints not proved')
 prior=mod.ROOT;mod.ROOT=job
 try:
  if compiled_graph_job is not None:
   old=Path(compiled_graph_job);authored=read_json(old/'graph-authored.json');compiled=read_json(old/'graph-compiled.json')
   if authored['SHA256']!=digest(graph)or compiled['SHA256']!=digest(old/'build/intake'/GRAPH)or not compiled['nativeCompiled']:raise ValueError('Reusable resave is not the byte-identical authored seam graph')
   shutil.copy2(old/'build/intake'/GRAPH,graph);changed=before_payload!=state(graph)[2][0][3]
   if not changed:raise ValueError('Official seam graph compiled payload did not change')
   compiled=dict(compiled,compiledPayloadChanged=changed,reusedByteIdenticalAuthoredGraph=dict(job=str(old),authoredSHA256=authored['SHA256'],receiptSHA256=digest(old/'graph-compiled.json')));write_json(job/'graph-compiled.json',compiled)
  else:
   temp=job/'build/graph-resave-temp';temp.mkdir(parents=True)
   command=mod.run_wcc(cfg,'resave',['-tmpdir='+str(temp),'-path='+str(Path(GRAPH).parent),'-ext=w2mg','-nosourcecontrol','-ignorefileversion'],job/'build/intake','source-seam-graph-resave')
   args=command['args'];compiled=Path(args[args.index('-uncookDir')+1])/GRAPH;shutil.copy2(compiled,graph)
   changed=before_payload!=state(graph)[2][0][3]
   if not changed:raise ValueError('Official seam graph compiled payload did not change')
   write_json(job/'graph-compiled.json',dict(command=command,SHA256=digest(graph),nativeCompiled=True,compiledPayloadChanged=changed,inspection=inspect(graph)))
  import xml.etree.ElementTree as ET
  groups=ET.fromstring((cfg['depot']/'engine/textures/texturegroups.xml').read_bytes())
  for label in ['V2AnatomyColor','V2AnatomyNormalRGB']:
   if any(g.attrib.get('name')==label for g in groups):raise ValueError('Owned group collision')
   g=ET.SubElement(groups,'group',name=label)
   for k,v in [('compression','TCM_QualityColor'),('maxsize','4096'),('resizable','0'),('category','Characters')]:ET.SubElement(g,k,value=v)
  group_data=ET.tostring(groups,encoding='utf-8',xml_declaration=True)
  def one(row):
   source=Path(row['path']);target=job/'build/intake/characters/malemod/anatomy'/source.with_suffix('.xbm').name
   if digest(source)!=row['sha256']:raise ValueError('Fresh seam image changed')
   old=digest(target);scratch=job/'build/texture-import'/source.stem;config=scratch/'engine/textures/texturegroups.xml';config.parent.mkdir(parents=True,exist_ok=True);config.write_bytes(group_data)
   group='V2AnatomyNormalRGB'if row['role']=='Normal'else'V2AnatomyColor'
   command=mod.run_wcc(cfg,'import',['-depot=local','-file='+str(source),'-out='+str(target),'-texturegroup='+group],scratch,'seam-'+source.stem)
   prop=texture_properties(target)
   if prop['textureGroup']!=group or prop['compression']!='TCM_QualityColor':raise ValueError('Source seam transport changed channel packing')
   return dict(source=str(source),sourceSHA256=digest(source),path=str(target),SHA256=digest(target),previousSHA256=old,properties=prop,command=command,role=row['role'])
  with ThreadPoolExecutor(max_workers=2)as pool:imports=list(pool.map(one,[r for lod in bake['lods']for r in lod['files']]))
 finally:mod.ROOT=prior
 # Retain the prior closed inventory, recording every changed resource as an
 # explicit override. The regular combined cooker revalidates these hashes.
 overrides={r['path']:r for r in proof['overrides']}
 for row in imports:
  rel=Path(row['path']).relative_to(job/'build/intake').as_posix();overrides[rel]=dict(path=rel,previousSHA256=row['previousSHA256'],SHA256=row['SHA256'])
 overrides[GRAPH]=dict(path=GRAPH,previousSHA256=digest(source_job/'build/intake'/GRAPH),SHA256=digest(graph))
 proof['overrides']=list(overrides.values());proof['normalImports']=[r for r in imports if r['role']=='Normal'];proof['seamImports']=imports;proof['derivedSeam']=dict(job=str(source_job),intakeSHA256=digest(source_job/'intake.json'),texturesPath=str(textures),texturesSHA256=digest(textures),graph=graph_proof)
 write_json(job/'intake.json',proof);return proof

def prepare_normals(job,textures,source_job):
 """Derive only two native normal inputs; preserve the accepted seam graph."""
 import xml.etree.ElementTree as ET
 job=Path(job).absolute();source_job=Path(source_job).absolute();textures=Path(textures).absolute()
 if job.exists()or not job.resolve().is_relative_to((ROOT/'v2/build/materials').resolve()):raise ValueError('Use fresh owned normal-only material job')
 proof=read_json(source_job/'intake.json');bake=read_json(textures);previous=read_json(proof['derivedSeam']['texturesPath'])
 for lod in bake['lods']:
  old=next(x for x in previous['lods']if x['lod']==lod['lod'])
  for row in lod['files']:
   if row['role']!='Normal'and row['sha256']!=next(x['sha256']for x in old['files']if x['role']==row['role']):raise ValueError('Normal-only bake changed a different material channel')
 mod.copy_tree(source_job/'build/intake',job/'build/intake')
 for name in ['graph-authored.json','graph-compiled.json']:shutil.copy2(source_job/name,job/name)
 cfg=mod.settings();cfg['depot']=complete_depot(cfg);cfg['wcc']=ROOT/'v2/build/materials/anatomy-01/build/shaders-05/runtime/bin/x64_RedKit/wcc_lite.exe'
 groups=ET.fromstring((cfg['depot']/'engine/textures/texturegroups.xml').read_bytes());group='V2AnatomyNormalRGB'
 if any(g.attrib.get('name')==group for g in groups):raise ValueError('Owned normal group collision')
 g=ET.SubElement(groups,'group',name=group)
 for k,v in [('compression','TCM_QualityColor'),('maxsize','4096'),('resizable','0'),('category','Characters')]:ET.SubElement(g,k,value=v)
 group_data=ET.tostring(groups,encoding='utf-8',xml_declaration=True);prior=mod.ROOT;mod.ROOT=job
 try:
  def one(row):
   source=Path(row['path']);target=job/'build/intake/characters/malemod/anatomy'/source.with_suffix('.xbm').name
   if digest(source)!=row['sha256']:raise ValueError('Actual-frame normal image changed')
   old=digest(target);scratch=job/'build/texture-import'/source.stem;config=scratch/'engine/textures/texturegroups.xml';config.parent.mkdir(parents=True,exist_ok=True);config.write_bytes(group_data)
   command=mod.run_wcc(cfg,'import',['-depot=local','-file='+str(source),'-out='+str(target),'-texturegroup='+group],scratch,'actual-native-normal-'+source.stem);properties=texture_properties(target)
   if properties['compression']!='TCM_QualityColor'or properties['textureGroup']!=group:raise ValueError('Native normal channel transport changed')
   return dict(source=str(source),sourceSHA256=digest(source),path=str(target),SHA256=digest(target),previousSHA256=old,properties=properties,command=command,role='Normal')
  with ThreadPoolExecutor(max_workers=2)as pool:imports=list(pool.map(one,[r for lod in bake['lods']for r in lod['files']if r['role']=='Normal']))
 finally:mod.ROOT=prior
 overrides={r['path']:r for r in proof['overrides']}
 for row in imports:
  rel=Path(row['path']).relative_to(job/'build/intake').as_posix();overrides[rel]=dict(path=rel,previousSHA256=row['previousSHA256'],SHA256=row['SHA256'])
 updated={Path(r['path']).relative_to(job/'build/intake').as_posix():r for r in imports};allimports=[]
 for row in proof['seamImports']:
  rel=Path(row['path']).relative_to(source_job/'build/intake');entry=updated.get(rel.as_posix(),dict(row,path=str(job/'build/intake'/rel),copiedFrom=row['path']))
  if digest(Path(entry['path']))!=entry['SHA256']:raise ValueError('Copied nonnormal native input changed')
  allimports.append(entry)
 if digest(job/'build/intake'/GRAPH)!=digest(source_job/'build/intake'/GRAPH):raise ValueError('Normal-only candidate changed the graph')
 proof['overrides']=list(overrides.values());proof['normalImports']=imports;proof['seamImports']=allimports;proof['derivedSeam']=dict(job=str(source_job),intakeSHA256=digest(source_job/'intake.json'),texturesPath=str(textures),texturesSHA256=digest(textures),normalOnly=True,nativeFrameDonor=bake['nativeFrameDonor'],previous=proof['derivedSeam'])
 write_json(job/'intake.json',proof);return proof

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);p.add_argument('--textures',type=Path,required=True);p.add_argument('--source-job',type=Path,required=True);p.add_argument('--compiled-graph-job',type=Path);p.add_argument('--normal-only',action='store_true');a=p.parse_args();print(json.dumps(prepare_normals(a.job,a.textures,a.source_job)if a.normal_only else prepare(a.job,a.textures,a.source_job,a.compiled_graph_job),indent=2))
