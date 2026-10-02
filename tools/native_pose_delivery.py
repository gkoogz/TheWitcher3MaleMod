"""REDengine local RotateBone delivery and read-only native instruction oracle.

The oracle interprets the installed editor's SIMD quaternion-update block. It
does not execute/inject code, attach to a process, or alter an SDK/game file.
"""
import ast,hashlib,mmap,re,struct
from types import SimpleNamespace
import numpy as np
import pefile,capstone
from scipy.spatial.transform import Rotation

SYMBOL='?Sample@CBehaviorGraphRotateBoneNode@@'

class NativeRotationOracle:
    def __init__(self,executable):
        self.executable=executable
        self.stream=executable.open('rb');self.data=mmap.mmap(self.stream.fileno(),0,access=mmap.ACCESS_READ)
        self.pe=pefile.PE(data=self.data[:4096],fast_load=True);self.base=self.pe.OPTIONAL_HEADER.ImageBase
        symbols=executable.with_suffix('.map');functions=[]
        map_text=symbols.read_text(errors='replace')
        for line in map_text.splitlines():
            m=re.match(r'\s+0001:[0-9a-f]+\s+(\S+)\s+([0-9a-f]{16})\s+f\s',line)
            if m:functions.append((int(m[2],16),m[1]))
        matches=[a for a,n in functions if SYMBOL in n]
        if len(matches)!=1:raise ValueError('Native RotateBone symbol changed')
        address=matches[0];end=min(a for a,n in functions if a>address)
        decoder=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64);decoder.detail=True
        ins=list(decoder.disasm(self.bytes(address,end-address),address))
        start=next(i for i,x in enumerate(ins) if x.mnemonic=='vshufps' and x.op_str=='xmm1, xmm8, xmm8, 0xc9')
        stop=next(i for i in range(start,len(ins)) if ins[i].mnemonic=='vmovups' and ins[i].op_str=='xmmword ptr [rax + rcx*8 + 0x10], xmm1')
        self.instructions=ins[start:stop+1]
        # XYZ_MASK is initialized in .bss from the named read-only DATA symbol.
        find=lambda name:int(re.search(r'\s'+re.escape(name)+r'\s+([0-9a-f]{16})\s',map_text)[1],16)
        mask_address=find('?XYZ_MASK@SIMD@RedMath@@3T__m128@@B')
        mask_data=find('?XYZ_MASKDATA@_Internal@SIMD@RedMath@@3QBIB')
        initializer=find('??__EXYZ_MASK@SIMD@RedMath@@YAXXZ')
        init=list(decoder.disasm(self.bytes(initializer,32),initializer))
        refs=[x.address+x.size+op.mem.disp for x in init for op in x.operands if op.type==capstone.CS_OP_MEM and x.reg_name(op.mem.base)=='rip']
        if mask_data not in refs or mask_address not in refs:raise ValueError('Native XYZ mask initializer changed')
        self.initialized_constants={mask_address:self.bytes(mask_data,16)}
        np.testing.assert_array_equal(np.frombuffer(self.initialized_constants[mask_address],dtype='<u4'),[0xffffffff]*3+[0])
        # Verify positive XYZ axes and degrees-to-half-radians from actual data.
        before=ins[:start]
        axes_load=next(x for x in before if x.mnemonic=='vmovaps' and x.op_str.startswith('ymm0, ymmword ptr [rip'))
        third_load=next(x for x in before if x.mnemonic=='vmovdqu' and x.op_str.startswith('xmm0, xmmword ptr [rip'))
        factor=next(x for x in before if x.mnemonic=='vmulss' and x.op_str.startswith('xmm1, xmm6, dword ptr [rip'))
        rip=lambda x:x.address+x.size+x.operands[-1].mem.disp
        axes=np.frombuffer(self.bytes(rip(axes_load),32),dtype='<f4').reshape(2,4)
        third=np.frombuffer(self.bytes(rip(third_load),16),dtype='<f4')
        np.testing.assert_array_equal(np.vstack([axes,third])[:,:3],np.eye(3))
        self.half_angle=struct.unpack('<f',self.bytes(rip(factor),4))[0]
        if abs(self.half_angle-np.pi/360)>1e-8:raise ValueError('Native angle units changed')
        self.evidence=dict(executableSHA256=hashlib.sha256(self.data).hexdigest(),mapSHA256=hashlib.sha256(symbols.read_bytes()).hexdigest(),
            symbol=SYMBOL,address=hex(address),blockStart=hex(ins[start].address),blockEnd=hex(ins[stop].address),
            halfAngleRadiansPerDegree=self.half_angle,readOnlyInstructionEmulation=True,observedGameplay=False)

    def bytes(self,address,count):
        offset=self.pe.get_offset_from_rva(address-self.base);return self.data[offset:offset+count]

    def close(self):self.data.close();self.stream.close()

    def update(self,current,delta):
        registers={'xmm8':np.asarray(current,dtype=np.float32),'xmm6':np.asarray(delta,dtype=np.float32),
            'xmm9':np.array([delta[3],0,0,0],dtype=np.float32)}
        output=None
        for ins in self.instructions:
            ops=ins.operands
            def read(op):
                if op.type==capstone.CS_OP_REG:return registers[ins.reg_name(op.reg)].copy()
                if op.type==capstone.CS_OP_IMM:return op.imm
                if op.type!=capstone.CS_OP_MEM:raise ValueError('Unknown operand')
                base=ins.reg_name(op.mem.base)
                if base=='rip':
                    address=ins.address+ins.size+op.mem.disp
                    raw=self.initialized_constants[address] if address in self.initialized_constants else self.bytes(address,op.size or 16)
                elif base=='rax' and op.mem.disp==0x1c:raw=struct.pack('<f',float(current[3]))
                else:raise ValueError('Uncalibrated memory operand '+ins.op_str)
                return np.frombuffer(raw,dtype='<f4').copy()
            values=[read(op) for op in ops[1:]];mn=ins.mnemonic
            if mn in ('vmovaps','vmovups'):result=values[0]
            elif mn=='vbroadcastss':result=np.repeat(values[0][0],4)
            elif mn in ('vmulps','vaddps','vsubps'):result={'vmulps':np.multiply,'vaddps':np.add,'vsubps':np.subtract}[mn](*values)
            elif mn in ('vmulss','vsubss'):
                result=values[0].copy();result[0]=(values[0][0]*values[1][0]) if mn=='vmulss' else (values[0][0]-values[1][0])
            elif mn=='vandps':result=np.bitwise_and(values[0].view(np.uint32),values[1].view(np.uint32)).view(np.float32)
            elif mn=='vhaddps':
                a,b=values;result=np.array([a[0]+a[1],a[2]+a[3],b[0]+b[1],b[2]+b[3]],dtype=np.float32)
            elif mn=='vshufps':
                a,b,imm=values;result=np.array([a[imm&3],a[(imm>>2)&3],b[(imm>>4)&3],b[(imm>>6)&3]],dtype=np.float32)
            elif mn=='vinsertps':
                a,b,imm=values;result=a.copy();result[(imm>>4)&3]=b[(imm>>6)&3]
                for lane in range(4):
                    if imm&(1<<lane):result[lane]=0
            else:raise ValueError('Unsupported native instruction '+mn)
            if ops[0].type==capstone.CS_OP_MEM:output=result
            else:registers[ins.reg_name(ops[0].reg)]=result
        if output is None:raise ValueError('Native block produced no quaternion')
        return output

    def xyz(self,bind,angles):
        current=Rotation.from_matrix(bind).as_quat()
        for axis,angle in enumerate(angles):
            delta=np.zeros(4);delta[axis]=np.sin(angle*self.half_angle);delta[3]=np.cos(angle*self.half_angle)
            current=self.update(current,delta)
        return Rotation.from_quat(current).as_matrix()

def bone_angles(bind,parent_delta):
    """Native local XYZ nodes right-multiply bind; supply intrinsic XYZ."""
    return Rotation.from_matrix(bind.T@parent_delta@bind).as_euler('XYZ',degrees=True)

def script_angles(q,script):
    """Evaluate the controller's actual scalar expressions against the oracle."""
    expressions=[re.search(r'result\.'+axis+r'\s*=\s*([^;]+);',script)[1] for axis in 'XYZ']
    scope=dict(q=SimpleNamespace(**dict(zip('XYZW',q))),Rad2Deg=np.rad2deg,AtanF=np.arctan2,AsinF=np.arcsin,ClampF=np.clip)
    results=[]
    for expression in expressions:
        tree=ast.parse(expression,mode='eval')
        for node in ast.walk(tree):
            if not isinstance(node,(ast.Expression,ast.Call,ast.Name,ast.Attribute,ast.Load,ast.BinOp,ast.Mult,ast.Add,ast.Sub,ast.Div,ast.Constant,ast.UnaryOp,ast.USub)):
                raise ValueError('Unsupported controller angle expression')
            if isinstance(node,ast.Name) and node.id not in scope:raise ValueError('Unknown angle identifier')
            if isinstance(node,ast.Attribute) and (not isinstance(node.value,ast.Name) or node.value.id!='q' or node.attr not in 'XYZW'):
                raise ValueError('Unknown quaternion member')
        results.append(eval(compile(tree,'controller-angle','eval'),{'__builtins__':{}},scope))
    return np.asarray(results)
