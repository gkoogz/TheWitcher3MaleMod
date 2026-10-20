#pragma once
#include "modular_render.hpp"
#include <future>
namespace malemod::witcher {
inline bool CompatibleModularTopology(const ModularFrame& a,const ModularFrame& b){
 for(unsigned i=0;i<a.parts.size();i++){
  const auto& x=a.parts[i];const auto& y=b.parts[i];
  if(x.resource!=y.resource||x.lod!=y.lod||x.indices!=y.indices||x.presentation!=y.presentation||x.vertices.size()!=y.vertices.size())return false;
 }
 return true;
}
inline std::shared_ptr<const ModularFrame> PresentModular(const ModularFrame& a,const ModularFrame& b,double t,const RenderContract& contract){
 auto out=std::make_shared<ModularFrame>(b);surface::PresentationPlan plan(a.frames,b.frames,t);
 for(unsigned i=0;i<15;i++){out->frames[i].origin=surface::Add(surface::Scale(a.frames[i].origin,1-t),surface::Scale(b.frames[i].origin,t));out->frames[i].basis=surface::InterpolateBasis(a.frames[i].basis,b.frames[i].basis,t);}
 auto unpack=[](unsigned v){return surface::PresentationPoint{double(v&1023)/511.5-1,double((v>>10)&1023)/511.5-1,double((v>>20)&1023)/511.5-1};};
 auto pack=[](surface::PresentationPoint p,unsigned previous){unsigned v=previous&0xc0000000u;p=surface::Unit(p);for(unsigned k=0;k<3;k++)v|=unsigned(std::clamp((p[k]+1)*.5,0.,1.)*1023+.5)<<(10*k);return v;};
 auto compose=[&](unsigned i){
  auto& part=out->parts[i];const auto& left=a.parts[i];const auto& right=b.parts[i];const auto& r=contract.resources[part.resource];
  if(left.indices!=right.indices||left.vertices.size()!=right.vertices.size()||!part.presentation||part.presentation->size()!=part.vertices.size())throw std::invalid_argument("Modular presentation topology changed without a snap");
  for(unsigned j=0;j<part.vertices.size();j++){
   auto& dst=part.vertices[j];const auto& x=left.vertices[j];const auto& y=right.vertices[j];auto binding=part.presentation->at(j);
   if(x.position!=y.position){surface::PresentationPoint p{},q{};for(unsigned k=0;k<3;k++){p[k]=x.position[k]*double(r.scale[k])+r.bias[k];q[k]=y.position[k]*double(r.scale[k])+r.bias[k];}auto v=plan.Point(p,q,binding);for(unsigned k=0;k<3;k++)dst.position[k]=float((v[k]-r.bias[k])/r.scale[k]);}
   if(x.normal!=y.normal)dst.normal=pack(plan.Direction(unpack(x.normal),unpack(y.normal),binding),y.normal);
   if(x.tangent!=y.tangent)dst.tangent=pack(plan.Direction(unpack(x.tangent),unpack(y.tangent),binding),y.tangent);
  }
 };
 std::array<std::future<void>,3> tasks;for(unsigned i=0;i<3;i++)tasks[i]=std::async(std::launch::async,compose,i);compose(3);for(auto& task:tasks)task.get();
 return out;
}
}
