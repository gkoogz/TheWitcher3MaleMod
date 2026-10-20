#include "target_surface.hpp"
#include <fstream>
#include <cstring>
#include <algorithm>
#include <limits>
#ifdef MALEMOD_FIXED_COLLAR_ANGLE
#include "fixed_collar_angle.hpp"
#include "pelvic_recruitment_data.hpp"
#include <malemod/surface/wire.hpp>
#endif
#include <malemod/surface/root_transition.hpp>
#ifdef MALEMOD_DILATING_COLLAR
#include <malemod/surface/dilating_collar.hpp>
#include <malemod/surface/collar_radial_support.hpp>
#endif
#ifdef MALEMOD_STOCK_ANCHOR_PREVIEW
#include "stock_attachment_anchor.hpp"
#endif
#ifdef MALEMOD_PROGRESSIVE_RECRUITMENT
#include "pelvic_recruitment_data.hpp"
#include <malemod/surface/recruitment_constraints.hpp>
#endif
#ifdef MALEMOD_ATTACHMENT_CORRECTIVE
#include "collar_corrective.hpp"
#include "sewn_collar_corrective.hpp"
#endif
#ifdef MALEMOD_ANGLE_CONDITIONED_COLLAR
#include <malemod/surface/angle_conditioned_collar.hpp>
#endif

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
bool Same(const GraftFrame& a,const GraftFrame& b){return a.root==b.root&&a.axis==b.axis&&a.up==b.up&&a.radius==b.radius&&a.length==b.length&&a.sourceLengthScale==b.sourceLengthScale&&a.seamSupportRadius==b.seamSupportRadius;}
struct Lod {
 GraftDomain domain;
 std::vector<PrecisePoint> restSource,restNative;
 std::vector<std::uint32_t> aliases,unique,protectedRender;
 std::vector<std::uint32_t> waistMasters;
 std::uint32_t bodyCount;
#ifdef MALEMOD_STOCK_ANCHOR_PREVIEW
 std::vector<double> dorsalRelease;
#endif
#ifdef MALEMOD_ATTACHMENT_CORRECTIVE
 std::unique_ptr<CollarCorrective> corrective;
 std::unique_ptr<SewnCollarCorrective> sewnCorrective;
#endif
 double correctiveWeight=0;
#ifdef MALEMOD_FIXED_COLLAR_ANGLE
 FixedAngleRegion fixedAngleRegion;
 double fixedAngleGain=1;bool fixedAngleFailureCaptured=false;
 std::vector<bool> fixedAngleRows;
 std::vector<bool> fixedAngleMoving;
 std::vector<unsigned> fixedAngleCore,fixedAngleEditable;
 std::unique_ptr<surface::corrective::EndpointConstraints> fixedAngleConstraints;
 std::unique_ptr<surface::root_articulation::Junction> fixedAngleJunction;
#ifdef MALEMOD_DILATING_COLLAR
 std::vector<PrecisePoint> fixedAngleCorrection;
#endif
#endif
 DeltaBinding body,module;
 GraftFrame cachedFrame{};std::unique_ptr<GraftPlan> plan,bodyPlan;
 GraftDomain bodyDomain;
#ifdef MALEMOD_ANGLE_CONDITIONED_COLLAR
 GraftDomain angleDomain;GraftFrame angleFrame{};
 std::unique_ptr<GraftPlan> anglePlan;
 std::unique_ptr<angle_collar::RestWeights> angleRestWeights;
 std::vector<double> dorsalWeights;
#endif
 // Projection depends on this immutable LOD domain and its complete input.
 // Reuse only an exactly equal field; motion and shape inputs remain unrounded.
 std::vector<PrecisePoint> projectedBodyInput,projectedBodyOutput;
 std::unique_ptr<RootTransition> transition;
#ifdef MALEMOD_DILATING_COLLAR
 std::unique_ptr<DilatingCollar> dilatingCollar;
 std::unique_ptr<CollarRadialSupport> collarRadialSupport;
#endif
#ifdef MALEMOD_PROGRESSIVE_RECRUITMENT
 std::unique_ptr<PelvicRecruitment> recruitment;
 std::vector<double> recruitmentParticipation;
 std::vector<double> recruitmentAngles,recruitmentStations;
 GraftDomain recruitmentDomain;
 std::unique_ptr<GraftPlan> recruitmentPlan;
 std::unique_ptr<GraftPlan> recruitmentBodyPlan;
 std::vector<std::uint32_t> recruitmentFixed;
 std::unique_ptr<RecruitmentConstraints> recruitmentConstraints;
#endif
};
}
struct TargetSurface::Impl {
 CoordinateCalibration calibration;
 std::vector<PrecisePoint> neutralAnatomy,neutralBody;
 std::vector<Lod> lods;
 std::vector<PrecisePoint> neutralCollar;
 double neutralRadius=0,neutralLength=0;
 std::filesystem::path diagnosticDirectory;
 std::string correctiveError;
 Impl(const std::filesystem::path& path,const std::string& expected){
  diagnosticDirectory=path.parent_path();
  Reader r(path);char magic[8],commit[40];r.Bytes(magic,8);r.Bytes(commit,40);
  const bool boundary=!std::memcmp(magic,"MMBIND03",8);
  if((!boundary&&std::memcmp(magic,"MMBIND02",8))||expected.size()!=40||std::string(commit,40)!=expected)throw std::invalid_argument("Character binding revision differs from pinned Base");
  calibration.basis=r.Value<std::array<PrecisePoint,3>>();calibration.sourceRoot=r.Value<PrecisePoint>();calibration.targetRoot=r.Value<PrecisePoint>();calibration.targetUnitsPerSourceUnit=r.Value<double>();calibration.Validate();
  neutralAnatomy=r.List<PrecisePoint>();neutralBody=r.List<PrecisePoint>();
  unsigned count=r.Value<std::uint32_t>();if(count!=2)throw std::invalid_argument("Expected both observed Geralt LODs");lods.resize(count);
  for(auto& l:lods){
   l.domain.points=r.List<PrecisePoint>();l.domain.triangles=r.List<std::array<std::uint32_t,3>>();
   unsigned seams=r.Value<std::uint32_t>();if(seams>l.domain.points.size())throw std::invalid_argument("Invalid character seam count");
   for(unsigned i=0;i<seams;i++){EdgeConstraint e;e.slave=r.Value<std::uint32_t>();e.a=r.Value<std::uint32_t>();e.b=r.Value<std::uint32_t>();e.weight=r.Value<double>();l.domain.seams.push_back(e);}
   l.domain.protectedVertices=r.List<std::uint32_t>();if(boundary)l.domain.prescribedVertices=r.List<std::uint32_t>();l.restSource=r.List<PrecisePoint>();l.restNative=r.List<PrecisePoint>();
   l.aliases=r.List<std::uint32_t>();l.unique=r.List<std::uint32_t>();l.protectedRender=r.List<std::uint32_t>();l.bodyCount=r.Value<std::uint32_t>();l.body=r.Binding();l.module=r.Binding();
   const auto n=l.restSource.size();
   if(!n||l.restNative.size()!=n||l.aliases.size()!=n||l.unique.size()!=l.domain.points.size()||l.bodyCount>=n||l.body.offsets.size()!=l.bodyCount+1||l.module.offsets.size()!=n-l.bodyCount+1||l.body.sourceVertexCount!=neutralBody.size()||l.module.sourceVertexCount!=neutralAnatomy.size())throw std::invalid_argument("Character binding dimensions differ");
   for(auto id:l.aliases)if(id>=l.domain.points.size())throw std::invalid_argument("Character alias outside unique domain");
   for(auto id:l.unique)if(id>=n)throw std::invalid_argument("Character master outside rendered domain");
   for(auto id:l.protectedRender)if(id>=l.bodyCount)throw std::invalid_argument("Protected character boundary outside body");
   for(const auto* list:{&l.restSource,&l.restNative,&l.domain.points})for(auto p:*list)for(double x:p)if(!std::isfinite(x))throw std::invalid_argument("Non-finite character rest binding");
   // Geralt's measured body is driven by the common radial field, not by
   // independently moving shaft rows. Keep its independent masters prescribed
   // so harmonic graft fitting cannot drag the pelvic tissue into a fold.
   l.waistMasters=l.domain.prescribedVertices;
   l.bodyDomain=l.domain;
   for(unsigned i=0;i<l.bodyDomain.triangles.size();i++){
    const auto f=l.bodyDomain.triangles[i];
    // Guard the complete recruited annulus, including thin native waist
    // subdivision faces. Moving anatomy is deliberately outside this guard.
    if(l.unique[f[0]]<l.bodyCount&&l.unique[f[1]]<l.bodyCount&&l.unique[f[2]]<l.bodyCount)
     l.bodyDomain.orientationTriangles.push_back(i);
   }
   std::vector<bool> prescribed(l.domain.points.size(),false);for(auto id:l.domain.prescribedVertices)prescribed[id]=true;
   for(auto id:l.domain.protectedVertices)prescribed[id]=true;
   std::vector<bool> slave(l.domain.points.size(),false);for(auto e:l.domain.seams)slave[e.slave]=true;
   std::vector<PrecisePoint> opening;for(auto e:l.domain.seams)opening.push_back(l.domain.points[e.slave]);
   for(unsigned id=0;id<l.unique.size();id++)if(l.unique[id]<l.bodyCount&&!prescribed[id]&&!slave[id]){
    double distance=1e100;for(auto p:opening){double squared=0;for(unsigned a=0;a<3;a++)squared+=(p[a]-l.domain.points[id][a])*(p[a]-l.domain.points[id][a]);distance=std::min(distance,std::sqrt(squared));}
#ifdef MALEMOD_DILATING_COLLAR
    l.domain.prescribedVertices.push_back(id);
#else
    if(distance>=4)l.domain.prescribedVertices.push_back(id);
#endif
   }
#ifdef MALEMOD_DILATING_COLLAR
   l.bodyDomain.orientationIterations=2048;
   l.domain.orientationAreaTargetRatio=.001; // Validate the already projected body without a second moving solve.
   // The opening is a dimensional constraint, not a soft fairing target.
   // Preserve original edge donors by prescribing only independent masters.
   auto pin=[&](GraftDomain& d,unsigned i){if(slave[i])return;
    if(std::find(d.protectedVertices.begin(),d.protectedVertices.end(),i)!=d.protectedVertices.end())return;
    if(std::find(d.prescribedVertices.begin(),d.prescribedVertices.end(),i)==d.prescribedVertices.end())d.prescribedVertices.push_back(i);
   };
   for(auto e:l.domain.seams)for(auto i:{e.a,e.b}){pin(l.domain,i);pin(l.bodyDomain,i);}
#endif
   // Preserve the measured transition's differential shape on the anatomy
   // side as well. Fairing its displacement toward zero against a fixed body
   // seam concentrates the change in the first shaft rows and creates a lip.
   l.domain.preserveTargetDifferential=true;
   l.domain.surfaceFairingDistance=7;
   l.domain.surfaceFairingStrength=64;
#ifdef MALEMOD_DILATING_COLLAR
   l.domain.surfaceFairingDistance=7;l.domain.surfaceFairingStrength=8;
#endif
#ifdef MALEMOD_STOCK_ANCHOR_PREVIEW
   std::vector<PrecisePoint> normals(l.unique.size());
   for(auto f:l.domain.triangles){
    PrecisePoint a{},b{},n{};
    for(unsigned k=0;k<3;k++){a[k]=l.domain.points[f[1]][k]-l.domain.points[f[0]][k];b[k]=l.domain.points[f[2]][k]-l.domain.points[f[0]][k];}
    n={a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]};
    for(auto i:f)for(unsigned k=0;k<3;k++)normals[i][k]+=n[k];
   }
   l.dorsalRelease.resize(l.restSource.size(),0);
   for(unsigned i=0;i<l.restSource.size();i++)if(i>=l.bodyCount){auto n=normals[l.aliases[i]];double r=std::hypot(n[1],n[2]);double t=std::clamp(((r>1e-10?n[2]/r:0)+.3)/.8,0.,1.);l.dorsalRelease[i]=t*t*t*(10+t*(-15+6*t));}
#endif
   l.domain.orientationTriangles=l.bodyDomain.orientationTriangles;
#ifdef MALEMOD_DILATING_COLLAR
   // Body is prescribed from the separately checked continuation below.
   l.domain.orientationTriangles.clear();
#endif
#ifdef MALEMOD_ANGLE_CONDITIONED_COLLAR
   l.angleDomain=l.domain;
   double dorsalZ=0;for(auto p:opening)dorsalZ+=p[2]/opening.size();
   std::vector<bool> pinned(l.domain.points.size(),false);
   for(auto i:l.angleDomain.prescribedVertices)pinned[i]=true;
   for(auto i:l.angleDomain.protectedVertices)pinned[i]=true;
   for(auto e:l.domain.seams)for(auto i:{e.a,e.b})if(!pinned[i]&&l.domain.points[i][2]>=dorsalZ){l.angleDomain.prescribedVertices.push_back(i);pinned[i]=true;}
#endif
   l.transition=std::make_unique<RootTransition>(l.restSource,l.bodyCount,opening);
  }
  if(r.remaining)throw std::invalid_argument("Trailing character binding data");
#ifdef MALEMOD_FIXED_COLLAR_ANGLE
  const auto angleMaterial=PelvicRecruitmentData::Load(path.parent_path()/"geralt.recruitment",path,expected);
  if(angleMaterial.lobeRoles.size()!=lods.size())throw std::invalid_argument("Root articulation requires MMPREC03 source material ownership");
  for(unsigned j=0;j<lods.size();j++){
   auto& l=lods[j];const auto& weights=angleMaterial.participation[j];
   if(weights.size()!=l.restNative.size())throw std::invalid_argument("Angle material topology differs");
   l.fixedAngleRows.resize(l.unique.size());l.fixedAngleMoving.resize(l.unique.size());
   for(unsigned i=0;i<l.unique.size();i++){
    const double role=angleMaterial.lobeRoles[j][l.unique[i]],station=angleMaterial.stations[j][l.unique[i]];
    const bool body=l.unique[i]<l.bodyCount,core=!body&&role>=.9;
    l.fixedAngleRows[i]=body||core;if(core)l.fixedAngleCore.push_back(i);
    l.fixedAngleMoving[i]=!body&&!core&&((role<.2&&station>=.15)||station>=.3);
   }
   for(auto i:l.domain.protectedVertices)l.fixedAngleRows[i]=true;
   for(auto e:l.domain.seams)for(auto i:{e.slave,e.a,e.b})l.fixedAngleRows[i]=true;
   for(unsigned i=0;i<l.unique.size();i++)if(l.fixedAngleRows[i])l.fixedAngleMoving[i]=false;
   if(l.fixedAngleCore.empty())throw std::invalid_argument("Missing protected lobe core");
#ifdef MALEMOD_DILATING_COLLAR
   std::vector<bool> body(l.unique.size());std::vector<double> stations(l.unique.size()),angles(l.unique.size()),roles(l.unique.size());std::vector<unsigned> seam;
   for(unsigned i=0;i<l.unique.size();i++){body[i]=l.unique[i]<l.bodyCount;stations[i]=angleMaterial.stations[j][l.unique[i]];angles[i]=angleMaterial.angles[j][l.unique[i]];roles[i]=angleMaterial.lobeRoles[j][l.unique[i]];}
   for(auto e:l.domain.seams)for(auto i:{e.slave,e.a,e.b})seam.push_back(i);
   l.collarRadialSupport=std::make_unique<CollarRadialSupport>(body,stations,angles,roles,seam);
#endif
  }
#endif
#ifdef MALEMOD_PROGRESSIVE_RECRUITMENT
  const auto recruitmentData=PelvicRecruitmentData::Load(path.parent_path()/"geralt.recruitment",path,expected);
  for(unsigned i=0;i<lods.size();i++){
   auto& l=lods[i];l.recruitmentParticipation=recruitmentData.participation[i];
   l.recruitmentAngles=recruitmentData.angles[i];l.recruitmentStations=recruitmentData.stations[i];
   if(l.recruitmentParticipation.size()!=l.restSource.size())throw std::invalid_argument("Pelvic material topology differs");
   l.recruitmentDomain=l.domain;
   // The expanded ramp can legitimately turn more than ninety degrees from
   // a tiny original cutout face. Its intrinsic area and neighbour checks
   // replace the old fixed rest-plane test on this opt-in path.
   l.recruitmentDomain.orientationTriangles.clear();
   std::vector<bool> locked(l.unique.size(),false);for(auto v:l.domain.protectedVertices)locked[v]=true;for(auto v:l.domain.prescribedVertices)locked[v]=true;for(auto e:l.domain.seams)locked[e.slave]=true;
   for(unsigned v=0;v<l.unique.size();v++)if(l.unique[v]>=l.bodyCount&&l.recruitmentParticipation[l.unique[v]]==0){l.recruitmentFixed.push_back(v);if(!locked[v]){l.recruitmentDomain.prescribedVertices.push_back(v);locked[v]=true;}}
   auto integrity=l.bodyDomain;
   integrity.orientationTriangles.clear();
   integrity.prescribedVertices.insert(integrity.prescribedVertices.end(),l.recruitmentFixed.begin(),l.recruitmentFixed.end());
   l.recruitmentBodyPlan=std::make_unique<GraftPlan>(integrity);
   l.recruitmentConstraints=std::make_unique<RecruitmentConstraints>(integrity);
  }
#endif
#ifdef MALEMOD_ATTACHMENT_CORRECTIVE
  // Optional data must not make the established full solver fail at startup.
  const auto correctivePath=path.parent_path()/"geralt.corrective";
  if(std::filesystem::exists(correctivePath))try{
   auto artifact=CollarCorrectiveArtifact::Load(correctivePath,path,expected);
   for(unsigned i=0;i<lods.size();i++)lods[i].corrective=std::make_unique<CollarCorrective>(artifact,i,lods[i].domain,lods[i].unique,lods[i].bodyCount);
  }catch(const std::exception& e){correctiveError=e.what();for(auto& l:lods)l.corrective.reset();}
  const auto sewnPath=path.parent_path()/"geralt.sewn-corrective";
  if(std::filesystem::exists(sewnPath))try{
   auto artifact=SewnCollarArtifact::Load(sewnPath,path,expected);
   for(unsigned i=0;i<lods.size();i++){lods[i].sewnCorrective=std::make_unique<SewnCollarCorrective>(artifact,i,lods[i].domain);lods[i].corrective.reset();}
  }catch(const std::exception& e){correctiveError=e.what();for(auto& l:lods)l.sewnCorrective.reset();}
#endif
  // One measured opening drives every LOD. Native LOD decimation must not
  // introduce a different recruitment frame at the shared waist.
  std::vector<PrecisePoint> opening;for(auto e:lods[0].domain.seams)opening.push_back(lods[0].domain.points[e.slave]);
  for(auto& l:lods){
#ifdef MALEMOD_DILATING_COLLAR
   std::vector<unsigned> mouth;for(auto e:l.domain.seams)for(auto i:{e.slave,e.a,e.b})mouth.push_back(l.unique[i]);
   l.dilatingCollar=std::make_unique<DilatingCollar>(l.restSource,opening,mouth);
#endif
#ifdef MALEMOD_STOCK_ANCHOR_PREVIEW
   l.transition=std::make_unique<RootTransition>(l.restSource,l.bodyCount,opening);
#else
   l.transition=std::make_unique<RootTransition>(l.restSource,l.bodyCount,opening);
#endif
#ifdef MALEMOD_PROGRESSIVE_RECRUITMENT
   l.recruitment=std::make_unique<PelvicRecruitment>(l.restSource,opening);
#endif
#ifdef MALEMOD_ANGLE_CONDITIONED_COLLAR
   l.angleRestWeights=std::make_unique<angle_collar::RestWeights>(l.domain.points,opening);
   for(auto p:l.domain.points)l.dorsalWeights.push_back(angle_collar::DorsalWeight(p,l.transition->Root(),{0,1,0},{0,0,1}));
#endif
  }
 }
 std::vector<PrecisePoint> Evaluate(unsigned id,const Output& source,float angleControl,double angleGainCap){
#ifdef MALEMOD_FIXED_COLLAR_ANGLE
 #ifdef MALEMOD_DILATING_COLLAR
  const float requestedAngle=std::clamp(angleControl,10.f,90.f);
 #else
  const float requestedAngle=angleControl;
 #endif
  angleControl=FixedCollarReferenceAngle;
#endif
  if(id>=lods.size())throw std::out_of_range("Unknown character LOD");auto& l=lods[id];
  auto anatomy=Points(source.anatomy);
  const auto& metric=source.collarMetric;
  if(!metric.generation)throw std::invalid_argument("Source collar support metric is unavailable");
  GraftFrame frame;frame.root={metric.root.x,metric.root.y,metric.root.z};frame.axis=Normalize({metric.axis.x,metric.axis.y,metric.axis.z});
  frame.up=Normalize({metric.up.x,metric.up.y,metric.up.z});frame.radius=metric.radius;frame.length=metric.length;
#ifdef MALEMOD_PROGRESSIVE_RECRUITMENT
  auto recruitmentFrame=frame;
  // The source collar metric deliberately retains its cached neutral support
  // axis. It is NOT the live root pose. Transport this growing attachment
  // using the observed mechanical guide from the very same source frame.
  recruitmentFrame.root={source.shaftGuide[0].x,source.shaftGuide[0].y,source.shaftGuide[0].z};
  recruitmentFrame.axis=Normalize({source.shaftGuide[2].x-source.shaftGuide[0].x,source.shaftGuide[2].y-source.shaftGuide[0].y,source.shaftGuide[2].z-source.shaftGuide[0].z});
  const auto side=Normalize({-recruitmentFrame.axis[1],recruitmentFrame.axis[0],0});
  recruitmentFrame.up={recruitmentFrame.axis[1]*side[2]-recruitmentFrame.axis[2]*side[1],recruitmentFrame.axis[2]*side[0]-recruitmentFrame.axis[0]*side[2],recruitmentFrame.axis[0]*side[1]-recruitmentFrame.axis[1]*side[0]};
  const double recruitmentGrowth=PelvicRecruitment::Growth(frame.radius,neutralRadius);
#endif
  frame.root=l.transition->Root();frame.seamSupportRadius=frame.radius*1.5;
#ifdef MALEMOD_DILATING_COLLAR
  auto ease=[](double x){x=std::clamp(x,0.,1.);return x*x*x*(10+x*(-15+6*x));};
  const double collarTravel=ease((source.restLength/std::max(neutralLength,1e-9)-.4)/.4);
  const double gain=requestedAngle<50?.25+.75*collarTravel:.5+.5*collarTravel;
  const double down=20+10*ease((source.collarMetric.radius/neutralRadius-1.25)/.5);
  const double collarAngle=(50-requestedAngle)/(requestedAngle<50?49.:50.)*(requestedAngle<50?55.:down)*3.141592653589793/180.*gain*angleGainCap;
  const auto bodyDisplacement=[&](unsigned i){auto p=source.shaftGuide[0];return l.dilatingCollar->Displacement(i,{p.x,p.y,p.z},source.proximalRadius,neutralRadius,collarAngle);};
#elif defined(MALEMOD_STOCK_ANCHOR_PREVIEW)
  const auto bodyDisplacement=[&](unsigned i){return l.transition->BodyDisplacement(i,frame,neutralRadius);};
#else
  const auto bodyDisplacement=[&](unsigned i){return l.transition->BodyDisplacement(i,frame,neutralRadius);};
#endif
  if(neutralRadius<=0)throw std::invalid_argument("Neutral measured collar radius is unavailable");
  if(!l.plan){l.plan=std::make_unique<GraftPlan>(l.domain,frame);
#ifdef MALEMOD_PROGRESSIVE_RECRUITMENT
   auto solveDomain=l.recruitmentDomain;
   solveDomain.surfaceFairingStrength*=1-recruitmentGrowth;
   l.recruitmentPlan=std::make_unique<GraftPlan>(solveDomain,frame);
#endif
 #ifdef MALEMOD_DILATING_COLLAR
   l.bodyDomain.preserveTargetDifferential=true;
   l.bodyDomain.surfaceFairingDistance=7;l.bodyDomain.surfaceFairingStrength=8;
   auto proposalDomain=l.bodyDomain;proposalDomain.orientationTriangles.clear();
   l.bodyPlan=std::make_unique<GraftPlan>(proposalDomain,frame);
#else
   l.bodyPlan=std::make_unique<GraftPlan>(l.bodyDomain);
#endif
   l.cachedFrame=frame;}
  else if(!Same(frame,l.cachedFrame)){
   // Rebuild from immutable bindings when the support metric changes. Reusing
   // the mutable sparse ordering across native slider transitions faulted in
   // Eigen's symmetric permutation path. Prepare before replacing the active
   // plan; fixed-control animation retains its already prepared factorization.
   auto next=std::make_unique<GraftPlan>(l.domain,frame);
#ifdef MALEMOD_PROGRESSIVE_RECRUITMENT
   auto solveDomain=l.recruitmentDomain;
   // Absolute positional fairing contracts a growing collar. Retain its
   // established neutral response, release it progressively with dilation.
   solveDomain.surfaceFairingStrength*=1-recruitmentGrowth;
   auto nextRecruitment=std::make_unique<GraftPlan>(solveDomain,frame);l.recruitmentPlan.swap(nextRecruitment);
#endif
 #ifdef MALEMOD_DILATING_COLLAR
   auto proposalDomain=l.bodyDomain;proposalDomain.orientationTriangles.clear();
   auto nextBody=std::make_unique<GraftPlan>(proposalDomain,frame);l.bodyPlan.swap(nextBody);
   l.projectedBodyInput.clear();l.projectedBodyOutput.clear();
#endif
   l.plan.swap(next);l.cachedFrame=frame;
  }
  auto moduleDelta=l.module.Apply(anatomy,neutralAnatomy);
  std::vector<PrecisePoint> delta(l.restSource.size());
  // Source radial queries use Wolverine's opening and upper-sector exclusions.
  // Geralt's body must recruit from its measured opening on BOTH resources;
  // otherwise the source field raises a separate shield at his native waist.
  for(unsigned i=0;i<l.bodyCount;i++)delta[i]=bodyDisplacement(i);
  // The same measured law drives both body resources and both LODs.
  std::copy(moduleDelta.begin(),moduleDelta.end(),delta.begin()+l.bodyCount);
#ifdef MALEMOD_DILATING_COLLAR
  // Keep the source shaft morphology. The constrained graft solve joins it
  // to the full-sized opening; the historical radial blend shrank this region.
#elif defined(MALEMOD_STOCK_ANCHOR_PREVIEW)
  // Retain the measured oblique baseline for the private support study.
  // Removing this transition was tested and increased the lower cleft.
  auto bodyBlended=l.transition->Evaluate(delta,frame,neutralRadius);
  double angleRelease=std::clamp((50.-angleControl)/25.,0.,1.);angleRelease=angleRelease*angleRelease*angleRelease*(10+angleRelease*(-15+6*angleRelease));
  for(unsigned i=l.bodyCount;i<delta.size();i++){const double w=l.dorsalRelease[i]*angleRelease;for(unsigned k=0;k<3;k++)bodyBlended[i][k]+=(delta[i][k]-bodyBlended[i][k])*w;}
  delta=std::move(bodyBlended);
#else
  delta=l.transition->Evaluate(delta,frame,neutralRadius);
#endif
#ifdef MALEMOD_PROGRESSIVE_RECRUITMENT
  auto originalDelta=delta;
  for(auto master:l.waistMasters){const auto render=l.unique[master];originalDelta[render]=l.transition->BodyDisplacement(render,frame,neutralRadius);}
  for(auto i:l.protectedRender)originalDelta[i]={0,0,0};
  if(recruitmentGrowth>0){
   auto desired=delta;
   for(unsigned i=l.bodyCount;i<desired.size();i++)if(l.recruitmentParticipation[i]>0)desired[i]=moduleDelta[i-l.bodyCount];
   std::vector<PrecisePoint> guide;for(auto p:source.shaftGuide)guide.push_back({p.x,p.y,p.z});
   desired=l.recruitment->Loft(desired,recruitmentFrame,neutralRadius,l.recruitmentParticipation,l.recruitmentAngles,l.recruitmentStations,guide);
   for(unsigned i=0;i<l.bodyCount;i++)desired[i]=l.recruitment->BodyDisplacement(i,recruitmentFrame,neutralRadius);
   for(unsigned i=0;i<delta.size();i++)for(unsigned a=0;a<3;a++)delta[i][a]=(1-recruitmentGrowth)*delta[i][a]+recruitmentGrowth*desired[i][a];
  }
#endif
  // Canonical waist rest samples are identical across resources and LODs.
  // Prescribe the one measured displacement on every alias of each sample.
  for(auto master:l.waistMasters){auto render=l.unique[master];delta[render]=bodyDisplacement(render);}
#ifdef MALEMOD_PROGRESSIVE_RECRUITMENT
  for(auto master:l.waistMasters){const auto render=l.unique[master];const auto desired=l.recruitment->BodyDisplacement(render,recruitmentFrame,neutralRadius);for(unsigned a=0;a<3;a++)delta[render][a]=(1-recruitmentGrowth)*delta[render][a]+recruitmentGrowth*desired[a];}
#endif
  for(auto i:l.protectedRender)delta[i]={0,0,0};
  std::vector<PrecisePoint> unique(l.unique.size());for(unsigned i=0;i<unique.size();i++)unique[i]=delta[l.unique[i]];
#ifdef MALEMOD_DILATING_COLLAR
  auto trace=[&](const char* stage,const std::vector<PrecisePoint>& displacement){
   const char* directory=std::getenv("MALEMOD_COLLAR_TRACE_DIRECTORY");if(!directory)return;
   auto positions=l.domain.points;for(unsigned i=0;i<positions.size();i++)for(unsigned k=0;k<3;k++)positions[i][k]+=displacement[i][k];
   std::ofstream output(std::filesystem::path(directory)/(std::string(stage)+"-lod"+std::to_string(id)+".bin"),std::ios::binary);
   output.write(reinterpret_cast<const char*>(positions.data()),positions.size()*sizeof(PrecisePoint));
  };
  trace("raw",unique);
#endif
#ifdef MALEMOD_DILATING_COLLAR
  std::vector<PrecisePoint> guide;for(auto p:source.shaftGuide)guide.push_back({p.x,p.y,p.z});
#endif
  // Preserve the measured bell field on the original body. Only exact donors
  // and orientation constraints may correct it; a harmonic fairing step can
  // spread mismatched seam targets into the surrounding pelvic surface.
  // Independent
  // anatomy rotation belongs to the second, sewn attachment solve and cannot
  // pull pelvic tissue into an angle-dependent wedge or folded triangle.
  auto stable=unique;
  for(unsigned i=0;i<stable.size();i++)if(l.unique[i]>=l.bodyCount)
   stable[i]=bodyDisplacement(l.unique[i]);
#ifdef MALEMOD_PROGRESSIVE_RECRUITMENT
  for(unsigned i=0;i<stable.size();i++)if(l.unique[i]>=l.bodyCount){const auto desired=l.recruitment->BodyDisplacement(l.unique[i],recruitmentFrame,neutralRadius);for(unsigned a=0;a<3;a++)stable[i][a]=(1-recruitmentGrowth)*stable[i][a]+recruitmentGrowth*desired[a];}
  for(auto i:l.domain.protectedVertices)stable[i]={0,0,0};
#endif
  std::vector<PrecisePoint> recruited;
  try{
   if(stable==l.projectedBodyInput&&!l.projectedBodyOutput.empty())recruited=l.projectedBodyOutput;
   else{
#ifdef MALEMOD_PROGRESSIVE_RECRUITMENT
    recruited=recruitmentGrowth>0?l.recruitmentBodyPlan->ProjectDisplacement(stable):l.bodyPlan->ProjectDisplacement(stable);
#else
  #ifdef MALEMOD_DILATING_COLLAR
    recruited=ProjectGraftContinuation(l.bodyDomain,l.bodyPlan->SolveDisplacement(stable));
#else
    recruited=l.bodyPlan->ProjectDisplacement(stable);
#endif
#endif
    // Commit the pair only after both allocations succeed; a rejected cache
    // preparation must not pair the new key with an older projection.
    auto nextInput=stable,nextOutput=recruited;
    l.projectedBodyInput.swap(nextInput);l.projectedBodyOutput.swap(nextOutput);
   }
  }catch(const std::exception& e){throw std::runtime_error(std::string("Authored body orientation LOD ")+std::to_string(id)+" radius "+std::to_string(frame.radius)+": "+e.what());}
  for(unsigned i=0;i<unique.size();i++)if(l.unique[i]<l.bodyCount)unique[i]=recruited[i];
  #ifdef MALEMOD_DILATING_COLLAR
  for(auto e:l.domain.seams)for(auto i:{e.a,e.b})unique[i]=recruited[i];
#endif
  std::vector<PrecisePoint> solved;
#ifdef MALEMOD_PROGRESSIVE_RECRUITMENT
  if(recruitmentGrowth>0){
   std::vector<PrecisePoint> originalInput(l.unique.size());for(unsigned i=0;i<originalInput.size();i++)originalInput[i]=originalDelta[l.unique[i]];
   auto originalStable=originalInput;
   for(unsigned i=0;i<originalStable.size();i++)if(l.unique[i]>=l.bodyCount)originalStable[i]=l.transition->BodyDisplacement(l.unique[i],frame,neutralRadius);
   auto originalBody=l.bodyPlan->ProjectDisplacement(originalStable);
   for(unsigned i=0;i<originalInput.size();i++)if(l.unique[i]<l.bodyCount)originalInput[i]=originalBody[i];
   const auto originalSolved=l.plan->SolveDisplacement(originalInput);
   for(auto i:l.recruitmentFixed)unique[i]=originalSolved[i];
   solved=l.recruitmentPlan->SolveDisplacement(unique);
   auto reference=l.domain.points,target=l.domain.points;
   for(unsigned i=0;i<reference.size();i++)for(unsigned a=0;a<3;a++){reference[i][a]+=originalSolved[i][a];target[i][a]+=solved[i][a];}
   auto projected=l.recruitmentConstraints->Project(reference,target);
   for(unsigned i=0;i<solved.size();i++)for(unsigned a=0;a<3;a++)solved[i][a]=projected[i][a]-l.domain.points[i][a];
  }else solved=l.plan->SolveDisplacement(unique);
#else
  solved=l.plan->SolveDisplacement(unique);
#endif
#ifdef MALEMOD_DILATING_COLLAR
  trace("fitted",solved);
#endif
#ifdef MALEMOD_ANGLE_CONDITIONED_COLLAR
  const double response=angle_collar::SliderResponse(angleControl)*angle_collar::GrowthResponse(frame.radius,neutralRadius);
  if(response>0){
   if(!l.anglePlan){l.anglePlan=std::make_unique<GraftPlan>(l.angleDomain,frame);l.angleFrame=frame;}
   else if(!Same(frame,l.angleFrame)){l.anglePlan->UpdateFrame(frame);l.angleFrame=frame;}
   auto supported=unique;
   for(unsigned i=0;i<supported.size();i++){
    unsigned render=l.unique[i];if(render<l.bodyCount)continue;
    auto body=l.transition->BodyDisplacement(render,frame,neutralRadius);
    const double weight=l.angleRestWeights->Weight(i,2*neutralRadius);
    for(unsigned a=0;a<3;a++)supported[i][a]=(1-weight)*body[a]+weight*moduleDelta[render-l.bodyCount][a];
   }
   supported=l.anglePlan->SolveDisplacement(supported);
   for(unsigned i=0;i<solved.size();i++)solved[i]=angle_collar::Reconcile(solved[i],supported[i],l.dorsalWeights[i],response,{0,0,1});
   // Project the two resources together; original-edge seam donors, protected
   // boundaries and the shared waist remain exact after the pose corrective.
   solved=l.bodyPlan->ProjectDisplacement(solved);
  }
#else
  (void)angleControl;
#endif
#ifdef MALEMOD_ATTACHMENT_CORRECTIVE
  l.correctiveWeight=0;
#ifndef MALEMOD_DILATING_COLLAR
  // The historical corrective belongs to the historical opening dimensions.
  if(l.corrective||l.sewnCorrective){
   auto posed=l.domain.points;for(unsigned i=0;i<posed.size();i++)for(unsigned a=0;a<3;a++)posed[i][a]+=solved[i][a];
   auto corrected=l.sewnCorrective?l.sewnCorrective->Apply(posed,source,angleControl,neutralRadius):l.corrective->Apply(posed,source,angleControl,neutralRadius);l.correctiveWeight=corrected.appliedWeight;
   for(unsigned i=0;i<solved.size();i++)if(corrected.positions[i]!=posed[i])
    for(unsigned a=0;a<3;a++)solved[i][a]+=corrected.positions[i][a]-posed[i][a];
  }
#endif
#endif
#ifdef MALEMOD_FIXED_COLLAR_ANGLE
  auto original=l.domain.points;for(unsigned i=0;i<solved.size();i++)for(unsigned k=0;k<3;k++)original[i][k]+=solved[i][k];
  auto& region=l.fixedAngleRegion;region.origin={source.shaftGuide[0].x,source.shaftGuide[0].y,source.shaftGuide[0].z};
  // Hinge through the measured dorsal attachment, not the end of a broad
  // protected interval. Keep its lateral axis centered on the source guide.
#ifndef MALEMOD_DILATING_COLLAR
  for(auto e:l.domain.seams)for(auto i:{e.slave,e.a,e.b})if(original[i][2]>region.origin[2]){region.origin[0]=original[i][0];region.origin[2]=original[i][2];}
#endif
  // Small attachments have less lower-tissue clearance. Restrict their range
  // smoothly in shape space, never by suppressing the proximal shaft motion.
  double travel=std::clamp((source.restLength/std::max(neutralLength,1e-9)-.4)/.4,0.,1.);travel=travel*travel*travel*(10+travel*(-15+6*travel));
  region.gain=requestedAngle<50?.25+.75*travel:.5+.5*travel;
  // The small socket / long shaft combination reaches lower-tissue contact
  // earlier. Set one continuous shape-dependent endpoint for the whole slider
  // instead of allowing a late feasibility fallback to reverse its travel.
  double clearance=std::clamp((source.collarMetric.radius/neutralRadius-1.25)/.5,0.,1.);clearance=clearance*clearance*clearance*(10+clearance*(-15+6*clearance));
  region.downwardDegrees=20+10*clearance;
  const double shapeGain=region.gain;auto posed=original;
  auto& junction=l.fixedAngleJunction;
  if(requestedAngle!=50){
   if(!junction)junction=std::make_unique<surface::root_articulation::Junction>(original,l.domain.triangles,l.fixedAngleRows,l.fixedAngleMoving);
   else junction->UpdateReference(original);
  }
  if(requestedAngle!=50&&!l.fixedAngleConstraints){
   std::vector<unsigned> editable;for(unsigned i=0;i<solved.size();i++)if(!l.fixedAngleRows[i]&&!l.fixedAngleMoving[i])editable.push_back(i);
   std::vector<surface::corrective::EdgeDonor> donors;for(auto e:l.domain.seams)donors.push_back({e.slave,e.a,e.b,e.weight});
   l.fixedAngleConstraints=std::make_unique<surface::corrective::EndpointConstraints>(original.size(),l.domain.triangles,editable,donors);
   l.fixedAngleEditable=editable;
  }
  l.fixedAngleGain=angleGainCap*surface::attachment_hinge::AdmissibleGain([&](double candidate){
   region.gain=shapeGain*angleGainCap*candidate;posed=original;
   if(region.gain==0||requestedAngle==50)return true;
   posed=junction->Apply(FixedCollarFlow(region,requestedAngle));
#ifdef MALEMOD_DILATING_COLLAR
   const auto cold=posed;
   auto remember=[&](){l.fixedAngleCorrection=posed;for(unsigned i=0;i<posed.size();i++)for(unsigned k=0;k<3;k++)l.fixedAngleCorrection[i][k]-=cold[i][k];};
   if(l.fixedAngleConstraints->ProjectWarm(original,posed,l.fixedAngleCorrection)){remember();return true;}
   if(l.fixedAngleConstraints->Project(original,posed,512)){remember();return true;}
#else
   if(l.fixedAngleConstraints->Project(original,posed,512))return true;
#endif
   if(surface::root_articulation::ContinueEndpoint(original,posed,[&](double fraction){
    auto portion=region;portion.gain*=fraction;return junction->Apply(FixedCollarFlow(portion,requestedAngle));
   },[&](auto& endpoint){return l.fixedAngleConstraints->Project(original,endpoint,512);} )){
#ifdef MALEMOD_DILATING_COLLAR
    remember();
#endif
    return true;
   }
   if(!l.fixedAngleFailureCaptured){
    const auto bytes=surface::wire::Encode(source);std::ofstream capture(diagnosticDirectory/("angle-transient-lod"+std::to_string(id)+".bin"),std::ios::binary);capture.write(reinterpret_cast<const char*>(bytes.data()),bytes.size());
    std::ofstream report(diagnosticDirectory/("angle-transient-lod"+std::to_string(id)+".txt"));report<<"slider "<<requestedAngle<<"\n"<<l.fixedAngleConstraints->Report();l.fixedAngleFailureCaptured=true;
   }return false;
  });
  for(unsigned i=0;i<solved.size();i++)for(unsigned k=0;k<3;k++)solved[i][k]+=posed[i][k]-original[i][k];
#ifdef MALEMOD_DILATING_COLLAR
  auto posedGuide=guide;const auto collarFlow=FixedCollarFlow(region,requestedAngle);
  for(auto& p:posedGuide)p=collarFlow.Apply(p);
  solved=l.collarRadialSupport->Apply(l.domain.points,solved,posedGuide,source.proximalRadius);
  solved=l.plan->ProjectDisplacement(solved);
#endif
#endif
  auto result=l.restNative;
  for(unsigned i=0;i<result.size();i++){
   auto v=calibration.VectorToTarget(solved[l.aliases[i]]);
   for(unsigned axis=0;axis<3;axis++)result[i][axis]+=v[axis]*calibration.targetUnitsPerSourceUnit;
  }
  return result;
 }
};
TargetSurface::TargetSurface(const std::filesystem::path& path,const std::string& commit):impl_(std::make_unique<Impl>(path,commit)){}
TargetSurface::~TargetSurface()=default;
std::vector<surface::PrecisePoint> TargetSurface::Evaluate(unsigned lod,const surface::Output& source,float angleControl,double angleGainCap){return impl_->Evaluate(lod,source,angleControl,angleGainCap);}
std::array<double,2> TargetSurface::FixedAngleGains()const{
#ifdef MALEMOD_FIXED_COLLAR_ANGLE
 return {impl_->lods[0].fixedAngleGain,impl_->lods[1].fixedAngleGain};
#else
 return {1,1};
#endif
}
unsigned TargetSurface::LODCount()const{return static_cast<unsigned>(impl_->lods.size());}
std::array<double,2> TargetSurface::CorrectiveWeights()const{return {impl_->lods[0].correctiveWeight,impl_->lods[1].correctiveWeight};}
void TargetSurface::PresentFixedAngleSource(surface::Output& source,float slider)const{
#ifdef MALEMOD_FIXED_COLLAR_ANGLE
 PresentFixedCollarSource(source,slider,impl_->lods[0].fixedAngleRegion);
#else
 (void)source;(void)slider;
#endif
}
std::string TargetSurface::CorrectiveError()const{return impl_->correctiveError;}
std::array<std::string,2> TargetSurface::CorrectiveReports()const{
 std::array<std::string,2> result;
#ifdef MALEMOD_ATTACHMENT_CORRECTIVE
 for(unsigned i=0;i<2;i++)if(impl_->lods[i].sewnCorrective)result[i]=impl_->lods[i].sewnCorrective->ConstraintReport();
#endif
#ifdef MALEMOD_FIXED_COLLAR_ANGLE
 for(unsigned i=0;i<2;i++)if(impl_->lods[i].fixedAngleConstraints)result[i]+="; hinge "+impl_->lods[i].fixedAngleConstraints->Report();
#endif
 return result;
}
std::vector<unsigned> TargetSurface::BodyCounts()const{std::vector<unsigned> counts;for(const auto& l:impl_->lods)counts.push_back(l.bodyCount);return counts;}
std::vector<surface::Point> TargetSurface::CollarQueries()const{std::vector<surface::Point> p;for(const auto& l:impl_->lods)for(unsigned i=0;i<l.bodyCount;i++){auto q=l.restSource[i];p.push_back({float(q[0]),float(q[1]),float(q[2])});}return p;}
void TargetSurface::SetNeutralCollar(const surface::Output& o){if(o.collarDisplacements.size()!=CollarQueries().size()||!std::isfinite(o.collarMetric.radius)||o.collarMetric.radius<=0)throw std::invalid_argument("Missing neutral radial targets");impl_->neutralRadius=o.collarMetric.radius;impl_->neutralLength=o.restLength;impl_->neutralCollar.clear();for(auto p:o.collarDisplacements)impl_->neutralCollar.push_back({p.x,p.y,p.z});}
}
