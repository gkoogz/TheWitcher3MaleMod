"""Generate Witcher UI/persistence/native bindings from pinned Base transport.

The native cage uses the observed shaft root X axis for axial scale, Y/Z for
radial scale, shaft knot 6 for the distal head, and independent pelvis-parented
lobe roots. This is a cage preview, not the authored surface/physics solver.
"""
import importlib
import json
import sys
from mod import ROOT,digest


def add_size_controls(source,base,names):
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
    return source,dict(supportedControls=[c['id'] for c in controls],backend='normalized-size-cage-preview',
        defaultRestPreserved=True,sharedTransportSHA256=digest(base/'malemod_base/control_transport.py'),
        sourceCatalogSHA256=digest(base/'modules/live-controls.json'),
        assignments=dict(shaftRoot=names[0],axialAxis='X',radialAxes=['Y','Z'],headRoot=names[6],lobeRoots=names[8:]),
        sourceSurfaceParity=False,physicsParity=False,observedGameplay=False)
