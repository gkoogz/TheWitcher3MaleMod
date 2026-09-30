"""Build the native motion/menu test from a verified cage export. Never installs."""
import shutil,uuid
from mod import *
from verify_motion import verify
from motion_entity import make_entity
from native_motion_profile import apply_profile
import numpy as np

def main():
    cfg=settings();pin=base_checkout(cfg);probe=read_json(ROOT/'build/motion/latest.json')
    if probe['baseCommit']!=pin['commit']:raise RuntimeError('Motion cage does not match Base pin')
    source=inside(ROOT,probe['job']);verify(source)
    for r in probe['resources']:
        if digest(required_file(inside(source,r['path'])))!=r['sha256']:raise RuntimeError('Motion resource changed')
    ws=ROOT/'build/jobs'/('motion-release-'+uuid.uuid4().hex[:12]);ws.mkdir(parents=True)
    authored=ROOT/'build/motion'/('revision-'+uuid.uuid4().hex[:12]);authored.mkdir(parents=True)
    make_entity(authored)
    dyng=read_json(source/'motion-dyng.json')
    cage=read_json(source/'motion.json');worlds=np.array(cage['authoredWorldRestFBX']);worlds[:,:3,3]/=100
    profile=apply_profile(dyng,cage['newBones'],worlds)
    write_json(authored/'bounded-dyng.json',dyng)
    converter=ROOT/'build/research/wkit-current/MaleModCR2W.exe'
    subprocess.run([str(converter),'import',str(authored/'bounded-dyng.json'),str(authored/'bounded.w3dyng')],check=True,capture_output=True)
    entity='items/bodyparts/geralt_items/legs/bare/l_01_mg__body_underwear.w2ent'
    for r in probe['resources']:
        src=authored/'scripted-motion-entity.w2ent' if r['path']==entity else authored/'bounded.w3dyng' if r['path'].endswith('.w3dyng') else inside(source,r['path'])
        target=inside(ws,r['path']);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target)
    scripts=ws/'scripts/local';scripts.mkdir(parents=True)
    shutil.copy2(ROOT/'probes/runtime/maleModPhysics.ws',scripts/'maleModPhysics.ws')
    project={'name':'modMaleMod','version':'0.4.3-controller-input-test','platform':'pc',
             'cacheBuilders':['textures','physics'],'scriptedCook':True,'motionEntity':entity,
             'scope':'Native secondary motion with F6 tuning panel: gravity, damping, simulation speed. Live size and Wolverine solver parity remain pending.'}
    write_json(authored/'profile-verification.json',profile)
    package=build(cfg,project,ws);verify_package(package)
    return package

if __name__=='__main__':main()
