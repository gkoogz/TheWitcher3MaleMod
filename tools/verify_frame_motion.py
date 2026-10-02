"""Motion regression on the approved guide using pinned Base numerical kernels.

This is a numerical gate, not native gameplay or a frame-cost measurement.
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
    values=lambda p:'{'+','.join(format(float(x),'.12f')+'f' for x in p)+'}'
    compliance=[.0015*(.02+.98*(i/10)**2)*m['bendMultipliers'][i] for i in range(10)]
    job=ROOT/'build/motion'/('frame-motion-test-'+uuid.uuid4().hex[:12]);job.mkdir()
    source=r'''#include <malemod/physics/rig_kernels.hpp>
#include <cstdio>
using namespace malemod;using namespace malemod::physics;
State initial(){State s;s.position={@points@};s.oldPosition=s.position;s.velocity.resize(12);s.invMass.resize(12,1.f/1.825f);s.invMass[0]=s.invMass[1]=0;return s;}
float compliance[10]=@compliance@;const float segment=@segment@,g=@gravity@,dt=1.f/60;
void step(State& s,V3 gravity,V3 linear,V3 omega,V3 alpha){
s.oldPosition=s.position;for(int i=2;i<12;i++)IntegrateRelative(s,i,gravity,linear,omega,alpha,6*g,1.8f,dt);
float ls[11]={};V3 bl[10]={};PDBendData bd[10];for(int i=0;i<10;i++)bd[i]=PrepareBend(s,i+1,compliance[i],dt,.5f);
for(int iteration=0;iteration<24;iteration++){for(int i=1;i<11;i++)SolveDistance(s,i,i+1,segment,.0000001f,ls[i],dt);for(int i=0;i<10;i++)SolveBendPrepared(s,i+1,bd[i],bl[i]);}
for(int i=2;i<12;i++)s.velocity[i]=(s.position[i]-s.oldPosition[i])/dt;
}
int main(){State stationary=initial(),travel=initial(),moving=initial();auto rest=moving.position;
float maxError=0,maxExcursion=0,travelError=0;V3 filteredLinear{},filteredOmega{},filteredAlpha{},travelAcceleration{},previousTravelOrigin{},previousTravelVelocity{3,0,0};
for(int frame=0;frame<1800;frame++){
float t=frame*dt;V3 gravity{0,0,-g},linear{},omega{},alpha{};
// Measure a float world-space pelvis travelling at 3 native units/second,
// including finite-difference roundoff, rather than supplying known zero input.
V3 travelOrigin{3*t,0,0},travelVelocity=frame==0?V3{3,0,0}:(travelOrigin-previousTravelOrigin)/dt;
travelAcceleration=FilterMotion(travelAcceleration,(travelVelocity-previousTravelVelocity)/dt,20,4*g,dt);
previousTravelOrigin=travelOrigin;previousTravelVelocity=travelVelocity;
step(stationary,gravity,{},{},{});step(travel,gravity,travelAcceleration,{},{});
for(int i=0;i<12;i++)travelError=max(travelError,Length(stationary.position[i]-travel.position[i]));
if(frame>=600&&frame<1200)linear={.8f*sinf(2*t),0,0};
if(frame>=1200){float angle=.6f*sinf(t);omega={.6f*cosf(t),0,0};alpha={-.6f*sinf(t),0,0};gravity={0,-g*sinf(angle),-g*cosf(angle)};}
filteredLinear=FilterMotion(filteredLinear,linear,20,4*g,dt);
filteredOmega=FilterMotion(filteredOmega,omega,20,10,dt);
filteredAlpha=FilterMotion(filteredAlpha,alpha,20,40,dt);
step(moving,gravity,filteredLinear,filteredOmega,filteredAlpha);
for(int i=0;i<12;i++){if(!std::isfinite(Length(moving.position[i])))return 2;maxExcursion=max(maxExcursion,Length(moving.position[i]-rest[i]));}
for(int i=1;i<11;i++)maxError=max(maxError,fabsf(Length(moving.position[i+1]-moving.position[i])-segment));
for(int i=0;i<8;i++){V3 p,tangent;SampleGuide(moving,12,i/7.f,p,tangent);if(!std::isfinite(Length(p))||fabsf(Length(tangent)-1)>1e-5f)return 3;}
}
if(travelError>.0001f||maxError>.002f||maxExcursion>.3f||Length(moving.position[0]-rest[0])>1e-7f||Length(moving.position[1]-rest[1])>1e-7f)return 4;
printf("{\"frames\":1800,\"nodes\":12,\"constantTravelTrajectoryError\":%.9g,\"maximumSegmentErrorNative\":%.9g,\"maximumExcursionNative\":%.9g,\"passed\":true}\n",travelError,maxError,maxExcursion);
}
'''
    source=source.replace('@points@',','.join(values(p) for p in guide)).replace('@compliance@',values(compliance)).replace('@segment@',format(m['restLength']*k/11,'.12f')+'f').replace('@gravity@',format(110*k,'.12f')+'f')
    (job/'test.cpp').write_text(source)
    batch=job/'run.cmd';batch.write_text('@call "C:/BuildTools/VC/Auxiliary/Build/vcvars64.bat" >nul\n@cl /nologo /O2 /fp:strict /EHsc /std:c++17 /I"'+str(cfg['base']/'include')+'" "'+str(job/'test.cpp')+'" /Fo"'+str(job/'test.obj')+'" /Fe"'+str(job/'test.exe')+'"\n@if errorlevel 1 exit /b %errorlevel%\n')
    subprocess.run(['cmd','/c',str(batch)],check=True,cwd=ROOT)
    result=subprocess.run([str(job/'test.exe')],check=True,capture_output=True,text=True);report=json.loads(result.stdout)
    report.update(baseCommit=pin['commit'],sourceFitSHA256=digest(ROOT/c['fitReport']),sourceSHA256=digest(job/'test.cpp'),
        executableSHA256=digest(job/'test.exe'),phases=['stationary/constant-travel equivalence','lateral acceleration','oscillating frame rotation'],
        omissions=['lobe/body contacts','WitcherScript runtime and frame cost'],observedGameplay=False)
    write_json(job/'verification.json',report);print(json.dumps(report,indent=2));return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('cage',type=Path);verify(p.parse_args().cage)
