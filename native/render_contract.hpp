#pragma once
#include "pose_input.hpp"
#include <malemod/surface/lighting.hpp>
#include <fstream>
#include <filesystem>
#include <cstring>
#include <cstddef>
#include <future>

namespace malemod::witcher {
struct RenderVertexBinding {
 std::uint32_t authored=0,normalGroup=0;
 std::array<std::uint8_t,4> bones{},weights{};
 std::array<double,2> uv{};surface::LightingFrame fallback;
 surface::PrecisePoint reference{};unsigned calibration=0;
};
struct RenderLOD {
 unsigned authoredCount=0,firstVertex=0,firstIndex=0,indexCount=0,uvOffset=0,extraOffset=0;
 std::vector<RenderVertexBinding> vertices;
 std::vector<std::array<std::uint32_t,3>> faces;
 std::vector<std::array<double,2>> lightingUV;
 std::vector<std::uint32_t> lightingGroups;
 std::vector<surface::LightingFrame> lightingFallback;
};
struct RenderContract {
 std::vector<unsigned> nativeBones;std::vector<PoseMatrix> inverseBind;
 std::array<RenderLOD,2> lods;
 explicit RenderContract(const std::filesystem::path& path,const std::string& pin,const std::string& bindingHash){
  std::ifstream f(path,std::ios::binary);if(!f||std::filesystem::file_size(path)>32*1024*1024)throw std::runtime_error("Invalid render contract size");
  auto bytes=[&](void* p,std::size_t n){if(!f.read(static_cast<char*>(p),n))throw std::runtime_error("Truncated render contract");};
  auto text=[&](std::size_t n){std::string s(n,'\0');bytes(s.data(),n);return s;};auto integer=[&]{unsigned x;bytes(&x,4);return x;};
  if(text(8)!="MMRND002"||text(40)!=pin||text(64)!=bindingHash)throw std::invalid_argument("Render contract differs from pinned geometry/binding");
  auto count=integer();if(count!=46)throw std::invalid_argument("Unexpected native skin palette");nativeBones.resize(count);inverseBind.resize(count);bytes(nativeBones.data(),count*4);bytes(inverseBind.data(),count*sizeof(PoseMatrix));
  for(unsigned i=0;i<count;i++){if(nativeBones[i]>=104)throw std::invalid_argument("Native bone outside observed skeleton");InversePose(inverseBind[i]);}
  if(integer()!=2)throw std::invalid_argument("Render contract LOD count differs");unsigned firstVertex=0,firstIndex=0;
  for(auto& l:lods){unsigned n=integer();l.authoredCount=integer();l.firstVertex=integer();l.firstIndex=integer();l.indexCount=integer();l.uvOffset=integer();l.extraOffset=integer();
   if(!n||n>100000||!l.authoredCount||l.authoredCount>100000||l.firstVertex!=firstVertex||l.firstIndex!=firstIndex||l.indexCount>1000000)throw std::invalid_argument("Invalid native render dimensions");
   l.vertices.resize(n);for(auto& v:l.vertices){v.authored=integer();v.normalGroup=integer();bytes(v.bones.data(),4);bytes(v.weights.data(),4);bytes(v.uv.data(),16);bytes(v.fallback.normal.data(),24);bytes(v.fallback.tangent.data(),24);bytes(&v.fallback.sign,8);bytes(v.reference.data(),24);v.calibration=integer();
    if(v.authored>=l.authoredCount||v.normalGroup>=n||v.calibration>1)throw std::invalid_argument("Invalid native lineage/normal alias");unsigned sum=0;for(unsigned i=0;i<4;i++){if(v.bones[i]>=count)throw std::invalid_argument("Invalid native skin index");sum+=v.weights[i];}if(!sum)throw std::invalid_argument("Empty native skin weights");
    for(double x:v.reference)if(!std::isfinite(x))throw std::invalid_argument("Nonfinite reference vertex");
   }
   auto faces=integer();if(faces*3!=l.indexCount)throw std::invalid_argument("Native topology count differs");l.faces.resize(faces);bytes(l.faces.data(),faces*12);for(auto face:l.faces)for(auto i:face)if(i>=n)throw std::invalid_argument("Native triangle outside topology");firstVertex+=n;firstIndex+=l.indexCount;
   l.lightingUV.reserve(n);l.lightingGroups.reserve(n);l.lightingFallback.reserve(n);
   for(const auto& v:l.vertices){l.lightingUV.push_back(v.uv);l.lightingGroups.push_back(v.normalGroup);l.lightingFallback.push_back(v.fallback);}
  }
  if(f.peek()!=EOF)throw std::invalid_argument("Trailing native render data");
 }
 unsigned VertexCount()const{return unsigned(lods[0].vertices.size()+lods[1].vertices.size());}
};
struct SourceRenderVertex {
 std::array<float,3> position;std::uint32_t bones,weights;
 std::array<float,3> normal,tangent;float sign;
 std::array<float,3> reference;unsigned calibration;
};
static_assert(sizeof(SourceRenderVertex)==64&&offsetof(SourceRenderVertex,normal)==20&&offsetof(SourceRenderVertex,tangent)==32&&offsetof(SourceRenderVertex,reference)==48);
inline std::vector<SourceRenderVertex> ComposeRenderVertices(const RenderContract& c,const std::array<std::vector<surface::PrecisePoint>,2>& positions,bool parallel=true){
 auto compose=[&](unsigned lod){std::vector<SourceRenderVertex> out;const auto& l=c.lods[lod];if(positions[lod].size()!=l.authoredCount)throw std::invalid_argument("Source geometry differs from native lineage");out.reserve(l.vertices.size());
  std::vector<surface::LightingPoint> p;p.reserve(l.vertices.size());
  // Geralt's separate stock torso shares this fixed boundary. Preserve the
  // exact cooked boundary positions and lighting, including UV-split aliases.
  // Only interior surface lighting may be rebuilt without changing both parts.
  for(const auto& v:l.vertices)p.push_back(v.calibration?v.reference:positions[lod][v.authored]);
  auto light=surface::RebuildLighting(p,l.lightingUV,l.faces,l.lightingGroups,l.lightingFallback);
  for(unsigned i=0;i<l.vertices.size();i++){if(l.vertices[i].calibration)light[i]=l.vertices[i].fallback;SourceRenderVertex row{};std::memcpy(&row.bones,l.vertices[i].bones.data(),4);std::memcpy(&row.weights,l.vertices[i].weights.data(),4);for(unsigned a=0;a<3;a++){row.position[a]=float(p[i][a]);row.reference[a]=float(l.vertices[i].reference[a]);row.normal[a]=float(light[i].normal[a]);row.tangent[a]=float(light[i].tangent[a]);}row.sign=float(light[i].sign);row.calibration=l.vertices[i].calibration;out.push_back(row);}
  return out;
 };
 std::vector<SourceRenderVertex> out,other;
 if(parallel){auto job=std::async(std::launch::async,[&]{return compose(1);});out=compose(0);other=job.get();}
 else{out=compose(0);other=compose(1);}
 out.reserve(c.VertexCount());out.insert(out.end(),other.begin(),other.end());
 return out;
}
}
