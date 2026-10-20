#pragma once
#include "render_contract.hpp"
#include "skin_output.hpp"
#include <malemod/surface/modular_asset.hpp>
#include <malemod/surface/modular_transfer.hpp>
#include <malemod/surface/root_articulation.hpp>
#include <malemod/surface/live_controls.hpp>
#include <memory>
#include <chrono>

namespace malemod::witcher {
struct ModularVertex {
 std::array<float,3> position;std::uint32_t bones=0,weights=0,normal=0,tangent=0;
 std::array<std::uint16_t,2> uv{};std::uint32_t color=0;std::array<std::uint16_t,2> reflection{};
};
static_assert(sizeof(ModularVertex)==40);
struct ModularPart {
 unsigned resource=0,lod=0,carrierFirst=0,carrierCount=0;
 std::vector<ModularVertex> vertices;
 std::shared_ptr<const std::vector<unsigned>> indices;
 std::shared_ptr<const std::vector<surface::PresentationBinding>> presentation;
 std::shared_ptr<const std::vector<unsigned>> controlVertices;
};
struct ModularControlTopology {
 std::vector<surface::LiveControlBinding> bindings;
 std::vector<std::array<unsigned,3>> faces;
 std::vector<surface::LiveControlLoft> lofts;
 std::vector<unsigned> sourceLofts;
 std::vector<surface::LiveControlDonor> bodyDonors;
};
struct ModularFrame {
 std::array<ModularPart,4> parts;surface::PresentationFrames frames{};
 double milliseconds=0;bool rebuilt=false;std::array<double,3> materialScale{1,1,1};
 std::shared_ptr<const ModularControlTopology> controlTopology;
 std::vector<surface::PresentationPoint> controlPoints;
 surface::LiveControlFrame controlFrame;
 std::vector<surface::LiveControlTangents> controlTangents;
};
}
#include "modular_dynamic_render.hpp"
namespace malemod::witcher {

class ModularRenderer {
 using Vec=surface::modular::Vec;using State=surface::modular::State;
 struct Row {unsigned geometric=0;std::uint32_t bones=0,weights=0;std::array<std::uint16_t,2> uv{};std::uint32_t color=0;std::array<std::uint16_t,2> reflection{};Vec tangent{};double sign=1;};
 struct Part {unsigned resource=0,lod=0,carrierFirst=0,carrierCount=0;std::vector<Row> rows;std::shared_ptr<const std::vector<unsigned>> indices;};
 surface::modular::Asset asset_;surface::modular::Plan plan_;
 const RenderContract& contract_;std::array<Part,4> parts_;
 std::vector<unsigned char> fixed_;std::vector<Vec> fixedPoints_,referenceNormals_;
 std::unique_ptr<ModularDynamicRenderer> dynamic_;
 std::unique_ptr<surface::modular::SurfaceTransfer> transfer_;
 mutable std::shared_ptr<const surface::Output> shapeSource_;
 mutable std::shared_ptr<const std::vector<Vec>> shapePoints_;
 mutable double shapeAngle_=0;
 mutable Vec materialScale_{1,1,1};
 mutable std::shared_ptr<const std::vector<surface::modular::Binding>> materialBindings_;
 mutable std::shared_ptr<const std::vector<double>> crownWeights_;
 mutable surface::PresentationFrames materialFrames_{};
 static Vec Normal(Vec v,Vec fallback){const double n=surface::Dot(v,v);return n>1e-24?surface::Scale(v,1/std::sqrt(n)):fallback;}
 static Vec Transport(Vec v,Vec a,Vec b){
  using namespace surface;const auto axis=Cross(a,b);const double cosine=std::clamp(Dot(a,b),-1.,1.);
  if(cosine<-.9999){auto side=Cross(a,Vec{1,0,0});if(Dot(side,side)<1e-6)side=Cross(a,Vec{0,1,0});side=Unit(side);return Sub(Scale(side,2*Dot(side,v)),v);}
  return Add(Add(v,Cross(axis,v)),Scale(Cross(axis,Cross(axis,v)),1/(1+cosine)));
 }
 std::vector<Vec> GeometricNormals(const std::vector<Vec>& p)const{
  std::vector<Vec> normals(p.size());
  for(auto f:asset_.faces){auto n=surface::Cross(surface::Sub(p[f[1]],p[f[0]]),surface::Sub(p[f[2]],p[f[0]]));for(auto i:f)normals[i]=surface::Add(normals[i],n);}
  for(unsigned i=0;i<normals.size();i++)normals[i]=Normal(normals[i],surface::Unit(asset_.normals[i]));return normals;
 }
 static unsigned Pack(Vec v,unsigned high){unsigned word=high<<30;v=surface::Unit(v);for(unsigned k=0;k<3;k++)word|=unsigned(std::clamp((v[k]+1)*.5,0.,1.)*1023+.5)<<(10*k);return word;}
 public:
 ModularRenderer(const std::filesystem::path& geometry,const std::filesystem::path& native,const RenderContract& contract,const std::string& geometryHash,const std::string& carrierHash)
 :asset_(geometry),plan_(asset_.MakePlan()),contract_(contract){
  if(std::filesystem::file_size(native)>64*1024*1024)throw std::invalid_argument("Oversize modular native contract");
  std::ifstream in(native,std::ios::binary);
  auto bytes=[&](void* p,std::size_t n){if(!in.read(static_cast<char*>(p),n))throw std::invalid_argument("Truncated modular native contract");};
  auto text=[&](unsigned n){std::string value(n,'\0');bytes(value.data(),n);return value;};auto u=[&]{unsigned n;bytes(&n,4);return n;};
  if(text(8)!="MMMODW01"||text(64)!=geometryHash||text(64)!=carrierHash||u()!=asset_.rest.size())throw std::invalid_argument("Modular native/source/carrier identity differs");
  fixed_.resize(asset_.rest.size());fixedPoints_.resize(asset_.rest.size());bytes(fixed_.data(),fixed_.size());bytes(fixedPoints_.data(),fixedPoints_.size()*24);
  for(unsigned i=0;i<fixed_.size();i++){if(fixed_[i]>1)throw std::invalid_argument("Invalid modular external boundary flag");for(double x:fixedPoints_[i])if(!std::isfinite(x))throw std::invalid_argument("Nonfinite modular boundary");}
  for(unsigned index=0;index<4;index++){
   auto& part=parts_[index];part.resource=u();part.lod=u();part.carrierFirst=u();part.carrierCount=u();auto nv=u(),ni=u();
   if(part.resource!=index/2||part.lod!=index%2||!nv||nv>500000||!ni||ni>3000000||ni%3)throw std::invalid_argument("Invalid modular native part");
   const auto& original=contract.lods[index];const auto& resource=contract.resources[part.resource];
   if(original.resource!=part.resource||original.lod!=part.lod||original.firstIndex!=part.carrierFirst||original.indexCount!=part.carrierCount)throw std::invalid_argument("Modular carrier draw range differs");
   part.rows.resize(nv);
   for(auto& row:part.rows){
    row.geometric=u();row.bones=u();row.weights=u();bytes(row.uv.data(),4);row.color=u();bytes(row.reflection.data(),4);bytes(row.tangent.data(),24);bytes(&row.sign,8);
    if(row.geometric>=asset_.rest.size()||!std::isfinite(row.sign)||std::abs(row.sign)!=1)throw std::invalid_argument("Invalid modular UV alias");
    unsigned sum=0;for(unsigned k=0;k<4;k++){if(((row.bones>>(k*8))&255)>=resource.paletteCount)throw std::invalid_argument("Modular skin leaves observed native palette");sum+=(row.weights>>(k*8))&255;}
    if(sum!=255)throw std::invalid_argument("Modular native skin is not normalized");for(double x:row.tangent)if(!std::isfinite(x))throw std::invalid_argument("Nonfinite modular tangent");
   }
   auto indices=std::make_shared<std::vector<unsigned>>(ni);bytes(indices->data(),ni*4);for(auto i:*indices)if(i>=nv)throw std::invalid_argument("Modular native index outside part");part.indices=indices;
  }
  if(in.peek()!=EOF)throw std::invalid_argument("Trailing modular native contract");referenceNormals_=GeometricNormals(asset_.rest);
 }
 State Drive(const surface::Output& source,Vec pivot={},double radians=0,std::shared_ptr<const surface::Output> shape={},double hang=50)const{
  auto state=surface::modular::DrivenState(asset_.reference,asset_.dimensions,source);
  state.hangControl=hang;
  state.suspensionProfile=true;
  if(transfer_){surface::root_articulation::Rotation flow(pivot,{1,0,0},{0,0,1},radians);if(shape){
    if(shapeSource_!=shape||shapeAngle_!=radians){
     auto rest=*shape;for(auto* guide:{&rest.shaftGuide,&rest.restGuide})for(auto& p:*guide){auto q=flow.Apply(surface::Precise(p));p={float(q[0]),float(q[1]),float(q[2])};}
     auto material=surface::modular::DrivenState(asset_.reference,asset_.dimensions,rest);
     transfer_->Apply(asset_,plan_,material,rest,[&](auto p){return flow.Apply(p);},true,true);
     crownWeights_=transfer_->CrownWeights();
     auto points=std::make_shared<std::vector<Vec>>(plan_.Evaluate(material));
     // The source restGuide and live shaftGuide do not use the same material
     // stations. Reposing an initialized surface onto restGuide compressed its
     // final intervals before simulation even started. The zero-motion capture
     // supplies both the material geometry and its matching guide frames.
     materialFrames_=material.frames;materialScale_=material.scales[1];
     auto bindings=std::make_shared<std::vector<surface::modular::Binding>>(surface::modular::BindMaterialStations(*points,asset_.bindings,materialFrames_));
     shapePoints_=points;materialBindings_=bindings;shapeSource_=shape;shapeAngle_=radians;
    }
    for(unsigned k=0;k<3;k++)state.materialScale[k]=state.scales[1][k]/materialScale_[k];
    state.shapeFrames=materialFrames_;state.materialBindings=materialBindings_;state.shaftMaterial=shapePoints_;state.crownWeights=crownWeights_;
    surface::modular::AnchorRootPhysics(state,source.proximalRadius,source.restLength);surface::modular::PreserveMaterialLengths(state);
   }
   transfer_->Apply(asset_,plan_,state,source,[&](auto p){return flow.Apply(p);},!shape);
  }
  return state;
 }
 void EnableTransfer(const std::filesystem::path& path,const std::string& geometryHash){auto transfer=std::make_unique<surface::modular::SurfaceTransfer>(path);if(transfer->geometryHash!=geometryHash)throw std::invalid_argument("Modular transfer geometry identity differs");transfer_=std::move(transfer);}
 void EnableDynamic(const std::filesystem::path& dynamic,const std::filesystem::path& materials,const std::string& geometryHash,const std::string& dynamicHash,const std::string& nativeHash){dynamic_=std::make_unique<ModularDynamicRenderer>(asset_,plan_,contract_,dynamic,materials,geometryHash,dynamicHash,nativeHash);}
 std::shared_ptr<const ModularFrame> Evaluate(const State& state)const{
  if(dynamic_){auto frame=dynamic_->Evaluate(state);return frame;}
  const auto start=std::chrono::steady_clock::now();auto p=asset_.Evaluate(plan_,state);auto geometryNormals=GeometricNormals(p);std::vector<Vec> normal(p.size());
  for(unsigned i=0;i<p.size();i++){normal[i]=Normal(Transport(surface::Unit(asset_.normals[i]),referenceNormals_[i],geometryNormals[i]),geometryNormals[i]);p[i]=fixed_[i]?fixedPoints_[i]:contract_.calibration.PointToTarget(p[i]);normal[i]=contract_.calibration.VectorToTarget(normal[i]);}
  auto frame=std::make_shared<ModularFrame>();
  for(unsigned index=0;index<4;index++){
   const auto& input=parts_[index];auto& output=frame->parts[index];output.resource=input.resource;output.lod=input.lod;output.carrierFirst=input.carrierFirst;output.carrierCount=input.carrierCount;output.indices=input.indices;output.vertices.reserve(input.rows.size());
   const auto& resource=contract_.resources[input.resource];
   for(const auto& row:input.rows){
    const auto g=row.geometric;auto tangent=contract_.calibration.VectorToTarget(Transport(row.tangent,referenceNormals_[g],geometryNormals[g]));
    tangent=Normal(surface::Sub(tangent,surface::Scale(normal[g],surface::Dot(tangent,normal[g]))),contract_.calibration.VectorToTarget(row.tangent));
    ModularVertex vertex;for(unsigned k=0;k<3;k++){vertex.position[k]=float((p[g][k]-resource.bias[k])/resource.scale[k]);if(!std::isfinite(vertex.position[k]))throw std::invalid_argument("Nonfinite modular native output");}
    vertex.bones=row.bones;vertex.weights=row.weights;vertex.normal=Pack(normal[g],1);vertex.tangent=Pack(tangent,row.sign<0?0:3);vertex.uv=row.uv;vertex.color=row.color;vertex.reflection=row.reflection;output.vertices.push_back(vertex);
   }
  }
  frame->milliseconds=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();return frame;
 }
};
}
