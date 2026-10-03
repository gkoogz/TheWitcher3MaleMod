#pragma once
#include "surface_transport.hpp"
#include "target_surface.hpp"
#include <chrono>
#include <future>

namespace malemod::witcher {
struct SurfaceFrame {
 surface::Output source;
 std::array<std::vector<surface::PrecisePoint>,2> targetPositions;
 double sourceMilliseconds=0,targetMilliseconds=0;
 std::array<float,3> workerMilliseconds{};
 std::array<float,16> geometryMilliseconds{};
};
// Blocking worker-side composition. Invoke from an owned numerical worker,
// never from a render hook or script callback while holding engine locks.
class SurfacePipeline {
 SurfaceClient source_;TargetSurface target_;bool parallel_;
 public:
 SurfacePipeline(const std::wstring& worker,const std::filesystem::path& bindings,const std::string& revision,bool parallel=true):source_(worker),target_(bindings,revision),parallel_(parallel){}
 void Initialize(const surface::Controls& controls){
  source_.Initialize(surface::Controls{});
  surface::wire::Request q;q.frame.seconds=0;q.frame.collarQueries=target_.CollarQueries();
  const auto rest=source_.Evaluate(q,10000);target_.SetNeutralCollar(rest);
  for(unsigned lod=0;lod<2;lod++)target_.Evaluate(lod,rest);
 }
 SurfaceFrame Evaluate(const surface::wire::Request& request){
  auto begin=std::chrono::steady_clock::now();SurfaceFrame result;
  auto query=request;query.frame.collarQueries=target_.CollarQueries();
  result.source=source_.Evaluate(query,10000);auto solved=std::chrono::steady_clock::now();
  result.workerMilliseconds=source_.LastWorkerTimings();result.geometryMilliseconds=source_.LastGeometryTimings();
  // Each LOD owns its plan/cache; the source and shared reductions are done.
  if(parallel_){auto other=std::async(std::launch::async,[&]{return target_.Evaluate(1,result.source);});result.targetPositions[0]=target_.Evaluate(0,result.source);result.targetPositions[1]=other.get();}
  else for(unsigned lod=0;lod<2;lod++)result.targetPositions[lod]=target_.Evaluate(lod,result.source);
  auto end=std::chrono::steady_clock::now();
  result.sourceMilliseconds=std::chrono::duration<double,std::milli>(solved-begin).count();
  result.targetMilliseconds=std::chrono::duration<double,std::milli>(end-solved).count();return result;
 }
};
}
