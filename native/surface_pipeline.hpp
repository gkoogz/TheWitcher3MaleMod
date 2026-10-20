#pragma once
#include "surface_transport.hpp"
#include "target_surface.hpp"
#include <chrono>
#include <future>
#ifdef MALEMOD_FIXED_COLLAR_ANGLE
#include "fixed_collar_angle.hpp"
#endif

namespace malemod::witcher {
struct SurfaceFrame {
 surface::Output source;
 std::shared_ptr<const surface::Output> modularShape;
 std::array<std::vector<surface::PrecisePoint>,2> targetPositions;
 double sourceMilliseconds=0,targetMilliseconds=0;
 std::array<float,3> workerMilliseconds{};
 std::array<float,16> geometryMilliseconds{};
 std::array<double,2> correctiveWeights{},angleGains{1,1};
 std::array<double,3> modularPivot{};double modularRadians=0;
};
// Blocking worker-side composition. Invoke from an owned numerical worker,
// never from a render hook or script callback while holding engine locks.
class SurfacePipeline {
 SurfaceClient source_;TargetSurface target_;bool parallel_,modular_,mechanicsOnly_;
 std::wstring workerPath_;std::shared_ptr<const surface::Output> shape_;
 std::optional<surface::Controls> shapeControls_;
 std::array<std::vector<surface::PrecisePoint>,2> neutralTarget_;
 public:
 SurfacePipeline(const std::wstring& worker,const std::filesystem::path& bindings,const std::string& revision,bool parallel=true,bool modular=false,bool mechanicsOnly=false):source_(worker),target_(bindings,revision),parallel_(parallel),modular_(modular),mechanicsOnly_(mechanicsOnly),workerPath_(worker){}
 void Initialize(const surface::Controls& controls){
  source_.Initialize(surface::Controls{});
  surface::wire::Request q;q.frame.seconds=0;q.frame.collarQueries=target_.CollarQueries();
  const auto rest=source_.Evaluate(q,10000);if(mechanicsOnly_)return;target_.SetNeutralCollar(rest);
  for(unsigned lod=0;lod<2;lod++)neutralTarget_[lod]=target_.Evaluate(lod,rest);
 }
 SurfaceFrame Evaluate(const surface::wire::Request& request){
  return EvaluateBatch({request});
 }
 // Advance every source-physics sample, but build the expensive character
 // surface only for the final pose. Intermediate time is never discarded.
 SurfaceFrame EvaluateBatch(const std::vector<surface::wire::Request>& requests){
  if(requests.empty()||requests.size()>32)throw std::invalid_argument("Invalid physics batch");
  for(const auto& q:requests){surface::wire::Validate(q.controls);surface::wire::Validate(q.frame);}
  const auto& request=requests.back();
  auto begin=std::chrono::steady_clock::now();SurfaceFrame result;
#ifdef MALEMOD_FIXED_COLLAR_ANGLE
  auto morphologyControls=request.controls;morphologyControls.values[7]=FixedCollarReferenceAngle;
  std::future<std::shared_ptr<const surface::Output>> morphology;
  if(modular_&&!mechanicsOnly_&&(!shapeControls_||shapeControls_->values!=morphologyControls.values)){
   // A zero-motion morphology still needs its own fresh process: reusing a
   // stepped worker changes the rest shape. Its independent work can overlap
   // the ordered live solver instead of adding another serial input stall.
   morphology=std::async(std::launch::async,[worker=workerPath_,controls=morphologyControls]{
    SurfaceClient source(worker);return std::make_shared<const surface::Output>(source.Initialize(controls));
   });
  }
#endif
  for(unsigned sample=0;sample<requests.size();sample++){auto query=requests[sample];
#ifdef MALEMOD_COMPACT_MECHANICS
  query.frame.collarQueries=modular_?std::vector<surface::Point>{}:target_.CollarQueries();
#else
  query.frame.collarQueries=target_.CollarQueries();
#endif
#ifdef MALEMOD_FIXED_COLLAR_ANGLE
  query.controls.values[7]=FixedCollarReferenceAngle;
#endif
#ifdef MALEMOD_COMPACT_MECHANICS
  result.source=mechanicsOnly_?source_.EvaluateMechanical(query,10000):!modular_?source_.Evaluate(query,10000):
   sample+1==requests.size()?source_.EvaluateRetainedSkin(query,10000):source_.EvaluateMechanical(query,10000);
#else
  result.source=source_.Evaluate(query,10000);
#endif
  }
  auto solved=std::chrono::steady_clock::now();
  result.workerMilliseconds=source_.LastWorkerTimings();result.geometryMilliseconds=source_.LastGeometryTimings();
  // Each LOD owns its plan/cache; the source and shared reductions are done.
  const float legacyAngle=modular_?50.f:request.controls.values[7];
  if(mechanicsOnly_){}
  else if(modular_)result.targetPositions=neutralTarget_;
  else if(parallel_){auto other=std::async(std::launch::async,[&]{return target_.Evaluate(1,result.source,legacyAngle);});result.targetPositions[0]=target_.Evaluate(0,result.source,legacyAngle);result.targetPositions[1]=other.get();}
  else for(unsigned lod=0;lod<2;lod++)result.targetPositions[lod]=target_.Evaluate(lod,result.source,legacyAngle);
#ifdef MALEMOD_FIXED_COLLAR_ANGLE
  if(modular_){
   if(morphology.valid()){shape_=morphology.get();shapeControls_=morphologyControls;}
   result.modularShape=shape_;
   // The replacement topology owns its opening. Do not inherit a dorsal
   // hinge or admissible angle from the superseded fixed collar mesh.
   const auto rootPoint=result.source.shaftGuide[0];FixedAngleRegion root;root.origin={rootPoint.x,rootPoint.y,rootPoint.z};
   root.upwardDegrees=45;
   result.modularPivot=root.origin;result.modularRadians=FixedCollarFlow(root,request.controls.values[7]).Radians();
   PresentFixedCollarSource(result.source,request.controls.values[7],root);
  }else{
  // Both LODs and delivered guides use one admissible angular amplitude.
  for(unsigned retry=0;retry<8;retry++){
   const auto gains=target_.FixedAngleGains();if(gains[0]==gains[1])break;
   const double cap=retry==7?0.:std::min(gains[0],gains[1]);
   for(unsigned lod=0;lod<2;lod++)result.targetPositions[lod]=target_.Evaluate(lod,result.source,request.controls.values[7],cap);
  }
  result.angleGains=target_.FixedAngleGains();
  target_.PresentFixedAngleSource(result.source,request.controls.values[7]);
  }
#endif
  auto end=std::chrono::steady_clock::now();
  result.correctiveWeights=target_.CorrectiveWeights();
  result.sourceMilliseconds=std::chrono::duration<double,std::milli>(solved-begin).count();
  result.targetMilliseconds=std::chrono::duration<double,std::milli>(end-solved).count();return result;
 }
};
}
