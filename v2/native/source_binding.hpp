#pragma once
#include "engine/live_renderer.hpp"
#include "engine/pose.hpp"
#include "binding_parallel.hpp"
#include <malemod/surface/canonical_packet.hpp>
#include <malemod/motion_filter.hpp>
#include <malemod/surface/normal_frame.hpp>
#include <filesystem>
#include <fstream>
#include <cstring>
#include <cmath>
#include <stdexcept>
#include <map>
#include <set>
#include <algorithm>
namespace malemod::witcher::v2 {
class SourceBinding {
 using Point=std::array<float,3>;
 struct Row {RenderDelivery::FloatVertex baseline;std::array<unsigned,3> donor;std::array<float,3> weight;};
 static_assert(sizeof(Row)==52);
 mutable std::shared_ptr<const RenderDelivery> cached_;mutable std::uint64_t generation_=0;mutable bool correctedLighting_=true;
 std::vector<Row> rows_;
 std::vector<unsigned> rowAliases_;
 std::shared_ptr<const std::vector<std::uint16_t>> coveredIndices_;
 std::vector<Point> source_;
 std::vector<Point> normals_;
 std::vector<Point> tangents_;
 struct NormalBinding {std::array<unsigned,3> donor;std::array<float,3> weight;Point reference,tangentReference;bool fullFrame=false;};
 std::vector<NormalBinding> normalBindings_;
 std::vector<unsigned> normalGroups_;
 struct Lighting {Point normal,tangent;};
 std::vector<Lighting> lighting_;
 static Point DecodeDirection(unsigned word){Point p{};for(unsigned a=0;a<3;a++)p[a]=float((word>>(a*10))&1023)/511.5f-1;return p;}
 std::vector<RenderResource> resources_;
 public:
 struct Bone {unsigned id;Matrix inverse;};
 private:
 std::vector<Bone> bones_;
 std::array<float,9> rotation_{};Point root_{},target_{};
 template<class T> static void Read(std::ifstream& stream,T* data,std::size_t count=1){
  stream.read(reinterpret_cast<char*>(data),sizeof(T)*count);if(!stream)throw std::runtime_error("Truncated Geralt source binding");
 }
 public:
 explicit SourceBinding(const std::filesystem::path& path){
  std::ifstream f(path,std::ios::binary);char magic[8];Read(f,magic,8);
  const bool sectioned=std::memcmp(magic,"MMV2B04\0",8)==0;
  if(!sectioned&&std::memcmp(magic,"MMV2B03\0",8))throw std::runtime_error("Unknown Geralt source binding");
  unsigned count=0;Read(f,&count);if(count!=2)throw std::runtime_error("Both body resources are required");
  Read(f,rotation_.data(),9);Read(f,root_.data(),3);Read(f,target_.data(),3);
  unsigned sources=0;Read(f,&sources);if(sources!=17528+15168+5615)throw std::runtime_error("Canonical source count changed");
  source_.resize(sources);Read(f,source_.data(),sources);
  normals_.resize(sources);Read(f,normals_.data(),sources);
  if(sectioned){tangents_.resize(sources);Read(f,tangents_.data(),sources);}
  for(unsigned part=0;part<count;part++){
   RenderResource r;std::array<unsigned,5> header{};Read(f,header.data(),header.size());
   if(!header[0]||header[0]>100000||!header[1]||header[1]>2000000||(!sectioned&&header[2])||header[3]||header[4])throw std::runtime_error("Invalid native resource bounds");
   r.firstVertex=unsigned(rows_.size());r.vertexCount=header[0];r.indexBytes=header[1];r.vertexBufferBytes=header[2];
   Read(f,r.scale.data(),3);Read(f,r.bias.data(),3);
   Read(f,r.lodFirstVertex.data(),2);Read(f,r.lodVertexCount.data(),2);Read(f,r.lodUVOffset.data(),2);Read(f,r.lodExtraOffset.data(),2);
   if(r.lodFirstVertex[0]||r.lodFirstVertex[1]!=r.lodVertexCount[0]||r.lodVertexCount[0]+r.lodVertexCount[1]!=r.vertexCount)throw std::runtime_error("Invalid native LOD ranges");
   if(sectioned){
    unsigned sections=0;Read(f,&sections);if(!r.vertexBufferBytes||sections<2||sections>16)throw std::runtime_error("Invalid native material section count");
    r.sections.resize(sections);Read(f,r.sections.data(),sections);
    unsigned nextVertex=0;std::array<unsigned,2> lodCounts{};std::vector<std::pair<unsigned,unsigned>> intervals;
    for(const auto& s:r.sections){
     if(s.lod>1||s.material>2||(part&&s.material)||!s.vertexCount||s.vertexCount>65535||s.firstVertex!=nextVertex||!s.indexCount||s.indexCount%3||s.indexFirst>r.indexBytes/2||s.indexCount>r.indexBytes/2-s.indexFirst)throw std::runtime_error("Invalid native material section interval");
     if(s.vertexCount>r.vertexCount-nextVertex||s.firstVertex<r.lodFirstVertex[s.lod]||s.firstVertex+s.vertexCount>r.lodFirstVertex[s.lod]+r.lodVertexCount[s.lod])throw std::runtime_error("Native section leaves its LOD");
     const unsigned offsets[]={s.positionOffset,s.uvOffset,s.lightingOffset,s.extraOffset},strides[]={16,4,8,8};
     for(unsigned slot=0;slot<4;slot++)if(offsets[slot]>r.vertexBufferBytes||std::uint64_t(s.vertexCount)*strides[slot]>r.vertexBufferBytes-offsets[slot])throw std::runtime_error("Native section stream leaves its allocation");
     for(const auto& other:r.sections){if(&other==&s)break;const bool overlap=s.indexFirst<other.indexFirst+other.indexCount&&other.indexFirst<s.indexFirst+s.indexCount;if(overlap&&(s.lod!=other.lod||!(s.material==1&&other.material==2||s.material==2&&other.material==1)||s.vertexCount!=other.vertexCount))throw std::runtime_error("Unobserved overlapping native material indices");}
     nextVertex+=s.vertexCount;lodCounts[s.lod]+=s.vertexCount;intervals.emplace_back(s.indexFirst,s.indexFirst+s.indexCount);
    }
    std::sort(intervals.begin(),intervals.end());unsigned covered=0;for(const auto& interval:intervals){if(interval.first>covered)throw std::runtime_error("Native material index gap");covered=(std::max)(covered,interval.second);}
    if(nextVertex!=r.vertexCount||covered*2!=r.indexBytes||lodCounts!=r.lodVertexCount)throw std::runtime_error("Incomplete native material sections");
   }
   Read(f,&r.paletteCount);r.firstPalette=unsigned(bones_.size());if(!r.paletteCount||r.paletteCount>256)throw std::runtime_error("Invalid observed palette");
   for(unsigned i=0;i<r.paletteCount;i++){Bone b;Read(f,&b.id);Read(f,b.inverse.data(),16);if(b.id>=94)throw std::runtime_error("Nonstock native bone");Inverse(b.inverse);bones_.push_back(b);}
   for(float x:r.scale)if(!std::isfinite(x)||x<=0)throw std::runtime_error("Invalid native quantization");
   rows_.resize(rows_.size()+r.vertexCount);Read(f,rows_.data()+r.firstVertex,r.vertexCount);resources_.push_back(r);
  }
  for(const auto& row:rows_){float sum=0;for(unsigned k=0;k<3;k++){if(row.donor[k]>=sources||!std::isfinite(row.weight[k])||row.weight[k]<-1e-5f)throw std::runtime_error("Invalid canonical donor");sum+=row.weight[k];}if(std::abs(sum-1)>1e-4f)throw std::runtime_error("Nonunit canonical donor weights");}
  std::vector<bool> fullFrame(rows_.size());
  if(sectioned)for(const auto& r:resources_)for(const auto& s:r.sections)if(s.material)for(unsigned i=0;i<s.vertexCount;i++)fullFrame[r.firstVertex+s.firstVertex+i]=true;
  if(sectioned){
   // A material split must not split the transported lighting frame at a
   // physical weld. Exact complete stock-row aliases use that stock frame;
   // distinct anatomy interior rows retain the canonical full-frame path.
   for(const auto& r:resources_){std::set<std::array<unsigned,13>> stock;
    for(const auto& s:r.sections)if(!s.material)for(unsigned n=0;n<s.vertexCount;n++){std::array<unsigned,13> key{};std::memcpy(key.data(),&rows_[r.firstVertex+s.firstVertex+n],sizeof(Row));stock.insert(key);}
    for(const auto& s:r.sections)if(s.material)for(unsigned n=0;n<s.vertexCount;n++){const unsigned i=r.firstVertex+s.firstVertex+n;std::array<unsigned,13> key{};std::memcpy(key.data(),&rows_[i],sizeof(Row));if(stock.count(key))fullFrame[i]=false;}
   }
  }
  rowAliases_.resize(rows_.size());
  if(sectioned){
   // Material-state aliases have identical native attributes and canonical
   // donors. Evaluate that exact row once per resource, then copy its bytes;
   // the alternate material never adds another numerical surface solve.
   for(const auto& r:resources_){std::map<std::array<unsigned,14>,unsigned> aliases;
    for(unsigned i=r.firstVertex;i<r.firstVertex+r.vertexCount;i++){std::array<unsigned,14> key{};std::memcpy(key.data(),&rows_[i],sizeof(Row));key[13]=fullFrame[i];rowAliases_[i]=aliases.emplace(key,i).first->second;}
   }
  }else for(unsigned i=0;i<rows_.size();i++)rowAliases_[i]=i;
  std::map<std::array<unsigned,7>,unsigned> normalKeys;unsigned rowIndex=0;
  for(const auto& row:rows_){
   std::array<unsigned,7> key{};std::memcpy(key.data(),row.donor.data(),12);std::memcpy(key.data()+3,row.weight.data(),12);key[6]=fullFrame[rowIndex++];
   auto found=normalKeys.emplace(key,unsigned(normalBindings_.size()));normalGroups_.push_back(found.first->second);
   if(found.second){NormalBinding b{row.donor,row.weight,{},{},key[6]!=0};for(unsigned k=0;k<3;k++)for(unsigned a=0;a<3;a++){b.reference[a]+=normals_[b.donor[k]][a]*b.weight[k];if(b.fullFrame)b.tangentReference[a]+=tangents_[b.donor[k]][a]*b.weight[k];}normalBindings_.push_back(b);}
   lighting_.push_back({DecodeDirection(row.baseline.normal),DecodeDirection(row.baseline.tangent)});
  }
  char extra;if(f.read(&extra,1))throw std::runtime_error("Trailing Geralt binding data");
 }
 void LoadCoverage(const std::filesystem::path& path){
  std::ifstream f(path,std::ios::binary);char magic[8]{};Read(f,magic,8);unsigned count=0;Read(f,&count);if(std::memcmp(magic,"MMV2C01\0",8)||resources_.empty()||count*2!=resources_[0].indexBytes)throw std::runtime_error("Canonical coverage bounds differ");
  auto data=std::make_shared<std::vector<std::uint16_t>>(count);Read(f,data->data(),count);char extra;if(f.read(&extra,1))throw std::runtime_error("Trailing coverage data");coveredIndices_=std::move(data);
 }
 Point ToSource(Point native)const{
  Point out=root_;for(unsigned a=0;a<3;a++)for(unsigned b=0;b<3;b++)out[a]+=rotation_[b*3+a]*(native[b]*100-target_[b]);return out;
 }
 const std::array<float,9>& Rotation()const{return rotation_;}
 const std::vector<Bone>& Bones()const{return bones_;}
 const std::vector<RenderResource>& Resources()const{return resources_;}
 Point ToNative(Point source)const{Point out{};for(unsigned a=0;a<3;a++){out[a]=target_[a];for(unsigned b=0;b<3;b++)out[a]+=rotation_[a*3+b]*(source[b]-root_[b]);out[a]*=.01f;}return out;}
 Matrix PelvisDelta(const Matrix& pose)const{for(const auto& b:bones_)if(b.id==9)return Multiply(pose,b.inverse);throw std::runtime_error("Missing pelvis binding");}
 malemod::motion::Tracker::Matrix MotionDelta(const Matrix& native)const{
  malemod::motion::Tracker::Matrix out{};const Point zero=ToSource(Transform(native,ToNative({0,0,0})));
  for(unsigned a=0;a<3;a++){out[a*4+3]=zero[a];for(unsigned b=0;b<3;b++){Point e{};e[b]=1;out[a*4+b]=ToSource(Transform(native,ToNative(e)))[a]-zero[a];}}return out;
 }
 std::shared_ptr<const RenderDelivery> Evaluate(const surface::canonical::Packet& packet,bool correctedLighting=true)const{
  if(cached_&&cached_->epoch==packet.epoch&&generation_==packet.surfaceServices&&correctedLighting_==correctedLighting){auto result=std::make_shared<RenderDelivery>(*cached_);result->sequence=result->presentationSerial=packet.completed;result->materialState=unsigned(packet.controls[0]);return result;}
  auto read=[&](unsigned i){if(i<17528)return packet.anatomy.data()+i*32;if(i<17528+15168)return packet.body0.data()+(i-17528)*32;return packet.body1.data()+(i-17528-15168)*32;};
  std::vector<Point> delta(source_.size()),normal(source_.size()),tangent(tangents_.size());for(unsigned i=0;i<delta.size();i++){Point p{};auto* raw=read(i);std::memcpy(p.data(),raw,12);for(unsigned a=0;a<3;a++){delta[i][a]=p[a]-source_[i][a];normal[i][a]=float(raw[16+a])/127.5f-1;if(!tangent.empty())tangent[i][a]=float(raw[12+a])/127.5f-1;if(!std::isfinite(delta[i][a]))throw std::runtime_error("Nonfinite canonical surface");}}
  std::vector<surface::normal_frame::Matrix> rotations(normalBindings_.size());std::vector<unsigned char> changed(normalBindings_.size());
  binding_parallel::FourPartitions(unsigned(normalBindings_.size()),[&](unsigned first,unsigned last){for(unsigned i=first;i<last;i++){
   const auto& b=normalBindings_[i];Point current{},currentTangent{};for(unsigned k=0;k<3;k++)for(unsigned a=0;a<3;a++){current[a]+=normal[b.donor[k]][a]*b.weight[k];if(b.fullFrame)currentTangent[a]+=tangent[b.donor[k]][a]*b.weight[k];}if(current==b.reference&&(!b.fullFrame||currentTangent==b.tangentReference))continue;
   changed[i]=true;const auto source=b.fullFrame?surface::normal_frame::FrameRotation(b.reference,b.tangentReference,current,currentTangent):surface::normal_frame::Rotation(b.reference,current);auto& target=rotations[i];
   surface::normal_frame::Matrix intermediate{};
   for(unsigned a=0;a<3;a++)for(unsigned b=0;b<3;b++)for(unsigned c=0;c<3;c++)intermediate[a*3+b]+=rotation_[a*3+c]*source[c*3+b];
   for(unsigned a=0;a<3;a++)for(unsigned b=0;b<3;b++)for(unsigned c=0;c<3;c++)target[a*3+b]+=intermediate[a*3+c]*rotation_[b*3+c];
  }});
  auto result=std::make_shared<RenderDelivery>();result->epoch=packet.epoch;result->materialState=unsigned(packet.controls[0]);result->sequence=packet.completed;result->presentationSerial=packet.completed;result->resources=resources_;result->coveredIndices=coveredIndices_;result->floatVertices.resize(rows_.size());
  for(const auto& r:resources_)binding_parallel::FourPartitions(r.vertexCount,[&](unsigned first,unsigned last){for(unsigned i=r.firstVertex+first;i<r.firstVertex+last;i++){
   if(rowAliases_[i]!=i)continue;
   const auto& binding=rows_[i];auto& out=result->floatVertices[i];out=binding.baseline;Point d{};
   for(unsigned k=0;k<3;k++)for(unsigned a=0;a<3;a++)d[a]+=delta[binding.donor[k]][a]*binding.weight[k];
   for(unsigned a=0;a<3;a++){float transformed=0;for(unsigned b=0;b<3;b++)transformed+=rotation_[a*3+b]*d[b];out.position[a]+=transformed*.01f/r.scale[a];}
   const auto group=normalGroups_[i];if(correctedLighting&&changed[group]){
    const auto& matrix=rotations[group];auto transfer=[&](unsigned word,Point p){Point q{};for(unsigned a=0;a<3;a++)for(unsigned b=0;b<3;b++)q[a]+=matrix[a*3+b]*p[b];q=surface::normal_frame::Unit(q);unsigned packed=word&0xc0000000u;for(unsigned a=0;a<3;a++)packed|=unsigned((std::max)(0.f,(std::min)(1.f,q[a]*.5f+.5f))*1023.f+.5f)<<(a*10);return packed;};
    out.normal=transfer(out.normal,lighting_[i].normal);out.tangent=transfer(out.tangent,lighting_[i].tangent);
   }
  }});
  // Every unique row is complete before any exact material-state alias copies.
  for(unsigned i=0;i<rows_.size();i++)if(rowAliases_[i]!=i)result->floatVertices[i]=result->floatVertices[rowAliases_[i]];
  cached_=result;generation_=packet.surfaceServices;correctedLighting_=correctedLighting;return result;
 }
};
}
