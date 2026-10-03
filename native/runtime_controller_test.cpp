#include "runtime_controller.hpp"
#include "runtime_profile.hpp"
#include "runtime_host.hpp"
#include <fstream>
#include <iostream>
using namespace malemod::witcher;
static void Check(bool value,const char* message){if(!value)throw std::runtime_error(message);}
int wmain(int argc,wchar_t** argv){try{
 Check(argc==5||argc==6,"Usage: runtime_controller_test pose-packet worker bindings Base-pin [runtime-profile]");
 std::ifstream data(argv[1],std::ios::binary);auto read=[&](auto& x){Check(bool(data.read(reinterpret_cast<char*>(&x),sizeof(x))),"Truncated pose input");};
 std::array<char,8> magic;read(magic);Check(std::string(magic.data(),8)=="MMPOSE01","Wrong pose version");
 malemod::surface::CoordinateCalibration c;read(c.basis);read(c.sourceRoot);read(c.targetRoot);read(c.targetUnitsPerSourceUnit);PoseMatrix bind;read(bind);unsigned count;read(count);Check(count>=48&&count<=10000,"Pose count differs");
 std::vector<PoseSample> samples(count);for(auto& s:samples){read(s.seconds);read(s.pelvisActorLocal);read(s.thighsActorLocal);}
 std::wstring wide=argv[4];std::string pin;for(auto x:wide){Check((x>=L'0'&&x<=L'9')||(x>=L'a'&&x<=L'f'),"Invalid Base pin");pin.push_back(static_cast<char>(x));}Check(pin.size()==40,"Base pin differs");
 bool rejected=false;try{RuntimeController invalid(argv[2],argv[3],pin,c,bind,std::nullopt);}catch(const std::invalid_argument&){rejected=true;}Check(rejected,"Production allowed uncalibrated character contacts");
 std::optional<malemod::surface::CollisionCalibration> contacts;if(argc==6){auto profile=RuntimeProfile::Load(argv[5],pin);Check(!profile.diagnosticSourceContacts&&profile.contacts.has_value(),"Production contact profile missing");contacts=profile.contacts;}
 RuntimeController live(argv[2],argv[3],pin,c,bind,contacts,!contacts);
 SurfacePipeline serial(argv[2],argv[3],pin,false);serial.Initialize(malemod::surface::Controls{});PoseInput mapper(c,bind,contacts);
 malemod::surface::Controls controls;std::uint64_t sequence=0;unsigned full=0,busy=0;double elapsed=0;
 SurfaceFrame expected;
 for(unsigned i=0;i<48;i++){
  if(i==24){
   Check(live.Tick(samples[i],true,controls,sequence)==RuntimeTick::Paused&&!sequence,"Pause submitted a frame");
   const auto seconds=live.SimulationSeconds();auto paused=samples[i];paused.seconds+=600;
   Check(live.Tick(paused,true,controls,sequence)==RuntimeTick::Paused&&live.SimulationSeconds()==seconds,"Paused wall time advanced solver");
   mapper=PoseInput(c,bind,contacts);
  }
  controls.values[0]=float((i/16)%3);
  for(unsigned k=1;k<18;k++)controls.values[k]=float(35+(i*7+k*3)%31);
  auto sample=samples[i];if(i>=24)sample.seconds+=600;
  auto invalid=controls;invalid.values[4]=-1;auto clock=live.SimulationSeconds();
  Check(live.Tick(sample,false,invalid,sequence)==RuntimeTick::Invalid&&!sequence&&live.SimulationSeconds()==clock,"Invalid controls mutated lifecycle");
  auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(30);
  for(;;){auto status=live.Tick(sample,false,controls,sequence);if(status==RuntimeTick::Accepted)break;
   if(status==RuntimeTick::Busy)++busy;else if(status==RuntimeTick::Full)++full;else if(status!=RuntimeTick::Loading&&status!=RuntimeTick::Computing)throw std::runtime_error("Live controller rejected input: "+live.Error());
   Check(live.SimulationSeconds()==clock&&!sequence,"Rejected queue submission advanced pose/time");
   Check(std::chrono::steady_clock::now()<deadline,"Controller did not progress");Sleep(1);
  }
  Check(sequence==i+1,"Accepted sequence is discontinuous");
  elapsed+=(i==0||i==24)?1./60.:samples[i].seconds-samples[i-1].seconds;
  auto offline=samples[i];offline.seconds=elapsed;malemod::surface::wire::Request request;request.controls=controls;request.frame=mapper.Map(offline).frame;expected=serial.Evaluate(request);
 }
 auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(30);std::shared_ptr<const RuntimeDelivery> result;
 do{live.Publish();result=live.Latest();if(result&&result->surface->sequence==48)break;Check(std::chrono::steady_clock::now()<deadline,"Final geometry missing");Sleep(1);}while(true);
 Check(result->surface->frame.targetPositions==expected.targetPositions&&malemod::surface::wire::Encode(result->surface->frame.source)==malemod::surface::wire::Encode(expected.source),"Native lifecycle changed source or composed geometry");
 Check(result->surface->input.controls.values==controls.values&&result->characterContactsCalibrated==contacts.has_value()&&std::abs(result->simulationSeconds-elapsed)<1e-9,"Controls/pose publication mismatch");
 // Paused edits still reach the shape solver, with zero elapsed physics time.
 controls.values[1]=60;auto paused=samples[47];paused.seconds+=1000;
 Check(live.Tick(paused,true,controls,sequence)==RuntimeTick::Paused&&sequence==49&&live.SimulationSeconds()==elapsed,"Paused preference edit advanced physics time or did not enqueue geometry");
 malemod::surface::wire::Request preview;preview.controls=controls;preview.frame=result->surface->input.frame;preview.frame.seconds=0;preview.frame.pitchForce=preview.frame.yawForce=0;expected=serial.Evaluate(preview);
 deadline=std::chrono::steady_clock::now()+std::chrono::seconds(30);
 do{live.Publish();result=live.Latest();if(result&&result->surface->sequence==49)break;Check(std::chrono::steady_clock::now()<deadline,"Paused edit did not produce geometry");Sleep(1);}while(true);
 Check(result->surface->frame.targetPositions==expected.targetPositions&&malemod::surface::wire::Encode(result->surface->frame.source)==malemod::surface::wire::Encode(expected.source),"Paused preview differs from source zero-time edit");
 // A real focus pause resets pose sampling while preserving solver state.
 // Slow active frames instead drain their entire interval, never latch a fault.
 RuntimeController slow(argv[2],argv[3],pin,c,bind,contacts,!contacts);
 SurfacePipeline slowSerial(argv[2],argv[3],pin);slowSerial.Initialize(malemod::surface::Controls{});PoseInput slowMapper(c,bind,contacts);
 auto slowSample=samples[0];slowSample.seconds=100;malemod::surface::Controls defaults;
 double slowClock=0;unsigned slowFrames=0;
 for(unsigned phase=0;phase<2;phase++){
  if(phase)slowSample.seconds+=.45;
  for(;;){
   auto until=std::chrono::steady_clock::now()+std::chrono::seconds(30);
   for(;;){auto status=slow.Tick(slowSample,false,defaults,sequence);if(status==RuntimeTick::Accepted)break;
    Check(status==RuntimeTick::Loading||status==RuntimeTick::Computing||status==RuntimeTick::Busy,"Slow active frame stopped the solver");
    Check(std::chrono::steady_clock::now()<until,"Slow-frame backlog did not progress");Sleep(1);
   }
   ++slowFrames;auto current=slow.SimulationSeconds();auto offline=slowSample;offline.seconds=current;
   malemod::surface::wire::Request q;q.controls=defaults;q.frame=slowMapper.Map(offline).frame;auto exact=slowSerial.Evaluate(q);
   std::shared_ptr<const RuntimeDelivery> completed;
   do{slow.Publish();completed=slow.Latest();if(completed&&completed->surface->sequence==sequence)break;Check(std::chrono::steady_clock::now()<until,"Slow-frame surface missing");Sleep(1);}while(true);
   Check(completed->surface->frame.targetPositions==exact.targetPositions&&malemod::surface::wire::Encode(completed->surface->frame.source)==malemod::surface::wire::Encode(exact.source),"Slow-frame scheduling changed source numerics");
   Check(current>slowClock&&current-slowClock<=.150000001,"Wire interval or backlog clock invalid");slowClock=current;
   if(!phase||std::abs(current-(1./60.+.45))<1e-9)break;
  }
 }
 Check(std::abs(slowClock-(1./60.+.45))<1e-9&&slowFrames>=4,"Active time was discarded");
 Check(slow.Tick(slowSample,false,defaults,sequence)==RuntimeTick::Computing&&!sequence,"Duplicate engine time latched a fault");
 std::cout<<"PASS: slow active interval preserves all elapsed time in exact source/target samples; duplicate time stays transient\n";
 // A new character epoch owns a fresh source process and cannot publish the
 // previous epoch's geometry. This exercises the actual asynchronous host.
 RuntimeHost host([&]{return std::make_unique<RuntimeController>(argv[2],argv[3],pin,c,bind,contacts,!contacts);});
 std::vector<std::uint8_t> firstSource;std::array<std::vector<malemod::surface::PrecisePoint>,2> firstTarget;
 for(unsigned epoch=1;epoch<=2;epoch++){
  auto sample=samples[0];sample.seconds+=epoch*100.;malemod::surface::Controls defaults;
  auto until=std::chrono::steady_clock::now()+std::chrono::seconds(30);
  for(;;){auto status=host.Tick(epoch,sample,false,defaults,sequence);if(status==HostTick::Accepted)break;
   Check(status==HostTick::Loading||status==HostTick::Busy,"Epoch startup failed");Check(!host.Poll(epoch),"Old geometry published during character replacement");Check(std::chrono::steady_clock::now()<until,"Epoch startup stalled");Sleep(1);
  }
  Check(sequence==1,"Reload continued old sequence");
  std::shared_ptr<const RuntimeDelivery> published;
  do{published=host.Poll(epoch);Check(std::chrono::steady_clock::now()<until,"Epoch output stalled");if(!published)Sleep(1);}while(!published);
  if(epoch==1){firstSource=malemod::surface::wire::Encode(published->surface->frame.source);firstTarget=published->surface->frame.targetPositions;}
  else Check(firstSource==malemod::surface::wire::Encode(published->surface->frame.source)&&firstTarget==published->surface->frame.targetPositions,"Fresh epoch leaked source/global cache history");
  Check(host.Tick(0,sample,true,defaults,sequence)==HostTick::Dormant&&!host.Poll(epoch),"Ended character retained visible output");
 }
 std::cout<<"PASS: 48 sequence-matched full-runtime frames, all 18 controls, exact serial source/both LODs, pause/resume and rejected-input clock preservation; full="<<full<<" busy="<<busy<<"; contact calibration mode="<<contacts.has_value()<<"; no game output\n";
 std::cout<<"PASS: asynchronous character epochs replace the source worker, restart sequence 1, preserve exact fresh output and hide retired geometry\n";
 std::cout<<"PASS: paused control edits generate exact zero-time source/target geometry without advancing simulation\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
