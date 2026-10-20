#include "modular_presentation.hpp"
#include <iostream>
using namespace malemod::witcher;
namespace surface=malemod::surface;
int main(int argc,char** argv){try{
 if(argc!=2)throw std::invalid_argument("Expected observed render contract");
 std::ifstream file(argv[1],std::ios::binary);std::string bytes((std::istreambuf_iterator<char>(file)),{});RenderContract contract(argv[1],bytes.substr(8,40),bytes.substr(48,64));
 ModularFrame a,b;for(unsigned i=1;i<15;i++)b.frames[i].basis={surface::PresentationPoint{0,1,0},surface::PresentationPoint{-1,0,0},surface::PresentationPoint{0,0,1}};
 for(unsigned i=0;i<4;i++){
  auto& x=a.parts[i];auto& y=b.parts[i];x.resource=y.resource=i/2;x.lod=y.lod=i%2;
  x.indices=y.indices=std::make_shared<const std::vector<unsigned>>(std::initializer_list<unsigned>{0,1,2});
  auto ownership=std::make_shared<std::vector<surface::PresentationBinding>>(3,surface::PresentationBinding{12,1});(*ownership)[2]={0,0};x.presentation=y.presentation=ownership;
  const auto& r=contract.resources[x.resource];x.vertices.resize(3);y.vertices.resize(3);
  for(unsigned j=0;j<3;j++){surface::PresentationPoint p=j==0?surface::PresentationPoint{0,1,0}:j==1?surface::PresentationPoint{0,-1,0}:surface::PresentationPoint{2,2,2};auto q=j==2?p:surface::Rotate(b.frames[12].basis,p);for(unsigned k=0;k<3;k++){x.vertices[j].position[k]=float((p[k]-r.bias[k])/r.scale[k]);y.vertices[j].position[k]=float((q[k]-r.bias[k])/r.scale[k]);}x.vertices[j].normal=y.vertices[j].normal=0x7ff80200;x.vertices[j].tangent=y.vertices[j].tangent=0xc00803ff;}
 }
 for(double t:{0.,.25,.5,.75,1.}){auto v=PresentModular(a,b,t,contract);for(unsigned i=0;i<4;i++){auto& p=v->parts[i];const auto& r=contract.resources[p.resource];double distance=0;for(unsigned k=0;k<3;k++){double d=(double(p.vertices[0].position[k])-p.vertices[1].position[k])*r.scale[k];distance+=d*d;}if(std::abs(distance-4)>1e-5)throw std::runtime_error("Temporal rotation shrank head diameter");if(p.vertices[2].position!=a.parts[i].vertices[2].position)throw std::runtime_error("Fixed body drifted");}}
 if(!CompatibleModularTopology(a,b))throw std::runtime_error("Unchanged topology cannot interpolate");
 auto wrong=b;wrong.parts[0].indices=std::make_shared<const std::vector<unsigned>>();if(CompatibleModularTopology(a,wrong))throw std::runtime_error("Asynchronous recut did not require a snap");bool rejected=false;try{PresentModular(a,wrong,.5,contract);}catch(const std::invalid_argument&){rejected=true;}if(!rejected)throw std::runtime_error("Topology transition was interpolated");
 std::cout<<"PASS: preserved crown diameter through 90-degree temporal rotation, fixed body exact, topology changes rejected\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
