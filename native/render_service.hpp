#pragma once
#include "render_pose.hpp"
#include "runtime_controller.hpp"
#include "skin_output.hpp"
#include <condition_variable>
#include <thread>

namespace malemod::witcher {
struct PreSkinnedVertex {
 std::array<float,4> position{};std::uint32_t normal=0,tangent=0;
};
static_assert(sizeof(PreSkinnedVertex)==24);
inline std::uint32_t PackDirection(skin::Point p,unsigned high,bool normalize=true){
 if(normalize)p=skin::Normalize(p);std::uint32_t word=high<<30;
 for(unsigned a=0;a<3;a++){
  const float quantized=(std::max)(0.f,(std::min)(1.f,(p[a]+1.f)*.5f))*1023.f;
  // Nonnegative range: double addition then truncation exactly implements
  // lround's halfway-away rule without three CRT calls per direction.
  word|=std::uint32_t(double(quantized)+.5)<<(10*a);
 }
 return word;
}
inline std::vector<PreSkinnedVertex> SkinRenderVertices(const std::vector<SourceRenderVertex>& vertices,const RenderPose& pose,bool world){
 std::vector<skin::Matrix> palette;palette.reserve(pose.skinDeltas.size());
 for(const auto& source:pose.skinDeltas){skin::Matrix m{};for(unsigned a=0;a<16;a++)m[a]=float(source[a]);palette.push_back(m);}
 skin::Matrix actor{};for(unsigned a=0;a<16;a++)actor[a]=float(pose.actorWorld[a]);
 std::vector<PreSkinnedVertex> out;out.reserve(vertices.size());
 for(const auto& v:vertices){
  skin::Vertex input{v.position,v.normal,v.tangent,v.sign,{},{}};
  std::memcpy(input.bones.data(),&v.bones,4);std::memcpy(input.weights.data(),&v.weights,4);
  auto blend=skin::Blend(input,palette);auto p=skin::Transform(blend,v.position),n=skin::Transform(blend,v.normal,true),t=skin::Transform(blend,v.tangent,true);
  if(world){p=skin::Transform(actor,p);n=skin::Transform(actor,n,true);t=skin::Transform(actor,t,true);}
  for(float x:p)if(!std::isfinite(x))throw std::invalid_argument("Nonfinite skinned render output");
  out.push_back({{p[0],p[1],p[2],1},PackDirection(n,0),PackDirection(t,v.sign<0?0:3)});
 }
 return out;
}
struct RenderDelivery {
 unsigned epoch=0;std::uint64_t sequence=0;double poseSeconds=0;
 std::shared_ptr<const std::vector<SourceRenderVertex>> vertices;
 RenderPose pose;
 surface::Controls controls;
 double sourceMilliseconds=0,targetMilliseconds=0,preparationMilliseconds=0,lightingMilliseconds=0;
 std::array<float,3> workerMilliseconds{};
 std::array<float,16> geometryMilliseconds{};
 std::vector<PreSkinnedVertex> actorLocal,world;
 struct FloatVertex {
  std::array<float,3> position;std::uint32_t bones,weights,normal,tangent;
 };
 std::vector<FloatVertex> floatVertices;
};
static_assert(sizeof(RenderDelivery::FloatVertex)==28);
inline std::vector<RenderDelivery::FloatVertex> PrepareFloatVertices(const std::vector<SourceRenderVertex>& vertices,const RenderContract& contract){
 if(contract.nativeBones.size()!=46)throw std::invalid_argument("Incomplete observed native palette");
 std::array<std::uint8_t,46> remap{};
 for(unsigned lod=0;lod<2;lod++){
  unsigned pelvis=lod*23;while(pelvis<(lod+1)*23&&contract.nativeBones[pelvis]!=9)++pelvis;
  if(pelvis==(lod+1)*23)throw std::invalid_argument("Native LOD palette has no pelvis");
  for(unsigned i=lod*23;i<(lod+1)*23;i++)remap[i]=std::uint8_t(contract.nativeBones[i]>=94?pelvis:i);
 }
 const skin::Point scale{.41360682249f,.45207571983f,.91064155102f},bias{-.2066219449f,-.16102458537f,.17968167365f};
 // The complete source surface already contains added-joint deformation.
 // Redirect those influences to the observed pelvis entry in each LOD.
 // The unchanged native shader now applies the CURRENT game palette once,
 // including mixed stock/collar weights. No stale CPU inverse skin map,
 // singular blend or render-thread pose upload is involved.
 std::vector<RenderDelivery::FloatVertex> out;out.reserve(vertices.size());
 for(const auto& v:vertices){
  auto p=v.position;std::array<std::uint8_t,4> bones{};std::memcpy(bones.data(),&v.bones,4);
  for(auto& bone:bones){if(bone>=remap.size())throw std::invalid_argument("Native vertex palette index outside contract");bone=remap[bone];}
  std::uint32_t boneWord;std::memcpy(&boneWord,bones.data(),4);
  for(unsigned a=0;a<3;a++){p[a]=(p[a]-bias[a])/scale[a];if(!std::isfinite(p[a]))throw std::invalid_argument("Nonfinite native float position");}
  // The exact owned cooked tangent-frame stream has normal metadata 1.
  out.push_back({p,boneWord,v.weights,PackDirection(v.normal,1,!v.calibration),PackDirection(v.tangent,v.sign<0?0:3,!v.calibration)});
 }
 return out;
}
// Only render snapshots are replaced. Numerical requests remain ordered in
// RuntimeController. Slow lighting/upload preparation never blocks the game VM.
class RenderService {
 const RenderContract& contract_;std::mutex mutex_;std::condition_variable changed_;
 bool stopping_=false;std::shared_ptr<const RuntimeDelivery> pending_;
 std::optional<RenderPose> pose_;std::string error_;std::thread worker_;
 std::shared_ptr<const RenderDelivery> delivery_;
 public:
 explicit RenderService(const RenderContract& c):contract_(c),worker_([this]{
  std::shared_ptr<const RuntimeDelivery> cached;unsigned cachedEpoch=0;
  std::shared_ptr<const std::vector<SourceRenderVertex>> vertices;
  for(;;){std::shared_ptr<const RuntimeDelivery> source;RenderPose pose;
   {std::unique_lock<std::mutex> lock(mutex_);changed_.wait(lock,[&]{return stopping_||pending_;});if(stopping_)return;source=std::move(pending_);pose=*pose_;}
   try{
    auto started=std::chrono::steady_clock::now();
    if(!cached||cachedEpoch!=pose.epoch||cached->surface->sequence!=source->surface->sequence){vertices=std::make_shared<const std::vector<SourceRenderVertex>>(ComposeRenderVertices(contract_,source->surface->frame.targetPositions));cached=source;cachedEpoch=pose.epoch;}
    auto lit=std::chrono::steady_clock::now();
    auto next=std::make_shared<RenderDelivery>();next->epoch=pose.epoch;next->sequence=source->surface->sequence;next->poseSeconds=pose.seconds;next->vertices=vertices;next->pose=pose;
    next->controls=source->surface->input.controls;next->sourceMilliseconds=source->surface->frame.sourceMilliseconds;next->targetMilliseconds=source->surface->frame.targetMilliseconds;
    next->workerMilliseconds=source->surface->frame.workerMilliseconds;next->geometryMilliseconds=source->surface->frame.geometryMilliseconds;
    next->floatVertices=PrepareFloatVertices(*vertices,contract_);
    next->lightingMilliseconds=std::chrono::duration<double,std::milli>(lit-started).count();
    next->preparationMilliseconds=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-started).count();
    // Preparation runs once per complete numerical surface, never per draw.
    std::atomic_store(&delivery_,std::shared_ptr<const RenderDelivery>(std::move(next)));
   }catch(const std::exception& e){std::lock_guard<std::mutex> lock(mutex_);error_=e.what();}
  }
 }){}
 ~RenderService(){ {std::lock_guard<std::mutex> lock(mutex_);stopping_=true;}changed_.notify_one();if(worker_.joinable())worker_.join();}
 bool Submit(std::shared_ptr<const RuntimeDelivery> source,const RenderPose& pose){
  if(!source||!pose.epoch)return false;std::unique_lock<std::mutex> lock(mutex_,std::try_to_lock);if(!lock.owns_lock()||stopping_||!error_.empty())return false;
  auto old=Latest();if(old&&old->epoch==pose.epoch&&old->sequence==source->surface->sequence)return true;
  pending_=std::move(source);pose_=pose;changed_.notify_one();return true;
 }
 std::shared_ptr<const RenderDelivery> Latest()const{return std::atomic_load(&delivery_);}
 std::string Error(){std::lock_guard<std::mutex> lock(mutex_);return error_;}
};
}
