"""Build the private v2 adapter against the exact prepared worker/bindings.

Generate the canonical kernel/worker and native fitted assets first, as
recorded in v2/README.md and docs/HANDOFF.md. This tool never stages or installs.
"""
from pathlib import Path
import hashlib,subprocess,json,os,shutil
from witcher_v2 import checked_reference
r=Path(__file__).resolve().parents[1];b=r/'v2/build';out=b/'native-runtime';out.mkdir(exist_ok=True);checked_reference();h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();extensions=json.loads((r/'v2/base-extensions.lock.json').read_text());
for row in extensions['files']:
 if h(r.parent/'MaleMod'/row['path'])!=row['sha256']:raise ValueError('Shared v2 source changed: '+row['path'])
from v2_native_draw_contract import generate as generate_draw_contract
generate_draw_contract(b/'runtime-binding/geralt-source-binding.bin',b/'runtime-binding/clinical-topology.json',b/'runtime-binding/geralt-clinical-topology.bin',out/'native_draw_contract.inc')
content='#pragma once\nnamespace malemod::witcher::v2::identity {\n'+''.join('inline constexpr char '+name+'[]="'+h(path)+'";\n'for name,path in [('worker',b/'canonical-core/canonical_worker.exe'),('binding',b/'runtime-binding/geralt-source-binding.bin'),('fingerprints',b/'runtime-binding/graphics-owned-fingerprints.bin'),('garment',b/'runtime-binding/geralt-meridian-binding.bin'),('garmentRender',b/'runtime-binding/garment.render'),('coverage',b/'runtime-binding/geralt-meridian-coverage.bin'),('clinicalTopology',b/'runtime-binding/geralt-clinical-topology.bin'),('clinicalTopologyMetadata',b/'runtime-binding/clinical-topology.json'),('nativeDrawContract',out/'native_draw_contract.inc'),('clinicalRender',b/'runtime-binding/clinical.render'),('clinicalBakes',b/'runtime-binding/clinical-splat-bakes.bin')])+'}\n'
identity=out/'runtime_identity.inc'
if not identity.exists() or identity.read_text()!=content:identity.write_text(content)
cmake=os.environ.get('MALEMOD_CMAKE') or shutil.which('cmake') or 'C:/BuildTools/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'
subprocess.run([cmake,'-S',str(r/'v2/native'),'-B',str(out/'cmake'),'-G','Visual Studio 17 2022','-A','x64','-DMALEMOD_IDENTITY_PATH='+str(out),'-DMALEMOD_CANONICAL_BASE_PATH='+str(r.parent/'Work/dependencies/base-wolverine')],check=True)
subprocess.run([cmake,'--build',str(out/'cmake'),'--config','Release','--parallel','4'],check=True)
