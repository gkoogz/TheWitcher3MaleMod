#pragma once
#include "pose_input.hpp"
#include <malemod/surface/lighting.hpp>
#include <malemod/surface/presentation.hpp>
#include <malemod/surface/binding.hpp>
#include <malemod/surface/graft_runtime.hpp>
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
 surface::PrecisePoint reference{},authoredReference{};unsigned calibration=0;
 surface::PresentationBinding presentation;
 unsigned boundary=0;
};
struct RenderLOD {
 unsigned resource=0,lod=0;
 unsigned authoredCount=0,firstVertex=0,firstIndex=0,indexCount=0,uvOffset=0,extraOffset=0;
 std::vector<RenderVertexBinding> vertices;
 std::vector<std::array<std::uint32_t,3>> faces;
 std::vector<surface::LightingEdgeConstraint> collarSeams;
 std::vector<std::array<double,2>> lightingUV;
 std::vector<std::uint32_t> lightingGroups;
 std::vector<surface::LightingFrame> lightingFallback;
 std::vector<surface::LightingFrame> lightingReference;
 std::vector<double> collarNormalBlend;
 std::vector<std::vector<unsigned>> collarNormalNeighbors;
 std::vector<unsigned> guardAliases,guardRepresentatives;
 std::vector<surface::PrecisePoint> guardRest;
 std::shared_ptr<const surface::GraftPlan> bodyGuard;
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
 std::vector<std::array<float,3>> encodedReference;
 explicit RenderContract(const std::filesystem::path& path,const std::string& pin,const std::string& bindingHash){
  std::ifstream f(path,std::ios::binary);if(!f||std::filesystem::file_size(path)>32*1024*1024)throw std::runtime_error("Invalid render contract size");
  auto bytes=[&](void* p,std::size_t n){if(!f.read(static_cast<char*>(p),n))throw std::runtime_error("Truncated render contract");};
  auto text=[&](std::size_t n){std::string s(n,'\0');bytes(s.data(),n);return s;};auto integer=[&]{unsigned x;bytes(&x,4);return x;};
  const auto magic=text(8);const bool collar=magic=="MMRND006";const bool residual=collar||magic=="MMRND005";const bool multipart=residual||magic=="MMRND004";
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
    if(residual)bytes(v.authoredReference.data(),24);else v.authoredReference=v.reference;
    if(v.authored>=l.authoredCount||v.normalGroup>=n||v.calibration>1||v.presentation.frame>=15||!std::isfinite(v.presentation.amount)||v.presentation.amount<0||v.presentation.amount>1)throw std::invalid_argument("Invalid native lineage/normal alias");unsigned sum=0;for(unsigned i=0;i<4;i++){if(v.bones[i]>=count)throw std::invalid_argument("Invalid native skin index");sum+=v.weights[i];}if(!sum)throw std::invalid_argument("Empty native skin weights");
   for(double x:v.reference)if(!std::isfinite(x))throw std::invalid_argument("Nonfinite reference vertex");
    std::array<float,3> encoded{};const auto& resource=resources[l.resource];
    for(unsigned axis=0;axis<3;axis++){
     const double cell=(v.reference[axis]-resource.bias[axis])/resource.scale[axis]*65535.;
     const double word=std::round(cell);
     if(word<0||word>65535||std::abs(cell-word)>1e-5)throw std::invalid_argument("Cooked reference is not an observed UNORM position");
     encoded[axis]=float(word)/65535.f;
    }
    encodedReference.push_back(encoded);
   }
   auto faces=integer();if(faces*3!=l.indexCount)throw std::invalid_argument("Native topology count differs");l.faces.resize(faces);bytes(l.faces.data(),faces*12);for(auto face:l.faces)for(auto i:face)if(i>=n)throw std::invalid_argument("Native triangle outside topology");firstVertex+=n;firstIndex+=l.indexCount;
   if(collar){auto seams=integer();if(seams>n)throw std::invalid_argument("Oversize collar lighting binding");for(unsigned i=0;i<seams;i++){surface::LightingEdgeConstraint e;e.slave=integer();e.a=integer();e.b=integer();bytes(&e.weight,8);if(e.slave>=n||e.a>=n||e.b>=n||!std::isfinite(e.weight)||e.weight<0||e.weight>1)throw std::invalid_argument("Invalid native collar donor");l.collarSeams.push_back(e);}}
   l.lightingUV.reserve(n);l.lightingGroups.reserve(n);l.lightingFallback.reserve(n);
   std::vector<surface::LightingPoint> rest;
   for(const auto& v:l.vertices){l.lightingUV.push_back(v.uv);l.lightingGroups.push_back(v.normalGroup);l.lightingFallback.push_back(v.fallback);rest.push_back(residual&&v.boundary?v.authoredReference:v.reference);}
   l.lightingReference=surface::RebuildLighting(rest,l.lightingUV,l.faces,l.lightingGroups,l.lightingFallback);
  }
  for(const auto& l:lods){auto& r=resources[l.resource];r.lodFirstVertex[l.lod]=l.firstVertex-r.firstVertex;r.lodVertexCount[l.lod]=unsigned(l.vertices.size());r.lodUVOffset[l.lod]=l.uvOffset;r.lodExtraOffset[l.lod]=l.extraOffset;}
  for(auto& l:lods){
   l.collarNormalNeighbors.resize(l.vertices.size());
   auto link=[&](unsigned a,unsigned b){a=l.vertices[a].normalGroup;b=l.vertices[b].normalGroup;if(a!=b){l.collarNormalNeighbors[a].push_back(b);l.collarNormalNeighbors[b].push_back(a);}};
   for(auto f:l.faces){link(f[0],f[1]);link(f[1],f[2]);link(f[2],f[0]);}for(auto e:l.collarSeams){link(e.slave,e.a);link(e.slave,e.b);}
   for(auto& row:l.collarNormalNeighbors){std::sort(row.begin(),row.end());row.erase(std::unique(row.begin(),row.end()),row.end());}
   std::vector<surface::LightingPoint> opening;for(const auto& lower:lods)if(lower.lod==l.lod)for(auto e:lower.collarSeams)opening.push_back(lower.vertices[e.slave].reference);
   for(const auto& v:l.vertices){double distance=1e100;for(auto p:opening){auto q=surface::LightingSub(v.reference,p);distance=(std::min)(distance,std::sqrt(surface::LightingDot(q,q)));}
    double t=std::clamp(1-distance/.07,0.,1.);l.collarNormalBlend.push_back(t*t*t*(t*(t*6-15)+10));
   }
  }
  for(const auto& r:resources)if(r.lodVertexCount[0]+r.lodVertexCount[1]!=r.vertexCount)throw std::invalid_argument("Incomplete resource LOD range");
  if(f.peek()!=EOF)throw std::invalid_argument("Trailing native render data");
  if(collar)for(auto& l:lods){
   // The upper resource's minimum authored lineage is the observed lower-body
   // count. It distinguishes native body triangles from the moving module
   // without guessing from bones or copying a character-specific vertex ID.
   unsigned lowerCount=~0u;for(const auto& upper:lods)if(upper.resource==1&&upper.lod==l.lod)
    for(const auto& v:upper.vertices)lowerCount=(std::min)(lowerCount,v.authored);
   if(lowerCount==~0u)throw std::invalid_argument("Missing measured body membership");
   surface::GraftDomain domain;domain.orientationAreaTargetRatio=.10;std::map<surface::PrecisePoint,unsigned> groups;
   for(unsigned i=0;i<l.vertices.size();i++){
    const auto& v=l.vertices[i];auto point=v.boundary?v.authoredReference:v.reference;
    auto [entry,added]=groups.emplace(point,unsigned(domain.points.size()));
    if(added){domain.points.push_back(point);l.guardRepresentatives.push_back(i);}
    l.guardAliases.push_back(entry->second);
   }
   std::map<unsigned,surface::EdgeConstraint> edges;
   for(auto e:l.collarSeams){surface::EdgeConstraint edge{l.guardAliases[e.slave],l.guardAliases[e.a],l.guardAliases[e.b],e.weight};
    if((edge.slave==edge.a&&edge.weight==0)||(edge.slave==edge.b&&edge.weight==1))continue;
    if(edge.a==edge.b||edge.slave==edge.a||edge.slave==edge.b)throw std::invalid_argument("Native guard seam collapsed");
    auto [it,added]=edges.emplace(edge.slave,edge);if(!added&&(it->second.a!=edge.a||it->second.b!=edge.b||it->second.weight!=edge.weight))throw std::invalid_argument("Native guard aliases have conflicting donors");
   }
   for(auto [slave,e]:edges){domain.seams.push_back(e);for(unsigned a=0;a<3;a++)domain.points[slave][a]=(1-e.weight)*domain.points[e.a][a]+e.weight*domain.points[e.b][a];}
   std::vector<unsigned> locks(domain.points.size());
   for(unsigned i=0;i<l.vertices.size();i++)if(l.vertices[i].calibration)locks[l.guardAliases[i]]=2;else if(l.vertices[i].boundary)locks[l.guardAliases[i]]=(std::max)(locks[l.guardAliases[i]],1u);
   for(unsigned i=0;i<locks.size();i++)if(locks[i]==2)domain.protectedVertices.push_back(i);else if(locks[i])domain.prescribedVertices.push_back(i);
   for(auto face:l.faces){std::array<unsigned,3> mapped{l.guardAliases[face[0]],l.guardAliases[face[1]],l.guardAliases[face[2]]};
    const auto index=unsigned(domain.triangles.size());domain.triangles.push_back(mapped);
    if(mapped[0]!=mapped[1]&&mapped[1]!=mapped[2]&&mapped[0]!=mapped[2]&&(l.resource==1||(l.vertices[face[0]].authored<lowerCount&&l.vertices[face[1]].authored<lowerCount&&l.vertices[face[2]].authored<lowerCount)))domain.orientationTriangles.push_back(index);
   }
   l.guardRest=domain.points;l.bodyGuard=std::make_shared<surface::GraftPlan>(domain);
  }
 }
 unsigned VertexCount()const{unsigned n=0;for(const auto& l:lods)n+=unsigned(l.vertices.size());return n;}
};
struct SourceRenderVertex {
 std::array<float,3> position;std::uint32_t bones,weights;
 std::array<float,3> normal,tangent;float sign;
 std::array<float,3> reference;unsigned calibration;
};
static_assert(sizeof(SourceRenderVertex)==64&&offsetof(SourceRenderVertex,normal)==20&&offsetof(SourceRenderVertex,tangent)==32&&offsetof(SourceRenderVertex,reference)==48);
inline surface::LightingFrame TransportCookedLighting(surface::LightingFrame before,surface::LightingFrame after,surface::LightingFrame native){
 auto basis=[](surface::LightingFrame f){auto n=surface::LightingUnit(f.normal,{0,0,1});auto t=f.tangent;double d=surface::LightingDot(t,n);for(unsigned a=0;a<3;a++)t[a]-=d*n[a];t=surface::LightingUnit(t,{1,0,0});return std::array<surface::LightingPoint,3>{t,surface::LightingCross(n,t),n};};
 const auto a=basis(before),b=basis(after);
 auto transport=[&](surface::LightingPoint v){surface::LightingPoint out{};for(unsigned axis=0;axis<3;axis++){double w=surface::LightingDot(v,a[axis]);for(unsigned j=0;j<3;j++)out[j]+=w*b[axis][j];}return out;};
 return {transport(native.normal),transport(native.tangent),native.sign*after.sign*before.sign};
}
inline std::vector<SourceRenderVertex> ComposeRenderVertices(const RenderContract& c,const std::array<std::vector<surface::PrecisePoint>,2>& positions,bool parallel=true){
 auto compose=[&](unsigned part){std::vector<SourceRenderVertex> out;const auto& l=c.lods[part];auto lod=l.lod;if(positions[lod].size()!=l.authoredCount)throw std::invalid_argument("Source geometry differs from native lineage");out.reserve(l.vertices.size());
  std::vector<surface::LightingPoint> p;p.reserve(l.vertices.size());
  // Neck, wrists and ankles remain protected native boundaries. The common
  // movable waist is published across both body resources below. Preserve
  // cooked attributes only at the protected boundaries and their UV aliases.
  for(const auto& v:l.vertices){auto q=v.reference;if(!v.calibration){q=positions[lod][v.authored];if(!v.boundary)for(unsigned a=0;a<3;a++)q[a]+=v.reference[a]-v.authoredReference[a];}p.push_back(q);}
  const auto before=p;for(auto e:l.collarSeams)for(unsigned a=0;a<3;a++)p[e.slave][a]=(1-e.weight)*before[e.a][a]+e.weight*before[e.b][a];
  if(l.bodyGuard){
   std::vector<surface::PrecisePoint> delta(l.guardRest.size());
   for(unsigned i=0;i<delta.size();i++)for(unsigned a=0;a<3;a++)delta[i][a]=p[l.guardRepresentatives[i]][a]-l.guardRest[i][a];
   std::vector<surface::PrecisePoint> corrected;
   try{corrected=l.bodyGuard->ProjectDisplacement(delta);}catch(const std::exception& e){throw std::runtime_error(std::string("Native body orientation: ")+e.what());}
   for(unsigned i=0;i<p.size();i++)for(unsigned a=0;a<3;a++)p[i][a]=l.guardRest[l.guardAliases[i]][a]+corrected[l.guardAliases[i]][a];
  }
  auto light=surface::RebuildLighting(p,l.lightingUV,l.faces,l.lightingGroups,l.lightingFallback);
  // REDkit's cooked tangent frame carries the native normal-map convention.
  // Apply the shared geometric frame's change to that frame; rebuilding the
  // entire frame from scratch changes UV seam handedness even on static skin.
  for(unsigned i=0;i<light.size();i++){
   const auto geometric=light[i];
   light[i]=surface::AlignGeometricNormal(TransportCookedLighting(l.lightingReference[i],geometric,l.lightingFallback[i]),geometric,l.collarNormalBlend[i]);
  }
  surface::FairLightingNormals(light,l.lightingGroups,l.collarNormalNeighbors,l.collarNormalBlend);
  surface::WeldEdgeLighting(light,l.collarSeams);
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
