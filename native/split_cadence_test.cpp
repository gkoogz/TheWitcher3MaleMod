#include "surface_service.hpp"
#include <iostream>
#include <fstream>
#include <chrono>

int wmain(int argc,wchar_t** argv){try{
 using namespace malemod;using namespace witcher;using Clock=std::chrono::steady_clock;
 if(argc!=3)throw std::runtime_error("Usage: split_cadence_test worker native-package");
 const std::filesystem::path dir=argv[2];
 std::ifstream input(dir/"geralt.bindings",std::ios::binary);
 if(!input)throw std::runtime_error("Missing bindings");
 std::string header(48,'\0');input.read(header.data(),48);const auto revision=header.substr(8,40);
 SurfaceService service(argv[1],dir/"geralt.bindings",revision,surface::Controls{},true);
 std::vector<surface::wire::Request> requests;
 unsigned maximumLead=0,skinPublications=0;std::uint64_t lastSkin=0;
 double total=0;const auto deadline=Clock::now()+std::chrono::seconds(180);
 auto fail=[&]{if(service.Failed())throw std::runtime_error(service.Error());if(Clock::now()>deadline)throw std::runtime_error("Split worker timed out");};
 std::shared_ptr<const CompletedSurface> numerical,skin;
 for(unsigned i=0;i<120;i++){
  surface::wire::Request q;q.frame.seconds=1.f/60;
  q.frame.pitchForce=.5f*std::sin(i*.2f);q.frame.yawForce=.3f*std::cos(i*.17f);
  if(i>=40)q.controls.values[3]=75;
  if(i>=80)q.controls.values[7]=30;
  requests.push_back(q);std::uint64_t sequence=0;
  for(;;){fail();auto status=service.Submit(q,sequence);if(status==Submission::Accepted)break;
   if(status!=Submission::Loading&&status!=Submission::Busy&&status!=Submission::Full)throw std::runtime_error("Split submission rejected");
   Sleep(1);
  }
  do{fail();numerical=service.Latest();if(!numerical||numerical->sequence<sequence)Sleep(1);}while(!numerical||numerical->sequence<sequence);
  if(!numerical->frame.source.anatomy.positions.empty())throw std::runtime_error("Numerical queue evaluated render skin");
  total+=numerical->frame.sourceMilliseconds;
  skin=service.LatestSkin();
  if(skin){maximumLead=(std::max)(maximumLead,unsigned(sequence-skin->sequence));if(skin->sequence!=lastSkin){lastSkin=skin->sequence;skinPublications++;}}
  Sleep(8);
 }
 do{fail();skin=service.LatestSkin();if(!skin||skin->sequence<120)Sleep(1);}while(!skin||skin->sequence<120);
 if(skin->frame.source.anatomy.positions.empty()||!skin->frame.modularShape)throw std::runtime_error("Skin worker did not publish retained geometry and morphology");
 auto mechanics=[](surface::Output q){q.anatomy={};q.body={};q.anatomyIndices.clear();q.collarDisplacements.clear();q.collarMetric={};q.nozzlePosition={};q.nozzleDirection={1,0,0};return surface::wire::Encode(q);};
 if(mechanics(numerical->frame.source)!=mechanics(skin->frame.source))throw std::runtime_error("Ordered skin replay diverged from numerical worker");
 if(maximumLead<2)throw std::runtime_error("Numerical stepping never advanced independently of skin preparation");
 std::cout<<"PASS 120 ordered samples; final mechanics exact; numerical mean "<<total/120
  <<" ms; largest lead "<<maximumLead<<" samples; observed skin publications "<<skinPublications<<"\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
