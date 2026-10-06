#pragma once
#include "render_service.hpp"
#include "garment_presentation.hpp"
#include "garment_cadence.hpp"
#include "garment_failure_capture.hpp"
#include <malemod/garments/jockstrap.hpp>
#include <malemod/garments/numerical_support.hpp>
#include <malemod/garments/reaction_support.hpp>
#include <malemod/surface/garment_impulse.hpp>
#include <condition_variable>
#include <thread>
#include <unordered_map>
namespace malemod::witcher {
struct GarmentDelivery {
 unsigned epoch=0;std::uint64_t serial=0,generation=0,restRevision=0;
 garments::Output output;
 surface::Frame::GarmentSupport support;
 double milliseconds=0;
 double samplingMilliseconds=0,updateMilliseconds=0,presentationBuildMilliseconds=0,diagnosticMilliseconds=0;
 double presentationMilliseconds=0,poseSeconds=0,activeSeconds=0;
 bool clockReset=false;
 std::shared_ptr<const RenderDelivery> sourceRender;
 std::shared_ptr<const GarmentPresentation> presentation;
};
class GarmentBindings {
 public:
 std::array<double,3> root{};
 std::array<std::vector<unsigned>,5> contours;
 std::vector<std::array<unsigned,3>> triangles;
 std::vector<unsigned> bodyContour;
 std::vector<std::array<std::uint32_t,3>> bodyTriangles;
 garments::AnatomyRegions anatomyRegions;
 std::vector<garments::MechanicalBinding> reactionBindings;
 struct SamplingCache {
  std::vector<std::uint64_t> sampleKeys,tupleKeys;
  std::vector<unsigned> tupleIds;
 };
 GarmentBindings(const std::filesystem::path& path,const std::string& pin,const std::string& renderHash){
  std::ifstream f(path,std::ios::binary);
  auto read=[&](void* p,size_t n){if(!f.read(static_cast<char*>(p),n))throw std::runtime_error("Incomplete garment binding");};
  auto text=[&](size_t n){std::string s(n,'\0');read(s.data(),n);return s;};
  const auto magic=text(8);if((magic!="MMGRB001"&&magic!="MMGRB002"&&magic!="MMGRB003")||text(40)!=pin||text(64)!=renderHash)throw std::runtime_error("Garment binding pin differs");
  read(root.data(),24);
  for(auto& ids:contours){unsigned n;read(&n,4);if(n<2||n>50000)throw std::runtime_error("Garment donor budget differs");ids.resize(n);read(ids.data(),n*4);}
  unsigned n;read(&n,4);if(n>100000)throw std::runtime_error("Garment topology budget differs");triangles.resize(n);read(triangles.data(),n*12);
  for(auto t:triangles)for(auto i:t)if(i>=contours[2].size())throw std::runtime_error("Garment topology outside anatomy");
  if(magic!="MMGRB001"){unsigned count;read(&count,4);if(count<8||count>200000)throw std::runtime_error("Measured garment body sample budget differs");bodyContour.resize(count);read(bodyContour.data(),count*4);read(&count,4);if(!count||count>400000)throw std::runtime_error("Measured garment body triangle budget differs");bodyTriangles.resize(count);read(bodyTriangles.data(),count*12);for(auto face:bodyTriangles)for(auto id:face)if(id>=bodyContour.size())throw std::runtime_error("Measured garment body triangle outside samples");}
  if(magic=="MMGRB003"){std::vector<bool> seen(contours[2].size());for(auto& group:anatomyRegions){unsigned count;read(&count,4);if(count>contours[2].size())throw std::runtime_error("Anatomical guide region budget differs");group.resize(count);read(group.data(),count*4);for(auto id:group){if(id>=seen.size()||seen[id])throw std::runtime_error("Anatomical guide region index overlaps or leaves full anatomy");seen[id]=true;}}}
  if(f.peek()!=EOF)throw std::runtime_error("Unexpected garment binding bytes");
  const auto reactionPath=path.parent_path()/"garment.reactions";
  if(std::filesystem::exists(reactionPath)){
   std::ifstream reactions(reactionPath,std::ios::binary);auto bytes=[&](void* p,std::size_t n){if(!reactions.read(static_cast<char*>(p),n))throw std::runtime_error("Incomplete mechanical garment binding");};auto word=[&](std::size_t n){std::string s(n,'\0');bytes(s.data(),n);return s;};
   if(word(8)!="MMGRE001"||word(40)!=pin||word(64)!=renderHash)throw std::runtime_error("Mechanical garment binding pin differs");unsigned count;bytes(&count,4);if(count!=contours[2].size())throw std::runtime_error("Mechanical garment binding omits retained anatomy");std::set<unsigned> seen;
   for(unsigned i=0;i<count;i++){unsigned vertex;bytes(&vertex,4);if(vertex>=200000||vertex!=contours[2][i]||!seen.insert(vertex).second)throw std::runtime_error("Mechanical garment binding native vertex differs");garments::MechanicalBinding b;bytes(b.weights.data(),14*8);double sum=0;for(double w:b.weights){if(!std::isfinite(w)||w<0)throw std::runtime_error("Invalid mechanical garment force weight");sum+=w;}if(sum>1+1e-6)throw std::runtime_error("Mechanical garment force binding amplifies impulse");if(reactionBindings.size()<=vertex)reactionBindings.resize(vertex+1);reactionBindings[vertex]=b;}
   if(reactions.peek()!=EOF)throw std::runtime_error("Unexpected mechanical garment binding bytes");
  }
 }
 garments::Input Input(const RenderContract& contract,const RenderDelivery& render,double dt,SamplingCache* persistentCache=nullptr)const{
  using namespace garments;
  unsigned pelvis=0;while(pelvis<contract.nativeBones.size()&&contract.nativeBones[pelvis]!=9)++pelvis;
  if(pelvis==contract.nativeBones.size()||!render.vertices)throw std::runtime_error("Missing garment character pose");
  const auto m=MultiplyPose(render.pose.actorWorld,render.pose.skinDeltas.at(pelvis));
  auto direction=[&](Point p){return Unit(Sub(TransformPosePoint(m,p),TransformPosePoint(m,{0,0,0})));};
  garments::Input in;in.frame.origin=TransformPosePoint(m,root);in.frame.up=direction({0,0,1});in.frame.lateral=direction({1,0,0});
  in.frame.forward=Unit(Cross(in.frame.up,in.frame.lateral));in.frame.lateral=Unit(Cross(in.frame.forward,in.frame.up));
  in.characterEpoch=render.epoch;in.topologyRevision=1;in.deltaTime=dt;
  in.anatomyMass=CurrentSourceMasses(render.controls).Total();
  // The source solver uses 72 source-length units for lobe gravity. Preserve
  // that measured magnitude, scaled into the game's world-space cloth input;
  // an assumed SI 9.81 would change garment support relative to Wolverine.
  in.gravity={0,0,-72*contract.calibration.targetUnitsPerSourceUnit};in.anatomyTriangles=triangles;in.anatomyRegions=anatomyRegions;
  std::vector<skin::Matrix> palette;for(auto p:render.pose.skinDeltas){skin::Matrix a{};for(unsigned j=0;j<16;j++)a[j]=float(p[j]);palette.push_back(a);}
  skin::Matrix actor{};for(unsigned j=0;j<16;j++)actor[j]=float(render.pose.actorWorld[j]);
  // A pose has one exact blended map for each packed bone/weight tuple.
  // Skin::Blend retains the SDK's four-matrix validation and float operation
  // order; only repeated validation/composition is avoided across mesh aliases.
  SamplingCache local;auto& cache=persistentCache?*persistentCache:local;
  std::array<const std::vector<unsigned>*,6> sampledContours={&contours[0],&contours[1],&contours[2],&contours[3],&contours[4],&bodyContour};
  unsigned sampleCount=0;for(const auto* contour:sampledContours)sampleCount+=unsigned(contour->size());bool rebuild=cache.sampleKeys.size()!=sampleCount;
  unsigned ordinal=0;if(!rebuild)for(const auto* contour:sampledContours)for(auto id:*contour){const auto& v=render.vertices->at(id);const auto key=std::uint64_t(v.bones)|(std::uint64_t(v.weights)<<32);if(cache.sampleKeys[ordinal++]!=key)rebuild=true;}
  if(rebuild){cache={};cache.sampleKeys.reserve(sampleCount);cache.tupleIds.reserve(sampleCount);std::unordered_map<std::uint64_t,unsigned> tuples;tuples.reserve(4096);for(const auto* contour:sampledContours)for(auto id:*contour){const auto& v=render.vertices->at(id);const auto key=std::uint64_t(v.bones)|(std::uint64_t(v.weights)<<32);auto inserted=tuples.emplace(key,unsigned(cache.tupleKeys.size()));if(inserted.second)cache.tupleKeys.push_back(key);cache.sampleKeys.push_back(key);cache.tupleIds.push_back(inserted.first->second);}}
  std::vector<skin::Matrix> blends;blends.reserve(cache.tupleKeys.size());for(auto key:cache.tupleKeys){skin::Vertex a{};const auto bones=std::uint32_t(key),weights=std::uint32_t(key>>32);std::memcpy(a.bones.data(),&bones,4);std::memcpy(a.weights.data(),&weights,4);blends.push_back(skin::Blend(a,palette));}
  ordinal=0;
  auto sample=[&](unsigned index,Surface surface){
   const auto& v=render.vertices->at(index);const auto& blend=blends.at(cache.tupleIds.at(ordinal++));
   auto p=skin::Transform(actor,skin::Transform(blend,v.position)),n=skin::Normalize(skin::Transform(actor,skin::Transform(blend,v.normal,true),true));
   Sample s;s.position={p[0],p[1],p[2]};s.normal={n[0],n[1],n[2]};s.lineage.donors[0]={surface,index,1};return s;
  };
  for(unsigned k=0;k<5;k++){auto& out=k==0?in.waist:k==1?in.opening:k==2?in.anatomy:in.rearStraps[k-3];out.reserve(contours[k].size());for(auto id:contours[k])out.push_back(sample(id,k==2?Surface::Anatomy:Surface::Body));}
  in.bodySurface.reserve(bodyContour.size());for(auto id:bodyContour)in.bodySurface.push_back(sample(id,Surface::Body));in.bodyTriangles=bodyTriangles;
  return in;
 }
};
class GarmentService {
 struct Request {
  std::shared_ptr<const RenderDelivery> render;
  std::vector<garments::Capsule> capsules;
  std::uint64_t generation=0;
  std::uint64_t restRevision=0;
  double activeSeconds=0;
 };
 const RenderContract& contract_;GarmentBindings bindings_;
 std::mutex mutex_;std::condition_variable changed_;
 bool stopping_=false;unsigned style_=0,activeEpoch_=0;
 std::uint64_t generation_=0;
 std::uint64_t restRevision_=0;
 std::array<float,10> shapeControls_{};
 bool shapeKnown_=false;
 std::optional<Request> pending_;
 std::shared_ptr<const GarmentDelivery> raw_,delivery_;std::string error_;
 std::shared_ptr<const RenderDelivery> lastGeometry_;
 GarmentCadence cadence_;
 std::vector<garments::SupportBody> supportBodies_;
 std::optional<surface::CollisionCalibration> contacts_;
 std::filesystem::path diagnosticDirectory_;
 // Last: the worker can run immediately, after every field it reads exists.
 std::thread worker_;
 void Run(){
  garments::Session session;surface::GarmentImpulseLedger reactionLedger;std::uint64_t reactionEpoch=0;unsigned epoch=0;double activeSeconds=0;
  GarmentBindings::SamplingCache samplingCache;
  std::shared_ptr<const GarmentPresentation> presentationCache;
  std::uint64_t serial=0,generation=std::uint64_t(-1);bool failureCaptured=false;
  for(;;){Request request;unsigned style;
   {std::unique_lock<std::mutex> l(mutex_);changed_.wait(l,[&]{return stopping_||pending_.has_value();});if(stopping_)return;request=std::move(*pending_);pending_.reset();style=style_;}
   const auto& render=request.render;
   try{auto begin=std::chrono::steady_clock::now();
    const bool reset=generation!=request.generation||epoch!=render->epoch||request.activeSeconds<activeSeconds||request.activeSeconds-activeSeconds>1;
    const double dt=reset?0:request.activeSeconds-activeSeconds;
    if(reset){session.Reset();failureCaptured=false;presentationCache.reset();reactionLedger.Reset(++reactionEpoch);}
    epoch=render->epoch;generation=request.generation;activeSeconds=request.activeSeconds;
    auto next=std::make_shared<GarmentDelivery>();next->epoch=epoch;next->serial=++serial;next->generation=generation;next->restRevision=request.restRevision;next->sourceRender=render;next->poseSeconds=render->poseSeconds;next->activeSeconds=activeSeconds;next->clockReset=reset;
    if(style){auto sampleBegin=std::chrono::steady_clock::now();auto input=bindings_.Input(contract_,*render,dt,&samplingCache);input.restRevision=request.restRevision;input.bodyContacts=std::move(request.capsules);next->samplingMilliseconds=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-sampleBegin).count();auto updateBegin=std::chrono::steady_clock::now();next->output=session.Update(garments::Style::WhiteJockstrap,input);next->updateMilliseconds=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-updateBegin).count();
     if((!next->output.contactBudgetSatisfied||!next->output.physics.materialBudgetSatisfied)&&!failureCaptured&&!diagnosticDirectory_.empty()){failureCaptured=true;auto captureBegin=std::chrono::steady_clock::now();try{garment_capture::Capture(diagnosticDirectory_,input,next->output,serial,render->poseSeconds);}catch(const std::exception& e){std::lock_guard<std::mutex> l(mutex_);error_=std::string("Garment diagnostic capture: ")+e.what();}next->diagnosticMilliseconds=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-captureBegin).count();}
     unsigned pelvis=0;while(pelvis<contract_.nativeBones.size()&&contract_.nativeBones[pelvis]!=9)++pelvis;
     const auto inverse=InversePose(MultiplyPose(render->pose.actorWorld,render->pose.skinDeltas.at(pelvis)));
     auto toSource=[&](garments::Point acceleration){auto zero=TransformPosePoint(inverse,{0,0,0});auto transformed=TransformPosePoint(inverse,acceleration);for(unsigned a=0;a<3;a++)transformed[a]=(transformed[a]-zero[a])/contract_.calibration.targetUnitsPerSourceUnit;return contract_.calibration.VectorToSource(transformed);};
     if(bindings_.reactionBindings.empty())throw std::runtime_error("Physical garment contact binding missing");
     auto binding=[&](garments::Donor d){return bindings_.reactionBindings.at(d.vertex);};
     const auto worldOriginInSource=contract_.calibration.PointToSource(TransformPosePoint(inverse,{0,0,0}));
     auto delta=garments::AggregateContactReactions(next->output,binding,toSource,worldOriginInSource,render->garmentLobeCenters,render->garmentLobeRadii,garments::CurrentSourceMasses(render->controls));
     next->support=reactionLedger.Append(delta);
    }
    else {session.Reset();next->output.style=garments::Style::Naked;}
    auto presentationBegin=std::chrono::steady_clock::now();next->presentation=std::make_shared<GarmentPresentation>(next->output,render,presentationCache);presentationCache=next->presentation;next->presentationBuildMilliseconds=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-presentationBegin).count();
    next->milliseconds=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-begin).count();
    std::lock_guard<std::mutex> l(mutex_);
    if(!stopping_&&style_&&generation_==generation&&activeEpoch_==epoch)std::atomic_store(&raw_,std::shared_ptr<const GarmentDelivery>(next));
   }catch(const std::exception& e){std::lock_guard<std::mutex> l(mutex_);if(generation_==request.generation)error_=e.what();}
  }
 }
 std::vector<garments::Capsule> Capsules(const RenderPose& pose)const{
  std::vector<garments::Capsule> out;if(!contacts_)return out;
  const double scale=contract_.calibration.targetUnitsPerSourceUnit;
  auto palette=[&](unsigned bone){unsigned k=0;while(k<contract_.nativeBones.size()&&contract_.nativeBones[k]!=bone)++k;if(k==contract_.nativeBones.size())throw std::invalid_argument("Garment measured contact pose missing");return k;};
  for(unsigned side=0;side<2;side++){std::array<garments::Point,2> endpoints;
   for(unsigned end=0;end<2;end++){const unsigned k=palette(side?18+end:15+end);auto boneWorld=MultiplyPose(pose.actorWorld,MultiplyPose(pose.skinDeltas.at(k),InversePose(contract_.inverseBind[k])));endpoints[end]=TransformPosePoint(boneWorld,{0,0,0});}
   out.push_back({endpoints[0],endpoints[1],contacts_->thighRadii[side]*scale});
  }
  const auto matrix=MultiplyPose(pose.actorWorld,pose.skinDeltas.at(palette(9)));std::array<garments::Point,2> endpoints;
  for(unsigned i=0;i<2;i++)endpoints[i]=TransformPosePoint(matrix,contract_.calibration.PointToTarget(surface::Precise(contacts_->pelvisEndpoints[i])));
  out.push_back({endpoints[0],endpoints[1],contacts_->pelvisRadius*scale});return out;
 }
 public:
 GarmentService(const RenderContract& c,GarmentBindings b,std::optional<surface::CollisionCalibration> contacts={},std::filesystem::path diagnosticDirectory={}):contract_(c),bindings_(std::move(b)),contacts_(contacts),diagnosticDirectory_(std::move(diagnosticDirectory)){
  supportBodies_.resize(c.VertexCount(),garments::SupportBody::None);
  for(const auto& lod:c.lods)for(unsigned i=0;i<lod.vertices.size();i++){auto frame=lod.vertices[i].presentation.frame;supportBodies_[lod.firstVertex+i]=frame==13?garments::SupportBody::Lobe0:frame==14?garments::SupportBody::Lobe1:frame?garments::SupportBody::Shaft:garments::SupportBody::None;}
  worker_=std::thread([this]{Run();});
 }
 ~GarmentService(){{std::lock_guard<std::mutex> l(mutex_);stopping_=true;}changed_.notify_one();if(worker_.joinable())worker_.join();}
 void Style(unsigned style){std::lock_guard<std::mutex> l(mutex_);style%=2;if(style_==style)return;style_=style;generation_++;pending_.reset();lastGeometry_.reset();shapeKnown_=false;cadence_.Reset();error_.clear();std::atomic_store(&raw_,std::shared_ptr<const GarmentDelivery>{});std::atomic_store(&delivery_,std::shared_ptr<const GarmentDelivery>{});}
 unsigned Style(){std::lock_guard<std::mutex> l(mutex_);return style_;}
 void Submit(std::shared_ptr<const RenderDelivery> input,const RenderPose& current,bool paused=false){
  std::uint64_t generation,restRevision;unsigned style;GarmentCadence::Sample sample;
  {
   std::lock_guard<std::mutex> l(mutex_);if(stopping_)return;
   if(!current.epoch){generation_++;activeEpoch_=0;pending_.reset();lastGeometry_.reset();shapeKnown_=false;cadence_.Reset();std::atomic_store(&raw_,std::shared_ptr<const GarmentDelivery>{});std::atomic_store(&delivery_,std::shared_ptr<const GarmentDelivery>{});return;}
   if(input&&input->epoch==current.epoch){}
   else if(lastGeometry_&&lastGeometry_->epoch==current.epoch)input=lastGeometry_;
   else {std::atomic_store(&delivery_,std::shared_ptr<const GarmentDelivery>{});return;}
   const bool changed=lastGeometry_!=input;
   sample=cadence_.Advance(current.epoch,current.seconds,paused,changed);
   if(sample.reset){generation_++;pending_.reset();shapeKnown_=false;error_.clear();std::atomic_store(&raw_,std::shared_ptr<const GarmentDelivery>{});}
   // The observed catalog's first ten values are state and morphology. Motion,
   // weight, bounce and stiffness values are not fabric rest-shape revisions.
   std::array<float,10> shape;std::copy_n(input->controls.values.begin(),shape.size(),shape.begin());
   if(!shapeKnown_||shape!=shapeControls_){shapeControls_=shape;shapeKnown_=true;restRevision_++;}
   restRevision=restRevision_;
   activeEpoch_=current.epoch;generation=generation_;style=style_;lastGeometry_=input;
  }
  auto raw=std::atomic_load(&raw_);
  if(!style||!raw||raw->epoch!=current.epoch||raw->generation!=generation)std::atomic_store(&delivery_,std::shared_ptr<const GarmentDelivery>{});
  else try{auto began=std::chrono::steady_clock::now();auto shown=std::make_shared<GarmentDelivery>(*raw);shown->poseSeconds=current.seconds;shown->output=raw->presentation->Present(raw->output,*input,current);shown->presentationMilliseconds=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-began).count();std::lock_guard<std::mutex> l(mutex_);if(style_&&generation_==generation)std::atomic_store(&delivery_,std::shared_ptr<const GarmentDelivery>(shown));}
  catch(const std::exception& e){std::atomic_store(&delivery_,std::shared_ptr<const GarmentDelivery>{});std::lock_guard<std::mutex> l(mutex_);error_=e.what();}
  if(!style||!sample.queue)return;
  // The shared geometry may be unchanged while actual pelvis/leg poses move.
  // Copy only the small pose header; vertex buffers remain immutable/shared.
  auto posed=std::make_shared<RenderDelivery>();posed->epoch=input->epoch;posed->sequence=input->sequence;posed->vertices=input->vertices;posed->controls=input->controls;posed->pose=current;posed->poseSeconds=current.seconds;posed->garmentLobeCenters=input->garmentLobeCenters;posed->garmentLobeRadii=input->garmentLobeRadii;
  Request request{posed,Capsules(current),generation,restRevision,sample.activeSeconds};
  std::lock_guard<std::mutex> l(mutex_);if(stopping_||!style_||generation_!=generation)return;pending_=std::move(request);changed_.notify_one();
 }
 surface::Frame::GarmentSupport Support(unsigned epoch){std::lock_guard<std::mutex> l(mutex_);if(!style_)return {};auto d=std::atomic_load(&raw_);return d&&d->epoch==epoch&&d->generation==generation_?d->support:surface::Frame::GarmentSupport{};}
 std::shared_ptr<const GarmentDelivery> Latest()const{return std::atomic_load(&delivery_);}
 std::string Error(){std::lock_guard<std::mutex> l(mutex_);return error_;}
};
}
