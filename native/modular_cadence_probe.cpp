#include "surface_transport.hpp"
#include "modular_render.hpp"
#include "fixed_collar_angle.hpp"
#include <iostream>
#include <iomanip>
int wmain(int argc,wchar_t** argv){try{
 using namespace malemod;using namespace witcher;
 if(argc<3||argc>5)throw std::runtime_error("Usage: modular_cadence_probe native-package output-directory [worker] [mechanical|retained]");
 const std::filesystem::path dir=argv[1],out=argv[2];std::filesystem::create_directories(out);
 const auto workerPath=argc>=4?std::filesystem::path(argv[3]):dir/"surface_worker.exe";
 const std::wstring mode=argc==5?argv[4]:L"full";
 if(mode!=L"full"&&mode!=L"mechanical"&&mode!=L"retained")throw std::runtime_error("Unknown worker mode");
 auto read=[](auto p){std::ifstream f(p,std::ios::binary);if(!f)throw std::runtime_error("Missing input");return std::string(std::istreambuf_iterator<char>(f),{});};
 auto c=read(dir/"geralt.render"),n=read(dir/"geralt.modular-native"),m=read(dir/"geralt.modular-materials");
 RenderContract contract(dir/"geralt.render",c.substr(8,40),c.substr(48,64));
 ModularRenderer renderer(dir/"geralt.modular",dir/"geralt.modular-native",contract,n.substr(8,64),n.substr(72,64));
 renderer.EnableDynamic(dir/"geralt.modular-dynamic",dir/"geralt.modular-materials",m.substr(8,64),m.substr(72,64),m.substr(136,64));
 renderer.EnableTransfer(dir/"geralt.modular-transfer",n.substr(8,64));
 std::ofstream report(out/"timings.jsonl");report<<std::setprecision(12);
 using Clock=std::chrono::steady_clock;
 auto ms=[](auto a,auto b){return std::chrono::duration<double,std::milli>(b-a).count();};
 for(unsigned test=0;test<6;test++){
  surface::Controls controls;controls.values[0]=float(test%3);
  if(test>=3)for(unsigned i:{1u,2u,3u,5u})controls.values[i]=90;
  controls.values[7]=FixedCollarReferenceAngle;
  SurfaceClient worker(workerPath.wstring());auto initial=worker.Initialize(controls);
  auto shape=std::make_shared<const surface::Output>(initial);
  for(unsigned frame=0;frame<40;frame++){
   surface::wire::Request q;q.controls=controls;q.frame.seconds=1.f/60;
   q.frame.pitchForce=float(std::sin(frame*.2)*.6);q.frame.yawForce=float(std::cos(frame*.17)*.3);
   auto start=Clock::now();auto source=mode==L"mechanical"?worker.EvaluateMechanical(q,10000):mode==L"retained"?worker.EvaluateRetainedSkin(q,10000):worker.Evaluate(q,10000);auto solved=Clock::now();
   const auto pivot=surface::Precise(source.shaftGuide[0]);FixedAngleRegion region;region.origin=pivot;region.upwardDegrees=45;
   const double angle=test>=3?15:50;
   PresentFixedCollarSource(source,float(angle),region);
   auto state=renderer.Drive(source,pivot,FixedCollarFlow(region,float(angle)).Radians(),shape,controls.values[6]);auto driven=Clock::now();
   auto mesh=renderer.Evaluate(state);auto end=Clock::now();
   std::uint64_t hash=14695981039346656037ull;
   for(const auto& part:mesh->parts)for(const auto& vertex:part.vertices)
    for(unsigned char b:std::string_view(reinterpret_cast<const char*>(&vertex),sizeof(vertex))){hash^=b;hash*=1099511628211ull;}
   report<<"{\"case\":"<<test<<",\"frame\":"<<frame<<",\"sourceMs\":"<<ms(start,solved)<<",\"driveMs\":"<<ms(solved,driven)<<",\"meshMs\":"<<ms(driven,end)<<",\"rebuilt\":"<<(mesh->rebuilt?"true":"false")<<",\"stages\":[";
   for(unsigned i=0;i<6;i++)report<<(i?",":"")<<mesh->stageMilliseconds[i];
   report<<"],\"poseStages\":[";for(unsigned i=0;i<4;i++)report<<(i?",":"")<<mesh->poseMilliseconds[i];
   report<<"],\"hash\":\""<<hash<<"\"}\n";
   if(frame==39){
    std::ofstream geometry(out/("shape-"+std::to_string(test)+".bin"),std::ios::binary);
    for(const auto& part:mesh->parts)geometry.write(reinterpret_cast<const char*>(part.vertices.data()),part.vertices.size()*sizeof(ModularVertex));
   }
  }
  report.flush();std::cout<<"Completed case "<<test<<std::endl;
 }
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
