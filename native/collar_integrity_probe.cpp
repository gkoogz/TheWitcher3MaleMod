// Export the actual target and native output for the mandatory collar gate.
#include "surface_pipeline.hpp"
#include "render_contract.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iomanip>
using namespace malemod::witcher;
namespace surface=malemod::surface;
template<class T>void Write(const std::filesystem::path& path,const std::vector<T>& v){std::ofstream f(path,std::ios::binary);f.write(reinterpret_cast<const char*>(v.data()),v.size()*sizeof(T));if(!f)throw std::runtime_error("Cannot write collar artifact");}
int wmain(int argc,wchar_t** argv){try{
 if(argc!=7&&argc!=8)throw std::runtime_error("Usage: collar_integrity_probe worker binding render pin bindingHash output [quick]");const bool quick=argc==8;
 std::wstring pw=argv[4],hw=argv[5];std::string pin(pw.begin(),pw.end()),hash(hw.begin(),hw.end());RenderContract render(argv[3],pin,hash);
 const std::filesystem::path out=argv[6];if(std::filesystem::exists(out))throw std::runtime_error("Use fresh output");std::filesystem::create_directories(out);
 std::unique_ptr<SurfacePipeline> pipeline;
 std::ofstream report(out/"cases.json");report<<std::setprecision(9)<<"[";unsigned count=0;
 auto run=[&](const std::string& label,surface::wire::Request q){if(q.reset){pipeline=std::make_unique<SurfacePipeline>(argv[1],argv[2],pin);pipeline->Initialize({});q.reset=false;auto settle=q;settle.frame.seconds=.15f;for(unsigned step=0;step<6;step++)pipeline->Evaluate(settle);}auto frame=pipeline->Evaluate(q);
  for(unsigned lod=0;lod<2;lod++)Write(out/(label+"-lod"+std::to_string(lod)+".bin"),frame.targetPositions[lod]);
  Write(out/(label+"-render.bin"),ComposeRenderVertices(render,frame.targetPositions));
  const auto& m=frame.source.collarMetric;if(count++)report<<",";
  report<<"{\"label\":\""<<label<<"\",\"controls\":[";for(unsigned i=0;i<18;i++){if(i)report<<",";report<<q.controls.values[i];}
  report<<"],\"radius\":"<<m.radius<<",\"length\":"<<m.length<<",\"sourceMs\":"<<frame.sourceMilliseconds<<",\"targetMs\":"<<frame.targetMilliseconds<<"}";report.flush();
  std::cout<<label<<"\n"<<std::flush;
 };
 surface::wire::Request q;q.reset=true;run("neutral",q);
 for(unsigned state=0;state<3;state++)for(unsigned overall:{1u,25u,50u,75u,100u})for(unsigned width:{1u,50u,100u})for(unsigned angle:{1u,50u,100u}){
  if(quick&&(overall!=100||width!=100))continue;
  q={};q.reset=true;q.controls.values[0]=float(state);q.controls.values[1]=float(overall);q.controls.values[3]=float(width);q.controls.values[7]=float(angle);
  run("s"+std::to_string(state)+"-o"+std::to_string(overall)+"-w"+std::to_string(width)+"-a"+std::to_string(angle),q);
 }
 for(unsigned control=2;control<=9;control++)for(unsigned side=0;side<2;side++){
  if(quick)continue;
  q={};q.reset=true;q.controls.values[1]=100;q.controls.values[control]=side?100.f:((control==2||control==4)?0.f:1.f);
  run("shape"+std::to_string(control)+"-"+std::to_string(side),q);
 }
 for(unsigned state=0;state<3;state++){
  q={};q.reset=true;q.controls.values[0]=float(state);for(unsigned i=1;i<18;i++)q.controls.values[i]=100;run("combined"+std::to_string(state),q);
  q={};q.reset=true;q.controls.values[0]=float(state);q.controls.values[1]=100;q.controls.values[3]=70;q.controls.values[7]=64;run("reported"+std::to_string(state),q);
  q.reset=false;q.frame.seconds=1.f/60.f;
  for(unsigned i=0;i<(quick?10u:40u);i++){q.frame.pitchForce=8.f*std::sin(i*.37f);q.frame.yawForce=12.f*std::sin(i*.29f);run("motion"+std::to_string(state)+"-"+std::to_string(i),q);}
 }
 report<<"]\n";std::cout<<"Exported "<<count<<" target/native cases\n";
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
