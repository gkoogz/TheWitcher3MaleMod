"""Native mesh pair controls and size-matched physical material pivots."""
import copy,json,re,uuid,base64
from pathlib import Path
import numpy as np
from mod import ROOT,read_json,digest,write_json
from prepare_motion import scalar
from fixed_physics import generate

def morph_entity(source,states,bank=None):
    result=copy.deepcopy(source)
    def handle(kind,path):
        return dict(_type='handle:'+kind,_vars=dict(_chunkHandle=scalar('bool',False),_className=scalar('string',kind),_depotPath=scalar('string',path.replace('/','\\')),_flags=scalar('uint16',0)))
    def edit(resource):
        chunks=resource['_chunks'];key=next(k for k,c in chunks.items() if c['_type']=='CMeshComponent');old=chunks.pop(key)
        parent=old['_parentKey'];refs=[]
        for i,(a,b) in enumerate(zip(states,states[1:])):
            ui=a['ui'];fraction=0.0
            name='CMorphedMeshComponent #'+str(20+i);c=copy.deepcopy(old);c.update(_type='CMorphedMeshComponent',_key=name)
            v=c['_vars'];v.pop('mesh');v['guid']=scalar('CGUID',base64.b64encode(uuid.uuid4().bytes_le).decode())
            v['name']=scalar('String','MaleModOverallPair_'+str(i));v['morphComponentId']=scalar('CName','MaleModOverallPair_'+str(i))
            v['morphSource']=handle('CMesh',a['resource']);v['morphTarget']=handle('CMesh',b['resource']);v['morphRatio']=scalar('Float',fraction)
            v['useControlTexturesForMorph']=scalar('Bool',False)
            v['useMorphBlendMaterials']=dict(_type='array:2,0,Bool',_elements=[scalar('Bool',False)])
            v['drawableFlags']=scalar('EDrawableFlags','DF_IsVisible|DF_CastShadows|DF_NoDissolves' if a['ui']==50 else 'DF_CastShadows|DF_NoDissolves')
            if bank:
                points=np.vstack([np.load(bank/f'ui-{s["ui"]}-lod0.npz')['points'] for s in (a,b)])/100
                for label,coords in [('Min',points.min(0)-.5),('Max',points.max(0)+.5)]:
                    for axis,value in zip('XYZ',coords):v['boundingBox']['_vars'][label]['_vars'][axis]['_value']=float(value)
            chunks[name]=c;refs.append(name)
        template=next(c for c in chunks.values() if c['_type']=='CItemEntity')['_vars']['Components']
        prototype=next(e for e in template['_elements'] if e['_vars']['_reference']['_value']==key)
        template['_elements']=[e for e in template['_elements'] if e['_vars']['_reference']['_value']!=key]
        for name in refs:
            r=copy.deepcopy(prototype);r['_vars']['_reference']['_value']=name;template['_elements'].append(r)
        for c in list(chunks.values()):
            for value in c['_vars'].values():
                if value.get('_type')=='CR2W':edit(value)
    edit(result);return result

VECTOR_FIELDS={'restPoints':21,'jointRestPoints':10,'restDirections':8,'radii':21,'anchorOffsets':2,'materialOffsets':2,'headRestCenter':1,'attachmentRestTangent':1,'lobeRestFrames':6}
FLOAT_FIELDS={'lengths':11,'bendCompliance':10,'tetherRest':2,'tetherLimit':2,'thighRadii':2}

def augment(base,rig,job,cage,bank,runtime):
    record=read_json(bank/'overall.json');native=read_json(bank/'native-bank.json')
    if not native['complete']:raise ValueError('Native Overall bank incomplete')
    if [s['ui'] for s in native['states']]!=[s['ui'] for s in record['states']]:raise ValueError('Bank keys differ')
    lines=[];keys=[s['ui'] for s in record['states']];n=len(keys)
    for field,size in VECTOR_FIELDS.items():lines.append(f'overall_{field}.Resize({size*n});')
    for field,size in FLOAT_FIELDS.items():lines.append(f'overall_{field}.Resize({size*n});')
    lines.append(f'overallKeys.Resize({n});')
    lines.append('overallMeshes.Resize(10);')
    lines.extend(f'overallMeshes[{i}] = (CMorphedMeshComponent)GetEntity().GetComponent("MaleModOverallPair_{i}");' for i in range(10))
    for k,state in enumerate(record['states']):
        folder=job/('physics-ui-'+str(state['ui']));folder.mkdir()
        text,receipt=generate(base,rig,folder,cage=cage,mechanics=state['mechanics'],surface_points=np.load(bank/f'ui-{state["ui"]}-lod0.npz')['points'])
        lines.append(f'overallKeys[{k}] = {state["ui"]}.0;')
        for field,size in {**VECTOR_FIELDS,**FLOAT_FIELDS}.items():
            if field=='lobeRestFrames':
                assignments=re.findall(r'lobeRestFrames\[(\d+)\]\.([XYZ]) = (Vector\([^;]+\));',text)
                values={int(i)*3+'XYZ'.index(a):v for i,a,v in assignments}
            elif size==1 and field in VECTOR_FIELDS:
                values={0:re.search(r'\b'+field+r' = (Vector\([^;]+\));',text)[1]}
            else:
                values={int(i):v for i,v in re.findall(r'\b'+field+r'\[(\d+)\] = ([^;]+);',text)}
            if len(values)!=size:raise ValueError('Incomplete physics bank '+field)
            lines.extend(f'overall_{field}[{k*size+i}] = {values[i]};' for i in range(size))
    declarations=['private var overallKeys : array<float>;','private var overallValue : float;','private var overallMeshes : array<CMorphedMeshComponent>;']
    declarations += [f'private var overall_{f} : array<Vector>;' for f in VECTOR_FIELDS]
    declarations += [f'private var overall_{f} : array<float>;' for f in FLOAT_FIELDS]
    methods=[];calls=[]
    for start in range(0,len(lines),64):
        name='InitializeOverallPart'+str(start//64);calls.append(name+'();')
        methods.append('private function '+name+'() {\n'+'\n'.join(lines[start:start+64])+'\n}')
    interpolation=[]
    for field,size in {**VECTOR_FIELDS,**FLOAT_FIELDS}.items():
        if field=='lobeRestFrames':
            for i in range(2):
                for j,axis in enumerate('XYZ'):
                    ix=i*3+j;interpolation.append(f'lobeRestFrames[{i}].{axis} = VecNormalize(overall_{field}[slot*6+{ix}] + (overall_{field}[(slot+1)*6+{ix}]-overall_{field}[slot*6+{ix}])*fraction);')
                interpolation += [f'lobeRestFrames[{i}].Z = VecNormalize(VecCross(lobeRestFrames[{i}].X,lobeRestFrames[{i}].Y));',f'lobeRestFrames[{i}].Y = VecNormalize(VecCross(lobeRestFrames[{i}].Z,lobeRestFrames[{i}].X));']
        else:
            for i in range(size):
                target=field if size==1 and field in VECTOR_FIELDS else f'{field}[{i}]'
                expr=f'overall_{field}[slot*{size}+{i}] + (overall_{field}[(slot+1)*{size}+{i}]-overall_{field}[slot*{size}+{i}])*fraction'
                if field in ('restDirections','attachmentRestTangent'):expr='VecNormalize('+expr+')'
                interpolation.append(target+' = '+expr+';')
    interpolation_methods=[];apply_calls=[]
    for start in range(0,len(interpolation),48):
        name='InterpolateOverallPart'+str(start//48);apply_calls.append(name+'(slot,fraction);')
        interpolation_methods.append('private function '+name+'(slot : int, fraction : float) {\n'+'\n'.join(interpolation[start:start+48])+'\n}')
    body=(ROOT/'probes/runtime/overall.ws.inc').read_text().replace('// BANK_INITIALIZERS','\n'.join(calls)).replace('// INTERPOLATE','\n'.join(apply_calls))
    runtime=runtime.replace('    private var headRestCenter, headRotation : Vector;','    private var headRestCenter, headRotation : Vector;\n'+'\n'.join(declarations))
    runtime=runtime.replace('reason = "fixed rest attached";', 'InitializeOverall();\n        reason = "overall attached";')
    runtime=runtime.replace('// PHYSICS_METHODS','// PHYSICS_METHODS') # numerical kernels were emitted by generate()
    where=runtime.index('    private function Point(')
    runtime=runtime[:where]+'\n'.join(methods+interpolation_methods)+'\n'+body+'\n'+runtime[where:]
    runtime+='\n'+(ROOT/'probes/runtime/overallMenu.ws.inc').read_text()
    receipt=dict(keys=keys,neutral=50,minimum=1,maximum=100,bank=bank.relative_to(ROOT).as_posix(),bankSHA256=digest(bank/'overall.json'),nativeBankSHA256=digest(bank/'native-bank.json'),states=native['states'],method='native morphRatio property and visibility-triggered render-proxy refresh on size edits; 10 adjacent pairs over 11 keys; size-matched physics',physicsNodes=21,renderJoints=10,perFrameVertexLoop=False,linearBetweenKeys=True,nativeComponents=10,visibleComponents=1,observedGameplay=False)
    receipt['verificationSHA256']=digest(bank/'verification.json') if (bank/'verification.json').exists() else None
    receipt['normalPolicy']=record['normalPolicy']
    write_json(job/'overall-controls.json',receipt);return runtime,receipt
