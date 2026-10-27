#define NOMINMAX
#include "source_host.hpp"
#include "clinical_adapter.hpp"
#include <iostream>
namespace original {
using malemod::V3;using malemod::Dot;using malemod::Cross;using malemod::Length;using malemod::Unit;using std::min;using std::max;
#include "../../../MaleMod/legacy/wolverine/src/runtime/teaching_sequence.h"
#include "../../../MaleMod/legacy/wolverine/src/runtime/teaching_volume.h"
}
int wmain(int argc,wchar_t** argv){try{
 if(argc!=3)return 2;
 using namespace malemod::witcher::v2;
 SourceHost host(argv[1]);SourceBinding binding(argv[2]);ClinicalAdapter clinical;
 auto& packet=host.Input();packet.epoch=1;packet.controls.fill(50);packet.controls[0]=2;packet.seconds=1.f/60;
 clinical.Runtime().Toggle(1);clinical.Before(packet,1000,true,true);host.Step();
 Matrix identity{};identity[0]=identity[5]=identity[10]=identity[15]=1;clinical.After(packet,binding,identity,identity,1.f/60,1000);
 original::volumeFluid::config={};original::teaching::Fluid reference;reference.SetVariationSeed(1);
 const auto& first=clinical.Runtime().Engine().fluid;if(!reference.Begin(first.lastTip))throw std::runtime_error("Reference initialization failed");reference.lastDir=first.lastDir;
 float maximum=0;
 for(unsigned frame=1;frame<=90;frame++){
  const unsigned now=1000+frame*100;clinical.Before(packet,now,true,true);auto actor=identity;actor[3]=float(frame)*.125f;
  // Deliberately retain normalized core1/60 while the source fluid clock is.1.
  clinical.After(packet,binding,identity,actor,1.f/60,now);const auto& actual=clinical.Runtime().Engine().fluid;
  reference.Advance(.1f,actual.lastTip,actual.lastDir,{125,0,0});
  if(!actual.ready||actual.steps!=reference.steps||actual.mesh.indices!=reference.mesh.indices||actual.mesh.vertices.size()!=reference.mesh.vertices.size())throw std::runtime_error("Adapter fluid timing diverged from source");
  for(unsigned i=0;i<actual.mesh.vertices.size();i++)maximum=(std::max)(maximum,malemod::Length(actual.mesh.vertices[i].p-reference.mesh.vertices[i].p));
 }
 if(maximum>1e-4f)throw std::runtime_error("Inherited actor velocity does not use source bounded fluid dt");
 std::cout<<"PASS native adapter core1/60 vs sourcefluid100ms hitch,90moving frames; independent original fluid mesh maximumerror="<<maximum<<".\n";return 0;
}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}}
