"""Check the native dumper's instantiated controller/constraint graph."""
from pathlib import Path
import xml.etree.ElementTree as ET
from mod import digest

def verify_binding(path):
    path=Path(path)
    root=ET.parse(path).getroot()
    objects=root.findall('.//object')
    def one(kind):
        found=[x for x in objects if x.get('class')==kind and x.get('id') is not None]
        if len(found)!=1:raise ValueError('Expected one cooked '+kind)
        return found[0]
    item=one('MaleModMotionComponent');component=one('CAnimDangleComponent')
    constraint=one('CAnimDangleConstraint_Dyng');mesh=one('CMeshComponent')
    link=one('CMeshSkinningAttachment')
    def ref(node,prop):
        p=node.find('./properties/prop[@name="'+prop+'"]')
        if p is None:raise ValueError('Missing native property '+prop)
        r=p.find('reference')
        if r is None:raise ValueError('Null native reference '+prop)
        return p,r.get('id')
    p,binding=ref(item,'dynamicConstraint')
    if p.get('scripted')!='1' or binding!=constraint.get('id'):
        raise ValueError('Script handle did not survive cooking')
    if ref(component,'constraint')[1]!=binding:raise ValueError('Script and component point to different constraints')
    if ref(link,'parent')[1]!=component.get('id') or ref(link,'child')[1]!=mesh.get('id'):
        raise ValueError('Motion output is not attached to the mesh')
    return {'cookedControllerBindingVerified':True,'dumpSHA256':digest(path),
            'sameConstraintReference':True,'meshSkinningAttachmentVerified':True,
            'runtimeHandleBindingVerified':False,'observedGameplay':False}
