#include "modular_render.hpp"
#include <malemod/surface/wire.hpp>
#include <iostream>
int main(int argc,char** argv){try{
 if(argc!=5&&argc!=7&&argc!=9)throw std::invalid_argument("geometry native carrier source-wire [dynamic materials [transfer slider]]");
 auto read=[](const char* path){std::ifstream f(path,std::ios::binary);if(!f)throw std::invalid_argument("Missing test input");return std::string((std::istreambuf_iterator<char>(f)),{});};
 const auto carrier=read(argv[3]),native=read(argv[2]),wire=read(argv[4]);
 malemod::witcher::RenderContract contract(argv[3],carrier.substr(8,40),carrier.substr(48,64));
 malemod::witcher::ModularRenderer renderer(argv[1],argv[2],contract,native.substr(8,64),native.substr(72,64));
 if(argc>=7){auto materials=read(argv[6]);renderer.EnableDynamic(argv[5],argv[6],materials.substr(8,64),materials.substr(72,64),materials.substr(136,64));}
 auto output=malemod::surface::wire::DecodeOutput({wire.begin(),wire.end()});
 double radians=0;if(argc==9){renderer.EnableTransfer(argv[7],native.substr(8,64));double slider=std::stod(argv[8]);radians=(50-slider)/(slider<50?49.:50.)*(slider<50?45.:30.)*3.141592653589793/180.;}
 auto pivot=malemod::surface::Precise(output.shaftGuide[0]);auto state=renderer.Drive(output,pivot,radians);auto first=renderer.Evaluate(state);auto moved=state;moved.frames[13].origin[2]-=.4;auto next=renderer.Evaluate(moved);
 unsigned changed=0,unchanged=0;
 for(unsigned i=0;i<4;i++){
  const auto& a=first->parts[i];const auto& b=next->parts[i];if(a.vertices.empty()||a.indices!=b.indices)throw std::runtime_error("Mutable or missing native topology");
  for(unsigned j=0;j<a.vertices.size();j++){if(a.vertices[j].position!=b.vertices[j].position)++changed;else ++unchanged;}
 }
 if(!changed||!unchanged)throw std::runtime_error("Mechanical objects not independently driven");
 // Physics may bend a proximal guide while the control/rest aperture stays
 // fixed. Rebuilding indices here would recut the body every simulation step.
 auto bent=state;bent.frames[2].origin[2]+=.1;
 const auto physical=renderer.Evaluate(bent);
 for(unsigned i=0;i<4;i++)if(physical->parts[i].indices!=first->parts[i].indices)throw std::runtime_error("Physics motion rebuilt the pelvic opening");
 if(argc==9){
  auto altered=output;for(auto& p:altered.anatomy.positions)if(p.x>30)p.z+=.03;
  auto alteredState=renderer.Drive(altered,pivot,radians);auto changedSurface=renderer.Evaluate(alteredState);bool saw=false;
  for(unsigned i=0;i<4;i++)for(unsigned j=0;j<first->parts[i].vertices.size();j++)saw|=first->parts[i].vertices[j].position!=changedSurface->parts[i].vertices[j].position;
  if(!saw)throw std::runtime_error("Solver shape changes did not reach retained surface");
 }
 std::cout<<"{\"changedVertices\":"<<changed<<",\"unchangedVertices\":"<<unchanged<<",\"evaluationMs\":"<<first->milliseconds<<",\"cachedEvaluationMs\":"<<next->milliseconds<<",\"nativeObserved\":false}\n";
 return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
