"""Check the native dumper's instantiated controller/constraint graph."""
from pathlib import Path
import xml.etree.ElementTree as ET
from mod import digest

def verify_binding(path,output='dangle'):
    if output not in ('dangle','direct'):raise ValueError('Unknown motion output')
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
    if (output=='dangle' and ref(link,'parent')[1]!=component.get('id')) or ref(link,'child')[1]!=mesh.get('id'):
        raise ValueError('Motion output is not attached to the mesh')
    evidence={'cookedControllerBindingVerified':True,'dumpSHA256':digest(path),
            'sameConstraintReference':True,'meshSkinningAttachmentVerified':True,
            'runtimeHandleBindingVerified':False,'observedGameplay':False}
    helpers=[x for x in objects if x.get('class')=='CAnimatedComponent' and x.get('id') is not None
             and x.find('./properties/prop[@name="name"]') is not None
             and x.find('./properties/prop[@name="name"]').text=='MaleModDeformation']
    if helpers:
        if len(helpers)!=1:raise ValueError('Expected one deformation root')
        helper=helpers[0]
        if output=='dangle':
            attachment=one('CAnimatedAttachment')
            if ref(attachment,'parent')[1]!=helper.get('id') or ref(attachment,'child')[1]!=component.get('id'):
                raise ValueError('Deformation root does not feed the dangle component')
            if ref(component,'transformParent')[1]!=attachment.get('id'):
                raise ValueError('Dangle transform parent disagrees with animated attachment')
        elif ref(link,'parent')[1]!=helper.get('id'):
            raise ValueError('Direct deformation root does not feed the mesh')
        rig=helper.find('./properties/prop[@name="skeleton"]/resource')
        graph=helper.find('./properties/prop[@name="behaviorInstanceSlots"]//prop[@name="graph"]/resource')
        if rig is None or rig.get('path')!='characters\\malemod\\physics\\deformation.w2rig':
            raise ValueError('Deformation skeleton handle is missing or wrong')
        if graph is None or graph.get('path')!='characters\\malemod\\behavior\\deformation.w2beh':
            raise ValueError('Deformation graph handle is missing or wrong')
        evidence.update(cookedDeformationBindingVerified=True,deformationOutput=output,
            deformationParentPoseObserved=False,liveScaleObserved=False,dangleScaleCompatibilityObserved=False)
    elif output=='direct':raise ValueError('Direct output lacks its deformation root')
    return evidence
