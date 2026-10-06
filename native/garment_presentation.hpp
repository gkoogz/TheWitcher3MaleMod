#pragma once
#include "render_service.hpp"
#include <malemod/garments/jockstrap.hpp>
#include <map>

namespace malemod::witcher {
// Presentation only: retain the solved cloth offset in its actual weighted
// donor frame. Numerical cloth/contact work and source support stay ordered.
class GarmentPresentation {
 using Point=garments::Point;
 static constexpr unsigned donorCapacity=unsigned(std::tuple_size<decltype(garments::Lineage{}.donors)>::value);
 struct Donor {unsigned sample=0;double weight=0;};
 struct Influence {unsigned bone=0;double weight=0;};
 struct Vertex {std::array<Donor,donorCapacity> donors{};unsigned count=0;std::array<Influence,donorCapacity*4> skin{};unsigned skinCount=0;garments::Lineage lineage;Point offset{},normal{},tangent{};};
 std::shared_ptr<const RenderDelivery> source_;
 std::vector<unsigned> donors_;
 std::vector<Vertex> vertices_;
 static Point Direction(const PoseMatrix& m,Point p){Point out{};for(unsigned a=0;a<3;a++)for(unsigned b=0;b<3;b++)out[a]+=m[a*4+b]*p[b];return out;}
 static Point TransposeDirection(const PoseMatrix& m,Point p){Point out{};for(unsigned a=0;a<3;a++)for(unsigned b=0;b<3;b++)out[a]+=m[b*4+a]*p[b];return out;}
 static std::vector<PoseMatrix> Palette(const RenderPose& pose){std::vector<PoseMatrix> out;out.reserve(pose.skinDeltas.size());for(const auto& skin:pose.skinDeltas)out.push_back(MultiplyPose(pose.actorWorld,skin));return out;}
 static PoseMatrix Map(const Vertex& v,const std::vector<PoseMatrix>& palette){PoseMatrix m{};m[15]=1;for(unsigned k=0;k<v.skinCount;k++){auto influence=v.skin[k];if(influence.bone>=palette.size())throw std::invalid_argument("Garment donor palette changed");for(unsigned a=0;a<12;a++)m[a]+=palette[influence.bone][a]*influence.weight;}return m;}
 static Point Position(const SourceRenderVertex& v,const std::vector<PoseMatrix>& palette){Point out{};std::array<std::uint8_t,4> bones{},weights{};std::memcpy(bones.data(),&v.bones,4);std::memcpy(weights.data(),&v.weights,4);double sum=0;for(auto w:weights)sum+=w;if(!sum)throw std::invalid_argument("Garment donor weights empty");for(unsigned k=0;k<4;k++)if(weights[k]){if(bones[k]>=palette.size())throw std::invalid_argument("Garment donor bone missing");auto point=TransformPosePoint(palette[bones[k]],{v.position[0],v.position[1],v.position[2]});for(unsigned a=0;a<3;a++)out[a]+=point[a]*weights[k]/sum;}return out;}
 static Point Anchor(const Vertex& v,const std::vector<Point>& points){Point out{};for(unsigned k=0;k<v.count;k++)for(unsigned a=0;a<3;a++)out[a]+=points[v.donors[k].sample][a]*v.donors[k].weight;return out;}
 public:
 GarmentPresentation(const garments::Output& cloth,std::shared_ptr<const RenderDelivery> source,std::shared_ptr<const GarmentPresentation> previous={}):source_(std::move(source)){
  if(cloth.style==garments::Style::Naked)return;
  if(!source_||!source_->vertices||cloth.characterEpoch!=source_->epoch||cloth.mesh.vertices.size()>16384)throw std::invalid_argument("Garment presentation source incomplete");
  bool reuse=previous&&previous->source_&&previous->source_->epoch==source_->epoch&&previous->vertices_.size()==cloth.mesh.vertices.size()&&previous->source_->vertices->size()==source_->vertices->size();
  if(reuse)for(unsigned i=0;i<cloth.mesh.vertices.size()&&reuse;i++)for(unsigned k=0;k<donorCapacity;k++){const auto a=cloth.mesh.vertices[i].lineage.donors[k],b=previous->vertices_[i].lineage.donors[k];if(a.surface!=b.surface||a.vertex!=b.vertex||a.weight!=b.weight){reuse=false;break;}}
  if(reuse)for(auto id:previous->donors_){const auto& a=source_->vertices->at(id);const auto& b=previous->source_->vertices->at(id);if(a.bones!=b.bones||a.weights!=b.weights){reuse=false;break;}}
  if(reuse){donors_=previous->donors_;vertices_=previous->vertices_;}
  else {
  std::map<unsigned,unsigned> sampleIds;vertices_.reserve(cloth.mesh.vertices.size());
  for(const auto& clothVertex:cloth.mesh.vertices){Vertex vertex;vertex.lineage=clothVertex.lineage;double sum=0;for(auto d:clothVertex.lineage.donors){if(!std::isfinite(d.weight)||d.weight<0)throw std::invalid_argument("Garment donor weight invalid");sum+=d.weight;}if(sum<=0)throw std::invalid_argument("Garment lineage empty");std::map<unsigned,double> skinWeights;
   for(auto donor:clothVertex.lineage.donors)if(donor.weight){if(donor.vertex>=source_->vertices->size())throw std::invalid_argument("Garment lineage outside surface");auto inserted=sampleIds.emplace(donor.vertex,unsigned(donors_.size()));if(inserted.second)donors_.push_back(donor.vertex);const double weight=donor.weight/sum;vertex.donors[vertex.count++]={inserted.first->second,weight};const auto& v=source_->vertices->at(donor.vertex);std::array<std::uint8_t,4> bones{},weights{};std::memcpy(bones.data(),&v.bones,4);std::memcpy(weights.data(),&v.weights,4);double total=0;for(auto w:weights)total+=w;if(!total)throw std::invalid_argument("Garment source skin empty");for(unsigned k=0;k<4;k++)if(weights[k])skinWeights[bones[k]]+=weight*weights[k]/total;}
   for(auto influence:skinWeights){if(vertex.skinCount==vertex.skin.size())throw std::invalid_argument("Garment donor influence budget exceeded");vertex.skin[vertex.skinCount++]={influence.first,influence.second};}vertices_.push_back(std::move(vertex));
  }
  }
  auto palette=Palette(source_->pose);std::vector<Point> points;points.reserve(donors_.size());for(auto id:donors_)points.push_back(Position(source_->vertices->at(id),palette));
  for(unsigned i=0;i<vertices_.size();i++){auto& v=vertices_[i];const auto& original=cloth.mesh.vertices[i];auto map=Map(v,palette),inverse=InversePose(map);v.offset=Direction(inverse,garments::Sub(original.position,Anchor(v,points)));v.normal=TransposeDirection(map,original.normal);v.tangent=Direction(inverse,original.tangent);}
 }
 garments::Output Present(const garments::Output& cloth,const RenderDelivery& geometry,const RenderPose& pose)const{
  if(cloth.style==garments::Style::Naked)return cloth;
  if(!source_||pose.epoch!=source_->epoch||geometry.epoch!=pose.epoch||!geometry.vertices||geometry.vertices->size()!=source_->vertices->size()||cloth.mesh.vertices.size()!=vertices_.size()||pose.skinDeltas.size()!=source_->pose.skinDeltas.size())throw std::invalid_argument("Stale garment presentation epoch/topology");
  auto palette=Palette(pose);std::vector<Point> points;points.reserve(donors_.size());for(auto id:donors_){const auto& v=geometry.vertices->at(id);const auto& old=source_->vertices->at(id);if(v.bones!=old.bones||v.weights!=old.weights)throw std::invalid_argument("Garment donor skin changed");points.push_back(Position(v,palette));}
  auto out=cloth;
  for(unsigned i=0;i<vertices_.size();i++){const auto& source=vertices_[i];auto map=Map(source,palette);auto& vertex=out.mesh.vertices[i];vertex.position=garments::Add(Anchor(source,points),Direction(map,source.offset));vertex.normal=garments::Unit(TransposeDirection(InversePose(map),source.normal));auto tangent=Direction(map,source.tangent);vertex.tangent=garments::Unit(garments::Sub(tangent,garments::Mul(vertex.normal,garments::Dot(tangent,vertex.normal))));if(!garments::Finite(vertex.position))throw std::invalid_argument("Nonfinite garment presentation");}
  return out;
 }
};
}
