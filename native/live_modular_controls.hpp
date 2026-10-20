#pragma once
#include "modular_render.hpp"

namespace malemod::witcher {
// Control presentation does not wait for RuntimeController's in-flight physics
// sample, rest authoring, aperture cutting, or native layout preparation.
inline std::shared_ptr<const ModularFrame> PresentLiveControls(
 std::shared_ptr<const ModularFrame> input,const surface::Controls& authored,
 const surface::Controls& requested,const RenderContract& contract){
 using namespace surface;
 bool changed=false;for(unsigned i=1;i<=9;i++)changed|=authored.values[i]!=requested.values[i];
 if(!changed||!input||!input->controlTopology)return input;
 auto& arena=ModularPresentationArena();
 const auto& topology=*input->controlTopology;
 auto out=std::make_shared<ModularFrame>(*input);
 const auto& before=input->controlPoints;
 LiveControlDeformation morph(input->controlFrame,authored,requested);
 auto after=before;
 arena.For(unsigned(after.size()),[&](unsigned i){after[i]=morph.Point(before[i],topology.bindings[i]);});
 DeformLiveControlDonors(topology.bodyDonors,before,after);
 DeformLiveControlLofts(morph,topology.bindings,topology.lofts,input->controlTangents,before,after,&arena);
 if(!topology.normals)throw std::runtime_error("Missing prepared normal adjacency");
 auto normals=topology.normals->Pair(before,after,&arena,true,false);
 const auto& normalsBefore=normals.first;const auto& normalsAfter=normals.second;
 auto unpack=[](unsigned v){return PresentationPoint{double(v&1023)/511.5-1,double((v>>10)&1023)/511.5-1,double((v>>20)&1023)/511.5-1};};
 auto pack=[](PresentationPoint p,unsigned old){p=Unit(p);unsigned word=old&0xc0000000u;for(unsigned k=0;k<3;k++)word|=unsigned(std::clamp((p[k]+1)*.5,0.,1.)*1023+.5)<<(10*k);return word;};
 std::vector<PresentationPoint> axis(before.size());std::vector<double> cosine(before.size(),1);
 arena.For(unsigned(before.size()),[&](unsigned i){if(Dot(normalsBefore[i],normalsBefore[i])>1e-20&&Dot(normalsAfter[i],normalsAfter[i])>1e-20){
  auto a=contract.calibration.VectorToTarget(Unit(normalsBefore[i])),b=contract.calibration.VectorToTarget(Unit(normalsAfter[i]));
  cosine[i]=std::clamp(Dot(a,b),-1.,1.);axis[i]=Cross(a,b);
  if(cosine[i]<-.9999){const auto& w=topology.bindings[i];throw std::runtime_error("Live controls reversed prepared vertex "+std::to_string(i)+" owners "+std::to_string(w.shaft)+","+std::to_string(w.lobe)+","+std::to_string(w.body)+" at "+std::to_string(before[i][0])+","+std::to_string(before[i][1])+","+std::to_string(before[i][2]));}
 }});
 auto direction=[&](PresentationPoint p,unsigned id){return Add(Add(p,Cross(axis[id],p)),Scale(Cross(axis[id],Cross(axis[id],p)),1/(1+cosine[id])));};
 auto compose=[&](unsigned partIndex){
  auto& part=out->parts[partIndex];
  if(!part.controlVertices||part.controlVertices->size()!=part.vertices.size())throw std::runtime_error("Missing prepared live control bindings");
  const auto& r=contract.resources[part.resource];
  arena.For(unsigned(part.vertices.size()),[&](unsigned i){
   auto id=part.controlVertices->at(i);if(topology.bindings[id].fixed||before[id]==after[id])return;
   auto& v=part.vertices[i];auto p=contract.calibration.PointToTarget(after[id]);
   for(unsigned k=0;k<3;k++)v.position[k]=float((p[k]-r.bias[k])/r.scale[k]);
   auto n=Unit(direction(unpack(v.normal),id)),t=direction(unpack(v.tangent),id);
   t=Unit(Sub(t,Scale(n,Dot(t,n))));
   v.normal=pack(n,v.normal);v.tangent=pack(t,v.tangent);
  });
 };
 for(unsigned i=0;i<4;i++)compose(i);
 for(unsigned i=1;i<15;i++){
  auto p=contract.calibration.PointToSource(input->frames[i].origin);
  LiveControlBinding binding;if(i>=13)binding.lobe=1;else binding.shaft=1;
  out->frames[i].origin=contract.calibration.PointToTarget(morph.Point(p,binding));
 }
 out->controlPoints=std::move(after);
 return out;
}
struct LiveControlPresentation {
 std::shared_ptr<const ModularFrame> frame;
 surface::Controls applied;
 double fraction=1;
};
inline LiveControlPresentation PresentBoundedLiveControls(
 std::shared_ptr<const ModularFrame> input,const surface::Controls& authored,
 const surface::Controls& requested,const RenderContract& contract){
 // A large preset jump can change the valid attachment chart. Continue showing
 // a safe deformation while the exact authoring job prepares that chart. Never
 // label a limited result as having reached the requested control values.
 for(unsigned attempt=0;attempt<7;attempt++){
  auto applied=authored;const double fraction=std::ldexp(1.,-int(attempt));
  for(unsigned i=1;i<=9;i++)applied.values[i]=float(authored.values[i]+fraction*(requested.values[i]-authored.values[i]));
  try{return {PresentLiveControls(input,authored,applied,contract),applied,fraction};}
  catch(const std::runtime_error& e){
   const std::string message=e.what();
   if(message.rfind("Live controls ",0)!=0)throw;
  }
 }
 return {input,authored,0};
}
}
