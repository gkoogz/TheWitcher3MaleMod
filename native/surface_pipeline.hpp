#pragma once
#include "surface_transport.hpp"
#include "target_surface.hpp"
#include <chrono>

namespace malemod::witcher {
struct SurfaceFrame {
 surface::Output source;
 std::array<std::vector<surface::PrecisePoint>,2> targetPositions;
 double sourceMilliseconds=0,targetMilliseconds=0;
};
// Blocking worker-side composition. Invoke from an owned numerical worker,
// never from a render hook or script callback while holding engine locks.
class SurfacePipeline {
 SurfaceClient source_;TargetSurface target_;
 public:
 SurfacePipeline(const std::wstring& worker,const std::filesystem::path& bindings,const std::string& revision):source_(worker),target_(bindings,revision){}
 SurfaceFrame Evaluate(const surface::wire::Request& request){
  auto begin=std::chrono::steady_clock::now();SurfaceFrame result;
  result.source=source_.Evaluate(request,10000);auto solved=std::chrono::steady_clock::now();
  for(unsigned lod=0;lod<2;lod++)result.targetPositions[lod]=target_.Evaluate(lod,result.source);
  auto end=std::chrono::steady_clock::now();
  result.sourceMilliseconds=std::chrono::duration<double,std::milli>(solved-begin).count();
  result.targetMilliseconds=std::chrono::duration<double,std::milli>(end-solved).count();return result;
 }
};
}
