#include "surface_transport.hpp"
#include "live_modular_controls.hpp"
#include "fixed_collar_angle.hpp"
#include <iostream>
#include <filesystem>
int wmain(int argc,wchar_t** argv){try{
 using namespace malemod;using namespace witcher;
 if(argc!=3&&argc!=4)throw std::runtime_error("Usage: live_controls_probe native-package output-directory [smallest]");
 std::filesystem::path dir=argv[1],out=argv[2];std::filesystem::create_directories(out);
 auto read=[](auto p){std::ifstream f(p,std::ios::binary);if(!f)throw std::runtime_error("Missing probe input");return std::string(std::istreambuf_iterator<char>(f),{});};
 auto c=read(dir/"geralt.render"),n=read(dir/"geralt.modular-native"),m=read(dir/"geralt.modular-materials");
 RenderContract contract(dir/"geralt.render",c.substr(8,40),c.substr(48,64));
 ModularRenderer renderer(dir/"geralt.modular",dir/"geralt.modular-native",contract,n.substr(8,64),n.substr(72,64));
 renderer.EnableDynamic(dir/"geralt.modular-dynamic",dir/"geralt.modular-materials",m.substr(8,64),m.substr(72,64),m.substr(136,64));
 renderer.EnableTransfer(dir/"geralt.modular-transfer",n.substr(8,64));
 surface::Controls controls;
 if(argc==4){controls.values[0]=2;for(unsigned i:{1u,2u,3u,5u})controls.values[i]=1;controls.values[4]=35;controls.values[6]=95;controls.values[7]=90;controls.values[8]=100;}
 auto sourceControls=controls;sourceControls.values[7]=FixedCollarReferenceAngle;
 SurfaceClient worker((dir/"surface_worker.exe").wstring());
 auto source=worker.Initialize(sourceControls);auto rest=std::make_shared<const surface::Output>(source);
 auto pivot=surface::Precise(source.shaftGuide[0]);FixedAngleRegion region;region.origin=pivot;region.upwardDegrees=45;
 PresentFixedCollarSource(source,controls.values[7],region);
 auto frame=renderer.Evaluate(renderer.Drive(source,pivot,0,rest,controls.values[6]));
 if(argc==4){
  for(unsigned i=0;i<100;i++)renderer.Evaluate(renderer.Drive(source,pivot,0,rest,controls.values[6]));
  std::cout<<"PASS smallest combined shape: 100 repeated exact evaluations\n";return 0;
 }
 std::ofstream report(out/"live-controls.jsonl");
 {auto requested=controls;requested.values[3]=51;try{PresentLiveControls(frame,controls,requested,contract);}catch(const std::exception& e){std::cerr<<"Single width step: "<<e.what()<<'\n';}}
 unsigned cases=0,limited=0;double total=0,maximum=0;
 for(unsigned control:{1u,2u,3u,4u,5u,6u,7u,8u,9u})for(float value:{1.f,15.f,25.f,49.f,50.f,51.f,75.f,90.f,100.f}){
  auto requested=controls;requested.values[control]=value;
  std::cout<<"control "<<control<<" value "<<value<<'\n';
  auto start=std::chrono::steady_clock::now();auto presented=PresentBoundedLiveControls(frame,controls,requested,contract);auto display=presented.frame;
  double ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
  unsigned changed=0;for(unsigned p=0;p<4;p++){
   if(frame->parts[p].indices!=display->parts[p].indices)throw std::runtime_error("Live controls rebuilt native topology");
   for(unsigned i=0;i<frame->parts[p].vertices.size();i++){
    const auto& a=frame->parts[p].vertices[i];const auto& b=display->parts[p].vertices[i];
    changed+=a.position!=b.position;
    if(a.uv!=b.uv||a.bones!=b.bones||a.weights!=b.weights||a.reflection!=b.reflection)throw std::runtime_error("Control update changed UV/bone ownership");
   }
  }
  report<<"{\"control\":"<<control<<",\"value\":"<<value<<",\"ms\":"<<ms<<",\"changed\":"<<changed<<",\"fraction\":"<<presented.fraction<<"}\n";report.flush();
  total+=ms;maximum=(std::max)(maximum,ms);++cases;
  limited+=presented.fraction<1;
  if((value==49||value==51)&&presented.fraction!=1)throw std::runtime_error("An ordinary single slider step required a slow refit");
 }
 std::cout<<"PASS "<<cases<<" bounded prepared mesh edits ("<<limited<<" large jumps limited pending exact fit); mean "<<total/cases<<" ms, maximum "<<maximum<<" ms; immutable indices/UV/weights. Offline only.\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
