#pragma once
#include "pose_input.hpp"
#include "surface_service.hpp"

namespace malemod::witcher {
enum class RuntimeTick {Accepted,Paused,Busy,Full,Stopped,Invalid,Loading,Computing};
struct RuntimeDelivery {
 std::shared_ptr<const CompletedSurface> surface;
 PoseMatrix pelvisSkinDeltaNative;
 double simulationSeconds=0;
 bool characterContactsCalibrated=false;
};
// The script callback is the sole producer. Render consumers receive immutable
// sequence-matched results. Worker lifetime is owned outside engine/loader locks.
class RuntimeController {
 surface::CoordinateCalibration calibration_;
 PoseMatrix inverseBind_;
 std::optional<surface::CollisionCalibration> contacts_;
 PoseInput pose_;
 SurfaceService service_;
 bool resume_=true;
 std::optional<MappedPose> lastMapped_;
 std::optional<PoseSample> lastNative_;
 surface::Controls lastControls_;
 double lastWall_=0,simulationSeconds_=0;
 struct Stamp {std::uint64_t sequence=0;PoseMatrix delta{};double seconds=0;bool contacts=false;};
 // In-flight + queued + last result. No geometry is retained in this ring.
 std::array<Stamp,16> stamps_{};
 std::shared_ptr<const RuntimeDelivery> delivery_;
 std::uint64_t inFlight_=0;
 public:
 RuntimeController(std::wstring worker,std::filesystem::path bindings,std::string revision,
  surface::CoordinateCalibration calibration,PoseMatrix inverseBind,
  std::optional<surface::CollisionCalibration> contacts,bool diagnosticSourceContacts=false):
  calibration_(calibration),inverseBind_(inverseBind),contacts_(contacts),pose_(calibration,inverseBind,contacts),
  service_(RequireContacts(std::move(worker),contacts,diagnosticSourceContacts),std::move(bindings),std::move(revision),surface::Controls{}){}
 static std::wstring RequireContacts(std::wstring worker,const std::optional<surface::CollisionCalibration>& contacts,bool diagnostic){
  if(!contacts&&!diagnostic)throw std::invalid_argument("Live character contacts must be calibrated; source-default contacts require explicit diagnostic mode");return worker;
 }
 RuntimeTick Tick(PoseSample sample,bool paused,const surface::Controls& controls,std::uint64_t& sequence,const surface::Frame::ClinicalProjection& clinical={}){
  sequence=0;if(service_.Failed())return RuntimeTick::Stopped;
  try{
   surface::wire::Validate(controls);
   Publish();
   if(paused)resume_=true;
   if(paused&&(!lastMapped_||lastControls_.values==controls.values))return RuntimeTick::Paused;
   const auto ready=Latest();
   // Geometry evaluation runs at its measured throughput. Native pose time
   // continues until the next accepted sample; its entire active interval is
   // then passed to the source's fixed-step solver. No request is discarded.
   if(inFlight_&&(!ready||ready->surface->sequence<inFlight_))return RuntimeTick::Computing;
   if(paused){
    resume_=true;
    if(lastMapped_&&lastControls_.values!=controls.values){
     surface::wire::Request preview;preview.controls=controls;preview.frame=lastMapped_->frame;
     preview.frame.clinical=clinical;preview.frame.seconds=0;preview.frame.pitchForce=preview.frame.yawForce=0;
     const auto status=service_.Submit(preview,sequence);
     if(status==Submission::Loading)return RuntimeTick::Loading;
     if(status==Submission::Busy)return RuntimeTick::Busy;if(status==Submission::Full)return RuntimeTick::Full;if(status!=Submission::Accepted)return RuntimeTick::Stopped;
     inFlight_=sequence;
     stamps_[sequence%stamps_.size()]={sequence,lastMapped_->pelvisSkinDeltaNative,simulationSeconds_,lastMapped_->characterContactsCalibrated};lastControls_=controls;
    }
    Publish();return RuntimeTick::Paused;
   }
   if(!std::isfinite(sample.seconds)||sample.seconds<0)return RuntimeTick::Invalid;
   if(!resume_&&sample.seconds<lastWall_)return RuntimeTick::Invalid;
   if(!resume_&&sample.seconds==lastWall_)return RuntimeTick::Computing;
   // Drain a slow active interval in wire-valid samples. Advance the accepted
   // wall clock only by the submitted interval, leaving all remaining time for
   // subsequent callbacks. Interpolate observed native poses along that same
   // interval; do not clamp away elapsed simulation time or reset the solver.
   double dt=resume_?1./60.:sample.seconds-lastWall_;
   if(dt>.15){
    if(!lastNative_)return RuntimeTick::Invalid;
    const double fraction=.1/dt;
    for(unsigned i=0;i<16;i++)sample.pelvisActorLocal[i]=lastNative_->pelvisActorLocal[i]+fraction*(sample.pelvisActorLocal[i]-lastNative_->pelvisActorLocal[i]);
    for(unsigned i=0;i<4;i++)for(unsigned a=0;a<3;a++)sample.thighsActorLocal[i][a]=lastNative_->thighsActorLocal[i][a]+fraction*(sample.thighsActorLocal[i][a]-lastNative_->thighsActorLocal[i][a]);
    dt=.1;sample.seconds=lastWall_+dt;
   }
   const auto nativeSample=sample;
   auto candidate=resume_?PoseInput(calibration_,inverseBind_,contacts_):pose_;
   const auto wall=sample.seconds;sample.seconds=simulationSeconds_+dt;
   auto mapped=candidate.Map(sample);surface::wire::Request request;request.controls=controls;request.frame=mapped.frame;request.frame.clinical=clinical;
   const auto status=service_.Submit(request,sequence);
   if(status!=Submission::Accepted){
    Publish();switch(status){case Submission::Loading:return RuntimeTick::Loading;case Submission::Busy:return RuntimeTick::Busy;case Submission::Full:return RuntimeTick::Full;case Submission::Stopped:return RuntimeTick::Stopped;default:return RuntimeTick::Invalid;}
   }
   // A rejected submission cannot advance the filter, simulation clock or UI
   // snapshot. Caller must retry this sample before submitting a newer one.
   pose_=std::move(candidate);lastWall_=wall;simulationSeconds_=sample.seconds;resume_=false;
   lastNative_=nativeSample;
   lastMapped_=mapped;lastControls_=controls;
   inFlight_=sequence;
   stamps_[sequence%stamps_.size()]={sequence,mapped.pelvisSkinDeltaNative,sample.seconds,mapped.characterContactsCalibrated};Publish();return RuntimeTick::Accepted;
  }catch(const std::invalid_argument&){return RuntimeTick::Invalid;}
 }
 void Publish(){
  auto result=service_.Latest();if(!result)return;
  auto old=Latest();if(old&&old->surface->sequence==result->sequence)return;
  const auto& stamp=stamps_[result->sequence%stamps_.size()];
  if(stamp.sequence!=result->sequence)throw std::runtime_error("Completed geometry lost its exact accepted pose stamp");
  auto next=std::make_shared<RuntimeDelivery>(RuntimeDelivery{std::move(result),stamp.delta,stamp.seconds,stamp.contacts});
  std::atomic_store_explicit(&delivery_,std::shared_ptr<const RuntimeDelivery>(std::move(next)),std::memory_order_release);
 }
 std::shared_ptr<const RuntimeDelivery> Latest()const{return std::atomic_load_explicit(&delivery_,std::memory_order_acquire);}
 std::string Error(){return service_.Error();}
 double SimulationSeconds()const{return simulationSeconds_;}
};
}
