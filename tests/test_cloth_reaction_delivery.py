"""A receipt must not confuse optical intent or a gravity bonus with contacts."""
import copy
import sys
import json
import struct
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from record_extended_delivery import validate_cloth_reaction,validate_source_reactions,digest

def physical_contact():
    return dict(garmentMaterialOpacity=[.95]*4,clothMass=1.32,
                clothReactionSeconds=1/120,clothReactionContacts=3,
                clothReactionRecords=4,garmentReactionMode=True,
                garmentSupportEnabled=True,clothContactImpulse=[.1,-.2,.3],
                anatomyContactImpulse=[-.1,.2,-.3],
                clothContactMoment=[.5,.6,-.7],anatomyContactMoment=[-.5,-.6,.7],
                clothParticleContactImpulse=[.1,-.2,.3],clothParticleContactMoment=[.4,.5,-.6],
                clothPrescribedSupportImpulse=[0,0,0],clothPrescribedSupportMoment=[.1,.1,-.1])

class ClothReactionReceipt(unittest.TestCase):
    def test_real_contact_and_zero_contact_frames(self):
        validate_cloth_reaction(physical_contact())
        row=physical_contact()
        row.update(clothReactionContacts=0,clothReactionRecords=0,
                   garmentReactionMode=False,garmentSupportEnabled=False)
        for name in ['clothContactImpulse','anatomyContactImpulse',
                     'clothContactMoment','anatomyContactMoment',
                     'clothParticleContactImpulse','clothParticleContactMoment',
                     'clothPrescribedSupportImpulse','clothPrescribedSupportMoment']:
            row[name]=[0,0,0]
        validate_cloth_reaction(row)

    def test_rejects_nonphysical_or_nonconserved_receipts(self):
        changes=[dict(garmentReactionMode=False),dict(garmentSupportEnabled=False),
                 dict(clothReactionSeconds=0),dict(clothMass=0),
                 dict(garmentMaterialOpacity=[1]*4),
                 dict(anatomyContactImpulse=[-.1,.2,.3]),
                 dict(anatomyContactMoment=[-.5,-.6,-.7]),
                 dict(clothParticleContactImpulse=[.1,-.2,.5]),
                 dict(clothPrescribedSupportMoment=[0,0,0]),
                 dict(clothContactImpulse=[float('nan'),0,0]),
                 dict(clothReactionContacts=-1),dict(clothContactMoment=[])]
        for change in changes:
            with self.subTest(change=change),self.assertRaises(ValueError):
                row=copy.deepcopy(physical_contact());row.update(change)
                validate_cloth_reaction(row)

class SourceConsumptionReceipt(unittest.TestCase):
    def fixture(self,base):
        build=base/'build';build.mkdir()
        output=build/'proof';output.mkdir()
        files=['src/surface/runtime.cpp','tools/extract_surface_runtime.py',
               'tests/garment_support_runtime_cli.cpp','include/malemod/surface/wire.hpp',
               'include/malemod/surface/runtime.hpp','include/malemod/surface/garment_impulse.hpp',
               'include/malemod/garments/reaction_support.hpp',
               'legacy/wolverine/src/runtime/compliant_dynamics.h',
               'provenance/wolverine.json','provenance/source-surface.json',
               'tools/verify_garment_source_reactions.py']
        for name in files:
            path=base/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fixture source')
        exe=build/'source.exe';exe.write_bytes(b'fixture executable')
        library=build/'source.lib';library.write_bytes(b'fixture library')
        cases=[]
        for state in range(3):
            records={}
            for mode in [0,2,3,4,5,6]:
                path=output/f'{state}-{mode}.bin'
                path.write_bytes(struct.pack('<II',6,state)+bytes([int(mode>=3)]))
                records[str(mode)]=dict(file=path.name,sha256=digest(path),bytes=path.stat().st_size)
            cases.append(dict(state=state,records=records,disabledExactParity=True,
                              cdfRetryExactParity=True,physicalImpulseChangesSource=True,
                              pendingNoSubstepExactParity=True,pendingCoalescingExactParity=True))
        pin='a'*40
        proof=dict(schema=2,wire=6,sourceProcessIsolated=True,sourceCommit=pin,sourceDirty='',
                   executable=dict(path='build/source.exe',sha256=digest(exe)),
                   library=dict(path='build/source.lib',sha256=digest(library)),
                   sourceHashes={name:digest(base/name) for name in files},cases=cases)
        worker=dict(baseCommit=pin,baseDirty=False,wireVersion=6,frames=48,
                    byteIdentical=True,exitCode=0,librarySHA256=digest(library))
        report=output/'proof.json';report.write_text(json.dumps(proof))
        return report,pin,proof,worker

    def test_accepts_same_clean_source_library_and_encoded_comparisons(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);report,pin,_,worker=self.fixture(base)
            self.assertEqual(len(validate_source_reactions(report,base,pin,worker)),21)

    def test_rejects_old_wire_dirty_source_or_unapplied_contact(self):
        for mutation in ['old_worker','different_library','dirty','changed_source','replayed_retry','pending_lost','no_response','changed_binary']:
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as folder:
                base=Path(folder);report,pin,proof,worker=self.fixture(base)
                if mutation=='old_worker':worker['wireVersion']=5
                elif mutation=='different_library':worker['librarySHA256']='b'*64
                elif mutation=='dirty':proof['sourceDirty']=' M src/surface/runtime.cpp'
                elif mutation=='changed_source':(base/'src/surface/runtime.cpp').write_bytes(b'changed')
                elif mutation=='changed_binary':(base/'build/source.exe').write_bytes(b'changed')
                else:
                    mode='4' if mutation=='replayed_retry' else '5' if mutation=='pending_lost' else '3'
                    record=proof['cases'][0]['records'][mode]
                    path=report.parent/record['file']
                    path.write_bytes(struct.pack('<II',6,0)+bytes([2 if mutation=='replayed_retry' else 0]))
                    record['sha256']=digest(path)
                    if mutation=='no_response':
                        retry=proof['cases'][0]['records']['4']
                        (report.parent/retry['file']).write_bytes(path.read_bytes())
                        retry['sha256']=digest(report.parent/retry['file'])
                report.write_text(json.dumps(proof))
                with self.assertRaises(ValueError):validate_source_reactions(report,base,pin,worker)

if __name__=='__main__':unittest.main()
