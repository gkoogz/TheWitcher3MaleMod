#include "surface_transport.hpp"
#include <iostream>
#include <chrono>
#include <filesystem>
#include <fstream>
int wmain(int argc,wchar_t** argv){try{
 using namespace malemod;using Clock=std::chrono::steady_clock;
 if(argc<2||argc>4)throw std::runtime_error("Usage: mechanical_worker_test candidate-worker [reference-worker] [transfer-file]");
 witcher::SurfaceClient full(argc>=3?argv[2]:argv[1]),compact(argv[1]);
 std::unique_ptr<witcher::SurfaceClient> retained;
 std::vector<std::vector<std::pair<unsigned,double>>> skinDonors;
 if(argc==4){
  std::ifstream input(std::filesystem::path(argv[3]),std::ios::binary);
  auto u=[&]{unsigned x=0;if(!input.read(reinterpret_cast<char*>(&x),4))throw std::runtime_error("Truncated transfer");return x;};
  auto d=[&]{double x=0;if(!input.read(reinterpret_cast<char*>(&x),8))throw std::runtime_error("Truncated transfer");return x;};
  input.seekg(72);u();u();auto rows=u();
  for(unsigned i=0;i<rows;i++){u();auto kind=u(),count=u();d();std::vector<std::pair<unsigned,double>> donors;for(unsigned j=0;j<count;j++){auto id=u();auto w=d();donors.emplace_back(id,w);}if(kind==2)skinDonors.push_back(std::move(donors));}
  retained=std::make_unique<witcher::SurfaceClient>(argv[1]);
 }
 surface::Controls controls;
 auto a=full.Initialize(controls),b=compact.Initialize(controls);
 if(retained)retained->Initialize(controls);
 if(surface::wire::Encode(a)!=surface::wire::Encode(b))throw std::runtime_error("Initialization differs");
 auto mechanics=[](surface::Output q){
  q.anatomy={};q.body={};q.anatomyIndices.clear();q.collarDisplacements.clear();
  // These are surface products, explicitly absent in a mechanical sample.
  q.nozzlePosition={};q.nozzleDirection={1,0,0};q.collarMetric={};
  return surface::wire::Encode(q);
 };
 double fullMs=0,compactMs=0;unsigned samples=0;
 for(unsigned frame=0;frame<240;frame++){
  surface::wire::Request q;q.controls=controls;
  q.controls.values[0]=float((frame/80)%3);
  if(frame>=40&&frame<80)for(unsigned i:{1u,2u,3u,5u,6u,7u})q.controls.values[i]=float(5+(frame*3+i*7)%91);
  if(frame>=120&&frame<160)for(unsigned i=1;i<18;i++)q.controls.values[i]=float(30+(frame+i*7)%41);
  q.frame.seconds=frame%17==0?0.f:(frame%47==0?.1f:frame%3==0?1.f/30:1.f/60);
  q.frame.pitchForce=.6f*std::sin(frame*.2f);q.frame.yawForce=.3f*std::cos(frame*.17f);
  if(frame>=80&&frame<200){
   // Existing shared reference-contact fixture; not a claimed Geralt mapping.
   q.frame.thighEndpoints=std::array<surface::Point,4>{{{2,-7.8f,79},{1,-8.2f,43},{2,7.8f,79},{1,8.2f,43}}};
   q.frame.collision=surface::CollisionCalibration{{7.2f,7.2f},{{{3,0,70},{5.4f,0,86}}},6.4f};
   const float movement=6*std::sin(frame*.08f);
   (*q.frame.thighEndpoints)[1].x+=movement;(*q.frame.thighEndpoints)[3].x-=movement;
  }
  if(frame>=160){q.frame.clinical.active=true;q.frame.clinical.time=(frame-160)*.08;}
  if(frame>=200){
   q.frame.garment.enabled=true;q.frame.garment.contactReaction=true;
   q.frame.garment.contactEpoch=1;q.frame.garment.contactSerial=1+(frame-200)/2;
   const double impulse=q.frame.garment.contactSerial*.01;
   q.frame.garment.rodImpulseTotals[3]={0,impulse,impulse*.5};
   q.frame.garment.lobeImpulseTotals[0]={0,0,impulse};
   q.frame.garment.lobeAngularImpulseTotals[1]={impulse*.03,0,0};
  }
  auto begin=Clock::now();a=full.Evaluate(q,10000);auto split=Clock::now();
  b=compact.EvaluateMechanical(q,10000);auto end=Clock::now();
  if(mechanics(a)!=mechanics(b)){
   auto distance=[](surface::Point x,surface::Point y){return std::sqrt((x.x-y.x)*(x.x-y.x)+(x.y-y.y)*(x.y-y.y)+(x.z-y.z)*(x.z-y.z));};
   std::cerr<<"Frame "<<frame<<" radius "<<a.proximalRadius<<"/"<<b.proximalRadius<<" length "<<a.restLength<<"/"<<b.restLength
    <<" tip delta "<<distance(a.shaftGuide[11],b.shaftGuide[11])<<" lobe delta "<<distance(a.lobeCenters[0],b.lobeCenters[0])<<"\n";
   throw std::runtime_error("Compact solver diverged from full mechanical state");
  }
  if(retained){
   auto skin=retained->EvaluateRetainedSkin(q,10000);
   if(mechanics(a)!=mechanics(skin))throw std::runtime_error("Retained skin changes mechanical state");
   for(const auto& row:skinDonors)for(const auto& field:{std::pair{&a.anatomy.positions,&skin.anatomy.positions},std::pair{&a.anatomy.normals,&skin.anatomy.normals}}){
    std::array<double,3> before{},after{};
    for(auto [id,w]:row){auto p=field.first->at(id),v=field.second->at(id);before[0]+=p.x*w;before[1]+=p.y*w;before[2]+=p.z*w;after[0]+=v.x*w;after[1]+=v.y*w;after[2]+=v.z*w;}
    if(before!=after)throw std::runtime_error("Retained skin donor differs at frame "+std::to_string(frame));
   }
  }
  if(frame>5){fullMs+=std::chrono::duration<double,std::milli>(split-begin).count();compactMs+=std::chrono::duration<double,std::milli>(end-split).count();samples++;}
 }
 std::cout<<"PASS 240 byte-identical mechanical samples across controls, pause, moving contacts, projected timing and contact impulses; retained skin rows "<<skinDonors.size()<<"; mean full "<<fullMs/samples<<" ms compact "<<compactMs/samples<<" ms\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
