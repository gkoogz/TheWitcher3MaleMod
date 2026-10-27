#define NOMINMAX
#include "source_host.hpp"
#include "clinical_adapter.hpp"
#include <iostream>
#include <limits>
int wmain(int argc,wchar_t** argv){try{
 if(argc!=3)return 2;
 using namespace malemod::witcher::v2;
 SourceHost host(argv[1]);SourceBinding binding(argv[2]);ClinicalAdapter clinical;
 clinical.Runtime().SetThrob(2);Matrix identity{};identity[0]=identity[5]=identity[10]=identity[15]=1;
 for(unsigned frame=0;frame<35;frame++){
  auto& input=host.Input();input.epoch=1;input.controls.fill(50);input.controls[0]=2;input.seconds=1.f/60;
  const unsigned now=frame<32?280+frame*16:1280+(frame-32)*16;
  clinical.Before(input,now,true,true);const auto& output=host.Step();
  auto actor=identity;if(frame==33)actor[3]=std::numeric_limits<float>::quiet_NaN();
  auto delivery=clinical.After(output,binding,identity,actor,input.seconds,now);
  if(output.completed!=frame+1||output.physicsServices!=frame+1||!delivery)throw std::runtime_error("Body source service did not complete");
  if(frame<32&&(!clinical.Runtime().PassiveRetryPending()||clinical.Runtime().ErrorSerial()!=1||clinical.Runtime().LastError().empty()))throw std::runtime_error("Rejected passive preparation did not retain bounded retry diagnostics");
  if(frame==32&&(!clinical.Runtime().Engine().fluid.ready||!clinical.Runtime().LastError().empty()))throw std::runtime_error("Fresh source seed did not recover after one second");
  if(frame==33&&clinical.Runtime().LastError().find("finite")==std::string::npos)throw std::runtime_error("Invalid clinical emitter was not cancelled locally");
 }
 std::cout<<"PASS actual x86 worker35/35physics requests complete through rejected passive seed280, one-second fresh-seed recovery and nonfinite native clinical pose; no anatomy exception.\n";return 0;
}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}}
