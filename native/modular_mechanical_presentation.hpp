#pragma once
#include "modular_render.hpp"
namespace malemod::witcher {
// Fresh compact mechanics deforms an immutable completed attachment. Full
// contact fitting/layout continues independently and replaces this reference.
inline void ReposePreparedRoot(const ModularControlTopology& topology,surface::PresentationPoint shaftAxis,
 std::vector<surface::PresentationPoint>& points,TaskArena& arena){
 surface::ReposeRootRamp(points,topology.rootRings,topology.rootFirstTangents,topology.rootAnchor,topology.rootAxis,shaftAxis,
  [&](unsigned,unsigned i){return std::make_pair(topology.rootEntryPoints.at(i),topology.rootEntryNormals.at(i));},&arena);
}
inline std::shared_ptr<const ModularFrame> PresentMechanical(
 const ModularFrame& input,const surface::Output& source,const ModularRenderer& renderer,
 const RenderContract& contract){
 using namespace surface;auto& arena=ModularPresentationArena();
 using Clock=std::chrono::steady_clock;auto mark=Clock::now();std::array<double,6> timings{};
 auto elapsed=[&](unsigned i){auto now=Clock::now();timings[i]=std::chrono::duration<double,std::milli>(now-mark).count();mark=now;};
 if(!input.controlTopology)throw std::runtime_error("Missing prepared mechanical topology");
 const auto& topology=*input.controlTopology;auto state=renderer.DriveMotion(source,input);
 auto fitted=state.shaftMaterial?modular::SocketMaterialState(state,input.materialRoot):state;
 PreparedMotionFrames frames{};std::array<PresentationPoint,17> scale;
 for(auto& s:scale)s={1,1,1};
 for(unsigned i=1;i<15;i++){
  frames[i]=i<=12?fitted.frames[i]:state.frames[i];frames[i].origin=Add(frames[i].origin,input.fitTranslation);
  if(i>=13)frames[i].origin=Add(frames[i].origin,input.lobeTranslation);
  for(unsigned k=0;k<3;k++)scale[i][k]=i<=12?state.materialScale[k]/input.driveState.materialScale[k]:state.scales[i][k]/input.driveState.scales[i][k];
 }
 const auto rim=SuspensionAttachmentFrames({state.shapeFrames[13],state.shapeFrames[14]},input.restLobeAnchors,
  {Precise(source.lobeAnchors[0]),Precise(source.lobeAnchors[1])});
 const auto shared=SuspensionEnvelopeFrames({state.shapeFrames[13],state.shapeFrames[14]},input.restLobeAnchors,
  {state.frames[13].origin,state.frames[14].origin},{Precise(source.lobeAnchors[0]),Precise(source.lobeAnchors[1])});
 frames[15]=shared[0];frames[16]=rim[0];
 for(unsigned i=15;i<17;i++){frames[i].origin=Add(frames[i].origin,Add(input.fitTranslation,input.lobeTranslation));scale[i]=scale[13];}
 PreparedMotionPlan motion(input.motionFrames,frames,scale);
 const auto& before=input.controlPoints;auto after=motion.Evaluate(before,topology.motion,&arena);
 DeformLiveControlDonors(topology.bodyDonors,before,after);
 TransportPreparedMotionLofts(motion,topology.motion,topology.lofts,input.controlTangents,before,after,0,topology.rootLoftStart,&arena);
 ReposePreparedRoot(topology,fitted.frames[1].basis[0],after,arena);
 DeformLiveControlDonors(topology.compoundDonors,before,after);
 TransportPreparedMotionLofts(motion,topology.motion,topology.lofts,input.controlTangents,before,after,topology.compoundLoftStart,unsigned(topology.lofts.size()),&arena);
 elapsed(0);
 elapsed(1);
 PreparedMotionCorrection correction;
 // Rotating a local material normal does not include gradients of spatial
 // skin weights or of the sewn loft. Its sign is not an inversion predicate.
 // Keep the area guard; actual self-contact is audited on captured geometry.
 try{ValidatePreparedMotionAreas(after,topology.faces,*input.motionFaceNormals,&arena);}
 catch(...){if(const char* prefix=std::getenv("MALEMOD_COMPOUND_FAILURE_PREFIX")){
  std::vector<PresentationPoint> expectedNormals(topology.faces.size());
  arena.For(unsigned(topology.faces.size()),[&](unsigned i){PreparedMotionWeights weights{};auto f=topology.faces[i];for(auto id:f)AddMotionWeights(weights,topology.motion[id],1./3);expectedNormals[i]=motion.Normal(input.motionFaceNormals->at(i),weights);});
  std::ofstream f(std::string(prefix)+"-mechanical.bin",std::ios::binary);std::array<unsigned,2> n{unsigned(before.size()),unsigned(topology.faces.size())};f.write(reinterpret_cast<const char*>(n.data()),8);f.write(reinterpret_cast<const char*>(before.data()),before.size()*24);f.write(reinterpret_cast<const char*>(after.data()),after.size()*24);f.write(reinterpret_cast<const char*>(topology.faces.data()),topology.faces.size()*12);
  auto proposed=motion.Evaluate(before,topology.motion,&arena);
  DeformLiveControlDonors(topology.bodyDonors,before,proposed);TransportPreparedMotionLofts(motion,topology.motion,topology.lofts,input.controlTangents,before,proposed,0,topology.rootLoftStart,&arena);ReposePreparedRoot(topology,fitted.frames[1].basis[0],proposed,arena);
  DeformLiveControlDonors(topology.compoundDonors,before,proposed);TransportPreparedMotionLofts(motion,topology.motion,topology.lofts,input.controlTangents,before,proposed,topology.compoundLoftStart,unsigned(topology.lofts.size()),&arena);
  f.write(reinterpret_cast<const char*>(expectedNormals.data()),expectedNormals.size()*24);
  f.write(reinterpret_cast<const char*>(proposed.data()),proposed.size()*24);
  f.write(reinterpret_cast<const char*>(topology.motion.data()),topology.motion.size()*17*8);
  auto write=[&](const auto& data){f.write(reinterpret_cast<const char*>(data.data()),data.size()*sizeof(data[0]));};
  std::array<unsigned,4> counts{unsigned(topology.lofts.size()),topology.compoundLoftStart,unsigned(topology.bodyDonors.size()),unsigned(topology.compoundDonors.size())};write(counts);
  write(topology.lofts);write(input.controlTangents);write(input.motionFrames);write(frames);write(scale);write(topology.bodyDonors);write(topology.compoundDonors);
 }throw;}
 elapsed(2);
 if(!input.motionNormals)throw std::runtime_error("Missing prepared mechanical normal field");
 std::vector<unsigned> movingVisible;movingVisible.reserve(topology.visiblePoints.size());
 for(auto id:topology.visiblePoints)if(before[id]!=after[id])movingVisible.push_back(id);
 const auto& normalsBefore=*input.motionNormals;auto normalsAfter=topology.normals->FieldSubset(after,movingVisible,&arena);
 std::vector<PresentationPoint> axis(before.size());std::vector<double> cosine(before.size(),1);
 arena.For(unsigned(movingVisible.size()),[&](unsigned index){auto i=movingVisible[index];{
  motion.Normal(normalsBefore[i],topology.motion[i]); // Reject a singular local material blend.
  auto a=contract.calibration.VectorToTarget(normalsBefore[i]),b=contract.calibration.VectorToTarget(normalsAfter[i]);cosine[i]=std::clamp(Dot(a,b),-1.,1.);axis[i]=Cross(a,b);
  if(cosine[i]<-.9999){axis[i]=Cross(a,PresentationPoint{1,0,0});if(Dot(axis[i],axis[i])<1e-6)axis[i]=Cross(a,PresentationPoint{0,1,0});axis[i]=Unit(axis[i]);}
 }});
 elapsed(3);
 auto unpack=[](unsigned v){return PresentationPoint{double(v&1023)/511.5-1,double((v>>10)&1023)/511.5-1,double((v>>20)&1023)/511.5-1};};
 auto pack=[](PresentationPoint p,unsigned old){p=Unit(p);unsigned word=old&0xc0000000u;for(unsigned k=0;k<3;k++)word|=unsigned(std::clamp((p[k]+1)*.5,0.,1.)*1023+.5)<<(10*k);return word;};
 auto out=std::make_shared<ModularFrame>(input);
 elapsed(4);
 out->mechanicalCorrection=correction;
 // Shade each geometric normal and UV tangent alias once. Native resources
 // and LODs share these values; their palette/UV/color bytes remain untouched.
 if(!input.motionPackedNormals||!input.motionPackedTangents)throw std::runtime_error("Missing prepared shading aliases");
 std::vector<PresentationPoint> positions(before.size()),normals(before.size());
 auto packedNormals=*input.motionPackedNormals,packedTangents=*input.motionPackedTangents;
 auto direction=[&](unsigned id,PresentationPoint p){if(cosine[id]<-.9999)return Sub(Scale(axis[id],2*Dot(axis[id],p)),p);return Add(Add(p,Cross(axis[id],p)),Scale(Cross(axis[id],Cross(axis[id],p)),1/(1+cosine[id])));};
 arena.For(unsigned(movingVisible.size()),[&](unsigned index){auto id=movingVisible[index];positions[id]=contract.calibration.PointToTarget(after[id]);normals[id]=Unit(direction(id,unpack(packedNormals[id])));packedNormals[id]=pack(normals[id],packedNormals[id]);});
 arena.For(unsigned(topology.shadingPoints.size()),[&](unsigned i){auto id=topology.shadingPoints[i];if(before[id]==after[id])return;auto n=normals[id],t=direction(id,unpack(packedTangents[i]));t=Unit(Sub(t,Scale(n,Dot(t,n))));packedTangents[i]=pack(t,packedTangents[i]);});
 for(auto& part:out->parts){const auto& r=contract.resources[part.resource];
  arena.For(unsigned(part.vertices.size()),[&](unsigned i){auto id=part.controlVertices->at(i);if(before[id]==after[id])return;auto& v=part.vertices[i];
   for(unsigned k=0;k<3;k++)v.position[k]=float((positions[id][k]-r.bias[k])/r.scale[k]);
   v.normal=packedNormals[id];v.tangent=packedTangents[part.shadingVertices->at(i)];
  });
 }
 for(unsigned i=1;i<15;i++){out->frames[i]=frames[i];out->frames[i].origin=contract.calibration.PointToTarget(frames[i].origin);for(auto& v:out->frames[i].basis)v=contract.calibration.VectorToTarget(v);}
 PreparedMotionWeights tip{};tip[12]=1;
 auto p=contract.calibration.PointToSource(input.nozzle),d=contract.calibration.VectorToSource(input.nozzleDirection);auto np=motion.Point(p,tip);
 out->nozzle=contract.calibration.PointToTarget(np);out->nozzleDirection=Unit(contract.calibration.VectorToTarget(Sub(motion.Point(Add(p,d),tip),np)));
 out->controlFrame.tip=motion.Point(input.controlFrame.tip,tip);
 out->controlFrame.lobes=Scale(Add(frames[13].origin,frames[14].origin),.5);
 out->controlPoints=std::move(after);out->motionFrames=frames;out->driveState=state;out->rimFrames=rim;
 out->envelopeFrames=shared;
 elapsed(5);out->mechanicalMilliseconds=timings;
 return out;
}
}
