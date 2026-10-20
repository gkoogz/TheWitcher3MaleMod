#include "target_surface.hpp"
#include "render_contract.hpp"
#include <malemod/surface/wire.hpp>
#include <fstream>
#include <iostream>
#include <chrono>
#include <future>
using namespace malemod::surface;
using namespace malemod::witcher;
Output Read(const std::filesystem::path& p){std::ifstream f(p,std::ios::binary);wire::Bytes b((std::istreambuf_iterator<char>(f)),{});return wire::DecodeOutput(b);}
int main(int argc,char** argv){try{
 if(argc==5){
  TargetSurface target(std::filesystem::path(argv[1])/"geralt.bindings","431e626cae6fb6720b552f8b20206727fe809c80");
  auto neutral=Read(argv[2]);target.SetNeutralCollar(neutral);for(unsigned lod=0;lod<2;lod++)target.Evaluate(lod,neutral);
  for(unsigned repeat=0;repeat<std::stoul(argv[4]);repeat++)for(unsigned state=0;state<3;state++)for(unsigned angle:{1,5,10,15,20,25,30,35,40,45,50,60,70,80,90,100}){
   auto label="s"+std::to_string(state)+"-a"+std::to_string(angle);
   auto source=Read(std::filesystem::path(argv[3])/label/"original"/(label+"-source.bin"));
   auto other=std::async(std::launch::async,[&]{return target.Evaluate(1,source,float(angle));});target.Evaluate(0,source,float(angle));other.get();
   std::cout<<repeat<<' '<<label<<'\n'<<std::flush;
  }return 0;
 }
 if(argc!=6)throw std::invalid_argument("native-directory source-output neutral-output result-directory angle OR native-directory neutral-output sweep-directory repeats");
 std::filesystem::path n(argv[1]),output(argv[4]);std::filesystem::create_directories(output);
 const std::string revision="431e626cae6fb6720b552f8b20206727fe809c80",binding="8a580482e44220bf0ec6f51541d2b9dae146e69f87454aa1e4a401d4ee80efad";
 TargetSurface target(n/"geralt.bindings",revision);if(!target.CorrectiveError().empty())throw std::runtime_error(target.CorrectiveError());
 auto neutral=Read(argv[3]);target.SetNeutralCollar(neutral);for(unsigned lod=0;lod<2;lod++)target.Evaluate(lod,neutral);
 auto source=Read(argv[2]);double angle=std::stod(argv[5]);auto begin=std::chrono::steady_clock::now();std::array<std::vector<PrecisePoint>,2> positions;
 for(unsigned lod=0;lod<2;lod++){
  positions[lod]=target.Evaluate(lod,source,float(angle));
 }
 for(unsigned retry=0;retry<8;retry++){
  const auto gains=target.FixedAngleGains();if(gains[0]==gains[1])break;
  const double cap=retry==7?0.:std::min(gains[0],gains[1]);for(unsigned lod=0;lod<2;lod++)positions[lod]=target.Evaluate(lod,source,float(angle),cap);
 }
 for(unsigned lod=0;lod<2;lod++){std::ofstream f(output/("case-lod"+std::to_string(lod)+".bin"),std::ios::binary);f.write(reinterpret_cast<const char*>(positions[lod].data()),positions[lod].size()*sizeof(PrecisePoint));}
 auto end=std::chrono::steady_clock::now();auto weights=target.CorrectiveWeights();
 RenderContract contract(n/"geralt.render",revision,binding);auto vertices=ComposeRenderVertices(contract,positions);std::ofstream rendered(output/"case-render.bin",std::ios::binary);rendered.write(reinterpret_cast<const char*>(vertices.data()),vertices.size()*sizeof(vertices[0]));
 const auto gains=target.FixedAngleGains();std::ofstream result(output/"result.json");result<<"{\"angle\":"<<angle<<",\"angleGains\":["<<gains[0]<<','<<gains[1]<<"],\"weights\":["<<weights[0]<<','<<weights[1]<<"],\"targetMs\":"<<std::chrono::duration<double,std::milli>(end-begin).count()<<"}";
 auto reports=target.CorrectiveReports();std::cout<<"angle "<<angle<<" weights "<<weights[0]<<' '<<weights[1]<<'\n'<<reports[0]<<'\n'<<reports[1]<<'\n';return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
