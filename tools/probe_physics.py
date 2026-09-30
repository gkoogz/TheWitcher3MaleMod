"""Compile isolated native tuning declarations; never installs a runtime."""
import json
import shutil
import sys
import uuid
from mod import ROOT, settings, base_checkout, compile_scripts, digest, write_json


def main():
    cfg = settings()
    pin = base_checkout(cfg)
    sys.path.insert(0, str(cfg['base']))
    from malemod_base.controls import catalog
    source = ROOT/'probes/dynamic_constraint.ws'
    job = ROOT/'build/probe'/('physics-'+uuid.uuid4().hex[:12])
    scripts = job/'scripts/local'
    scripts.mkdir(parents=True)
    shutil.copy2(source, scripts/'maleModPhysicsProbe.ws')
    write_json(job/'control-catalog.json', catalog())
    native = compile_scripts(cfg, job)
    report = dict(baseCommit=pin['commit'], sourceSHA256=digest(source),
                  source='probes/dynamic_constraint.ws', native=native,
                  scriptImportsVerified=True, nativeHandleBindingVerified=False,
                  meshDeformationVerified=False, observedGameplay=False)
    write_json(job/'probe.json', report)
    print(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    main()
