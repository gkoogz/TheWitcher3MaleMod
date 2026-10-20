#pragma once
#include "collar_corrective.hpp"
#include <malemod/surface/endpoint_constraints.hpp>
#include <malemod/surface/section_clearance.hpp>

namespace malemod::witcher {
// Private authoring format: all displacement knots share exact original-edge
// donors. A common affine scale preserves those constraints during playback.
// Unlike MMCORR03, no ownership mask is multiplied into the reviewed geometry.
struct SewnCollarPose {double angle,radius,length;std::vector<surface::corrective::Knot> knots;};
struct SewnCollarLod {
 std::uint32_t pointCount;std::vector<std::uint32_t> fixed,ids;
 std::vector<SewnCollarPose> poses;
};
struct SewnCollarArtifact {
 double radius,length;std::vector<SewnCollarLod> lods;
 static SewnCollarArtifact Load(const std::filesystem::path& path,const std::filesystem::path& binding,const std::string& revision){
  auto bytes=collar_detail::File(path);if(bytes.size()<100)throw std::invalid_argument("Short sewn corrective artifact");
  std::uint64_t expected;std::memcpy(&expected,bytes.data()+bytes.size()-8,8);
  if(collar_detail::FNV(bytes.data(),bytes.size()-8)!=expected)throw std::invalid_argument("Sewn corrective checksum differs");
  collar_detail::Reader r(bytes);char magic[8],base[40];r.Read(magic,8);auto version=r.Get<std::uint32_t>();auto hash=r.Get<std::uint64_t>();r.Read(base,40);
  const auto source=collar_detail::File(binding);
  if(std::memcmp(magic,"MMSEWN02",8)||version!=2||std::string(base,40)!=revision||hash!=collar_detail::FNV(source.data(),source.size()))throw std::invalid_argument("Sewn corrective binding differs");
  SewnCollarArtifact out;out.radius=r.Get<double>();out.length=r.Get<double>();
  if(!std::isfinite(out.radius+out.length)||out.radius<=0||out.length<=0||r.Get<std::uint32_t>()!=2)throw std::invalid_argument("Invalid sewn corrective dimensions");
  for(unsigned lod=0;lod<2;lod++){
   SewnCollarLod data;data.pointCount=r.Get<std::uint32_t>();data.fixed=r.List<std::uint32_t>();data.ids=r.List<std::uint32_t>();const auto count=r.Get<std::uint32_t>();
   if(!count||count>32)throw std::invalid_argument("Invalid sewn corrective pose count");
   double previous=0;
   for(unsigned pose=0;pose<count;pose++){
    SewnCollarPose p;p.angle=r.Get<double>();p.radius=r.Get<double>();p.length=r.Get<double>();auto knots=r.Get<std::uint32_t>();
    if(!std::isfinite(p.radius+p.length)||p.radius<=0||p.length<=0)throw std::invalid_argument("Invalid sewn pose dimensions");
    if(!std::isfinite(p.angle)||p.angle<=previous||p.angle>100||!knots||knots>128)throw std::invalid_argument("Invalid sewn corrective pose");previous=p.angle;
    for(unsigned k=0;k<knots;k++){surface::corrective::Knot knot;knot.weight=r.Get<double>();knot.localDisplacement=r.List<surface::corrective::Point>();p.knots.push_back(std::move(knot));}
    data.poses.push_back(std::move(p));
   }
   out.lods.push_back(std::move(data));
  }
  if(r.at!=r.limit)throw std::invalid_argument("Trailing sewn corrective data");return out;
 }
};
class SewnCollarCorrective {
 std::unique_ptr<surface::corrective::Plan> plan_;
 std::unique_ptr<surface::corrective::EndpointConstraints> constraints_;
 std::vector<surface::corrective::Point> finalField_;
 std::vector<unsigned> boundary_;
 SewnCollarLod data_;double radius_,length_,lastAngle_=-1;
 public:
 const std::vector<std::uint32_t>& FixedRows()const{return data_.fixed;}
 std::string ConstraintReport()const{return constraints_?constraints_->Report():"none";}
 SewnCollarCorrective(const SewnCollarArtifact& artifact,unsigned lod,const surface::GraftDomain& domain):data_(artifact.lods.at(lod)),radius_(artifact.radius),length_(artifact.length){
  using namespace surface::corrective;
  if(data_.pointCount!=domain.points.size())throw std::invalid_argument("Sewn corrective topology differs");
  auto fixed=data_.fixed;fixed.insert(fixed.end(),domain.protectedVertices.begin(),domain.protectedVertices.end());
  std::vector<int> lookup(domain.points.size(),-1);for(unsigned j=0;j<data_.ids.size();j++){auto id=data_.ids[j];if(id>=lookup.size()||lookup[id]>=0)throw std::invalid_argument("Invalid sewn corrective row");lookup[id]=int(j);}
  const auto& first=data_.poses.front().knots;
  for(const auto& pose:data_.poses){
   if(pose.knots.size()!=first.size())throw std::invalid_argument("Sewn path lengths differ");
   // Plan validates every pose, not merely the first pose selected for display.
   Plan validation(domain.points.size(),domain.triangles,fixed,data_.ids,pose.knots);
   for(unsigned k=0;k<pose.knots.size();k++){
    if(pose.knots[k].weight!=first[k].weight)throw std::invalid_argument("Sewn path fractions differ");
    auto delta=[&](unsigned i){return lookup[i]<0?Point{}:pose.knots[k].localDisplacement[lookup[i]];};
    for(auto e:domain.seams){auto error=Sub(delta(e.slave),Add(Scale(delta(e.a),1-e.weight),Scale(delta(e.b),e.weight)));if(Dot(error,error)>1e-14)throw std::invalid_argument("Sewn corrective changes original-edge donors");}
   }
  }
  plan_=std::make_unique<Plan>(domain.points.size(),domain.triangles,fixed,data_.ids,first);
  std::vector<EdgeDonor> donors;for(auto e:domain.seams)donors.push_back({e.slave,e.a,e.b,e.weight});
  for(auto e:domain.seams){boundary_.push_back(e.a);boundary_.push_back(e.b);}
  constraints_=std::make_unique<EndpointConstraints>(domain.points.size(),domain.triangles,data_.ids,donors,domain.points,domain.orientationTriangles);
 }
 surface::corrective::Result Apply(const std::vector<surface::PrecisePoint>& points,const surface::Output& source,double angle,double neutralRadius){
  using namespace surface::corrective;
  if(!std::isfinite(angle)||angle<1||angle>100)throw std::invalid_argument("Invalid sewn corrective angle");
  const double r=source.collarMetric.radius;
  if(r<=neutralRadius||radius_<=neutralRadius||angle>=data_.poses.back().angle)return {points,0};
  if(lastAngle_!=angle){
   unsigned hi=0;while(hi+1<data_.poses.size()&&data_.poses[hi].angle<angle)++hi;
   const unsigned lo=hi?hi-1:0;const double span=data_.poses[hi].angle-data_.poses[lo].angle;
   const double t=span>0?std::clamp((angle-data_.poses[lo].angle)/span,0.,1.):0.;
   auto knots=data_.poses[lo].knots;
   for(unsigned k=0;k<knots.size();k++)for(unsigned i=0;i<data_.ids.size();i++)knots[k].localDisplacement[i]=Add(Scale(knots[k].localDisplacement[i],1-t),Scale(data_.poses[hi].knots[k].localDisplacement[i],t));
   finalField_=knots.back().localDisplacement;
   plan_->UpdateKnots(std::move(knots));lastAngle_=angle;
   radius_=(1-t)*data_.poses[lo].radius+t*data_.poses[hi].radius;
   length_=(1-t)*data_.poses[lo].length+t*data_.poses[hi].length;
  }
  auto field=finalField_;const Point scale{source.restLength/length_,r/radius_,r/radius_};
  for(auto& p:field)for(unsigned a=0;a<3;a++)p[a]*=scale[a];
  auto guide=[&](unsigned i){auto p=source.shaftGuide[i];return Point{p.x,p.y,p.z};};
  double boundaryX=-std::numeric_limits<double>::infinity();for(auto i:boundary_)boundaryX=std::max(boundaryX,points[i][0]);
  const double measured=UpperClearanceResponse(points,data_.ids,field,Scale(Add(guide(6),guide(7)),.5),Sub(guide(7),guide(5)),r,boundaryX)
   *Smooth((r-neutralRadius)/(.01*neutralRadius));
  const double gain=std::max(Smooth((r-neutralRadius)/(radius_-neutralRadius)),measured);
  // SurfacePipeline uploads this completed frame directly. Validate the real
  // size/angle output; it does not animate from the broken baseline through
  // every activation knot on each frame. Actual control/motion transitions
  // require their separate native frame regression.
  return plan_->EvaluateEndpoint(points,Frame::FromAxis({1,0,0}),scale,gain,
   [&](const auto& original,auto& target){return constraints_->Project(original,target);});
 }
};
}
