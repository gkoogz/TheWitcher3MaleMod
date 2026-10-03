#pragma once
#include "render_contract.hpp"
#include <optional>
#include <map>
#include <set>

namespace malemod::witcher {
struct RenderPose {
 unsigned epoch=0;double seconds=0;
 PoseMatrix actorWorld{};
 std::vector<PoseMatrix> skinDeltas;
 std::vector<PoseMatrix> nativeSkinDeltas;
};
// The script sends an entire observed stock pose at one engine timestamp.
// A partial pose, character change or older packet cannot publish mixed bones.
class RenderPoseInput {
 const RenderContract& contract_;
 unsigned epoch_=0;double seconds_=-1;
 std::map<unsigned,PoseMatrix> bones_;
 std::optional<PoseMatrix> world_;
 std::set<unsigned> required_;
 public:
 explicit RenderPoseInput(const RenderContract& c):contract_(c){
  for(auto id:c.nativeBones)required_.insert(id);
  if(required_.size()!=23||!required_.count(9))throw std::invalid_argument("Observed render palette differs");
 }
 void Reset(){epoch_=0;seconds_=-1;bones_.clear();world_.reset();}
 bool Add(unsigned epoch,int bone,double seconds,const PoseMatrix& pose){
  if(!epoch||!std::isfinite(seconds)||seconds<0||bone<-1||bone>=104||!required_.count(unsigned(bone))&&bone!=-1)return false;
  try{InversePose(pose);}catch(const std::invalid_argument&){return false;}
  // Geralt stock basis vectors are unit directions. VecTransform is a point
  // operation in the SDK and must never inject world translation into these.
  if(bone>=0&&bone<94)for(unsigned column=0;column<3;column++){
   double n=0;for(unsigned row=0;row<3;row++)n+=pose[row*4+column]*pose[row*4+column];
   if(n<.25||n>4)return false;
  }
  if(epoch==epoch_&&seconds<seconds_)return false;
  if(epoch!=epoch_||seconds!=seconds_){epoch_=epoch;seconds_=seconds;bones_.clear();world_.reset();}
  if(bone==-1)world_=pose;else bones_[unsigned(bone)]=pose;
  return true;
 }
 std::optional<RenderPose> Complete(unsigned epoch,double seconds)const{
  if(epoch!=epoch_||seconds!=seconds_||!world_||bones_.size()!=required_.size())return {};
  RenderPose out{epoch,seconds,*world_,{}};out.skinDeltas.reserve(contract_.nativeBones.size());
  unsigned pelvis=0;while(pelvis<contract_.nativeBones.size()&&contract_.nativeBones[pelvis]!=9)++pelvis;
  if(pelvis==contract_.nativeBones.size())throw std::invalid_argument("Render palette has no observed pelvis");
  const auto pelvisDelta=MultiplyPose(bones_.at(9),contract_.inverseBind[pelvis]);
  for(unsigned i=0;i<contract_.nativeBones.size();i++){
   const auto id=contract_.nativeBones[i];
   // All ten added bones are observed pelvis children. The full source
   // surface already contains their secondary motion; apply it only once.
   out.skinDeltas.push_back(id>=94?pelvisDelta:MultiplyPose(bones_.at(id),contract_.inverseBind[i]));
   out.nativeSkinDeltas.push_back(MultiplyPose(bones_.at(id),contract_.inverseBind[i]));
  }
  return out;
 }
 std::optional<RenderPose> LastComplete(unsigned epoch)const{return Complete(epoch,seconds_);}
};
}
