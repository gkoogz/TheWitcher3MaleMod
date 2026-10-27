#pragma once
#include <memory>
#include <optional>
#include <cstdint>
#include <cmath>
#include <stdexcept>
#include <utility>
#include <vector>
#include <algorithm>
namespace malemod::witcher::v2 {
// Used only after the caller verifies its sealed diagnostic station.
class SealedCheckpointRequests {
 std::vector<std::int32_t> stages_;
public:
 bool Queue(std::int32_t stage){
  if(stage<0||stage>=1000)return false;
  if(std::find(stages_.begin(),stages_.end(),stage)!=stages_.end())return true;
  if(stages_.size()>=32)return false;
  stages_.push_back(stage);return true;
 }
 std::vector<std::int32_t> Take(){auto result=std::move(stages_);stages_.clear();return result;}
};
// Engine transport only. Completed surfaces wait for a fresh render pose.
// The original solver is never called by Refresh.
template<class Surface,class Fluid> class RenderPosePublication {
public:
 struct Frame {
  unsigned actorEpoch=0,style=0;float seconds=0;
  std::uint64_t serial=0,stepPoseRevision=0;
  std::shared_ptr<const Surface> surface;
  std::shared_ptr<const Fluid> fluid;
  std::uint32_t milliseconds=0;float coreSeconds=0;
 };
private:
 std::optional<Frame> pending_;
public:
 bool Pending()const{return pending_.has_value();}
 void Clear(){pending_.reset();}
 void Stage(Frame frame){
  if(pending_)throw std::runtime_error("Previous completed surface has no render-pose refresh");
  if(!frame.actorEpoch||!frame.serial||!frame.stepPoseRevision||!std::isfinite(frame.seconds)||!frame.surface||frame.style>1)
   throw std::runtime_error("Invalid pending render frame");
  pending_=std::move(frame);
 }
 template<class Evaluate,class Publish>
 bool Refresh(unsigned actorEpoch,float seconds,std::uint64_t serial,std::uint64_t revision,bool completePose,Evaluate evaluate,Publish publish){
  if(!pending_)return false;
  // Consume before validation/evaluation; stale or failed requests cannot be
  // replayed on another character or through a duplicate callback.
  auto frame=std::move(*pending_);pending_.reset();
  if(frame.actorEpoch!=actorEpoch||frame.seconds!=seconds||frame.serial!=serial||revision<=frame.stepPoseRevision||!completePose)return false;
  auto garment=evaluate(frame);
  // The caller holds the publication lock across all three feed changes.
  publish(frame,std::move(garment));return true;
 }
};
}
