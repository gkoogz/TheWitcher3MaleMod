#define MALEMOD_LEGACY_WIRE_TEST
#include "surface_transport.hpp"
static auto OriginalFields(malemod::surface::Output o){o.nozzlePosition={};o.nozzleDirection={1,0,0};o.collarDisplacements.clear();return malemod::surface::wire::Encode(o);}
#include <iostream>
int wmain(int argc,wchar_t** argv){try{
 if(argc!=3)throw std::runtime_error("Usage: worker_initialization_test original-worker startup-worker");
 malemod::witcher::SurfaceClient original(argv[1],3),direct(argv[2]),initialized(argv[2]);
 malemod::surface::wire::Request q;initialized.Initialize(q.controls);
 for(unsigned i=0;i<48;i++){
  if(i){q.controls.values[0]=float((i/16)%3);for(unsigned k=1;k<18;k++)q.controls.values[k]=float(35+(i*7+k*3)%31);}
  q.frame.pitchForce=.2f*std::sin(float(i)*.15f);q.frame.yawForce=.15f*std::cos(float(i)*.1f);
  q.frame.seconds=i%3==0?1.f/30.f:1.f/60.f;
  auto expected=OriginalFields(original.Evaluate(q,10000));
  if(expected!=OriginalFields(direct.Evaluate(q,10000))||expected!=OriginalFields(initialized.Evaluate(q,10000)))
   throw std::runtime_error("Startup changed complete source surface or mechanics");
 }
 bool rejected=false;try{initialized.Initialize(q.controls);}catch(const std::runtime_error&){rejected=true;}
 if(!rejected)throw std::runtime_error("Worker permitted repeated initialization");
 if(OriginalFields(original.Evaluate(q,10000))!=OriginalFields(initialized.Evaluate(q,10000)))
  throw std::runtime_error("Rejected initialization changed the live source state");
 std::cout<<"PASS: original, direct and initialized workers are byte-identical for 48 changing full-source frames (new nozzle fields excluded; original fields byte-identical), all 18 controls and variable elapsed intervals; repeated initialization rejected without changing state\n";
 return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
