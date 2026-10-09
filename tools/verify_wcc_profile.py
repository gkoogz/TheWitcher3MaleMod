"""Read-only verification of the observed official WCC compiler call chain.

This uses the compiler's own LogChannel registration and native dispatcher,
never offsets borrowed from editor.exe or the retail game. No process is run.
"""
import argparse
from pathlib import Path
import capstone
from capstone import x86_const as X
import pefile
from mod import ROOT, digest, read_json, settings, write_json


def verify(executable=None, profile=None):
    executable=Path(executable or settings()['wcc'])
    profile=profile or read_json(ROOT/'characters/compiler-native-profile.json')
    if digest(executable)!=profile['executableSHA256']:
        raise ValueError('Unknown official WCC identity; reobserve its ABI')
    pe=pefile.PE(str(executable),fast_load=True)
    try:
        if pe.OPTIONAL_HEADER.SizeOfImage!=profile['imageSize']:
            raise ValueError('Compiler image size differs')
        for name,row in {**profile['functions'],**profile['sessionABI']}.items():
            if pe.get_data(row['rva'],16).hex()!=row['prefix']:
                raise ValueError('Compiler function prefix differs: '+name)
        begin,end=profile['registrationFunctionRange']
        decoder=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64)
        decoder.detail=True
        instructions=list(decoder.disasm(pe.get_data(begin,end-begin),begin))
        ref=profile['registrationReferenceRVA']
        index=next((i for i,x in enumerate(instructions) if x.address==ref),None)
        if index is None:raise ValueError('Registration reference is not an instruction')
        instruction=instructions[index]
        if instruction.mnemonic!='lea' or instruction.operands[1].type!=X.X86_OP_MEM or instruction.operands[1].mem.base!=X.X86_REG_RIP:
            raise ValueError('Registration reference no longer addresses its native name')
        name_rva=instruction.address+instruction.size+instruction.operands[1].mem.disp
        if pe.get_data(name_rva,11)!=b'LogChannel\0':
            raise ValueError('Registration reference no longer names LogChannel')
        def calls(code):
            return [x.operands[0].imm for x in code if x.mnemonic=='call' and x.operands[0].type==X.X86_OP_IMM]
        preceding=calls(instructions[:index])
        following=calls(instructions[index:])
        expected=[profile['functions'][key]['rva'] for key in ('intern','construct','registry','register')]
        if not preceding or preceding[-1]!=profile['functions']['allocate']['rva'] or following[:4]!=expected:
            raise ValueError('Actual native allocation/registration call chain differs')
        return dict(schema='malemod.official-wcc-observation/1',compilerSHA256=profile['executableSHA256'],
            registrationReferenceRVA=ref,registrationFunctionRange=[begin,end],
            nativeName='LogChannel',callChainVerified=True,functionPrefixesVerified=True,
            SDKModified=False,gameModified=False,observedGameplay=False)
    finally:pe.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to((ROOT/'build').resolve()) or output.exists():
        raise ValueError('Use a fresh owned diagnostic output')
    write_json(output,verify())
    print('PASS official WCC identity, prefixes and measured LogChannel call chain')
