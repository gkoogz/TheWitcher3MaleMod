"""Reject cooked pose graphs whose nodes exist but are disconnected."""
from pathlib import Path
import xml.etree.ElementTree as ET
from mod import digest


def verify_graph(path,stock_names=None):
    path=Path(path)
    root=ET.parse(path).getroot()
    objects={o.get('id'):o for o in root.findall('.//object') if o.get('id') is not None}
    def kind(name):return [o for o in objects.values() if o.get('class')==name]
    def value(o,name):return o.findtext('./properties/prop[@name="'+name+'"]')
    def linked(o,name):
        p=o.find('./properties/prop[@name="'+name+'"]/reference')
        if p is None or p.get('id') not in objects:
            raise ValueError('Null or missing cooked '+o.get('class')+'.'+name)
        return objects[p.get('id')]
    # Native graph construction retains an unused top-level/output pair with
    # node id 0 alongside the serialized authored container. Only that exact
    # disconnected constructor artifact is excluded, never an authored output.
    outputs=[o for o in kind('CBehaviorGraphOutputNode') if value(o,'id')!='0']
    defaults=[o for o in kind('CBehaviorGraphOutputNode') if value(o,'id')=='0']
    if len(defaults)>1 or any(o.find('./properties/prop[@name="cachedInputNode"]/reference') is not None for o in defaults):
        raise ValueError('Unexpected extra native output')
    if len(outputs)!=1:raise ValueError('Expected one native graph output')
    current=linked(outputs[0],'cachedInputNode')
    seen=set();scales=[];align=[];terminal=False
    while True:
        if current.get('id') in seen:raise ValueError('Cyclic cooked pose chain')
        seen.add(current.get('id'))
        t=current.get('class')
        if t=='CBehaviorGraphScaleBoneNode':
            if align:raise ValueError('Scale nodes must follow inherited stock pose')
            bone=value(current,'boneName');control=linked(current,'cachedControlVariableNode')
            if control.get('class')!='CBehaviorGraphVectorVariableNode' or value(control,'variableName')!=bone+'_scale':
                raise ValueError('Scale control is not bound to its named vector variable')
            scales.append(bone)
        elif t=='CBehaviorGraphConstraintNodeParentAlign':
            bone=value(current,'bone')
            if bone!=value(current,'parentBone') or value(current,'localSpace')!='true':
                raise ValueError('Stock pose parent alignment changed')
            align.append(bone)
        elif t=='CBehaviorGraphTPoseNode':terminal=True;break
        else:raise ValueError('Unexpected cooked pose node '+str(t))
        current=linked(current,'cachedInputNode')
    if not terminal or len(align)!=94 or len(scales)!=10 or len(set(align+scales))!=104:
        raise ValueError('Cooked graph does not reach all 94 stock and 10 authored joints')
    expected=['mm_shaft_'+str(i).zfill(2) for i in range(8)]+['mm_scrotum_l','mm_scrotum_r']
    if scales!=expected[::-1]:raise ValueError('Authored scale chain order changed')
    if stock_names is not None and align!=list(stock_names)[::-1]:
        raise ValueError('Pose alignment does not match the observed stock rig names/order')
    return dict(cookedPoseConnectionsVerified=True,stockAlignmentNodes=94,authoredScaleNodes=10,
        connectedPoseNodes=len(seen),dumpSHA256=digest(path),observedGameplay=False)
