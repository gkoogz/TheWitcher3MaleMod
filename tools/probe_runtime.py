"""Build and verify an isolated native cage/menu candidate. Never installs."""
from pathlib import Path
import shutil
from mod import ROOT,settings,base_checkout,digest,write_json,run_wcc,compile_scripts,import_mesh,export_resource,required_file
from prepare_motion import prepare
from motion_entity import make_entity
from verify_motion import verify


def main():
    cfg=settings();pin=base_checkout(cfg);job=prepare()
    resource='characters/malemod/probes/'+job.name+'/geralt_motion.w2mesh'
    import_mesh(cfg,job/'geralt-motion.fbx',resource)
    export_resource(cfg,resource,job/'native-motion.fbx')
    mesh_verification=verify(job)
    mesh=job/'characters/malemod/body/geralt_motion.w2mesh';mesh.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'generated/workspace'/resource,mesh)
    entity=make_entity(job)
    scripts=job/'scripts/local';scripts.mkdir(parents=True)
    shutil.copy2(ROOT/'probes/runtime/maleModPhysics.ws',scripts/'maleModPhysics.ws')
    compilation=compile_scripts(cfg,job)
    inputs=[mesh,entity,job/'characters/malemod/physics/geralt_motion.w3dyng']
    intake=job/'intake'
    for source in inputs:
        target=intake/source.relative_to(job);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    native=run_wcc(cfg,'cook',['-platform=pc','-mod='+str(intake),'-outdir='+str(job/'cooked')+'\\'],job,'motion-cage')
    for source in inputs:required_file(job/'cooked'/source.relative_to(job))
    log=(ROOT/native['logPath']).read_text()
    for kind in ['CMeshSkinningAttachment','CAnimDangleComponent','CAnimDangleConstraint_Dyng','CDyngResource','CSkeleton']:
        if ': '+kind+' (' not in log:raise RuntimeError('Native cooker did not retain '+kind)
    # Custom script classes are tested in a separate input/output tree. Failure
    # is recorded as an unresolved gate; it never enters a production package.
    scripted=job/'scripted-intake'/entity.relative_to(job);scripted.parent.mkdir(parents=True)
    shutil.copy2(job/'scripted-motion-entity.w2ent',scripted)
    scripted_workspace=job/'scripted-workspace'
    for source in inputs:
        target=scripted_workspace/source.relative_to(job);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(job/'scripted-motion-entity.w2ent' if source==entity else source,target)
    shutil.copytree(job/'scripts',scripted_workspace/'scripts')
    try:
        scripted_native=run_wcc(cfg,'cook',['-platform=pc','-mod='+str(job/'scripted-intake'),
                               '-outdir='+str(job/'scripted-cooked')+'\\'],scripted_workspace,'scripted-motion')
        script_cook_succeeded=True;script_error=None
    except RuntimeError as error:
        scripted_native=None;script_cook_succeeded=False;script_error=str(error).splitlines()[0]
    report={'baseCommit':pin['commit'],'job':job.relative_to(ROOT).as_posix(),
            'meshVerification':mesh_verification,'nativeCook':native,'menuCompilation':compilation,
            'customItemCookSucceeded':script_cook_succeeded,'customItemCook':scripted_native,
            'customItemCookFailure':script_error,'runtimeHandleBindingVerified':False,
            'observedGameplay':False,'liveSizeVerified':False,'installed':False,
            'toolchain':{'converter':digest(ROOT/'build/research/wkit-current/MaleModCR2W.exe'),
                         'library':digest(ROOT/'build/research/wkit-current/WolvenKit.CR2W.dll')},
            'resources':[{'path':p.relative_to(job).as_posix(),'sha256':digest(p)} for p in inputs]}
    write_json(job/'runtime-probe.json',report);write_json(ROOT/'build/motion/latest.json',report)
    print('Native cage probe complete; runtime binding/gameplay and live dimensions are separate gates.')
    return report


if __name__=='__main__':main()
