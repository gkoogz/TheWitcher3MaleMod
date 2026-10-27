#pragma once
#include "source_binding.hpp"
#include "engine/skin_output.hpp"
#include "engine/garment_delivery.hpp"
#include "canonical-meridian-recipe.inc"
#include "canonical-meridian.inc"
#include <malemod/garments/target_frame.hpp>
#include <limits>
namespace malemod::witcher::v2 {
class MeridianAdapter {
 using M=malemod::garments::meridian::Binding;
 std::vector<M> bindings_;
 // Immutable row-to-slot lookup, derived from the native donor file once.
 // Frame samples and readiness remain local, preserving independent callers.
 std::vector<unsigned> cacheIndexByRow_;
 unsigned cacheSampleCount_=0;
 public:
 explicit MeridianAdapter(const std::filesystem::path& path){
  static_assert(sizeof(M)==40);std::ifstream f(path,std::ios::binary);char magic[8]{};unsigned count=0;f.read(magic,8);f.read(reinterpret_cast<char*>(&count),4);
  if(std::memcmp(magic,"MMV2G02\0",8)||count!=CanonicalMeridianRecipe::sampleCount)throw std::runtime_error("Geralt Meridian binding differs");
  bindings_.resize(count);f.read(reinterpret_cast<char*>(bindings_.data()),count*sizeof(M));if(!f||f.peek()!=EOF)throw std::runtime_error("Truncated Geralt Meridian bindings");
  unsigned maximum=0;for(const auto& binding:bindings_)for(unsigned id:binding.source){
   // SourceBinding admits exactly two resources of at most100000 rows each.
   if(id>=200000)throw std::runtime_error("Garment donor leaves native row bounds");maximum=(std::max)(maximum,id);
  }
  cacheIndexByRow_.assign(maximum+1,std::numeric_limits<unsigned>::max());
  for(const auto& binding:bindings_)for(unsigned id:binding.source)if(cacheIndexByRow_[id]==std::numeric_limits<unsigned>::max())cacheIndexByRow_[id]=cacheSampleCount_++;
 }
 std::shared_ptr<const GarmentDelivery> Evaluate(const SourceBinding& binding,const RenderDelivery& render,const std::array<Matrix,94>& poses,const Matrix& actor,const surface::canonical::Packet& source){
  namespace G=malemod::garments::meridian;using Recipe=CanonicalMeridianRecipe;
  std::vector<skin::Matrix> palette;for(const auto& b:binding.Bones())palette.push_back(Multiply(poses[b.id],b.inverse));
  std::vector<std::vector<skin::Matrix>> resourcePalettes;for(const auto& r:binding.Resources())resourcePalettes.emplace_back(palette.begin()+r.firstPalette,palette.begin()+r.firstPalette+r.paletteCount);
  struct Sample {Point position,normal;};std::vector<Sample> cached(cacheSampleCount_);std::vector<unsigned char> ready(cacheSampleCount_);
  const auto fetch=[&](unsigned,unsigned id){
   if(id>=render.floatVertices.size()||id>=cacheIndexByRow_.size())throw std::runtime_error("Garment donor leaves native surface");
   const unsigned slot=cacheIndexByRow_[id];if(slot==std::numeric_limits<unsigned>::max())throw std::runtime_error("Garment donor has no native cache slot");
   if(ready[slot])return cached[slot].position;const auto& row=render.floatVertices[id];
   const RenderResource* resource=nullptr;unsigned resourceIndex=0;for(unsigned i=0;i<binding.Resources().size();i++){const auto& r=binding.Resources()[i];if(id>=r.firstVertex&&id<r.firstVertex+r.vertexCount){resource=&r;resourceIndex=i;}}
   if(!resource)throw std::runtime_error("Missing garment native resource");
   skin::Vertex v{};std::memcpy(v.bones.data(),&row.bones,4);std::memcpy(v.weights.data(),&row.weights,4);
   auto blend=skin::Blend(v,resourcePalettes[resourceIndex]);Point native{};for(unsigned a=0;a<3;a++)native[a]=row.position[a]*resource->scale[a]+resource->bias[a];
   auto q=binding.ToSource(skin::Transform(blend,native));auto n=skin::Transform(blend,skin::Dec10(row.normal),true);Point normal{};const auto& rotation=binding.Rotation();for(unsigned a=0;a<3;a++)for(unsigned b=0;b<3;b++)normal[a]+=rotation[b*3+a]*n[b];cached[slot]=Sample{q,G::Unit(normal)};ready[slot]=1;return q;
  };
  std::vector<G::Vec> points(Recipe::sampleCount);
  for(unsigned i:Recipe::runtimeSamples){
   if(i>=Recipe::clothCount&&i<Recipe::aliasStart)points[i]=G::TransportSmooth(bindings_[i],fetch,[&](unsigned id){return cached.at(cacheIndexByRow_.at(id)).normal;});
   else points[i]=G::Transport(bindings_[i],fetch);
  }
  const auto pelvis=binding.PelvisDelta(poses[9]);
  for(unsigned side=0;side<2;side++)for(unsigned control=0;control<6;control++){
   const auto& v=source.garmentLobeControls[side*6+control];points[Recipe::lobeControls[side][control]]=binding.ToSource(Transform(pelvis,binding.ToNative({v.x,v.y,v.z})));
  }
  std::vector<malemod::garments::reference::Vertex> fitted;malemod::garments::reference::Build<Recipe>(std::move(points),fitted);
  auto result=std::make_shared<GarmentDelivery>();result->epoch=render.epoch;result->serial=render.sequence;auto& mesh=result->output.mesh;mesh.vertices.resize(Recipe::count);mesh.triangles.reserve(Recipe::faceCount);
  for(unsigned i=0;i<Recipe::count;i++){
   auto& v=mesh.vertices[i];const auto& raw=fitted[i];v.position=Transform(actor,binding.ToNative({raw.p[0],raw.p[1],raw.p[2]}));Point n{};
   const auto& rotation=binding.Rotation();for(unsigned a=0;a<3;a++)for(unsigned b=0;b<3;b++)n[a]+=rotation[a*3+b]*raw.n[b];
   Point world{};for(unsigned a=0;a<3;a++)for(unsigned b=0;b<3;b++)world[a]+=actor[a*4+b]*n[b];v.normal=G::Unit(world);
   const auto axis=std::abs(v.normal[2])<.9f?Point{0,0,1}:Point{1,0,0};v.tangent=G::Unit(G::Cross(axis,v.normal));v.uv={raw.uv[0],raw.uv[1]};
  }
  for(auto face:Recipe::faces){
   unsigned material=0;const auto& a=fitted[face[0]];const auto& b=fitted[face[1]];const auto& c=fitted[face[2]];
   if(a.color[0]||b.color[0]||c.color[0]){
    material=1;const float v=(a.uv[1]+b.uv[1]+c.uv[1])/3;
    if(a.color[0]==1&&b.color[0]==1&&c.color[0]==1){if(v>.4f&&v<.455f)material=2;else if(v>.545f&&v<.6f)material=3;}
   }
   // Canonical fitting normals use outward cross products. Native REDengine
   // carriers use clockwise faces, as measured on both cooked body resources.
   mesh.triangles.push_back({{face[0],face[2],face[1]},material});
  }
  // Native normal maps need the actual authored fabric UV frame. Pole and
  // degenerate UV samples retain the finite geometric fallback above.
  std::vector<Point> tangents(Recipe::count),bitangents(Recipe::count);
  for(auto face:Recipe::faces){
   const auto& a=mesh.vertices[face[0]];const auto& b=mesh.vertices[face[1]];const auto& c=mesh.vertices[face[2]];
   const float u=b.uv[0]-a.uv[0],v=b.uv[1]-a.uv[1],s=c.uv[0]-a.uv[0],t=c.uv[1]-a.uv[1],det=u*t-v*s;if(std::abs(det)<1e-10f)continue;
   auto e=G::Sub(b.position,a.position),f=G::Sub(c.position,a.position);Point tangent{},bitangent{};
   for(unsigned k=0;k<3;k++){tangent[k]=(e[k]*t-f[k]*v)/det;bitangent[k]=(f[k]*u-e[k]*s)/det;}
   for(auto id:face){tangents[id]=G::Add(tangents[id],tangent);bitangents[id]=G::Add(bitangents[id],bitangent);}
  }
  for(unsigned i=0;i<Recipe::count;i++){
   auto& vertex=mesh.vertices[i];auto tangent=G::Sub(tangents[i],G::Mul(vertex.normal,G::Dot(tangents[i],vertex.normal)));
   if(G::Dot(tangent,tangent)>1e-12f)vertex.tangent=G::Unit(tangent);
   vertex.tangentSign=G::Dot(G::Cross(vertex.normal,vertex.tangent),bitangents[i])<0?-1.f:1.f;
  }
  return result;
 }
};
}
