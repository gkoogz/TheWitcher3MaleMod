"""Reject cooked pose graphs whose nodes exist but are disconnected."""
from pathlib import Path
import xml.etree.ElementTree as ET
from mod import digest


def verify_graph(path,stock_names=None,*,identity_root=None,transform_controls=False,parent_space='local'):
    if parent_space not in ('local','model','attached'):raise ValueError('Unknown parent pose space')
    if parent_space=='attached' and (transform_controls or identity_root is None):
        raise ValueError('Attached pose is a scale-only observed-root probe')
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
    seen=set();scales=[];align=[];terminal=False;channels=[];deformations=[]
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
            deformations.append((bone,'scale'))
        elif t in ('CBehaviorGraphTranslateBoneNode','CBehaviorGraphRotateBoneNode'):
            if not transform_controls or align:raise ValueError('Unexpected scalar deformation stage')
            bone=value(current,'boneName')
            operation='translate' if t=='CBehaviorGraphTranslateBoneNode' else 'rotate'
            control=linked(current,'cachedValueNode' if operation=='translate' else 'cachedControlVariableNode')
            variable=value(control,'variableName')
            if control.get('class')!='CBehaviorGraphVariableNode' or variable not in [bone+'_'+operation+'_'+axis for axis in 'xyz']:
                raise ValueError('Scalar control does not match its bone/operation/axis')
            axis=variable[-1]
            if value(current,'scale')!='1' or (operation=='rotate' and
                    (value(current,'axis')!='ROTAXIS_'+axis.upper() or value(current,'localSpace')!='true')):
                raise ValueError('Scalar deformation units/space changed')
            if operation=='translate':
                for component in 'XYZ':
                    observed=current.findtext('./properties/prop[@name="axis"]/object/properties/prop[@name="'+component+'"]')
                    if observed is None or float(observed)!=float(component.lower()==axis):
                        raise ValueError('Translation axis differs from the named control')
            channels.append(variable)
            deformations.append((bone,operation+'_'+axis))
        elif t=='CBehaviorGraphConstraintNodeParentAlign':
            if parent_space=='attached':raise ValueError('Attached pose must not reread parent buffers')
            bone=value(current,'bone')
            if bone!=value(current,'parentBone') or value(current,'localSpace')!=('true' if parent_space=='local' else 'false'):
                raise ValueError('Stock pose parent alignment changed')
            align.append(bone)
        elif t=='CBehaviorGraphConstraintReset':
            if parent_space!='attached' or align:raise ValueError('Unexpected pose reset')
            bone=value(current,'bone')
            if value(current,'translation')!='false' or value(current,'rotation')!='false' or value(current,'scale')!='true':
                raise ValueError('Attached-pose reset must preserve position/rotation')
            if current.find('./properties/prop[@name="cachedControlValueNode"]/reference') is not None:
                raise ValueError('Scale reset must be unconditional')
            deformations.append((bone,'reset_scale'))
        elif t==('CBehaviorGraphInputNode' if parent_space=='attached' else 'CBehaviorGraphTPoseNode'):
            terminal=True;break
        else:raise ValueError('Unexpected cooked pose node '+str(t))
        current=linked(current,'cachedInputNode')
    alignment_count=0 if parent_space=='attached' else 94-int(identity_root is not None)
    if not terminal or len(align)!=alignment_count or len(scales)!=10 or len(set(align+scales))!=alignment_count+10:
        raise ValueError('Cooked graph does not reach the declared stock and authored joints')
    expected=['mm_shaft_'+str(i).zfill(2) for i in range(8)]+['mm_scrotum_l','mm_scrotum_r']
    if scales!=expected[::-1]:raise ValueError('Authored scale chain order changed')
    operations=(['reset_scale'] if parent_space=='attached' else [])+['scale']+([operation+'_'+axis for operation in ('translate','rotate') for axis in 'xyz'] if transform_controls else [])
    if deformations!=[(bone,op) for bone in expected for op in operations][::-1]:
        raise ValueError('Deformation node chain order changed')
    if identity_root is not None and (stock_names is None or list(stock_names)[0]!=identity_root or identity_root in align):
        raise ValueError('Identity root must be the observed bone zero, never aligned')
    if stock_names is not None and parent_space!='attached' and align!=[n for n in stock_names if n!=identity_root][::-1]:
        raise ValueError('Pose alignment does not match the observed stock rig names/order')
    return dict(cookedPoseConnectionsVerified=True,stockAlignmentNodes=alignment_count,authoredScaleNodes=10,
        authoredScalarNodes=len(channels),identityRoot=identity_root,
        parentPoseSpace=parent_space,
        connectedPoseNodes=len(seen),dumpSHA256=digest(path),observedGameplay=False)
