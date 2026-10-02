#pragma once
#include <malemod/motion_filter.hpp>
#include <malemod/surface/binding.hpp>
#include <malemod/surface/runtime.hpp>
#include <optional>

namespace malemod::witcher {
using PoseMatrix=std::array<double,16>;
inline PoseMatrix MultiplyPose(const PoseMatrix& a,const PoseMatrix& b){
 PoseMatrix out{};for(unsigned i=0;i<4;i++)for(unsigned j=0;j<4;j++)for(unsigned k=0;k<4;k++)out[i*4+j]+=a[i*4+k]*b[k*4+j];return out;
}
inline surface::PrecisePoint TransformPosePoint(const PoseMatrix& a,surface::PrecisePoint p){
 surface::PrecisePoint out{};for(unsigned i=0;i<3;i++){out[i]=a[i*4+3];for(unsigned j=0;j<3;j++)out[i]+=a[i*4+j]*p[j];}return out;
}
inline PoseMatrix InversePose(const PoseMatrix& a){
 for(double v:a)if(!std::isfinite(v))throw std::invalid_argument("Nonfinite pose");
 if(a[12]!=0||a[13]!=0||a[14]!=0||a[15]!=1)throw std::invalid_argument("Nonaffine pose");
 double determinant=a[0]*(a[5]*a[10]-a[6]*a[9])-a[1]*(a[4]*a[10]-a[6]*a[8])+a[2]*(a[4]*a[9]-a[5]*a[8]);
 if(std::abs(determinant)<1e-8)throw std::invalid_argument("Singular pose");
 PoseMatrix out={a[5]*a[10]-a[6]*a[9],a[2]*a[9]-a[1]*a[10],a[1]*a[6]-a[2]*a[5],0,
  a[6]*a[8]-a[4]*a[10],a[0]*a[10]-a[2]*a[8],a[2]*a[4]-a[0]*a[6],0,
  a[4]*a[9]-a[5]*a[8],a[1]*a[8]-a[0]*a[9],a[0]*a[5]-a[1]*a[4],0,0,0,0,1};
 for(unsigned i=0;i<3;i++)for(unsigned j=0;j<3;j++)out[i*4+j]/=determinant;
 for(unsigned i=0;i<3;i++)for(unsigned j=0;j<3;j++)out[i*4+3]-=out[i*4+j]*a[j*4+3];return out;
}
struct PoseSample {
 double seconds=0;
 PoseMatrix pelvisActorLocal{};
 std::array<surface::PrecisePoint,4> thighsActorLocal{};
};
struct MappedPose {
 surface::Frame frame;
 PoseMatrix pelvisSkinDeltaNative{};
 std::array<surface::Point,4> measuredThighsSource{};
 bool characterContactsCalibrated=false;
};
// The engine supplies an observed actor-local bone pose and this character's
// actual inverse bind. Shared numerical filtering is consumed from Base.
class PoseInput {
 surface::CoordinateCalibration calibration_;
 PoseMatrix inverseBind_;
 motion::Tracker motion_;
 std::optional<surface::CollisionCalibration> contacts_;
 double previousSeconds_=0;
 bool previousReady_=false;
 public:
 PoseInput(surface::CoordinateCalibration calibration,PoseMatrix inverseBind,
           std::optional<surface::CollisionCalibration> contacts=std::nullopt):calibration_(calibration),inverseBind_(inverseBind),contacts_(contacts){
  calibration_.Validate();InversePose(inverseBind_);
  if(contacts_){
   for(float r:contacts_->thighRadii)if(!std::isfinite(r)||r<=0)throw std::invalid_argument("Uncalibrated thigh radius");
   if(!std::isfinite(contacts_->pelvisRadius)||contacts_->pelvisRadius<=0)throw std::invalid_argument("Uncalibrated pelvis radius");
   for(auto p:contacts_->pelvisEndpoints)for(float x:{p.x,p.y,p.z})if(!std::isfinite(x))throw std::invalid_argument("Invalid measured pelvis capsule");
  }
 }
 MappedPose Map(const PoseSample& sample){
  if(!std::isfinite(sample.seconds)||sample.seconds<0||sample.seconds>1e12||(previousReady_&&sample.seconds<=previousSeconds_))throw std::invalid_argument("Invalid chronological pose time");
  MappedPose out;out.pelvisSkinDeltaNative=MultiplyPose(sample.pelvisActorLocal,inverseBind_);
  const auto sourceDelta=calibration_.SkinDeltaToSource(out.pelvisSkinDeltaNative);
  const auto inverseDelta=InversePose(out.pelvisSkinDeltaNative);
  for(unsigned i=0;i<4;i++){
   for(double x:sample.thighsActorLocal[i])if(!std::isfinite(x))throw std::invalid_argument("Nonfinite measured thigh");
   auto p=calibration_.PointToSource(TransformPosePoint(inverseDelta,sample.thighsActorLocal[i]));
   out.measuredThighsSource[i]={float(p[0]),float(p[1]),float(p[2])};
  }
  motion::Tracker::Matrix matrix{};for(unsigned i=0;i<12;i++)matrix[i]=float(sourceDelta[i]);
  const auto tick=static_cast<std::uint32_t>(std::fmod(std::floor(sample.seconds*1000),4294967296.));
  motion_.TrackPoseOnly(tick,matrix);
  out.frame.seconds=previousReady_?float(sample.seconds-previousSeconds_):1.f/60.f;
  out.frame.pitchForce=motion_.Read().motionPitchForce;out.frame.yawForce=motion_.Read().motionYawForce;
  if(contacts_){out.frame.thighEndpoints=out.measuredThighsSource;out.frame.collision=contacts_;out.characterContactsCalibrated=true;}
  previousSeconds_=sample.seconds;previousReady_=true;return out;
 }
 const motion::Tracker::State& MotionState()const noexcept{return motion_.Read();}
};
}
