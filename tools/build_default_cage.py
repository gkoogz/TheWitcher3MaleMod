"""Author and officially round-trip a new evaluated-default motion cage."""
import shutil,uuid
from mod import ROOT,settings,import_mesh,export_resource,write_json,digest
from prepare_motion import prepare
from verify_motion import verify
def main():
    cfg=settings();job=prepare()
    resource='characters/malemod/body/default_'+uuid.uuid4().hex[:12]+'.w2mesh'
    import_mesh(cfg,job/'geralt-motion.fbx',resource)
    export_resource(cfg,resource,job/'native-motion.fbx')
    target=job/'characters/malemod/body/geralt_motion.w2mesh';target.parent.mkdir(parents=True)
    shutil.copy2(ROOT/'generated/workspace'/resource,target)
    verification=verify(job)
    receipt=dict(cage=job.relative_to(ROOT).as_posix(),motionSHA256=digest(job/'motion.json'),nativeVerification=verification)
    write_json(ROOT/'generated/default-cage.json',receipt);return job
if __name__=='__main__':print(main())
