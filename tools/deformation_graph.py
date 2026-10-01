"""Author an adapter-owned skeletal deformation graph from observed rig names.

ParentAlign modes read the observed parent stream. Input mode requires an
additional player-stack layer; ordinary helper stacks reset to reference pose.
Vector variables change only the authored joints' local scale.
The caller owns native verification and gameplay evidence.
"""
import copy
from prepare_motion import scalar, array, reference, handle, vector


def deformation_graph(template, stock_names, controlled_names, *, transform_controls=False,
                      identity_root=None,parent_space='local'):
    if parent_space not in ('local','model','attached'):raise ValueError('Unknown observed parent pose space')
    if parent_space=='attached' and (transform_controls or identity_root is None):
        raise ValueError('Attached-pose probe requires observed root and scale-only controls')
    if not stock_names or len(set(stock_names + controlled_names)) != len(stock_names + controlled_names):
        raise ValueError('Rig names must be observed, distinct and nonempty')
    result = {k: copy.deepcopy(v) for k, v in template.items() if k != '_chunks'}
    chunks = {}

    def node(kind, parent, values):
        key = kind + ' #' + str(len(chunks))
        chunks[key] = dict(_type=kind, _key=key, _parentKey=parent, _flags=0, _vars=values)
        return key

    root = node('CBehaviorGraph', '', {})
    top = node('CBehaviorGraphTopLevelNode', root, {'id': scalar('Uint32', 1)})
    pose = node('CBehaviorGraphInputNode' if parent_space=='attached' else 'CBehaviorGraphTPoseNode',
                top, {'id': scalar('Uint32', 2)})
    nodes = [pose]
    variables = []
    scalar_variables = []
    for name in stock_names:
        if parent_space=='attached':
            # InputNode preserves the previous graph output. An additional
            # player layer is required: PrepareForSample resets the first graph
            # to reference pose, so this must never be a helper's first graph.
            continue
        if name == identity_root:
            # Native attached components explicitly clear bone zero after
            # copying the parent pose. Do not reintroduce extracted root motion.
            # Caller must verify this is the observed identity rig root.
            continue
        pose = node('CBehaviorGraphConstraintNodeParentAlign', top, {
            'id': scalar('Uint32', len(nodes) + 2),
            'bone': scalar('String', name), 'parentBone': scalar('String', name),
            'localSpace': scalar('Bool', parent_space=='local'),
            'cachedInputNode': reference('ptr:CBehaviorGraphNode', pose)})
        nodes.append(pose)
    for i, name in enumerate(controlled_names):
        if parent_space=='attached':
            # ScaleBone multiplies incoming scale. Reset only authored scale;
            # preserve stock output and authored translations/rotations.
            pose=node('CBehaviorGraphConstraintReset',top,{
                'id':scalar('Uint32',len(nodes)+2), 'bone':scalar('String',name),
                'translation':scalar('Bool',False),'rotation':scalar('Bool',False),
                'scale':scalar('Bool',True),
                'cachedInputNode':reference('ptr:CBehaviorGraphNode',pose)})
            nodes.append(pose)
        variable_name = name + '_scale'
        control = node('CBehaviorGraphVectorVariableNode', top, {
            'id': scalar('Uint32', len(nodes) + 2),
            'variableName': scalar('CName', variable_name)})
        nodes.append(control)
        pose = node('CBehaviorGraphScaleBoneNode', top, {
            'id': scalar('Uint32', len(nodes) + 2), 'boneName': scalar('String', name),
            'scale': vector('Vector', [1, 1, 1, 0]),
            'cachedInputNode': reference('ptr:CBehaviorGraphNode', pose),
            'cachedControlVariableNode': reference('ptr:CBehaviorGraphVectorValueNode', control)})
        nodes.append(pose)
        variable = node('CBehaviorVectorVariable', root, {
            'name': scalar('CName', variable_name), 'varIndex': scalar('Uint32', i),
            'value': vector('Vector', [1, 1, 1, 0]),
            'defaultValue': vector('Vector', [1, 1, 1, 0])})
        variables.append({'_type': 'IdHandle', '_vars': {
            'handlename': scalar('CName', variable_name),
            'handle': handle('CBehaviorVariable', variable)}})
        if transform_controls:
            for operation in ('translate', 'rotate'):
                for axis in 'XYZ':
                    variable_name = name+'_'+operation+'_'+axis.lower()
                    control = node('CBehaviorGraphVariableNode', top, {
                        'id':scalar('Uint32',len(nodes)+2),
                        'variableName':scalar('CName',variable_name)})
                    nodes.append(control)
                    values={'id':scalar('Uint32',len(nodes)+2), 'boneName':scalar('String',name),
                            'scale':scalar('Float',1),
                            'cachedInputNode':reference('ptr:CBehaviorGraphNode',pose)}
                    if operation=='translate':
                        kind='CBehaviorGraphTranslateBoneNode'
                        values.update(axis=vector('Vector',[float(c==axis) for c in 'XYZ']+[0]),
                            biasValue=scalar('Float',0),clampValue=scalar('Bool',False),
                            cachedValueNode=reference('ptr:CBehaviorGraphValueNode',control))
                    else:
                        kind='CBehaviorGraphRotateBoneNode'
                        values.update(axis=scalar('EBoneRotationAxis','ROTAXIS_'+axis),
                            biasAngle=scalar('Float',0),clampRotation=scalar('Bool',False),
                            localSpace=scalar('Bool',True),
                            cachedControlVariableNode=reference('ptr:CBehaviorGraphValueNode',control))
                    pose=node(kind,top,values)
                    nodes.append(pose)
                    variable=node('CBehaviorVariable',root,{
                        'name':scalar('CName',variable_name),
                        'varIndex':scalar('Uint32',len(scalar_variables)),
                        'value':scalar('Float',0),'defaultValue':scalar('Float',0)})
                    scalar_variables.append({'_type':'IdHandle','_vars':{
                        'handlename':scalar('CName',variable_name),
                        'handle':handle('CBehaviorVariable',variable)}})
    out = node('CBehaviorGraphOutputNode', top, {
        'id': scalar('Uint32', len(nodes) + 2),
        'cachedInputNode': reference('ptr:CBehaviorGraphNode', pose)})
    nodes.append(out)
    values = copy.deepcopy(template['_chunks']['CBehaviorGraph #0']['_vars'])
    values.update(stateMachines=array('array:2,0,ptr:CBehaviorGraphStateMachineNode', []),
                  sourceDataRemoved=scalar('Bool',True),
                  Toplevelnode=handle('CBehaviorVariable', top),
                  Unk2=scalar('Uint32', len(scalar_variables)), Variables1=array('array:0,0,IdHandle', scalar_variables),
                  Unk4=scalar('Uint32', len(variables)),
                  Vectorvariables1=array('array:0,0,IdHandle', variables))
    chunks[root]['_vars'] = values
    chunks[top]['_vars'].update({
        'Inputnodes': array('CBufferVLQInt32:CHandle:CBehaviorVariable',
                            [handle('CBehaviorVariable', x) for x in nodes]),
        'Unk1': array('CBufferVLQInt32:CName', []),
        'Unk2': array('CBufferVLQInt32:CName', []),
        'Outputnode': handle('CBehaviorVariable', out)})
    # This is an authored compiled graph: every cached input and buffered node
    # table is supplied above, with no editor socket topology. Native
    # CBehaviorGraph::CacheConnections clears these inputs when
    # sourceDataRemoved is false; mark the graph consistently and verify every
    # connection after native cooking. Do not use this flag to bypass that gate.
    result['_chunks'] = chunks
    return result


def add_deformation_component(resource, rig_path, graph_path, *, output='dangle'):
    """Attach the existing dangle to an independent graph-driven animated root.

    The stock item attachment code creates an animated parent attachment for
    orphan CAnimatedComponents. This is an inspected engine path, not yet an
    observed assertion about a transplanted player appearance.
    """
    if output not in ('dangle', 'direct'):
        raise ValueError('Unknown deformation output path')
    result = copy.deepcopy(resource)

    def edit(data):
        chunks = data['_chunks']
        item = next(k for k, c in chunks.items() if c['_type'] == 'CItemEntity')
        child = next(k for k, c in chunks.items() if c['_type'] == 'CAnimDangleComponent')
        prefix = data['_extension']
        helper = prefix + 'CAnimatedComponent #' + str(len(chunks))
        attachment = prefix + 'CAnimatedAttachment #' + str(len(chunks) + 1)

        def depot_handle(kind, path):
            return {'_type': 'handle:' + kind, '_vars': {
                '_chunkHandle': scalar('bool', False),
                '_className': scalar('string', kind),
                '_depotPath': scalar('string', path),
                '_flags': scalar('uint16', 0)}}

        chunks[helper] = dict(_type='CAnimatedComponent', _key=helper, _parentKey=item,
            _flags=0, _vars={
                'name': scalar('String', 'MaleModDeformation'),
                'skeleton': depot_handle('CSkeleton', rig_path),
                'useExtractedMotion': scalar('Bool', False),
                'animationSets': array('array:2,0,handle:CSkeletalAnimationSet', []),
                'behaviorInstanceSlots': array('array:2,0,SBehaviorGraphInstanceSlot', [{
                    '_type': 'SBehaviorGraphInstanceSlot', '_vars': {
                        'instanceName': scalar('CName', 'MaleModDeformation'),
                        'graph': depot_handle('CBehaviorGraph', graph_path),
                        'alwaysLoaded': scalar('Bool', True),
                        'alwaysOnTopOfStack': scalar('Bool', True)}}]),
                'AttachmentsChild': array('array:0,0,handle:IAttachment',
                                           [handle('IAttachment', attachment)])})
        chunks[attachment] = dict(_type='CAnimatedAttachment', _key=attachment,
            _parentKey=helper, _flags=0, _vars={
                'parent': reference('ptr:CNode', helper),
                'child': reference('ptr:CNode', child)})
        chunks[child]['_vars']['transformParent'] = reference('ptr:CHardAttachment', attachment)
        chunks[child]['_vars']['AttachmentsReference'] = array('array:0,0,handle:IAttachment',
                                                            [handle('IAttachment', attachment)])
        chunks[item]['_vars']['Components']['_elements'].append(reference('ptr:CComponent', helper))
        if output == 'direct':
            # Isolate graph pose output from the dangle's matrix reconstruction.
            # Keep the old constraint serialized for controller compatibility,
            # but route the skin exclusively through the animated component.
            skin=next(k for k,c in chunks.items() if c['_type']=='CMeshSkinningAttachment')
            chunks[skin]['_vars']['parent']=reference('ptr:CNode',helper)
            chunks[skin]['_parentKey']=helper
            chunks[helper]['_vars']['AttachmentsChild']=array('array:0,0,handle:IAttachment',
                                                             [handle('IAttachment',skin)])
            chunks[child]['_vars']['AttachmentsChild']=array('array:0,0,handle:IAttachment',[])
            chunks[child]['_vars'].pop('transformParent',None)
            chunks[child]['_vars']['AttachmentsReference']=array('array:0,0,handle:IAttachment',[])
            del chunks[attachment]
        for chunk in list(chunks.values()):
            for value in chunk['_vars'].values():
                if value.get('_type') == 'CR2W':
                    edit(value)
        # WolvenKit mounts children while filling their parent objects. Keep
        # parents before children in both the source and flat compiled tree.
        ordered = {}
        visiting = set()
        def append(key):
            if key in ordered:return
            if key in visiting:raise ValueError('Cyclic native object ownership')
            visiting.add(key)
            parent = chunks[key].get('_parentKey','')
            if parent:
                if parent not in chunks:raise ValueError('Missing native object owner '+parent)
                append(parent)
            ordered[key] = chunks[key]
            visiting.remove(key)
        for key in chunks:append(key)
        data['_chunks'] = ordered

    edit(result)
    return result
