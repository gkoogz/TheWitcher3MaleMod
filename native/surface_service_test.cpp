#include "surface_service.hpp"
#include <iostream>
#include <cmath>
int wmain(int argc,wchar_t** argv){
 if(argc!=4)return 2;
 try{
  std::wstring wide=argv[3];std::string revision;
  if(wide.size()!=40)throw std::invalid_argument("Expected a pinned Base commit");
  for(auto c:wide){if(!((c>=L'0'&&c<=L'9')||(c>=L'a'&&c<=L'f')))throw std::invalid_argument("Invalid Base commit");revision.push_back(static_cast<char>(c));}
  malemod::witcher::SurfaceService service(argv[1],argv[2],revision);
  malemod::witcher::SurfacePipeline serial(argv[1],argv[2],revision);
  malemod::surface::wire::Request q;std::uint64_t sequence=0;
  q.controls.values[0]=3;
  if(service.Submit(q,sequence)!=malemod::witcher::Submission::Invalid||sequence)throw std::runtime_error("Invalid input changed queue");
  q={};unsigned full=0,busy=0;malemod::witcher::SurfaceFrame expected;std::vector<malemod::surface::wire::Request> inputs;
  for(unsigned frame=0;frame<48;frame++){
   q.controls.values[1]=frame<24?50.f:60.f;q.controls.values[13]=frame<16?50.f:70.f;
   q.frame.pitchForce=.2f*std::sin(frame*.15f);q.frame.yawForce=.15f*std::cos(frame*.1f);
   auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(30);
   for(;;){auto status=service.Submit(q,sequence);if(status==malemod::witcher::Submission::Accepted)break;
    if(status==malemod::witcher::Submission::Full)++full;else if(status==malemod::witcher::Submission::Busy)++busy;else throw std::runtime_error(service.Error());
    if(std::chrono::steady_clock::now()>deadline)throw std::runtime_error("Service failed to progress");Sleep(1);
   }
   if(sequence!=frame+1)throw std::runtime_error("Accepted sequence skipped/reordered");
   inputs.push_back(q);
  }
  for(const auto& input:inputs)expected=serial.Evaluate(input);
  if(!full)throw std::runtime_error("Bounded queue backpressure was not exercised");
  auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(30);
  std::shared_ptr<const malemod::witcher::CompletedSurface> result;
  do{result=service.Latest();if(result&&result->sequence==48)break;if(service.Failed())throw std::runtime_error(service.Error());
   if(std::chrono::steady_clock::now()>deadline)throw std::runtime_error("Final surface did not arrive");Sleep(1);
  }while(true);
  if(result->input.controls.values!=q.controls.values||result->frame.targetPositions!=expected.targetPositions||malemod::surface::wire::Encode(result->frame.source)!=malemod::surface::wire::Encode(expected.source))throw std::runtime_error("Asynchronous sequence differs from serial source/composition");
  std::cout<<"PASS: 48 ordered asynchronous frames match serial wire and both LODs exactly; full="<<full<<", busy="<<busy<<". No game/GPU output.\n";
 }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
