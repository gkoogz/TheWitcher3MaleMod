"""Translate pinned SDK-free Base kernels to WitcherScript; no numerical fork."""
import hashlib,re


def function(text,name):
    match=re.search(r'inline\s+\w+\s+'+name+r'\(',text)
    if not match:raise ValueError('Missing pinned Base kernel '+name)
    start=text.index('{',match.start());depth=1;end=start+1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start+1:end-1]


def split(text):
    depth=0;start=0;parts=[]
    for i,c in enumerate(text):
        depth+=(c in '([{')-(c in ')]}')
        if c==',' and depth==0:parts.append(text[start:i]);start=i+1
    return parts+[text[start:]]


def emit(base):
    paths=['include/malemod/physics/xpbd_kernels.hpp','include/malemod/physics/rig_kernels.hpp','include/malemod/physics/ovoid_support.hpp','include/malemod/physics/rigid_cluster.hpp']
    texts=[(base/p).read_text() for p in paths];receipts=[dict(path=p,sha256=hashlib.sha256((base/p).read_bytes()).hexdigest()) for p in paths]
    specs=[('SolveDistance',0,'a : int, b : int, rest : float, compliance : float, out lambda : float, dt : float',''),
        ('PrepareBend',0,'i : int, compliance : float, dt : float, bounce01 : float','MaleModPDBendData'),
        ('SolveBendPrepared',0,'i : int, data : MaleModPDBendData, out lambda : Vector',''),
        ('FilterMotion',1,'previous : Vector, measured : Vector, response : float, limit : float, dt : float','Vector'),
        ('FrameAcceleration',1,'position : Vector, velocity : Vector, linear : Vector, angularVelocity : Vector, angularAcceleration : Vector','Vector'),
        ('IntegrateRelative',1,'i : int, gravity : Vector, linear : Vector, angularVelocity : Vector, angularAcceleration : Vector, accelerationLimit : float, drag : float, dt : float',''),
        ('SampleGuide',1,'count : int, t : float, out center : Vector, out tangent : Vector',''),
        ('SolveRestBend',1,'i : int, data : MaleModPDBendData, rest : Vector, oldRest : Vector, out lambda : Vector',''),
        ('SolveMaterial',1,'i : int, target : Vector, oldTarget : Vector, compliance : float, ratio : float, dt : float, out lambda : Vector',''),
        ('SolveReach',1,'i : int, anchor : Vector, limit : float',''),
        ('SolveSuspension',1,'i : int, anchor : Vector, oldAnchor : Vector, rest : float, compliance : float, ratio : float, dt : float, out lambda : float',''),
        ('SolveMaterialAxis',1,'i : int, target : Vector, oldTarget : Vector, axis : Vector, compliance : float, dt : float, out lambda : float',''),
        ('ProjectRodContact',1,'a : int, b : int, body : int, part : float, normal : Vector, gap : float',''),
        ('ProjectPairContact',1,'a : int, b : int, normal : Vector, gap : float',''),
        ('ProjectMovingContact',1,'i : int, normal : Vector, gap : float, surfaceMove : Vector',''),
        ('OvoidSupport',2,'n : Vector, r : Vector','Vector'),
        ('ClusterIndex',3,'i : int, firstA : int, countA : int, firstB : int','int'),
        ('ClusterCenter',3,'firstA : int, countA : int, firstB : int, countB : int','Vector'),
        ('RotateCluster',3,'q : Vector, p : Vector','Vector'),
        ('FitCluster',3,'rest : array<Vector>, restCenter : Vector, firstA : int, countA : int, firstB : int, countB : int, seed : Vector','Vector'),
        ('ProjectCluster',3,'rest : array<Vector>, restCenter : Vector, firstA : int, countA : int, firstB : int, countB : int, rotation : Vector','')]
    methods=[]
    for name,source,params,result in specs:
        body=function(texts[source],name);body=re.sub(r'//[^\n]*','',body)
        body=body.replace('state.oldPosition','physicsOld').replace('state.position','physicsPosition').replace('state.invMass','physicsInvMass').replace('state.velocity','physicsVelocity')
        body=re.sub(r'=\s*\{([^{}]+)\}',lambda m:'= Vector('+m[1]+(',0.0' if len(split(m[1]))==3 else '')+')',body)
        body=body.replace('ClusterCenter(state,','ClusterCenter(').replace('ProjectCluster(state,','ProjectCluster(').replace('FitCluster(state,','FitCluster(')
        declarations={}
        def declare(m):
            kind,members=m.groups();assign=[]
            for member in split(members):
                key,sep,value=member.strip().partition('=');key=key.strip();declarations[key]={'V3':'Vector','float':'float','int':'int','PDBendData':'MaleModPDBendData'}[kind]
                if sep:assign.append(key+' = '+value.strip()+';')
            return '\n'.join(assign)
        body=re.sub(r'\b(V3|float|int|PDBendData)\s+([^;{}]+);',declare,body)
        # The loop declaration consumed its semicolon; retain the for syntax.
        body=re.sub(r'for\((\w+)\s*=\s*([^;]+);',r'for (\1 = \2;',body)
        body=re.sub(r'(\w+)\+\+',r'\1 += 1',body)
        body=re.sub(r'\bfloat\(', '(',body)
        body=re.sub(r'\bint\(', 'FloorF(',body)
        for cpp,ws in [('sqrtf','SqrtF'),('expf','ExpF'),('Cross','VecCross'),('Length','VecLength'),('Dot','VecDot'),('min','MinF'),('max','MaxF')]:body=re.sub(r'\b'+cpp+r'\(',ws+'(',body)
        body=re.sub(r'\bUnit\(', 'VecNormalize(',body)
        body=re.sub(r'\.([xyzw])\b',lambda m:'.'+m[1].upper(),body)
        if name=='PrepareBend':
            m=re.search(r'return\s*\{([^{}]+)\};',body);values=split(m[1]);declarations['prepared']='MaleModPDBendData'
            body=body[:m.start()]+'\n'.join('prepared.'+k+' = '+v+';' for k,v in zip(['alpha','gamma','factor','oldValue'],values))+'\nreturn prepared;'+body[m.end():]
        else:body=re.sub(r'return\s*\{([^{}]+)\};',lambda m:'return Vector('+m[1]+(', 0.0' if len(split(m[1]))==3 else '')+');',body)
        body=re.sub(r'(?<![\w.])(\d*\.\d*|\d+(?:\.\d*)?[eE][+-]?\d+)(?:f)?(?![\w.])',lambda m:format(float(m[1]),'.30f' if 0<abs(float(m[1]))<1e-12 else '.12f'),body)
        methods.append('    private function '+name+'('+params+')'+(' : '+result if result else '')+'\n    {\n'+
            '\n'.join('        var '+k+' : '+v+';' for k,v in declarations.items())+'\n'+body+'\n    }')
    return '\n\n'.join(methods),dict(kernels=receipts,numericalCodeGeneratedFromBase=True)
