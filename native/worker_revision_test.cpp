#include "surface_transport.hpp"
#include <iostream>
// Intentional shared algorithm revisions cannot claim equivalence to the old
// live-frame collar. Compare the adapter worker against the exact pinned Base
// API in a separately compiled process instead, including all new wire fields.
int wmain(int argc,wchar_t** argv){try{
 if(argc<2||argc>4)throw std::runtime_error("Usage: worker_revision_test worker [--target-owned|--legacy] [--minimum]");
 using namespace malemod;
 bool targetOwned=false,minimum=false;
#if defined(MALEMOD_WORKER_TARGET_OWNS_COLLAR) || defined(MALEMOD_STOCK_ANCHOR_PREVIEW) || defined(MALEMOD_DILATING_COLLAR)
 targetOwned=true;
#endif
 for(int i=2;i<argc;i++){
  const std::wstring arg=argv[i];
  if(arg==L"--target-owned")targetOwned=true;
  else if(arg==L"--legacy")targetOwned=false;
  else if(arg==L"--minimum")minimum=true;
  else throw std::runtime_error("Unknown worker API test option");
 }
 surface::wire::Request q;
 // These combined settings exposed an axial reversal in legacy source skin.
 // The displayed angle is50; the modular pipeline requests source angle35.
 if(minimum)q.controls.values={0,1,1,1,35,1,1,35,100,50,50,50,50,50,50,50,50,51};
 std::unique_ptr<surface::Session> direct;
 if(targetOwned)direct=std::make_unique<surface::Session>(q.controls,surface::Point{9.f,0.f,84.3f},true);
 else direct=std::make_unique<surface::Session>(q.controls);
 witcher::SurfaceClient worker(argv[1]);
 if(surface::wire::Encode(direct->Read())!=surface::wire::Encode(worker.Initialize(q.controls)))throw std::runtime_error("Native initialization differs from requested Base ownership mode");
 for(unsigned i=0;i<48;i++){
  q.controls.values[0]=float((i/16)%3);for(unsigned k=1;k<18;k++)q.controls.values[k]=float(35+(i*7+k*3)%31);
  if(i%8==0){q.controls.values[1]=100;q.controls.values[7]=i%16==0?1.f:100.f;}
  q.frame.pitchForce=.2f*std::sin(float(i)*.15f);q.frame.yawForce=.15f*std::cos(float(i)*.1f);q.frame.seconds=i%3==0?1.f/30.f:1.f/60.f;
  q.frame.clinical={};if(i>=24){q.frame.clinical.active=true;q.frame.clinical.time=(i-24)*.8;}
  q.frame.garment={};if(i>=40){
   q.frame.garment.enabled=true;q.frame.garment.contactReaction=true;
   q.frame.garment.contactEpoch=1;q.frame.garment.contactSerial=1+(i-40)/2;
   const double cumulative=double(q.frame.garment.contactSerial)*.01;
   q.frame.garment.rodImpulseTotals[3]={0,cumulative,cumulative*.5};
   q.frame.garment.lobeImpulseTotals[0]={0,0,cumulative};
   q.frame.garment.lobeImpulseTotals[1]={0,-cumulative*.2,cumulative*.8};
   q.frame.garment.lobeAngularImpulseTotals[0]={cumulative*.03,0,0};
   if(i==41)q.frame.seconds=0; // Same cumulative publication and a paused source step.
  }
  q.frame.collarQueries={{9,0,84.3f},{8,2,88},{7,-4,80}};
  direct->SetControls(q.controls);direct->Step(q.frame);
  if(surface::wire::Encode(direct->Read())!=surface::wire::Encode(worker.Evaluate(q,10000)))throw std::runtime_error("Native transport changed current Base geometry/mechanics at frame "+std::to_string(i));
 }
 std::cout<<"PASS: "<<(targetOwned?"target-owned":"legacy")<<" Base API and native initialized worker are byte-identical; "<<(minimum?"combined-minimum":"default")<<" initialization; 48 frames, all controls, extreme angles, clinical projection, collar queries and cumulative wire6 contact impulses (retry, zero-time queue and lobe moment)\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
