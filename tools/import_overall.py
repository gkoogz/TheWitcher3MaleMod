"""Official native round-trip for each prepared Overall mesh, without install."""
import argparse,shutil
from pathlib import Path
from mod import ROOT,settings,read_json,write_json,import_mesh,export_resource,digest
from verify_motion import verify
import numpy as np

def import_bank(job):
    job=Path(job).resolve();cfg=settings();record=read_json(job/'overall.json')
    cage=ROOT/record['cage'];outputs=[]
    for state in record['states']:
        ui=state['ui'];check=job/'native'/('ui-'+str(ui));check.mkdir(parents=True,exist_ok=True)
        resource='characters/malemod/body/overall_'+job.name+'/overall_'+str(ui)+'.w2mesh'
        source=ROOT/state['fbx']
        if digest(source)!=state['fbxSHA256']:raise ValueError('Prepared state changed')
        if not (check/'native-verification.json').exists():
            if not (ROOT/'generated/workspace'/resource).exists():import_mesh(cfg,source,resource)
            if not (check/'native-motion.fbx').exists():export_resource(cfg,resource,check/'native-motion.fbx')
            shutil.copy2(source,check/'geralt-motion.fbx');shutil.copy2(cage/'motion.json',check/'motion.json')
            for lod in range(2):
                old=dict(np.load(cage/f'motion-lod{lod}.npz'));old['points']=np.load(job/f'ui-{ui}-lod{lod}.npz')['points']
                np.savez_compressed(check/f'motion-lod{lod}.npz',**old)
            verify(check)
        outputs.append(dict(ui=ui,resource=resource,sha256=digest(ROOT/'generated/workspace'/resource),verification=(check/'native-verification.json').relative_to(ROOT).as_posix()))
        write_json(job/'native-bank.json',dict(states=outputs,complete=len(outputs)==len(record['states']),observedGameplay=False))
    print('PASS complete Overall native mesh bank:',job)
    return outputs

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('job',type=Path);import_bank(p.parse_args().job)
