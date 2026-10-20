#pragma once
#include MALEMOD_ATTACHMENT_CORRECTIVE_HEADER
#include <malemod/surface/graft_runtime.hpp>
#include <malemod/surface/runtime.hpp>
#include <filesystem>
#include <fstream>
#include <cstring>
#include <memory>

namespace malemod::witcher {
namespace collar_detail {
inline std::uint64_t FNV(const unsigned char* p,std::size_t n){std::uint64_t h=14695981039346656037ull;for(std::size_t i=0;i<n;i++){h^=p[i];h*=1099511628211ull;}return h;}
inline std::vector<unsigned char> File(const std::filesystem::path& path){
 auto size=std::filesystem::file_size(path);if(size>64*1024*1024)throw std::invalid_argument("Oversize corrective input");
 std::ifstream in(path,std::ios::binary);std::vector<unsigned char> out(std::size_t(size),0);
 if(!in.read(reinterpret_cast<char*>(out.data()),out.size()))throw std::invalid_argument("Cannot read corrective input");return out;
}
struct Reader {
 const std::vector<unsigned char>& bytes;std::size_t at=0,limit;
 explicit Reader(const std::vector<unsigned char>& b):bytes(b),limit(b.size()-8){}
 void Read(void* p,std::size_t n){if(n>limit-at)throw std::invalid_argument("Truncated corrective artifact");std::memcpy(p,bytes.data()+at,n);at+=n;}
 template<class T>T Get(){T t{};Read(&t,sizeof(t));return t;}
 template<class T>std::vector<T> List(){auto n=Get<std::uint32_t>();if(n>1000000||std::uint64_t(n)*sizeof(T)>limit-at)throw std::invalid_argument("Invalid corrective list");std::vector<T> v(n);Read(v.data(),v.size()*sizeof(T));return v;}
};
}
struct CollarCorrectiveData {std::uint32_t pointCount;double referenceDepth;std::vector<std::uint32_t> fixed,ids,saddle,rim;std::vector<double> frameWeights;std::vector<surface::corrective::Knot> knots;};
struct CollarCorrectiveArtifact {
 double radius,length,depth;surface::corrective::Point measureUp;surface::corrective::Frame referenceFrame;std::vector<CollarCorrectiveData> lods;
 static CollarCorrectiveArtifact Load(const std::filesystem::path& path,const std::filesystem::path& binding,const std::string& revision){
  auto bytes=collar_detail::File(path);if(bytes.size()<112)throw std::invalid_argument("Short corrective artifact");
  std::uint64_t expected;std::memcpy(&expected,bytes.data()+bytes.size()-8,8);
  if(collar_detail::FNV(bytes.data(),bytes.size()-8)!=expected)throw std::invalid_argument("Corrective checksum differs");
  collar_detail::Reader r(bytes);char magic[8],base[40];r.Read(magic,8);auto version=r.Get<std::uint32_t>();auto source=r.Get<std::uint64_t>();r.Read(base,40);auto original=collar_detail::File(binding);
  if(std::memcmp(magic,"MMCORR03",8)||version!=3||std::string(base,40)!=revision||source!=collar_detail::FNV(original.data(),original.size()))throw std::invalid_argument("Corrective binding revision differs");
  CollarCorrectiveArtifact a;a.radius=r.Get<double>();a.length=r.Get<double>();a.depth=r.Get<double>();a.measureUp=r.Get<surface::corrective::Point>();
  if(!std::isfinite(a.radius+a.length+a.depth)||a.radius<=0||a.length<=0||a.depth<=0||!surface::corrective::Finite(a.measureUp)||std::abs(surface::corrective::Dot(a.measureUp,a.measureUp)-1)>1e-6)throw std::invalid_argument("Invalid corrective reference dimensions");
  a.referenceFrame.forward=r.Get<surface::corrective::Point>();a.referenceFrame.side=r.Get<surface::corrective::Point>();a.referenceFrame.up=r.Get<surface::corrective::Point>();if(!a.referenceFrame.Valid())throw std::invalid_argument("Invalid corrective anchor frame");
  auto count=r.Get<std::uint32_t>();if(count!=2)throw std::invalid_argument("Corrective must cover both LODs");
  for(unsigned i=0;i<count;i++){
   CollarCorrectiveData d;d.pointCount=r.Get<std::uint32_t>();d.referenceDepth=r.Get<double>();if(!std::isfinite(d.referenceDepth)||d.referenceDepth<=0)throw std::invalid_argument("Invalid LOD depth reference");d.fixed=r.List<std::uint32_t>();d.ids=r.List<std::uint32_t>();d.saddle=r.List<std::uint32_t>();d.rim=r.List<std::uint32_t>();d.frameWeights=r.List<double>();auto n=r.Get<std::uint32_t>();
   if(!n||n>16||d.saddle.empty()||d.rim.empty())throw std::invalid_argument("Invalid corrective landmarks/path");
   for(unsigned j=0;j<n;j++){surface::corrective::Knot k;k.weight=r.Get<double>();k.localDisplacement=r.List<surface::corrective::Point>();d.knots.push_back(std::move(k));}
   for(auto list:{&d.saddle,&d.rim})for(auto id:*list)if(id>=d.pointCount)throw std::invalid_argument("Corrective landmark outside mesh");a.lods.push_back(std::move(d));
  }
  if(r.at!=r.limit)throw std::invalid_argument("Trailing corrective data");return a;
 }
};
class CollarCorrective {
 surface::corrective::Plan plan_;std::vector<std::uint32_t> saddle_,rim_;double radius_,length_,depth_;surface::corrective::Point up_;surface::corrective::Frame anchor_;
 static std::vector<std::uint32_t> Fixed(const CollarCorrectiveData& d,const surface::GraftDomain& domain,const std::vector<std::uint32_t>& unique,unsigned bodyCount){
  auto ids=d.fixed;ids.insert(ids.end(),domain.protectedVertices.begin(),domain.protectedVertices.end());ids.insert(ids.end(),domain.prescribedVertices.begin(),domain.prescribedVertices.end());
  for(unsigned i=0;i<unique.size();i++)if(unique[i]<bodyCount)ids.push_back(i);for(auto e:domain.seams)for(auto i:{e.slave,e.a,e.b})ids.push_back(i);return ids;
 }
 public:
 CollarCorrective(const CollarCorrectiveArtifact& a,unsigned lod,const surface::GraftDomain& domain,const std::vector<std::uint32_t>& unique,unsigned bodyCount):
  plan_(domain.points.size(),domain.triangles,Fixed(a.lods.at(lod),domain,unique,bodyCount),a.lods.at(lod).ids,a.lods.at(lod).knots,.02,a.lods.at(lod).frameWeights),
  saddle_(a.lods[lod].saddle),rim_(a.lods[lod].rim),radius_(a.radius),length_(a.length),depth_(a.lods[lod].referenceDepth),up_(a.measureUp),anchor_(a.referenceFrame){if(a.lods[lod].pointCount!=domain.points.size())throw std::invalid_argument("Corrective point count differs");}
 surface::corrective::Result Apply(const std::vector<surface::PrecisePoint>& points,const surface::Output& source,double ui,double neutralRadius)const{
  using namespace surface::corrective;if(!std::isfinite(ui)||ui<1||ui>100)throw std::invalid_argument("Invalid corrective angle control");
  // Established signed-downward control: UI1=-80 degrees, UI50=30 degrees.
  const double response=ui<50?Smooth((80.-110.*(ui-1.)/49.)/25.):0,r=source.collarMetric.radius;
  if(!response||r<=neutralRadius||radius_<=neutralRadius)return {points,0};
  double rim=-std::numeric_limits<double>::infinity(),sample=0;for(auto i:rim_)rim=std::max(rim,Dot(points[i],up_));for(auto i:saddle_)sample+=Dot(points[i],up_)/saddle_.size();
  const double sag=std::max(0.,rim-sample),gain=response*Smooth((r-neutralRadius)/(radius_-neutralRadius))*std::min(1.,sag/depth_);if(!gain)return {points,0};
  auto a=source.shaftGuide[0],b=source.shaftGuide[2];Point axis={double(b.x-a.x),double(b.y-a.y),double(b.z-a.z)};
  try{return plan_.Apply(points,Frame::FromAxis(axis),{source.restLength/length_,r/radius_,r/radius_},gain,true,&anchor_);}catch(const std::invalid_argument&){return {points,0};}
 }
};
}
