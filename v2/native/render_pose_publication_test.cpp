#include "render_pose_publication.hpp"
#include <iostream>
#include <string>
namespace {
struct Surface {unsigned serial;};struct Fluid {unsigned serial;};struct Cloth {unsigned serial;int pose;};
using Gate=malemod::witcher::v2::RenderPosePublication<Surface,Fluid>;
void Check(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
Gate::Frame Completed(unsigned serial=1){return {3,1,2.f,serial,10,std::make_shared<Surface>(Surface{serial}),std::make_shared<Fluid>(Fluid{serial})};}
void OneStepOneClothLatestPoseAtomicPublication(){
 Gate gate;unsigned steps=0,evaluations=0,fluidUpdates=0,publications=0;int latestPose=1;
 struct Published {unsigned body=0,cloth=0,fluid=0;int pose=0,fluidPose=0;} published;
 struct Presentation {Cloth cloth;unsigned fluidSerial;int fluidPose;};
 const auto coreStep=[&]{++steps;auto frame=Completed();frame.milliseconds=1234;frame.coreSeconds=1.f/60;return frame;};gate.Stage(coreStep());
 Check(steps==1&&evaluations==0&&published.body==0,"Stage must not evaluate cloth or publish before fresh pose");
 latestPose=28;
 const auto evaluate=[&](const auto& frame){++evaluations;++fluidUpdates;Check(frame.milliseconds==1234&&frame.coreSeconds==1.f/60,"Late fluid update retains Main captured clock and dt");Check(published.body==0&&published.cloth==0&&published.fluid==0,"Old complete frame must remain during evaluation");return Presentation{{unsigned(frame.serial),latestPose},unsigned(frame.serial),latestPose};};
 const auto publish=[&](const auto& frame,Presentation value){++publications;published={frame.surface->serial,value.cloth.serial,value.fluidSerial,value.cloth.pose,value.fluidPose};};
 Check(gate.Refresh(3,2.f,1,11,true,evaluate,publish),"Fresh completed pose must publish");
 Check(steps==1&&evaluations==1&&fluidUpdates==1&&publications==1,"One source step, one Meridian evaluation and one fluid update per accepted tick");
 Check(published.body==1&&published.cloth==1&&published.fluid==1&&published.pose==28&&published.fluidPose==28,"All feeds use completed serial and latest pose");
 Check(!gate.Refresh(3,2.f,1,12,true,evaluate,publish)&&evaluations==1&&publications==1,"Duplicate refresh cannot evaluate or publish");
}
void InvalidAndInterruptedLifecycle(){
 for(unsigned fault=0;fault<5;fault++){
  Gate gate;gate.Stage(Completed());unsigned calls=0;
  auto eval=[&](const auto&){++calls;return Cloth{};};auto publish=[&](const auto&,Cloth){++calls;};
  Check(!gate.Refresh(fault==0?4:3,fault==1?3.f:2.f,fault==2?2:1,fault==3?10:11,fault!=4,eval,publish),"Mismatched or incomplete render pose must be rejected");
  Check(!gate.Pending()&&calls==0,"Rejected pending frame is consumed without partial publication");
 }
 Gate gate;gate.Stage(Completed());bool rejected=false;try{gate.Stage(Completed(2));}catch(const std::runtime_error&){rejected=true;}
 Check(rejected&&gate.Pending(),"Unconsumed frame cannot be overwritten by a later step");
 gate.Clear();Check(!gate.Pending(),"Pause, actor invalidation and shutdown clear pending frame");
 unsigned calls=0;Check(!gate.Refresh(3,2.f,1,11,true,[&](const auto&){++calls;return Cloth{};},[&](const auto&,Cloth){++calls;})&&calls==0,"Cancelled frame cannot reappear");
 gate.Stage(Completed());bool threw=false;try{gate.Refresh(3,2.f,1,11,true,[](const auto&)->Cloth{throw std::runtime_error("fixture failure");},[&](const auto&,Cloth){++calls;});}catch(const std::runtime_error&){threw=true;}
 Check(threw&&!gate.Pending()&&calls==0,"Evaluation failure consumes pending without publishing half a frame");
}
void BoundedSealedCheckpointLifecycle(){
 malemod::witcher::v2::SealedCheckpointRequests requests;
 Check(!requests.Queue(-1)&&!requests.Queue(1000),"Invalid sealed stage rejected");
 for(int i=0;i<32;i++)Check(requests.Queue(i),"Bounded unique stage admitted");
 Check(requests.Queue(5)&&!requests.Queue(32),"Duplicates do not consume capacity, overflow rejected");
 auto stages=requests.Take();Check(stages.size()==32&&stages.front()==0&&stages.back()==31,"Flush takes exact ordered requests");
 Check(requests.Take().empty(),"Flushed requests cannot be written twice");
 Gate gate;gate.Stage(Completed());requests.Queue(523);gate.Clear();auto cancelled=requests.Take();
 Check(cancelled.size()==1&&cancelled[0]==523&&!gate.Pending()&&requests.Take().empty(),"Suspended or invalidated requests are discarded with their pending frame");
 gate.Stage(Completed());requests.Queue(524);try{gate.Refresh(3,2.f,1,11,true,[](const auto&)->Cloth{throw std::runtime_error("fixture");},[](const auto&,Cloth){});}catch(const std::runtime_error&){requests.Take();}
 Check(!gate.Pending()&&requests.Take().empty(),"Failed evaluation cannot retain checkpoint requests for another serial");
}
}
int main(){try{OneStepOneClothLatestPoseAtomicPublication();InvalidAndInterruptedLifecycle();BoundedSealedCheckpointLifecycle();std::cout<<"Render-pose publication: once-per-step, latest pose, atomic serial, duplicate, mismatch, cancellation, failure and bounded checkpoint checks passed\n";return 0;}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
