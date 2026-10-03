#pragma once
#include "pose_input.hpp"
#include <malemod/surface/lighting.hpp>
#include <malemod/surface/presentation.hpp>
#include <malemod/surface/binding.hpp>
#include <fstream>
#include <filesystem>
#include <cstring>
#include <cstddef>
#include <future>
#include <map>

namespace malemod::witcher {
struct RenderVertexBinding {
 std::uint32_t authored=0,normalGroup=0;
 std::array<std::uint8_t,4> bones{},weights{};
 std::array<double,2> uv{};surface::LightingFrame fallback;
 surface::PrecisePoint reference{};unsigned calibration=0;
 surface::PresentationBinding presentation;
 unsigned boundary=0;
};
struct RenderLOD {
 unsigned resource=0,lod=0;
 unsigned authoredCount=0,firstVertex=0,firstIndex=0,indexCount=0,uvOffset=0,extraOffset=0;
 std::vector<RenderVertexBinding> vertices;
 std::vector<std::array<std::uint32_t,3>> faces;
 std::vector<std::array<double,2>> lightingUV;
 std::vector<std::uint32_t> lightingGroups;
 std::vector<surface::LightingFrame> lightingFallback;
};
struct RenderResource {
 unsigned firstVertex=0,vertexCount=0,firstPalette=0,paletteCount=0,indexBytes=0;
 std::array<float,3> scale{},bias{};
 std::array<unsigned,2> lodFirstVertex{},lodVertexCount{},lodUVOffset{},lodExtraOffset{};
};
struct RenderContract {
 std::vector<unsigned> nativeBones;std::vector<PoseMatrix> inverseBind;
 surface::CoordinateCalibration calibration;
 std::vector<RenderLOD> lods;
 std::vector<RenderResource> resources;
 explicit RenderContract(const std::filesystem::path& path,const std::string& pin,const std::string& bindingHash){
  std::ifstream f(path,std::ios::binary);if(!f||std::filesystem::file_size(path)>32*1024*1024)throw std::runtime_error("Invalid render contract size");
  auto bytes=[&](void* p,std::size_t n){if(!f.read(static_cast<char*>(p),n))throw std::runtime_error("Truncated render contract");};
  auto text=[&](std::size_t n){std::string s(n,'\0');bytes(s.data(),n);return s;};auto integer=[&]{unsigned x;bytes(&x,4);return x;};
  const auto magic=text(8);const bool multipart=magic=="MMRND004";
  if((!multipart&&magic!="MMRND003")||text(40)!=pin||text(64)!=bindingHash)throw std::invalid_argument("Render contract differs from pinned geometry/binding");
  bytes(calibration.basis.data(),72);bytes(calibration.sourceRoot.data(),24);bytes(calibration.targetRoot.data(),24);bytes(&calibration.targetUnitsPerSourceUnit,8);calibration.Validate();
  auto count=integer();if(!count||count>256)throw std::invalid_argument("Unexpected native skin palette");nativeBones.resize(count);inverseBind.resize(count);bytes(nativeBones.data(),count*4);bytes(inverseBind.data(),count*sizeof(PoseMatrix));
  for(unsigned i=0;i<count;i++){if(nativeBones[i]>=104)throw std::invalid_argument("Native bone outside observed skeleton");InversePose(inverseBind[i]);}
  if(multipart){auto n=integer();if(n!=2)throw std::invalid_argument("Expected both body resources");resources.resize(n);for(auto& r:resources){r.firstVertex=integer();r.vertexCount=integer();r.firstPalette=integer();r.paletteCount=integer();r.indexBytes=integer();bytes(r.scale.data(),12);bytes(r.bias.data(),12);if(!r.vertexCount||r.firstPalette+r.paletteCount>count||!r.indexBytes)throw std::invalid_argument("Invalid native resource contract");for(float s:r.scale)if(!std::isfinite(s)||s<=0)throw std::invalid_argument("Invalid quantization scale");}}
  else resources.push_back({0,36547,0,46,435936,{.41360682249f,.45207571983f,.91064155102f},{-.2066219449f,-.16102458537f,.17968167365f}});
  auto lodCount=integer();if(lodCount!=resources.size()*2)throw std::invalid_argument("Render contract LOD count differs");lods.resize(lodCount);unsigned firstVertex=0,firstIndex=0;
  for(unsigned li=0;li<lods.size();li++){auto& l=lods[li];l.resource=multipart?integer():0;l.lod=multipart?integer():li;if(l.resource>=resources.size()||l.lod>=2)throw std::invalid_argument("Invalid part/LOD");if(l.lod==0)firstIndex=0;unsigned n=integer();l.authoredCount=integer();l.firstVertex=integer();l.firstIndex=integer();l.indexCount=integer();l.uvOffset=integer();l.extraOffset=integer();
   if(!n||n>100000||!l.authoredCount||l.authoredCount>100000||l.firstVertex!=firstVertex||l.firstIndex!=firstIndex||l.indexCount>1000000)throw std::invalid_argument("Invalid native render dimensions");
   l.vertices.resize(n);for(auto& v:l.vertices){v.authored=integer();v.normalGroup=integer();bytes(v.bones.data(),4);bytes(v.weights.data(),4);bytes(v.uv.data(),16);bytes(v.fallback.normal.data(),24);bytes(v.fallback.tangent.data(),24);bytes(&v.fallback.sign,8);bytes(v.reference.data(),24);v.calibration=integer();
    v.presentation.frame=integer();bytes(&v.presentation.amount,8);
    if(multipart)v.boundary=integer();
    if(v.authored>=l.authoredCount||v.normalGroup>=n||v.calibration>1||v.presentation.frame>=15||!std::isfinite(v.presentation.amount)||v.presentation.amount<0||v.presentation.amount>1)throw std::invalid_argument("Invalid native lineage/normal alias");unsigned sum=0;for(unsigned i=0;i<4;i++){if(v.bones[i]>=count)throw std::invalid_argument("Invalid native skin index");sum+=v.weights[i];}if(!sum)throw std::invalid_argument("Empty native skin weights");
    for(double x:v.reference)if(!std::isfinite(x))throw std::invalid_argument("Nonfinite reference vertex");
   }
   auto faces=integer();if(faces*3!=l.indexCount)throw std::invalid_argument("Native topology count differs");l.faces.resize(faces);bytes(l.faces.data(),faces*12);for(auto face:l.faces)for(auto i:face)if(i>=n)throw std::invalid_argument("Native triangle outside topology");firstVertex+=n;firstIndex+=l.indexCount;
   l.lightingUV.reserve(n);l.lightingGroups.reserve(n);l.lightingFallback.reserve(n);
   for(const auto& v:l.vertices){l.lightingUV.push_back(v.uv);l.lightingGroups.push_back(v.normalGroup);l.lightingFallback.push_back(v.fallback);}
  }
  for(const auto& l:lods){auto& r=resources[l.resource];r.lodFirstVertex[l.lod]=l.firstVertex-r.firstVertex;r.lodVertexCount[l.lod]=unsigned(l.vertices.size());r.lodUVOffset[l.lod]=l.uvOffset;r.lodExtraOffset[l.lod]=l.extraOffset;}
  for(const auto& r:resources)if(r.lodVertexCount[0]+r.lodVertexCount[1]!=r.vertexCount)throw std::invalid_argument("Incomplete resource LOD range");
  if(f.peek()!=EOF)throw std::invalid_argument("Trailing native render data");
 }
 unsigned VertexCount()const{unsigned n=0;for(const auto& l:lods)n+=unsigned(l.vertices.size());return n;}
};
struct SourceRenderVertex {
 std::array<float,3> position;std::uint32_t bones,weights;
 std::array<float,3> normal,tangent;float sign;
 std::array<float,3> reference;unsigned calibration;
};
static_assert(sizeof(SourceRenderVertex)==64&&offsetof(SourceRenderVertex,normal)==20&&offsetof(SourceRenderVertex,tangent)==32&&offsetof(SourceRenderVertex,reference)==48);
inline std::vector<SourceRenderVertex> ComposeRenderVertices(const RenderContract& c,const std::array<std::vector<surface::PrecisePoint>,2>& positions,bool parallel=true){
 auto compose=[&](unsigned part){std::vector<SourceRenderVertex> out;const auto& l=c.lods[part];auto lod=l.lod;if(positions[lod].size()!=l.authoredCount)throw std::invalid_argument("Source geometry differs from native lineage");out.reserve(l.vertices.size());
  std::vector<surface::LightingPoint> p;p.reserve(l.vertices.size());
  // Neck, wrists and ankles remain protected native boundaries. The common
  // movable waist is published across both body resources below. Preserve
  // cooked attributes only at the protected boundaries and their UV aliases.
  for(const auto& v:l.vertices)p.push_back(v.calibration?v.reference:positions[lod][v.authored]);
  auto light=surface::RebuildLighting(p,l.lightingUV,l.faces,l.lightingGroups,l.lightingFallback);
  for(unsigned i=0;i<l.vertices.size();i++){if(l.vertices[i].calibration)light[i]=l.vertices[i].fallback;SourceRenderVertex row{};std::memcpy(&row.bones,l.vertices[i].bones.data(),4);std::memcpy(&row.weights,l.vertices[i].weights.data(),4);for(unsigned a=0;a<3;a++){row.position[a]=float(p[i][a]);row.reference[a]=float(l.vertices[i].reference[a]);row.normal[a]=float(light[i].normal[a]);row.tangent[a]=float(light[i].tangent[a]);}row.sign=float(light[i].sign);row.calibration=l.vertices[i].calibration;out.push_back(row);}
  return out;
 };
 std::vector<SourceRenderVertex> out;out.reserve(c.VertexCount());
 std::vector<std::future<std::vector<SourceRenderVertex>>> jobs;
 if(parallel)for(unsigned i=1;i<c.lods.size();i++)jobs.push_back(std::async(std::launch::async,[&,i]{return compose(i);}));
 for(unsigned i=0;i<c.lods.size();i++){auto rows=parallel&&i?jobs[i-1].get():compose(i);out.insert(out.end(),rows.begin(),rows.end());}
 // Shared waist normals are published from both actual surface sides at one
 // completed solution. UV tangents retain each material island's handedness.
 std::map<std::pair<unsigned,unsigned>,surface::LightingPoint> sums;
 for(const auto& l:c.lods)for(unsigned i=0;i<l.vertices.size();i++)if(auto knot=l.vertices[i].boundary){auto& n=sums[{l.lod,knot}];for(unsigned a=0;a<3;a++)n[a]+=out[l.firstVertex+i].normal[a];}
 for(const auto& l:c.lods)for(unsigned i=0;i<l.vertices.size();i++)if(auto knot=l.vertices[i].boundary){auto n=sums[{l.lod,knot}];double len=0;for(double x:n)len+=x*x;len=std::sqrt(len);auto& v=out[l.firstVertex+i];double dot=0;for(unsigned a=0;a<3;a++){v.normal[a]=float(n[a]/len);dot+=v.normal[a]*v.tangent[a];}double norm=0;for(unsigned a=0;a<3;a++){v.tangent[a]-=float(dot*v.normal[a]);norm+=v.tangent[a]*v.tangent[a];}norm=std::sqrt(norm);for(auto& x:v.tangent)x=float(x/norm);}
 return out;
}
}
