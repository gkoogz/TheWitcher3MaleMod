#pragma once
#include <malemod/garments/jockstrap.hpp>
#include <filesystem>
#include <fstream>
#include <iomanip>

namespace malemod::witcher::garment_capture {
using namespace garments;
// Adapter diagnostic format: explicit fields avoid structure padding and retain
// the exact double-valued input supplied to the shared worker. Never Git data.
// This records inputs/output, not persistent cloth particles or prior history.
// A fitted-geometry replay cannot establish a dynamic-session replay.
inline void WriteInput(const std::filesystem::path& path,const Input& input){
 std::ofstream f(path,std::ios::binary);auto put=[&](const auto& x){f.write(reinterpret_cast<const char*>(&x),sizeof(x));};
 f.write("MMGFC006",8);const std::uint32_t donorCapacity=unsigned(Lineage{}.donors.size());put(donorCapacity);put(input.frame.origin);put(input.frame.lateral);put(input.frame.forward);put(input.frame.up);
 put(input.characterEpoch);put(input.topologyRevision);put(input.restRevision);put(input.gravity);put(input.deltaTime);
 for(const auto* samples:{&input.waist,&input.opening,&input.anatomy,&input.rearStraps[0],&input.rearStraps[1]}){std::uint32_t n=unsigned(samples->size());put(n);for(const auto& s:*samples){put(s.position);put(s.normal);for(const auto& d:s.lineage.donors){put(d.surface);put(d.vertex);put(d.weight);}}}
 std::uint32_t n=unsigned(input.anatomyTriangles.size());put(n);for(auto t:input.anatomyTriangles)put(t);
 n=unsigned(input.bodyContacts.size());put(n);for(auto c:input.bodyContacts){put(c.a);put(c.b);put(c.radius);}
 n=unsigned(input.bodySurface.size());put(n);for(const auto& s:input.bodySurface){put(s.position);put(s.normal);for(const auto& d:s.lineage.donors){put(d.surface);put(d.vertex);put(d.weight);}}
 n=unsigned(input.bodyTriangles.size());put(n);for(auto t:input.bodyTriangles)put(t);
 for(const auto& region:input.anatomyRegions){n=unsigned(region.size());put(n);for(auto id:region)put(id);}
 put(input.anatomyMass);
 if(!f)throw std::runtime_error("Cannot capture complete garment failure input");
}
inline Input ReadInput(const std::filesystem::path& path){
 std::ifstream f(path,std::ios::binary);auto get=[&](auto& x){if(!f.read(reinterpret_cast<char*>(&x),sizeof(x)))throw std::runtime_error("Incomplete garment failure input");};
 char magic[8];if(!f.read(magic,8))throw std::runtime_error("Incomplete garment failure header");
 const std::string version(magic,8);if(version!="MMGFC001"&&version!="MMGFC002"&&version!="MMGFC003"&&version!="MMGFC004"&&version!="MMGFC005"&&version!="MMGFC006")throw std::runtime_error("Unknown garment failure input");
 std::uint32_t donorCapacity=4;if(version=="MMGFC005"||version=="MMGFC006")get(donorCapacity);
 if(!donorCapacity||donorCapacity>Lineage{}.donors.size())throw std::runtime_error("Garment capture donor capacity exceeds shared contract");
 auto readSample=[&](Sample& s){get(s.position);get(s.normal);for(unsigned i=0;i<donorCapacity;i++){auto& d=s.lineage.donors[i];get(d.surface);get(d.vertex);get(d.weight);}};
 Input in;get(in.frame.origin);get(in.frame.lateral);get(in.frame.forward);get(in.frame.up);get(in.characterEpoch);get(in.topologyRevision);if(version!="MMGFC001")get(in.restRevision);get(in.gravity);get(in.deltaTime);
 for(auto* samples:{&in.waist,&in.opening,&in.anatomy,&in.rearStraps[0],&in.rearStraps[1]}){std::uint32_t n;get(n);if(n>100000)throw std::runtime_error("Garment capture sample budget");samples->resize(n);for(auto& s:*samples)readSample(s);}
 std::uint32_t n;get(n);if(n>100000)throw std::runtime_error("Garment capture face budget");in.anatomyTriangles.resize(n);for(auto& t:in.anatomyTriangles)get(t);
 get(n);if(n>64)throw std::runtime_error("Garment capture capsule budget");in.bodyContacts.resize(n);for(auto& c:in.bodyContacts){get(c.a);get(c.b);get(c.radius);}
 if(version=="MMGFC003"||version=="MMGFC004"||version=="MMGFC005"||version=="MMGFC006"){
  get(n);if(n>262144)throw std::runtime_error("Garment capture body surface budget");in.bodySurface.resize(n);for(auto& s:in.bodySurface)readSample(s);
  get(n);if(n>524288)throw std::runtime_error("Garment capture body face budget");in.bodyTriangles.resize(n);for(auto& t:in.bodyTriangles)get(t);
 }
 if(version=="MMGFC004"||version=="MMGFC005"||version=="MMGFC006"){
  std::vector<bool> assigned(in.anatomy.size());
  for(auto& region:in.anatomyRegions){get(n);if(n>in.anatomy.size())throw std::runtime_error("Garment capture tissue region budget");region.resize(n);for(auto& id:region){get(id);if(id>=in.anatomy.size()||assigned[id])throw std::runtime_error("Garment capture invalid or overlapping tissue region");assigned[id]=true;}}
 }
 if(version=="MMGFC006")get(in.anatomyMass);
 if(!std::isfinite(in.anatomyMass)||in.anatomyMass<0)throw std::runtime_error("Invalid captured generalized anatomy mass");
 if(f.peek()!=EOF)throw std::runtime_error("Trailing garment failure input");return in;
}
inline void WriteOutput(const std::filesystem::path& path,const Output& out){
 std::ofstream f(path);f<<std::setprecision(17);for(auto v:out.mesh.vertices)f<<"v "<<v.position[0]<<' '<<v.position[1]<<' '<<v.position[2]<<'\n';
 unsigned material=unsigned(-1);for(auto t:out.mesh.triangles){if(material!=unsigned(t.material)){material=unsigned(t.material);f<<"g material"<<material<<'\n';}f<<"f "<<t.vertices[0]+1<<' '<<t.vertices[1]+1<<' '<<t.vertices[2]+1<<'\n';}if(!f)throw std::runtime_error("Cannot capture garment failure geometry");
}
inline void WriteDiagnostics(const std::filesystem::path& path,const Input& in,const Output& out,std::uint64_t serial,double seconds){
 double minimum=1e100;unsigned triangle=unsigned(-1),capsule=unsigned(-1);Point cloth{},axis{};
 double faceDistance=1e100;unsigned bodyTriangle=unsigned(-1),bodyFaceClothTriangle=unsigned(-1),bodyVertex=unsigned(-1),classificationCaps=0;
 if(!in.bodySurface.empty()){
  detail::BodyCollider body;body.Update(in.bodySurface,in.bodyTriangles);
  auto closedFaces=in.bodyTriangles;auto caps=SurfaceCaps(in.bodySurface,in.bodyTriangles,out.measuredCircumference);closedFaces.insert(closedFaces.end(),caps.begin(),caps.end());
  classificationCaps=unsigned(caps.size());
  detail::BodyCollider membership;membership.Update(in.bodySurface,closedFaces);
  for(unsigned i=0;i<out.mesh.vertices.size();i++){auto hit=body.Closest(out.mesh.vertices[i].position);auto side=membership.Classify(out.mesh.vertices[i].position,true);if(side==detail::BodyCollider::Side::Indeterminate)throw std::runtime_error("Indeterminate captured closed body membership");double distance=side==detail::BodyCollider::Side::Inside?-hit.distance:side==detail::BodyCollider::Side::Boundary?0:hit.distance;if(distance<minimum){minimum=distance;bodyVertex=i;bodyTriangle=hit.triangle;cloth=out.mesh.vertices[i].position;axis=hit.point;}}
  for(unsigned i=0;i<out.mesh.triangles.size();i++){auto t=out.mesh.triangles[i];auto hit=body.ClosestFace({out.mesh.vertices[t.vertices[0]].position,out.mesh.vertices[t.vertices[1]].position,out.mesh.vertices[t.vertices[2]].position},out.measuredCircumference*.008*.3);if(hit.distance<faceDistance){faceDistance=hit.distance;bodyFaceClothTriangle=i;}}
 }else for(unsigned i=0;i<out.mesh.triangles.size();i++)for(unsigned j=0;j<in.bodyContacts.size();j++){auto t=out.mesh.triangles[i];Point p,q;double d=detail::TriangleCapsule(out.mesh.vertices[t.vertices[0]].position,out.mesh.vertices[t.vertices[1]].position,out.mesh.vertices[t.vertices[2]].position,in.bodyContacts[j],p,q,out.measuredCircumference*.008*.3);if(d<minimum){minimum=d;triangle=i;capsule=j;cloth=p;axis=q;}}
 const auto& physics=out.physics;
 std::ofstream materialProof(path.parent_path()/L"cloth-material-diagnostics.json");
 materialProof<<std::setprecision(17)<<"{\"materialBudgetSatisfied\":"<<(physics.materialBudgetSatisfied?"true":"false")<<",\"solverStretchRatio\":"<<physics.maxStretchRatio<<",\"fineSurfaceStretchRatio\":"<<physics.maxRenderStretchRatio<<",\"worstFineVertices\":["<<physics.worstRenderA<<','<<physics.worstRenderB<<"],\"clothSeamGap\":"<<physics.maxSeamGap<<",\"includesPersistentClothState\":false}\n";
 if(!materialProof)throw std::runtime_error("Cannot capture full fine-surface material diagnostic");
 std::ofstream bodyProof(path.parent_path()/L"body-contact-diagnostics.json");bodyProof<<std::setprecision(17)<<"{\"model\":\""<<(in.bodySurface.empty()?"capsule-fallback":"measured-body-surface")<<"\",\"bodyVertices\":"<<in.bodySurface.size()<<",\"bodyTriangles\":"<<in.bodyTriangles.size()<<",\"classificationOnlyCaps\":"<<classificationCaps<<",\"capsArePhysicalObstacles\":false,\"minimumVertexSignedDistance\":"<<minimum<<",\"minimumWholeFaceDistanceWithinMargin\":"<<faceDistance<<",\"worstBodyVertex\":"<<bodyVertex<<",\"worstBodyTriangle\":"<<bodyTriangle<<",\"worstClothFace\":"<<bodyFaceClothTriangle<<",\"requiredClearance\":"<<out.measuredCircumference*.008*.3<<"}\n";if(!bodyProof)throw std::runtime_error("Cannot capture actual body contact diagnostics");
 std::ofstream f(path);f<<std::setprecision(17)<<"{\"serial\":"<<serial<<",\"poseSeconds\":"<<seconds<<",\"restRevision\":"<<in.restRevision<<",\"includesPersistentClothState\":false,\"clothActive\":"<<(physics.active?"true":"false")<<",\"clothMaterialBudgetSatisfied\":"<<(physics.materialBudgetSatisfied?"true":"false")<<",\"clothAccumulatedSeconds\":"<<physics.accumulatedSeconds<<",\"clothStretchRatio\":"<<physics.maxStretchRatio<<",\"clothSeamGap\":"<<physics.maxSeamGap<<",\"contactBudgetSatisfied\":"<<(out.contactBudgetSatisfied?"true":"false")<<",\"projectedContacts\":"<<out.projectedContacts<<",\"circumference\":"<<out.measuredCircumference<<",\"requiredClearance\":"<<out.measuredCircumference*.008*.3<<",\"minimumSignedDistance\":"<<minimum<<",\"worstTriangle\":"<<triangle<<",\"worstCapsule\":"<<capsule<<",\"cloth\":["<<cloth[0]<<','<<cloth[1]<<','<<cloth[2]<<"],\"axis\":["<<axis[0]<<','<<axis[1]<<','<<axis[2]<<"]}\n";if(!f)throw std::runtime_error("Cannot capture garment failure diagnostics");
}
inline void Capture(const std::filesystem::path& dir,const Input& in,const Output& out,std::uint64_t serial,double seconds){
 std::filesystem::create_directories(dir);WriteInput(dir/L"first-failure.input",in);WriteOutput(dir/L"first-failure.obj",out);WriteDiagnostics(dir/L"first-failure.json",in,out,serial,seconds);
}
}
