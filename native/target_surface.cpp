#include "target_surface.hpp"
#include <fstream>
#include <cstring>
#include <algorithm>
#include <limits>

namespace malemod::witcher {
namespace {
using namespace surface;
struct Reader {
 std::ifstream file;std::uint64_t remaining;
 explicit Reader(const std::filesystem::path& path):file(path,std::ios::binary),remaining(std::filesystem::file_size(path)){
  if(!file||remaining>64*1024*1024)throw std::invalid_argument("Invalid character binding artifact size");
 }
 void Bytes(void* p,std::size_t bytes){if(bytes>remaining||!file.read(static_cast<char*>(p),bytes))throw std::invalid_argument("Truncated character binding artifact");remaining-=bytes;}
 template<class T>T Value(){T value;Bytes(&value,sizeof(value));return value;}
 template<class T>std::vector<T> List(){auto count=Value<std::uint32_t>();if(count>2000000||std::uint64_t(count)*sizeof(T)>remaining)throw std::invalid_argument("Oversize character binding list");std::vector<T> out(count);Bytes(out.data(),out.size()*sizeof(T));return out;}
 DeltaBinding Binding(){DeltaBinding b;b.sourceVertexCount=Value<std::uint32_t>();b.offsets=List<std::uint32_t>();b.donors=List<std::uint32_t>();b.weights=List<double>();b.Validate();return b;}
};
std::vector<PrecisePoint> Points(const Surface& s){std::vector<PrecisePoint> out;out.reserve(s.positions.size());for(auto p:s.positions)out.push_back({p.x,p.y,p.z});return out;}
PrecisePoint Normalize(PrecisePoint p){double length=std::sqrt(p[0]*p[0]+p[1]*p[1]+p[2]*p[2]);if(!std::isfinite(length)||length<1e-10)throw std::invalid_argument("Invalid source collar direction");for(double& v:p)v/=length;return p;}
bool Same(const GraftFrame& a,const GraftFrame& b){return a.root==b.root&&a.axis==b.axis&&a.up==b.up&&a.radius==b.radius&&a.length==b.length&&a.sourceLengthScale==b.sourceLengthScale;}
struct Lod {
 GraftDomain domain;
 std::vector<PrecisePoint> restSource,restNative;
 std::vector<std::uint32_t> aliases,unique,protectedRender;
 std::uint32_t bodyCount;
 DeltaBinding body,module;
 GraftFrame cachedFrame{};std::unique_ptr<GraftPlan> plan;
};
}
struct TargetSurface::Impl {
 CoordinateCalibration calibration;
 std::vector<PrecisePoint> neutralAnatomy,neutralBody;
 std::vector<Lod> lods;
 Impl(const std::filesystem::path& path,const std::string& expected){
  Reader r(path);char magic[8],commit[40];r.Bytes(magic,8);r.Bytes(commit,40);
  if(std::memcmp(magic,"MMBIND02",8)||expected.size()!=40||std::string(commit,40)!=expected)throw std::invalid_argument("Character binding revision differs from pinned Base");
  calibration.basis=r.Value<std::array<PrecisePoint,3>>();calibration.sourceRoot=r.Value<PrecisePoint>();calibration.targetRoot=r.Value<PrecisePoint>();calibration.targetUnitsPerSourceUnit=r.Value<double>();calibration.Validate();
  neutralAnatomy=r.List<PrecisePoint>();neutralBody=r.List<PrecisePoint>();
  unsigned count=r.Value<std::uint32_t>();if(count!=2)throw std::invalid_argument("Expected both observed Geralt LODs");lods.resize(count);
  for(auto& l:lods){
   l.domain.points=r.List<PrecisePoint>();l.domain.triangles=r.List<std::array<std::uint32_t,3>>();
   unsigned seams=r.Value<std::uint32_t>();if(seams>l.domain.points.size())throw std::invalid_argument("Invalid character seam count");
   for(unsigned i=0;i<seams;i++){EdgeConstraint e;e.slave=r.Value<std::uint32_t>();e.a=r.Value<std::uint32_t>();e.b=r.Value<std::uint32_t>();e.weight=r.Value<double>();l.domain.seams.push_back(e);}
   l.domain.protectedVertices=r.List<std::uint32_t>();l.restSource=r.List<PrecisePoint>();l.restNative=r.List<PrecisePoint>();
   l.aliases=r.List<std::uint32_t>();l.unique=r.List<std::uint32_t>();l.protectedRender=r.List<std::uint32_t>();l.bodyCount=r.Value<std::uint32_t>();l.body=r.Binding();l.module=r.Binding();
   const auto n=l.restSource.size();
   if(!n||l.restNative.size()!=n||l.aliases.size()!=n||l.unique.size()!=l.domain.points.size()||l.bodyCount>=n||l.body.offsets.size()!=l.bodyCount+1||l.module.offsets.size()!=n-l.bodyCount+1||l.body.sourceVertexCount!=neutralBody.size()||l.module.sourceVertexCount!=neutralAnatomy.size())throw std::invalid_argument("Character binding dimensions differ");
   for(auto id:l.aliases)if(id>=l.domain.points.size())throw std::invalid_argument("Character alias outside unique domain");
   for(auto id:l.unique)if(id>=n)throw std::invalid_argument("Character master outside rendered domain");
   for(auto id:l.protectedRender)if(id>=l.bodyCount)throw std::invalid_argument("Protected character boundary outside body");
   for(const auto* list:{&l.restSource,&l.restNative,&l.domain.points})for(auto p:*list)for(double x:p)if(!std::isfinite(x))throw std::invalid_argument("Non-finite character rest binding");
  }
  if(r.remaining)throw std::invalid_argument("Trailing character binding data");
 }
 std::vector<PrecisePoint> Evaluate(unsigned id,const Output& source){
  if(id>=lods.size())throw std::out_of_range("Unknown character LOD");auto& l=lods[id];
  auto anatomy=Points(source.anatomy),body=Points(source.body[0]);auto body1=Points(source.body[1]);body.insert(body.end(),body1.begin(),body1.end());
  const auto& metric=source.collarMetric;
  if(!metric.generation)throw std::invalid_argument("Source collar support metric is unavailable");
  GraftFrame frame;frame.root={metric.root.x,metric.root.y,metric.root.z};frame.axis=Normalize({metric.axis.x,metric.axis.y,metric.axis.z});
  frame.up=Normalize({metric.up.x,metric.up.y,metric.up.z});frame.radius=metric.radius;frame.length=metric.length;
  if(!l.plan){l.plan=std::make_unique<GraftPlan>(l.domain,frame);l.cachedFrame=frame;}
  else if(!Same(frame,l.cachedFrame)){l.plan->UpdateFrame(frame);l.cachedFrame=frame;}
  auto bodyDelta=l.body.Apply(body,neutralBody),moduleDelta=l.module.Apply(anatomy,neutralAnatomy);
  std::vector<PrecisePoint> delta(l.restSource.size());
  for(unsigned i=0;i<l.bodyCount;i++)if(GraftRecruitmentWeight(l.restSource[i],frame)>1e-4)delta[i]=bodyDelta[i];
  std::copy(moduleDelta.begin(),moduleDelta.end(),delta.begin()+l.bodyCount);
  for(auto i:l.protectedRender)delta[i]={0,0,0};
  std::vector<PrecisePoint> unique(l.unique.size());for(unsigned i=0;i<unique.size();i++)unique[i]=delta[l.unique[i]];
  auto solved=l.plan->SolveDisplacement(unique);auto result=l.restNative;
  for(unsigned i=0;i<result.size();i++){
   auto v=calibration.VectorToTarget(solved[l.aliases[i]]);
   for(unsigned axis=0;axis<3;axis++)result[i][axis]+=v[axis]*calibration.targetUnitsPerSourceUnit;
  }
  return result;
 }
};
TargetSurface::TargetSurface(const std::filesystem::path& path,const std::string& commit):impl_(std::make_unique<Impl>(path,commit)){}
TargetSurface::~TargetSurface()=default;
std::vector<surface::PrecisePoint> TargetSurface::Evaluate(unsigned lod,const surface::Output& source){return impl_->Evaluate(lod,source);}
unsigned TargetSurface::LODCount()const{return static_cast<unsigned>(impl_->lods.size());}
}
