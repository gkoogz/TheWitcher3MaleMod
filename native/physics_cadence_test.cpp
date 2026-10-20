#include "runtime_profile.hpp"
#include <iostream>
#include <fstream>
using namespace malemod::witcher;
static void Check(bool value,const char* why){if(!value)throw std::runtime_error(why);}
int wmain(int argc,wchar_t** argv){try{
 Check(argc==3,"Usage: physics_cadence_test native-directory report.jsonl");
 std::filesystem::path dir=argv[1];std::ofstream log(argv[2]);
 const std::string pin="431e626cae6fb6720b552f8b20206727fe809c80";
 auto profile=RuntimeProfile::Load(dir/"malemod-runtime.profile",pin);
 RuntimeController live((dir/"surface_worker.exe").wstring(),dir/"geralt.bindings",pin,profile.calibration,profile.inverseBind,profile.contacts);
 SurfacePipeline serial((dir/"surface_worker.exe").wstring(),dir/"geralt.bindings",pin);
 serial.Initialize(malemod::surface::Controls{});PoseInput mapper(profile.calibration,profile.inverseBind,profile.contacts);
 malemod::surface::Controls controls;controls.values[1]=controls.values[2]=controls.values[3]=100;controls.values[7]=15;
 auto base=InversePose(profile.inverseBind);PoseSample prior;double sim=0;
 malemod::surface::Output first;double lobeMotion=0,shaftMotion=0,targetMotion=0,targetMs=0;
 std::vector<malemod::surface::PrecisePoint> firstTarget;
 for(unsigned frame=0;frame<24;frame++){
  PoseSample sample;sample.seconds=10+frame*.24;sample.pelvisActorLocal=base;
  auto offset=profile.calibration.VectorToTarget({1.5*std::sin(frame*.8),2*std::sin(frame*.7),3*std::sin(frame*1.1)});
  for(unsigned k=0;k<3;k++)sample.pelvisActorLocal[k*4+3]+=offset[k]*profile.calibration.targetUnitsPerSourceUnit;
  const std::array<malemod::surface::PrecisePoint,4> legs={{{2,-7.8,79},{1,-8.2,43},{2,7.8,79},{1,8.2,43}}};
  for(unsigned k=0;k<4;k++)sample.thighsActorLocal[k]=profile.calibration.PointToTarget(legs[k]);
  std::uint64_t sequence=0;auto end=std::chrono::steady_clock::now()+std::chrono::seconds(45);
  for(;;){auto status=live.Tick(sample,false,controls,sequence);if(status==RuntimeTick::Accepted)break;
   Check(status==RuntimeTick::Loading||status==RuntimeTick::Computing||status==RuntimeTick::Busy,"Runtime failed");Check(std::chrono::steady_clock::now()<end,"Runtime timed out");Sleep(1);}
  Check(std::abs(live.SimulationSeconds()-(1./60.+frame*.24))<1e-8,"Slow geometry caused accumulating physics lag");
  std::vector<malemod::surface::wire::Request> batch;double elapsed=frame?.24:1./60.,advanced=0;
  while(advanced<elapsed){double left=elapsed-advanced;advanced+=left>.15?.1:left;auto step=sample;
   if(frame&&advanced<elapsed){double t=advanced/elapsed;for(unsigned i=0;i<16;i++)step.pelvisActorLocal[i]=prior.pelvisActorLocal[i]+t*(sample.pelvisActorLocal[i]-prior.pelvisActorLocal[i]);}
   step.seconds=sim+advanced;malemod::surface::wire::Request q;q.controls=controls;q.frame=mapper.Map(step).frame;batch.push_back(q);}
  sim+=elapsed;prior=sample;
  // A separate worker advances every intermediate sample and composes every
  // surface, proving batch composition has not changed source physics.
  SurfaceFrame exact;for(auto q:batch)exact=serial.Evaluate(q);
  std::shared_ptr<const RuntimeDelivery> done;
  do{live.Publish();done=live.Latest();Check(std::chrono::steady_clock::now()<end,"Physics batch stalled");if(!done||done->surface->sequence!=sequence)Sleep(1);}while(!done||done->surface->sequence!=sequence);
  const auto& output=done->surface->frame;
  Check(malemod::surface::wire::Encode(output.source)==malemod::surface::wire::Encode(exact.source),"Batched source differs from every-step replay");
  double error=0;for(unsigned lod=0;lod<2;lod++)for(unsigned i=0;i<output.targetPositions[lod].size();i++)for(unsigned k=0;k<3;k++)error=std::max(error,std::abs(output.targetPositions[lod][i][k]-exact.targetPositions[lod][i][k]));
  Check(error<1e-9,"Batched target differs from every-step replay");
  if(!frame){first=output.source;firstTarget=output.targetPositions[0];}
  auto distance=[](auto a,auto b){return std::sqrt((a.x-b.x)*(a.x-b.x)+(a.y-b.y)*(a.y-b.y)+(a.z-b.z)*(a.z-b.z));};
  for(unsigned k=0;k<2;k++)lobeMotion=std::max(lobeMotion,double(distance(first.lobeCenters[k],output.source.lobeCenters[k])));
  shaftMotion=std::max(shaftMotion,double(distance(first.shaftGuide[11],output.source.shaftGuide[11])));
  for(unsigned i=0;i<firstTarget.size();i++)for(unsigned k=0;k<3;k++)targetMotion=std::max(targetMotion,std::abs(firstTarget[i][k]-output.targetPositions[0][i][k]));
  targetMs+=output.targetMilliseconds;
  log<<"{\"frame\":"<<frame<<",\"simulationSeconds\":"<<sim<<",\"targetMs\":"<<output.targetMilliseconds<<",\"sourceMs\":"<<output.sourceMilliseconds<<",\"targetError\":"<<error<<"}\n"<<std::flush;
 }
 Check(lobeMotion>.01&&shaftMotion>.01&&targetMotion>.0001,"Motion input produced no anatomical response");
 auto clock=live.SimulationSeconds();std::uint64_t sequence=0;prior.seconds+=30;
 Check(live.Tick(prior,true,controls,sequence)==RuntimeTick::Paused&&live.SimulationSeconds()==clock,"Pause advanced physics");
 log<<"{\"passed\":true,\"lobeExcursionSourceUnits\":"<<lobeMotion<<",\"shaftExcursionSourceUnits\":"<<shaftMotion<<",\"targetExcursionNativeUnits\":"<<targetMotion<<",\"targetMeanMs\":"<<targetMs/24<<",\"wallInterval\":0.24,\"accumulatingLag\":false}\n";
 std::cout<<"PASS: 24 slow-cadence moving poses, full elapsed time, exact source physics, both LODs, pause and nonzero lobe/shaft response\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
