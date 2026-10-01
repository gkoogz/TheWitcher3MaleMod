"""Generate Witcher UI/persistence/native bindings from pinned Base transport.

Production receives calibrated source poses and independently drives the joints.
The no-poses branch retains the historical ratio probe for fixture compatibility.
Both are cage approximations, not the final authored surface/physics solver.
"""
import importlib
import json
import sys
from mod import ROOT,digest


def add_size_controls(source,base,names,*,poses=None):
    expected=['mm_shaft_'+str(i).zfill(2) for i in range(8)]+['mm_scrotum_l','mm_scrotum_r']
    if names!=expected:raise ValueError('Recalibrate size transport for changed cage joints')
    sys.path.insert(0,str(base))
    transport=importlib.import_module('malemod_base.control_transport')
    catalog=json.loads((base/'modules/live-controls.json').read_text())
    controls=[c for c in catalog['controls'] if c['id'] in transport.SIZE_CONTROLS]
    def replace(old,new):
        nonlocal source
        if source.count(old)!=1:raise ValueError('Size controller insertion marker changed: '+old[:80])
        source=source.replace(old,new,1)
    fields=[];init=[];initializers=[];get=[];setters=[];load=[];store=[];rows=[]
    for c in controls:
        key=c['id'];native='MaleModSize_'+key;field='size_'+key;table=field+'_ratios'
        fields += ['    private var '+field+' : float;','    private var '+table+' : array<float>;']
        init += ['        '+field+' = '+str(float(c['default']))+';', '        InitializeSize_'+key+'();']
        values=['        '+table+'.Clear();']
        values += ['        '+table+'.PushBack('+format(float(v),'.10f')+');' for v in transport.normalized_samples(key)]
        # WCC's script parser exhausts its stack on a single 500-statement
        # initializer. Each control gets a bounded, independently parsed method.
        initializers.append('    private function InitializeSize_'+key+'()\n    {\n'+'\n'.join(values)+'\n    }')
        get.append("        if (control == '%s') { return %s; }"%(native,field))
        setters.append("        if (control == '%s') { %s = RoundF(ClampF(value,%s.0,%s.0)); StoreSourceSize(); ApplySourceSize(); bridgeChanges += 1; return; }"%(native,field,c['minimum'],c['maximum']))
        load.append('        raw = cfg.GetRawConfigValueByStr("MaleModPortable", "'+key+'");\n        if (raw != "") { '+field+' = ClampF(StringToFloat(raw),'+str(c['minimum'])+'.0,'+str(c['maximum'])+'.0); if ('+field+' != '+field+') { '+field+' = 50.0; } '+field+' = RoundF('+field+'); }')
        store.append('        cfg.SetRawConfigValueByStr("MaleModPortable", "'+key+'", FloatToString('+field+'));')
        rows.append("    controls.PushBackFlashObject(MaleModSlider(m_flashValueStorage, '%s',\n        \"%s\", controller.GetTuning('%s'),%s.0,%s.0,%s));"%(native,c['label'],native,c['minimum'],c['maximum'],c['maximum']-c['minimum']))
    replace('    private var bridgeScale : float;','    private var bridgeScale : float;\n'+'\n'.join(fields))
    replace('        bridgeScale = 1.0;','        bridgeScale = 1.0;\n        InitializeSourceSize();')
    replace('        LoadTuning();','        LoadTuning();\n        LoadSourceSize();')
    replace('    public function GetTuning(control : name) : float\n    {',
        '    public function GetTuning(control : name) : float\n    {\n'+'\n'.join(get))
    replace('        if (!InitializeController()) { return; }','        if (!InitializeController()) { return; }\n'+'\n'.join(setters))
    begin=source.index('        var scale : Vector;\n',source.index('    private function ApplyTuning()'))
    end=source.index('        if (!dynamicConstraint)',begin)
    source=source[:begin]+'        ApplySourceSize();\n'+source[end:]
    # Retain diagnostic getter/exec compatibility; the old probe row is removed.
    begin=source.index("    controls.PushBackFlashObject(MaleModSlider(m_flashValueStorage, 'MaleModBridgeScale',")
    end=source.index('));',begin)+3
    source=source[:begin]+'\n'.join(rows)+source[end:]
    source=source.replace('MaleMod - player pose test','MaleMod - size controls')
    source=source.replace('Slider changes: ', 'Size changes: ')
    source=source.replace(' | requested: ', ' | legacy test: ')
    methods='''
    private function InitializeSourceSize()
    {
INIT
    }
    private function LoadSourceSize()
    {
        var cfg : CInGameConfigWrapper;
        var raw : string;
        cfg = theGame.GetInGameConfigWrapper();
        if (cfg.GetRawConfigValueByStr("MaleModPortable", "Version") != "1") { return; }
LOAD
    }
    private function StoreSourceSize()
    {
        var cfg : CInGameConfigWrapper;
        cfg = theGame.GetInGameConfigWrapper();
        cfg.SetRawConfigValueByStr("MaleModPortable", "Version", "1");
STORE
        preferencesDirty = true;
    }
    private function ApplySourceSize()
    {
        var overall : float;
        var axial : float;
        var radial : float;
        var head : float;
        var lobes : float;
        var accepted : bool;
        if (!bridgeBooted || !deformationRoot) { return; }
        overall = size_overall_ratios[RoundF(size_overall) - 1];
        axial = overall * size_length_ratios[RoundF(size_length)];
        radial = overall * size_width_ratios[RoundF(size_width) - 1];
        head = size_glans_ratios[RoundF(size_glans)];
        lobes = overall * size_scrotum_ratios[RoundF(size_scrotum) - 1];
        bridgeAccepted = true;
APPLY
    }
'''.replace('INIT','\n'.join(init)).replace('LOAD','\n'.join(load)).replace('STORE','\n'.join(store))
    calls=[]
    for i,name in enumerate(names):
        vector='Vector(axial, radial, radial)' if i==0 else 'Vector(head, head, head)' if i==6 else 'Vector(lobes, lobes, lobes)' if i>=8 else 'Vector(1.0, 1.0, 1.0)'
        calls += ["        accepted = deformationRoot.SetBehaviorVectorVariable('%s_scale', %s);"%(name,vector),
                  '        bridgeAccepted = bridgeAccepted && accepted;']
    methods=methods.replace('APPLY','\n'.join(calls))
    methods+='\n'+'\n'.join(initializers)+'\n'
    replace('    public function BridgeBooted() : bool',methods+'\n    public function BridgeBooted() : bool')
    if poses is not None:
        source=source_backed_script(source,base,names,poses)
    return source,dict(supportedControls=[c['id'] for c in controls],backend='normalized-size-cage-preview',
        defaultRestPreserved=True,sharedTransportSHA256=digest(base/'malemod_base/control_transport.py'),
        sourceCatalogSHA256=digest(base/'modules/live-controls.json'),
        assignments=dict(shaftRoot=names[0],axialAxis='X',radialAxes=['Y','Z'],headRoot=names[6],lobeRoots=names[8:]),
        sourceSurfaceParity=False,physicsParity=False,observedGameplay=False)


def source_backed_script(source,base,names,poses):
    import numpy as np
    shared=importlib.import_module('malemod_base.shape_transport')
    if poses.shape!=(4,4,4,4,10,12) or not np.isfinite(poses).all():
        raise ValueError('Invalid calibrated source pose lattice')
    fields=['    private var sourcePoses : array<float>;']
    init=['        sourcePoses.Clear();']
    helpers=[]
    flat=poses.reshape(-1)
    for start in range(0,len(flat),96):
        name='InitializeSourcePose_'+str(start//96)
        init.append('        '+name+'();')
        helpers.append('    private function '+name+'()\n    {\n'+ '\n'.join(
            '        sourcePoses.PushBack('+format(float(v),'.10f')+');' for v in flat[start:start+96])+'\n    }')
    # The dispatcher itself must also stay below the measured parser limit.
    calls=init[1:];init=init[:1]
    for start in range(0,len(calls),64):
        name='InitializeSourcePoseBatch_'+str(start//64)
        helpers.append('    private function '+name+'()\n    {\n'+'\n'.join(calls[start:start+64])+'\n    }')
        init.append('        '+name+'();')
    for key in shared.AXES:
        fields.append('    private var sourceCoord_'+key+' : array<float>;')
        name='InitializeSourceCoord_'+key
        init.append('        '+name+'();')
        helpers.append('    private function '+name+'()\n    {\n        sourceCoord_'+key+'.Clear();\n'+
            '\n'.join('        sourceCoord_'+key+'.PushBack('+format(v,'.10f')+');' for v in shared.coordinates(key))+'\n    }')
    source=source.replace('    private var bridgeScale : float;', '    private var bridgeScale : float;\n'+'\n'.join(fields),1)
    source=source.replace('        InitializeSourceSize();','        InitializeSourceSize();\n'+'\n'.join(init),1)
    begin=source.index('    private function ApplySourceSize()')
    end=source.index('    private function InitializeSize_',begin)
    setup=[]
    for i,key in enumerate(shared.AXES):
        low=0 if key=='length' else 1
        setup.append('        coords.PushBack(sourceCoord_'+key+'[RoundF(size_'+key+') - '+str(low)+']);')
    calls=[]
    for i,name in enumerate(names):
        # fields: local displacement, scale, parent-space Euler delta, crown offset.
        bone_calls=[]
        get=lambda j: 'SampleSourcePose('+str(i*12+j)+', coords)'
        if i in (6,7):
            translation=[get(j)+' + (head - 1.0) * '+get(j+9) for j in range(3)]
            scales=[get(j)+' * head' for j in range(3,6)]
        else:translation=[get(j) for j in range(3)];scales=[get(j) for j in range(3,6)]
        bone_calls.append("        accepted = deformationRoot.SetBehaviorVectorVariable('%s_scale', Vector(%s));"%(name,', '.join(scales)))
        bone_calls.append('        bridgeAccepted = bridgeAccepted && accepted;')
        for axis,expression in zip('xyz',translation):
            bone_calls.extend(["        accepted = deformationRoot.SetBehaviorVariable('%s_translate_%s', %s);"%(name,axis,expression),
                          '        bridgeAccepted = bridgeAccepted && accepted;'])
        for j,axis in enumerate('xyz'):
            bone_calls.extend(["        accepted = deformationRoot.SetBehaviorVariable('%s_rotate_%s', %s);"%(name,axis,get(j+6)),
                          '        bridgeAccepted = bridgeAccepted && accepted;'])
        helper='ApplySourceBone_'+str(i)
        calls.append('        '+helper+'(coords, head);')
        helpers.append('    private function '+helper+'(coords : array<float>, head : float)\n    {\n        var accepted : bool;\n'+'\n'.join(bone_calls)+'\n    }')
    methods='''    private function ApplySourceSize()
    {
        var coords : array<float>;
        var head : float;
        var accepted : bool;
        if (!bridgeBooted || !deformationRoot) { return; }
SETUP
        head = size_glans_ratios[RoundF(size_glans)];
        bridgeAccepted = true;
CALLS
    }
    private function SampleSourcePose(field : int, coords : array<float>) : float
    {
        var corner, axis, index, low, choice, bits : int;
        var weight, fraction, total : float;
        total = 0.0;
        for (corner = 0; corner < 16; corner += 1)
        {
            weight = 1.0;
            index = 0;
            bits = corner;
            for (axis = 0; axis < 4; axis += 1)
            {
                low = Min(FloorF(coords[axis]), 2);
                fraction = coords[axis] - low;
                choice = bits % 2;
                bits = bits / 2;
                if (choice == 0) { weight *= 1.0 - fraction; }
                else { weight *= fraction; }
                index = index * 4 + low + choice;
            }
            total += weight * sourcePoses[index * 120 + field];
        }
        return total;
    }
'''.replace('SETUP','\n'.join(setup)).replace('CALLS','\n'.join(calls))
    return source[:begin]+methods+'\n'+'\n'.join(helpers)+'\n'+source[end:]
