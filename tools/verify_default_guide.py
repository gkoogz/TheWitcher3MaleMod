"""Exercise the exported default guide with pinned Base kernels, not gameplay.

This isolated free-guide gate excludes lobe/body contacts and WitcherScript cost.
"""
import argparse,json,subprocess,uuid
from pathlib import Path
import numpy as np
from mod import ROOT,settings,base_checkout,read_json,write_json,digest
def verify(cage):
    cfg=settings();pin=base_checkout(cfg);cage=Path(cage).resolve()
    if not cage.is_relative_to(ROOT/'build/motion'):raise ValueError('Expected owned cage')
    c=read_json(cage/'motion.json');fit=read_json(ROOT/c['fitReport']);m=fit['sourceMechanics']
    k=fit['sourceToFBXScale']/100;guide=np.asarray(m['shaftGuide'])*k
    compliance=[.0015*(.02+.98*(i/10)**2)*m['bendMultipliers'][i] for i in range(10)]
    values=lambda p:'{'+','.join(format(float(x),'.9g')+'f' if '.' in format(float(x),'.9g') or 'e' in format(float(x),'.9g') else str(int(x))+'.0f' for x in p)+'}'
    job=ROOT/'build/motion'/('default-guide-test-'+uuid.uuid4().hex[:12]);job.mkdir()
    source='''#include <malemod/physics/rig_kernels.hpp>
#include <cstdio>
using namespace malemod;using namespace malemod::physics;
int main(){State s;s.position={@points@};s.oldPosition=s.position;s.velocity.resize(12);s.invMass.resize(12,1.f/1.825f);s.invMass[0]=s.invMass[1]=0;
auto rest=s.position;float compliance[10]=@compliance@,maxError=0;const float segment=@segment@,dt=1.f/60;
for(int frame=0;frame<600;frame++){
s.oldPosition=s.position;for(int i=2;i<12;i++){s.velocity[i].z-=@gravity@*dt;s.velocity[i]=s.velocity[i]*expf(-1.8f*dt);s.position[i]=s.position[i]+s.velocity[i]*dt;}
float ls[11]={};V3 bl[10]={};PDBendData bd[10];for(int i=0;i<10;i++)bd[i]=PrepareBend(s,i+1,compliance[i],dt,.5f);
for(int iteration=0;iteration<24;iteration++){for(int i=1;i<11;i++)SolveDistance(s,i,i+1,segment,.0000001f,ls[i],dt);for(int i=0;i<10;i++)SolveBendPrepared(s,i+1,bd[i],bl[i]);}
for(int i=2;i<12;i++){s.velocity[i]=(s.position[i]-s.oldPosition[i])/dt;if(!std::isfinite(Length(s.position[i])))return 2;}
for(int i=1;i<11;i++)maxError=max(maxError,fabsf(Length(s.position[i+1]-s.position[i])-segment));
for(int i=0;i<8;i++){V3 p,t;SampleGuide(s,12,i/7.f,p,t);if(!std::isfinite(Length(p))||fabsf(Length(t)-1)>1e-5f)return 3;}
}
if(Length(s.position[0]-rest[0])>1e-7f||Length(s.position[1]-rest[1])>1e-7f||maxError>.002f||s.position[11].z>=rest[11].z)return 4;
printf("{\\"frames\\":600,\\"nodes\\":12,\\"maximumSegmentErrorNative\\":%.9g,\\"tipSagNative\\":%.9g,\\"passed\\":true}\\n",maxError,rest[11].z-s.position[11].z);
}
'''
    source=source.replace('@points@',','.join(values(p) for p in guide)).replace('@compliance@',values(compliance)).replace('@segment@',format(m['restLength']*k/11,'.12f')+'f').replace('@gravity@',format(110*k,'.12f')+'f')
    (job/'test.cpp').write_text(source)
    batch=job/'run.cmd';batch.write_text('@call "C:/BuildTools/VC/Auxiliary/Build/vcvars64.bat" >nul\n@cl /nologo /O2 /fp:strict /EHsc /std:c++17 /I"'+str(cfg['base']/'include')+'" "'+str(job/'test.cpp')+'" /Fo"'+str(job/'test.obj')+'" /Fe"'+str(job/'test.exe')+'"\n@if errorlevel 1 exit /b %errorlevel%\n')
    subprocess.run(['cmd','/c',str(batch)],check=True,cwd=ROOT)
    result=subprocess.run([str(job/'test.exe')],check=True,capture_output=True,text=True);report=json.loads(result.stdout)
    report.update(baseCommit=pin['commit'],sourceGuide='evaluated default at 120 source frames',sourceFitSHA256=digest(ROOT/c['fitReport']),
        sourceSHA256=digest(job/'test.cpp'),executableSHA256=digest(job/'test.exe'),omissions=['lobe/body contacts','WitcherScript runtime and frame cost'],observedGameplay=False)
    write_json(cage/'free-guide-verification.json',report);print(json.dumps(report,indent=2));return report
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('cage',type=Path);verify(p.parse_args().cage)
