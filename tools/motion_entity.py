"""Create a native candidate entity; never cooks, installs or edits stock files."""
import copy
import json
from pathlib import Path
import subprocess
import sys
from mod import ROOT,settings,write_json
from prepare_motion import scalar,array,reference,handle


def make_entity(job):
    job=Path(job).resolve()
    if not job.is_relative_to(ROOT/'build/motion'):raise ValueError('Expected an owned motion job')
    cfg=settings();converter=ROOT/'build/research/wkit-current/MaleModCR2W.exe'
    source=cfg['redkit']/'r4data/items/bodyparts/geralt_items/legs/bare/l_01_mg__body.w2ent'
    bare=job/'stock-bare.json'
    subprocess.run([str(converter),'export',str(source),str(bare)],check=True,capture_output=True)
    shirt_source=cfg['redkit']/'r4data/items/bodyparts/geralt_items/trunk/witcher_shirt/t_01_mg__shirt.w2ent'
    shirt_file=job/'stock-shirt.json'
    subprocess.run([str(converter),'export',str(shirt_source),str(shirt_file)],check=True,capture_output=True)
    entity=json.loads(bare.read_text());shirt=json.loads(shirt_file.read_text())
    templates=shirt['_chunks']

    def edit(resource):
        chunks=resource['_chunks'];prefix=resource['_extension']
        item_key=next(k for k,c in chunks.items() if c['_type']=='CItemEntity')
        mesh_key=next(k for k,c in chunks.items() if c['_type']=='CMeshComponent')
        offset=len(chunks);dangle_key=prefix+'CAnimDangleComponent #'+str(offset)
        skin_key=prefix+'CMeshSkinningAttachment #'+str(offset+1)
        constraint_key=prefix+'CAnimDangleConstraint_Dyng #'+str(offset+2)
        mesh=chunks[mesh_key]['_vars']
        mesh['mesh']['_vars']['_depotPath']['_value']='characters\\malemod\\body\\geralt_motion.w2mesh'
        mesh['transformParent']=reference('ptr:CHardAttachment',skin_key)
        mesh['AttachmentsReference']=array('array:0,0,handle:IAttachment',[handle('IAttachment',skin_key)])
        dangle=copy.deepcopy(templates['CAnimDangleComponent #8'])
        dangle.update(_key=dangle_key,_parentKey=item_key)
        v=dangle['_vars'];v['name']=scalar('String','MaleModMotion')
        v['constraint']=reference('ptr:IAnimDangleConstraint',constraint_key)
        v['AttachmentsChild']=array('array:0,0,handle:IAttachment',[handle('IAttachment',skin_key)])
        v['debugRender']=scalar('Bool',False)
        skin=copy.deepcopy(templates['CMeshSkinningAttachment #9'])
        skin.update(_key=skin_key,_parentKey=dangle_key)
        skin['_vars']={'parent':reference('ptr:CNode',dangle_key),'child':reference('ptr:CNode',mesh_key)}
        constraint=copy.deepcopy(templates['CAnimDangleConstraint_Dyng #10'])
        constraint.update(_key=constraint_key,_parentKey=dangle_key)
        v=constraint['_vars'];v['dyng']['_vars']['_depotPath']['_value']='characters\\malemod\\physics\\geralt_motion.w3dyng'
        v['gravity']=scalar('Float',.3);v['dampening']=scalar('Float',.95);v['speed']=scalar('Float',.4)
        v['planeCollision']=scalar('Bool',False);v['max_links_iterations']=scalar('Int32',12)
        chunks.update({dangle_key:dangle,skin_key:skin,constraint_key:constraint})
        chunks[item_key]['_vars']['Components']['_elements'].append(reference('ptr:CComponent',dangle_key))
        for chunk in list(chunks.values()):
            for value in chunk['_vars'].values():
                if value.get('_type')=='CR2W':edit(value)
    edit(entity)
    output=job/'items/bodyparts/geralt_items/legs/bare/l_01_mg__body_underwear.w2ent'
    output.parent.mkdir(parents=True)
    recipe=job/'motion-entity.json';write_json(recipe,entity)
    subprocess.run([str(converter),'import',str(recipe),str(output)],check=True,capture_output=True)
    # Keep the custom-class candidate separate from the stock-class cook input.
    def script_binding(resource):
        old=next(k for k,c in resource['_chunks'].items() if c['_type']=='CItemEntity')
        new=old.replace('CItemEntity','MaleModPhysicsItem')
        text=json.dumps(resource).replace(old,new)
        resource=json.loads(text);item=resource['_chunks'][new];item['_type']='MaleModPhysicsItem'
        target=next(k for k,c in resource['_chunks'].items() if c['_type']=='CAnimDangleConstraint_Dyng')
        item['_vars']['dynamicConstraint']=handle('CAnimDangleConstraint_Dyng',target)
        for c in resource['_chunks'].values():
            if c['_type']=='CEntityTemplate':c['_vars']['entityClass']=scalar('CName','MaleModPhysicsItem')
            for key,value in list(c['_vars'].items()):
                if value.get('_type')=='CR2W':c['_vars'][key]=script_binding(value)
        return resource
    custom=script_binding(copy.deepcopy(entity));candidate=job/'scripted-motion-entity.json';write_json(candidate,custom)
    subprocess.run([str(converter),'import',str(candidate),str(job/'scripted-motion-entity.w2ent')],check=True,capture_output=True)
    print(output);return output


if __name__=='__main__':make_entity(sys.argv[1])
