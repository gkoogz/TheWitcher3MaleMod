"""Check the native dumper's instantiated controller/constraint graph."""
from pathlib import Path
import xml.etree.ElementTree as ET
from mod import digest

def verify_binding(path,output='dangle',require_late=False):
    if output not in ('dangle','direct','player'):raise ValueError('Unknown motion output')
    path=Path(path)
    root=ET.parse(path).getroot()
    objects=root.findall('.//object')
    def one(kind):
        found=[x for x in objects if x.get('class')==kind and x.get('id') is not None]
        if len(found)!=1:raise ValueError('Expected one cooked '+kind)
        return found[0]
    item=one('MaleModMotionComponent')
    component=one('CAnimDangleComponent') if output!='player' else None
    constraint=one('CAnimDangleConstraint_Dyng')
    morphs=[o for o in objects if o.get('class')=='CMorphedMeshComponent' and o.get('id') is not None]
    mesh=morphs[0] if morphs else one('CMeshComponent')
    morph_evidence={}
    if morphs:
        if output!='player' or len(morphs)!=10:raise ValueError('Expected ten native player Overall pairs')
        if any(o.get('class')=='CMorphedMeshManagerComponent' and o.get('id') is not None for o in objects):raise ValueError('Endpoint manager would overwrite authored fractions')
        if any(o.get('class')=='CMeshComponent' and o.get('id') is not None for o in objects):raise ValueError('Duplicate original body mesh')
        pairs=[];visible=[]
        for i in range(10):
            found=[m for m in morphs if m.findtext('./properties/prop[@name="name"]')=='MaleModOverallPair_'+str(i)]
            if len(found)!=1:raise ValueError('Missing named Overall pair')
            m=found[0]
            a=m.find('./properties/prop[@name="morphSource"]/resource');b=m.find('./properties/prop[@name="morphTarget"]/resource')
            if a is None or b is None or a.get('class')!='CMesh' or b.get('class')!='CMesh':raise ValueError('Lost native morph resources')
            if m.findtext('./properties/prop[@name="useControlTexturesForMorph"]')!='false':raise ValueError('Unexpected textured morph')
            if m.find('./properties/prop[@name="transformParent"]/reference') is not None:raise ValueError('Morph pair has another transform parent')
            flags=m.findtext('./properties/prop[@name="drawableFlags"]') or ''
            if 'DF_IsVisible' in flags:visible.append(i)
            pairs.append(dict(source=a.get('path').replace('\\','/'),target=b.get('path').replace('\\','/'),ratio=float(m.findtext('./properties/prop[@name="morphRatio"]'))))
        if visible!=[5]:raise ValueError('Default must show only neutral Overall 50')
        morph_evidence=dict(cookedOverallMorphBindingVerified=True,overallPairs=pairs,visibleDefaultPair=5)
    link=one('CMeshSkinningAttachment') if output!='player' else None
    def ref(node,prop):
        p=node.find('./properties/prop[@name="'+prop+'"]')
        if p is None:raise ValueError('Missing native property '+prop)
        r=p.find('reference')
        if r is None:raise ValueError('Null native reference '+prop)
        return p,r.get('id')
    p,binding=ref(item,'dynamicConstraint')
    if p.get('scripted')!='1' or binding!=constraint.get('id'):
        raise ValueError('Script handle did not survive cooking')
    if output=='player':
        if require_late:raise ValueError('Player layer must append, never activate helper slots')
        if any(o.get('class') in ('CAnimatedComponent','CAnimDangleComponent','CMeshSkinningAttachment') and o.get('id') is not None for o in objects):
            raise ValueError('Player output must retain orphan stock-style appearance mesh; no second sampler')
        if mesh.find('./properties/prop[@name="transformParent"]/reference') is not None:
            raise ValueError('Player appearance mesh has an authored transform parent')
        graph_prop=item.find('./properties/prop[@name="deformationGraph"]')
        graph=graph_prop.find('resource') if graph_prop is not None else None
        if graph is None or graph_prop.get('scripted')!='1' or graph.get('path')!='characters\\malemod\\behavior\\deformation.w2beh':
            raise ValueError('Player layer controller lost its owned graph handle')
        return dict(cookedControllerBindingVerified=True,sameConstraintReference=True,
            cookedDeformationBindingVerified=True,deformationOutput=output,
            cookedPlayerStackBindingVerified=True,stockAppearanceAutobindingExpected=True,
            meshSkinningAttachmentVerified=False,runtimeHandleBindingVerified=False,
            observedGameplay=False,dumpSHA256=digest(path),**morph_evidence)
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
        if require_late:
            slots=helper.findall('./properties/prop[@name="behaviorInstanceSlots"]/array/element/object/properties')
            names=[slot.findtext('./prop[@name="instanceName"]') for slot in slots]
            if names!=['MaleModDeformation','MaleModDeformationLate']:
                raise ValueError('Late graph requires exactly the ordered initial and delayed slots')
            for slot in slots:
                if slot.findtext('./prop[@name="alwaysOnTopOfStack"]')!='false':
                    raise ValueError('Initial graph must not override delayed graph activation')
                resource=slot.find('./prop[@name="graph"]/resource')
                if resource is None or resource.get('path')!='characters\\malemod\\behavior\\deformation.w2beh':
                    raise ValueError('Late graph slot lost its graph resource')
            evidence['cookedLateGraphSlotsVerified']=True
        evidence.update(cookedDeformationBindingVerified=True,deformationOutput=output,
            deformationParentPoseObserved=False,liveScaleObserved=False,dangleScaleCompatibilityObserved=False)
    elif output=='direct' or require_late:raise ValueError('Direct/late output lacks its deformation root')
    return evidence
