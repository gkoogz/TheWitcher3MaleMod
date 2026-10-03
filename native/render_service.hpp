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
 std::array<double,3> nozzleWorld{},nozzleDirectionWorld{1,0,0};
 surface::Controls controls;
 double sourceMilliseconds=0,targetMilliseconds=0,preparationMilliseconds=0,lightingMilliseconds=0;
 std::array<float,3> workerMilliseconds{};
 std::array<float,16> geometryMilliseconds{};
 double presentationPhase=1,presentationIntervalMilliseconds=0;
 std::uint64_t presentationSerial=0;
 std::vector<PreSkinnedVertex> actorLocal,world;
 struct FloatVertex {
  std::array<float,3> position;std::uint32_t bones,weights,normal,tangent;
 };
 struct MorphReference {std::array<float,3> position;std::uint32_t normal,tangent,boundary;};
 std::shared_ptr<const std::vector<MorphReference>> morphReference;
 std::vector<FloatVertex> floatVertices;
 std::vector<RenderResource> resources;
};
static_assert(sizeof(RenderDelivery::FloatVertex)==28);
static_assert(sizeof(RenderDelivery::MorphReference)==24);
inline std::shared_ptr<const std::vector<RenderDelivery::MorphReference>> PrepareMorphReference(const RenderContract& contract){
 auto out=std::make_shared<std::vector<RenderDelivery::MorphReference>>();out->reserve(contract.VertexCount());
 for(const auto& lod:contract.lods)for(const auto& row:lod.vertices)out->push_back({contract.encodedReference.at(out->size()),PackDirection(skin::Point{float(row.fallback.normal[0]),float(row.fallback.normal[1]),float(row.fallback.normal[2])},1,false),PackDirection(skin::Point{float(row.fallback.tangent[0]),float(row.fallback.tangent[1]),float(row.fallback.tangent[2])},row.fallback.sign<0?0:3,false),row.boundary});
 return out;
}
inline std::vector<RenderDelivery::FloatVertex> PrepareFloatVertices(const std::vector<SourceRenderVertex>& vertices,const RenderContract& contract){
 if(vertices.size()!=contract.VertexCount())throw std::invalid_argument("Incomplete observed native surface");
 std::vector<RenderDelivery::FloatVertex> out;out.reserve(vertices.size());
 for(const auto& r:contract.resources){
  if(r.firstVertex+r.vertexCount>vertices.size())throw std::invalid_argument("Resource leaves coherent surface");
  std::vector<std::uint8_t> remap(contract.nativeBones.size());
  for(unsigned i=r.firstPalette;i<r.firstPalette+r.paletteCount;i++){
   unsigned target=i;
   if(contract.nativeBones[i]>=94){
    const auto begin=r.firstPalette+((i-r.firstPalette)/(r.paletteCount/2))*(r.paletteCount/2);
    target=begin;while(target<begin+r.paletteCount/2&&contract.nativeBones[target]!=9)++target;
    if(target==begin+r.paletteCount/2)throw std::invalid_argument("Native LOD has no pelvis");
   }
   remap[i]=std::uint8_t(target-r.firstPalette);
  }
  for(unsigned vi=r.firstVertex;vi<r.firstVertex+r.vertexCount;vi++){
   const auto& v=vertices[vi];auto p=v.position;std::array<std::uint8_t,4> bones{};std::memcpy(bones.data(),&v.bones,4);
   for(auto& bone:bones){if(bone<r.firstPalette||bone>=r.firstPalette+r.paletteCount)throw std::invalid_argument("Vertex palette outside owned resource");bone=remap[bone];}
   std::uint32_t boneWord;std::memcpy(&boneWord,bones.data(),4);
   // Preserve the exact native UNORM decode at zero displacement. Inverting
   // float(rest)*QS+QB loses input ULPs and lets precise/fast depth variants
   // disagree even on static body skin. Add unbounded deformation to the
   // observed integer baseline; never clamp or quantize the deformation.
   for(unsigned axis=0;axis<3;axis++){p[axis]=contract.encodedReference.at(vi)[axis]+(p[axis]-v.reference[axis])/r.scale[axis];if(!std::isfinite(p[axis]))throw std::invalid_argument("Nonfinite native float position");}
   out.push_back({p,boneWord,v.weights,PackDirection(v.normal,1,!v.calibration),PackDirection(v.tangent,v.sign<0?0:3,!v.calibration)});
  }
 }
 return out;
}
// Only render snapshots are replaced. Numerical requests remain ordered in
// RuntimeController. Slow lighting/upload preparation never blocks the game VM.
class RenderService {
 const RenderContract& contract_;std::mutex mutex_;std::condition_variable changed_;
 std::shared_ptr<const std::vector<RenderDelivery::MorphReference>> morphReference_;
 bool stopping_=false,paused_=false;std::shared_ptr<const RuntimeDelivery> pending_;
 std::optional<RenderPose> pose_;std::string error_;
 std::shared_ptr<const RenderDelivery> delivery_;
 std::thread worker_;
 public:
 explicit RenderService(const RenderContract& c):contract_(c),morphReference_(PrepareMorphReference(c)),worker_([this]{
  using Clock=std::chrono::steady_clock;
  std::shared_ptr<const RuntimeDelivery> cached;unsigned cachedEpoch=0;
  std::shared_ptr<const std::vector<SourceRenderVertex>> a,b,vertices;
  surface::PresentationFrames fa{},fb{},displayFrames{};
  surface::PrecisePoint nozzleA{},nozzleB{},directionA{},directionB{},shownNozzle{},shownDirection{1,0,0};
  auto began=Clock::now(),arrived=began,nextTick=began;double duration=1./60.;bool active=false;
  std::uint64_t presentationSerial=0;
  std::vector<surface::PresentationBinding> bindings;for(const auto& lod:contract_.lods)for(const auto& v:lod.vertices)bindings.push_back(v.presentation);
  auto frames=[&](const surface::Output& output){auto f=surface::MaterialFrames(output);for(unsigned i=1;i<f.size();i++){f[i].origin=contract_.calibration.PointToTarget(f[i].origin);for(auto& axis:f[i].basis)axis=contract_.calibration.VectorToTarget(axis);}return f;};
  for(;;){std::shared_ptr<const RuntimeDelivery> source;RenderPose pose;
   bool paused;
   {std::unique_lock<std::mutex> lock(mutex_);if(!cached||!active)changed_.wait(lock,[&]{return stopping_||pending_;});else changed_.wait_until(lock,nextTick,[&]{return stopping_;});if(stopping_)return;source=pending_?std::move(pending_):cached;pose=*pose_;paused=paused_;}
   try{
    auto started=Clock::now();double lightMilliseconds=0;
    const bool changed=!cached||cachedEpoch!=pose.epoch||cached->surface->sequence!=source->surface->sequence;
    if(changed){
     auto complete=std::make_shared<const std::vector<SourceRenderVertex>>(ComposeRenderVertices(contract_,source->surface->frame.targetPositions));
     lightMilliseconds=std::chrono::duration<double,std::milli>(Clock::now()-started).count();
     auto targetFrames=frames(source->surface->frame.source);
     const bool snap=paused||!cached||cachedEpoch!=pose.epoch||cached->surface->input.controls.values!=source->surface->input.controls.values;
     a=snap?complete:vertices;fa=snap?targetFrames:displayFrames;b=complete;fb=targetFrames;
     auto np=contract_.calibration.PointToTarget(surface::Precise(source->surface->frame.source.nozzlePosition));
     auto nd=contract_.calibration.VectorToTarget(surface::Precise(source->surface->frame.source.nozzleDirection));
     nozzleA=snap?np:shownNozzle;directionA=snap?nd:shownDirection;nozzleB=np;directionB=nd;
     duration=std::clamp(std::chrono::duration<double>(started-arrived).count(),1./60.,.15);arrived=began=started;
     active=!snap;cached=source;cachedEpoch=pose.epoch;
    }
    if(paused)active=false;
    const double phase=active?std::clamp(std::chrono::duration<double>(Clock::now()-began).count()/duration,0.,1.):1.;
    if(phase==1){vertices=b;displayFrames=fb;shownNozzle=nozzleB;shownDirection=directionB;active=false;}
    else{
     surface::PresentationPlan plan(fa,fb,phase);shownNozzle=plan.Point(nozzleA,nozzleB,{12,1});shownDirection=plan.Direction(directionA,directionB,{12,1});auto display=std::make_shared<std::vector<SourceRenderVertex>>(*b);
     for(unsigned i=0;i<display->size();i++){
      if((*b)[i].calibration)continue;
      auto point=[](const std::array<float,3>& p){return surface::PresentationPoint{p[0],p[1],p[2]};};
      auto p=plan.Point(point((*a)[i].position),point((*b)[i].position),bindings[i]);
      auto n=plan.Direction(point((*a)[i].normal),point((*b)[i].normal),bindings[i]);
      auto t=plan.Direction(point((*a)[i].tangent),point((*b)[i].tangent),bindings[i]);
      for(unsigned axis=0;axis<3;axis++){(*display)[i].position[axis]=float(p[axis]);(*display)[i].normal[axis]=float(n[axis]);(*display)[i].tangent[axis]=float(t[axis]);}
     }
     vertices=display;
     for(unsigned i=0;i<displayFrames.size();i++){displayFrames[i].origin=surface::Add(surface::Scale(fa[i].origin,1-phase),surface::Scale(fb[i].origin,phase));displayFrames[i].basis=surface::InterpolateBasis(fa[i].basis,fb[i].basis,phase);}
    }
    auto next=std::make_shared<RenderDelivery>();next->epoch=pose.epoch;next->sequence=source->surface->sequence;next->poseSeconds=pose.seconds;next->vertices=vertices;next->pose=pose;
    unsigned pelvis=0;while(pelvis<contract_.nativeBones.size()&&contract_.nativeBones[pelvis]!=9)++pelvis;
    auto nozzleTransform=MultiplyPose(pose.actorWorld,pose.skinDeltas.at(pelvis));
    next->nozzleWorld=TransformPosePoint(nozzleTransform,shownNozzle);
    auto end=TransformPosePoint(nozzleTransform,surface::Add(shownNozzle,shownDirection));next->nozzleDirectionWorld=surface::Unit(surface::Sub(end,next->nozzleWorld));
    next->controls=source->surface->input.controls;next->sourceMilliseconds=source->surface->frame.sourceMilliseconds;next->targetMilliseconds=source->surface->frame.targetMilliseconds;
    next->workerMilliseconds=source->surface->frame.workerMilliseconds;next->geometryMilliseconds=source->surface->frame.geometryMilliseconds;
    next->presentationPhase=phase;next->presentationIntervalMilliseconds=duration*1000;
    next->presentationSerial=++presentationSerial;
    next->floatVertices=PrepareFloatVertices(*vertices,contract_);next->resources=contract_.resources;next->morphReference=morphReference_;
    next->lightingMilliseconds=lightMilliseconds;
    next->preparationMilliseconds=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-started).count();
    // Lighting runs once per numerical surface. Rigid material presentation
    // runs on this worker at 60 Hz; source dynamics/contact work is unchanged.
    std::atomic_store(&delivery_,std::shared_ptr<const RenderDelivery>(std::move(next)));
    nextTick=started+std::chrono::microseconds(16667);
   }catch(const std::exception& e){std::lock_guard<std::mutex> lock(mutex_);error_=e.what();}
  }
 }){}
 ~RenderService(){ {std::lock_guard<std::mutex> lock(mutex_);stopping_=true;}changed_.notify_one();if(worker_.joinable())worker_.join();}
 bool Submit(std::shared_ptr<const RuntimeDelivery> source,const RenderPose& pose,bool paused=false){
  if(!source||!pose.epoch)return false;std::unique_lock<std::mutex> lock(mutex_,std::try_to_lock);if(!lock.owns_lock()||stopping_||!error_.empty())return false;
  auto old=Latest();pose_=pose;paused_=paused;
  if(old&&old->epoch==pose.epoch&&old->sequence==source->surface->sequence)return true;
  pending_=std::move(source);changed_.notify_one();return true;
 }
 std::shared_ptr<const RenderDelivery> Latest()const{return std::atomic_load(&delivery_);}
 std::string Error(){std::lock_guard<std::mutex> lock(mutex_);return error_;}
};
}
