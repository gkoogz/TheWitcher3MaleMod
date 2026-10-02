"""Exercise the measured solid body coupled to the flexible Base rod.

Native script compilation and contacts are separate gates; this regression
checks accepted solid shape and attachment stability under 3D frame forces.
"""
import json,re,subprocess,uuid
from pathlib import Path
from mod import ROOT,settings,base_checkout,read_json,write_json,digest
from fixed_physics import independent_rig,generate

def verify(cage):
    cfg=settings();pin=base_checkout(cfg);cage=Path(cage).resolve()
    rig=read_json(cage/'motion-dyng.json');rig['_chunks']={'CSkeleton #0':rig['_chunks']['CSkeleton #1']};rig,_=independent_rig(rig)
    job=ROOT/'build/motion'/('solid-physics-test-'+uuid.uuid4().hex[:12]);job.mkdir()
    runtime,receipt=generate(cfg['base'],rig,job,cage=cage)
    def vectors(name,n):
        return ['{'+','.join(re.search(re.escape(name)+r'\['+str(i)+r'\] = Vector\(([^)]*)\)',runtime)[1].split(',')[:3])+'}' for i in range(n)]
    def scalars(name,n):return [re.search(re.escape(name)+r'\['+str(i)+r'\] = ([^;]+)',runtime)[1]+'f' for i in range(n)]
    cpp=r'''#include <malemod/physics/rig_kernels.hpp>
#include <malemod/physics/rigid_cluster.hpp>
#include <cstdio>
using namespace malemod;using namespace malemod::physics;
int main(){State s;s.position={@points@};s.oldPosition=s.position;s.velocity.resize(21);s.invMass={@mass@};auto rest=s.position;
V3 rc=@center@;Q4 rotation{0,0,0,1};float bc[10]={@bend@};const float dt=1.f/60,g=@gravity@,segment=@segment@;
float maxSegment=0,maxPair=0,maxExcursion=0;V3 filteredLinear{},filteredOmega{},filteredAlpha{};
for(int frame=0;frame<1800;frame++){
float t=frame*dt;V3 gravity{0,0,-g},linear{},omega{},alpha{};
if(frame>=600&&frame<1200)linear={.8f*sinf(2*t),.6f*cosf(1.5f*t),.5f*sinf(3*t)};
if(frame>=1200){omega={.5f*cosf(t),.4f*sinf(1.3f*t),.3f*cosf(1.7f*t)};alpha={-.5f*sinf(t),.52f*cosf(1.3f*t),-.51f*sinf(1.7f*t)};}
filteredLinear=FilterMotion(filteredLinear,linear,20,4*g,dt);filteredOmega=FilterMotion(filteredOmega,omega,20,10,dt);filteredAlpha=FilterMotion(filteredAlpha,alpha,20,40,dt);
s.oldPosition=s.position;
for(int i=2;i<21;i++)if(i<12||i>=14)IntegrateRelative(s,i,gravity,filteredLinear,filteredOmega,filteredAlpha,6*g,1.8f,dt);
float ls[11]={};V3 bl[10]={};PDBendData bd[10];for(int i=0;i<10;i++)bd[i]=PrepareBend(s,i+1,bc[i],dt,.5f);
for(int iteration=0;iteration<24;iteration++){
for(int i=1;i<11;i++)SolveDistance(s,i,i+1,segment,.0000001f,ls[i],dt);
for(int i=0;i<8;i++)SolveBendPrepared(s,i+1,bd[i],bl[i]);
if(iteration==0||iteration==8||iteration==16||iteration==23)rotation=FitCluster(s,rest,rc,8,4,14,7,rotation);
ProjectCluster(s,rest,rc,8,4,14,7,rotation);
}
for(int i=2;i<21;i++)if(i<12||i>=14){s.velocity[i]=(s.position[i]-s.oldPosition[i])/dt;if(!std::isfinite(Length(s.position[i])))return 2;maxExcursion=max(maxExcursion,Length(s.position[i]-rest[i]));}
for(int i=1;i<11;i++)maxSegment=max(maxSegment,fabsf(Length(s.position[i+1]-s.position[i])-segment));
for(int i=0;i<11;i++)for(int j=0;j<i;j++){int a=ClusterIndex(i,8,4,14),b=ClusterIndex(j,8,4,14);maxPair=max(maxPair,fabsf(Length(s.position[a]-s.position[b])-Length(rest[a]-rest[b])));}
}
printf("{\"frames\":1800,\"maximumSegmentError\":%.9g,\"maximumSolidPairError\":%.9g,\"maximumExcursion\":%.9g}\n",maxSegment,maxPair,maxExcursion);
if(maxSegment>.002f||maxPair>1e-6f||maxExcursion>.4f||Length(s.position[0]-rest[0])>1e-7f||Length(s.position[1]-rest[1])>1e-7f)return 3;
}
'''
    c=receipt['coefficients'];replacements=dict(points=','.join(vectors('restPoints',21)),mass=','.join(scalars('physicsInvMass',21)),
       center='{'+','.join(re.search(r'headRestCenter = Vector\(([^)]*)',runtime)[1].split(',')[:3])+'}',
       bend=','.join(scalars('bendCompliance',10)),gravity=format(c['shaft_gravity'],'.12f')+'f',segment=format(receipt['restLengths'][0],'.12f')+'f')
    for key,value in replacements.items():cpp=cpp.replace('@'+key+'@',value)
    (job/'test.cpp').write_text(cpp)
    batch=job/'run.cmd';batch.write_text('@call "C:/BuildTools/VC/Auxiliary/Build/vcvars64.bat" >nul\n@cl /nologo /O2 /fp:strict /EHsc /std:c++17 /I"'+str(cfg['base']/'include')+'" "'+str(job/'test.cpp')+'" /Fo"'+str(job/'test.obj')+'" /Fe"'+str(job/'test.exe')+'"\n@if errorlevel 1 exit /b %errorlevel%\n')
    subprocess.run(['cmd','/c',str(batch)],check=True,cwd=ROOT)
    result=subprocess.run([str(job/'test.exe')],capture_output=True,text=True)
    print(result.stdout);result.check_returncode();report=json.loads(result.stdout)
    report.update(baseCommit=pin['commit'],sourceSHA256=digest(job/'test.cpp'),cageSHA256=digest(cage/'motion.json'),
                  passed=True,observedGameplay=False,omissions=['lobe/body contact trajectories','native script frame cost'])
    write_json(job/'verification.json',report);print(job);return report

if __name__=='__main__':
    verify(ROOT/read_json(ROOT/'generated/default-cage.json')['cage'])
