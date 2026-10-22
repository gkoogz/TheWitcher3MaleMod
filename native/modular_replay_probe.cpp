#include "modular_render.hpp"
#include <malemod/surface/wire.hpp>
#include <iostream>
int main(int argc,char** argv){try{
 if(argc!=5&&argc!=7&&argc!=9&&argc!=10&&argc!=11&&argc!=12)throw std::invalid_argument("geometry native carrier source-wire [dynamic materials [transfer slider [output | shape output [hang]]]]");
 auto read=[](const char* path){std::ifstream f(path,std::ios::binary);if(!f)throw std::invalid_argument("Missing test input");return std::string((std::istreambuf_iterator<char>(f)),{});};
 const auto carrier=read(argv[3]),native=read(argv[2]),wire=read(argv[4]);
 malemod::witcher::RenderContract contract(argv[3],carrier.substr(8,40),carrier.substr(48,64));
 malemod::witcher::ModularRenderer renderer(argv[1],argv[2],contract,native.substr(8,64),native.substr(72,64));
 if(argc>=7){auto materials=read(argv[6]);renderer.EnableDynamic(argv[5],argv[6],materials.substr(8,64),materials.substr(72,64),materials.substr(136,64));}
 auto output=malemod::surface::wire::DecodeOutput({wire.begin(),wire.end()});
 double radians=0;if(argc>=9){renderer.EnableTransfer(argv[7],native.substr(8,64));double slider=std::stod(argv[8]);radians=(50-slider)/(slider<50?49.:50.)*(slider<50?45.:30.)*3.141592653589793/180.;}
 auto pivot=malemod::surface::Precise(output.shaftGuide[0]);std::shared_ptr<const malemod::surface::Output> shape;
 if(argc>=11){auto wire=read(argv[9]);shape=std::make_shared<const malemod::surface::Output>(malemod::surface::wire::DecodeOutput({wire.begin(),wire.end()}));}
 auto state=renderer.Drive(output,pivot,radians,shape,argc==12?std::stod(argv[11]):50.);
 if(argc>=11){using namespace malemod::surface;modular::Asset asset(argv[1]);auto plan=asset.MakePlan();modular::DynamicMount mount(argv[5]);auto rest=state;rest.frames=rest.shapeFrames;auto mesh=mount.Evaluate(asset,plan,rest);auto live=mount.Repose(mesh,asset,plan,state);std::vector<std::array<unsigned,3>> faces;for(auto f:mesh.surface.faces)faces.push_back({f[0].vertex,f[1].vertex,f[2].vertex});
 auto write=[&](const char* suffix,const auto& v){std::ofstream f(std::string(argv[10])+suffix,std::ios::binary);f.write(reinterpret_cast<const char*>(v.data()),v.size()*sizeof(v[0]));};
 auto restPoints=mount.Pose(asset,plan,rest,mesh.fitTranslation,mesh.advances,mesh.suspensionTranslation);
 for(auto c:mesh.moduleVertices){PresentationPoint p{};for(unsigned k=0;k<3;k++)p=Add(p,Scale(restPoints[asset.faces[c.parent][k]],c.donor[k]));auto d=Sub(p,mesh.surface.points[c.vertex]);if(Dot(d,d)>1e-12)throw std::runtime_error("Rebinding altered the zero-motion material shape");}
 if(!mesh.clearedBindings)throw std::runtime_error("Final cleared material has no physics stations");
 {auto points=mount.ClearedMaterial(asset,rest,mesh.advances);auto socket=modular::SocketMaterialState(rest,mesh.materialRoot);auto expected=modular::BindMaterialStations(*points,asset.bindings,socket.shapeFrames);
 for(unsigned i=0;i<expected.size();i++)for(unsigned k=0;k<2;k++){auto a=expected[i].influences[k],b=mesh.clearedBindings->at(i).influences[k];if(a.frame!=b.frame||std::abs(a.weight-b.weight)>1e-12)throw std::runtime_error("Clearance retained stale material ownership");}
 auto moving=mount.Pose(asset,plan,state,mesh.fitTranslation,mesh.advances,mesh.suspensionTranslation,mesh.clearedBindings,mesh.materialRoot);
 for(auto id:mount.inner){auto d=Sub(moving[id],restPoints[id]);if(Dot(d,d)>1e-12)throw std::runtime_error("Live material motion moved the fixed socket rim");}}
 {auto cleared=restPoints;for(auto& p:cleared)p=Sub(p,mesh.fitTranslation);auto bindings=modular::BindMaterialStations(cleared,asset.bindings,state.shapeFrames);
 std::ofstream trace(std::string(argv[10])+"-root-bindings.json");trace<<"[";bool first=true;
 for(auto id:mount.inner){if(!first)trace<<",";first=false;auto old=state.materialBindings->at(id),fresh=bindings[id];
 trace<<"{\"vertex\":"<<id<<",\"beforeStation\":"<<old.influences[0].frame+old.influences[1].weight<<",\"clearedStation\":"<<fresh.influences[0].frame+fresh.influences[1].weight<<",\"advance\":"<<mesh.advances[id]<<"}";}trace<<"]";}
 auto supported=rest;for(unsigned i=13;i<15;i++)supported.frames[i].origin=Add(supported.frames[i].origin,Add(mesh.fitTranslation,mesh.suspensionTranslation));
 auto error=plan.SuspensionRestOffset(restPoints,supported);if(Dot(error,error)>1e-12)throw std::runtime_error("Suspended equilibrium is not under the final cleared rim");
 write("-posed-module.bin",mount.Pose(asset,plan,state,mesh.fitTranslation,mesh.advances,mesh.suspensionTranslation));
  {auto raw=mount.Pose(asset,plan,state,mesh.fitTranslation,mesh.advances,mesh.suspensionTranslation,mesh.clearedBindings,mesh.materialRoot,false);write("-smooth-module.bin",raw);auto relief=asset.Relieve(raw,state);std::ofstream report(std::string(argv[10])+"-skin.json");report<<"{\"amplitude\":"<<relief.amplitude<<",\"maximum\":"<<relief.maximumDisplacement<<",\"attempted\":"<<relief.attemptedMaximum<<",\"limitingFace\":["<<relief.limitingFace[0]<<","<<relief.limitingFace[1]<<","<<relief.limitingFace[2]<<"]}";}
 {auto input=*shape;root_articulation::Rotation rotation(pivot,{1,0,0},{0,0,1},radians);for(auto* guide:{&input.shaftGuide,&input.restGuide})for(auto& p:*guide){auto v=rotation.Apply(Precise(p));p={float(v[0]),float(v[1]),float(v[2])};}auto material=modular::DrivenState(asset.reference,asset.dimensions,input);modular::SurfaceTransfer transfer(argv[7]);transfer.Apply(asset,plan,material,input,[&](auto p){return rotation.Apply(p);},true,true);auto points=plan.Evaluate(material);write("-before-straight.bin",points);write("-material-frames.bin",material.frames);}
 write("-points.bin",live);write("-faces.bin",faces);write("-material.bin",*state.shaftMaterial);write("-frames.bin",state.frames);write("-shape-frames.bin",state.shapeFrames);write("-asset-faces.bin",asset.faces);std::vector<unsigned> rings;for(auto row:mesh.surface.rings)rings.insert(rings.end(),row.begin(),row.end());write("-rings.bin",rings);
 write("-root-tangents.bin",mesh.surface.firstTangents);
 write("-body-displacements.bin",mesh.surface.bodyDisplacements);
 std::vector<unsigned> domains;for(auto f:mesh.surface.faces)domains.push_back(f[0].domain);write("-face-domains.bin",domains);
 std::ofstream meta(std::string(argv[10])+"-mesh.json");meta<<"{\"rows\":"<<mesh.surface.rings.size()<<",\"knots\":"<<mesh.surface.rings[0].size()<<",\"anchor\":["<<mesh.anchor[0]<<","<<mesh.anchor[1]<<","<<mesh.anchor[2]<<"]}";
 }auto first=renderer.Evaluate(state);auto moved=state;moved.frames[13].origin[2]-=.4;auto next=renderer.Evaluate(moved);
 if(argc>=10){
  const auto outputPrefix=std::string(argv[argc==10?9:10]);
  // Export actual packed corner attributes and topology: positional welds alone
  // cannot expose a UV or tangent-space discontinuity at a material boundary.
  std::ofstream attributes(outputPrefix+"-native-attributes.bin",std::ios::binary);
  std::ofstream triangles(outputPrefix+"-native-triangles.bin",std::ios::binary);
  std::ofstream secondary(outputPrefix+"-native-secondary.bin",std::ios::binary);
  unsigned offset=0;
  for(const auto& part:first->parts)if(part.lod==0){const auto& resource=contract.resources[part.resource];
   for(const auto& vertex:part.vertices){
    std::array<double,3> position;for(unsigned k=0;k<3;k++)position[k]=vertex.position[k]*resource.scale[k]+resource.bias[k];
    attributes.write(reinterpret_cast<const char*>(position.data()),sizeof(position));
    attributes.write(reinterpret_cast<const char*>(&vertex.normal),4);attributes.write(reinterpret_cast<const char*>(&vertex.tangent),4);
    attributes.write(reinterpret_cast<const char*>(vertex.uv.data()),4);
    secondary.write(reinterpret_cast<const char*>(vertex.reflection.data()),4);secondary.write(reinterpret_cast<const char*>(&vertex.color),4);
   }
   for(auto index:*part.indices){auto value=index+offset;triangles.write(reinterpret_cast<const char*>(&value),4);}
   offset+=unsigned(part.vertices.size());
  }
  std::ofstream dump(outputPrefix+"-native-shading.bin",std::ios::binary);
  for(const auto& part:first->parts)if(part.lod==0){const auto& resource=contract.resources[part.resource];for(const auto& vertex:part.vertices){
   std::array<double,3> position;for(unsigned k=0;k<3;k++)position[k]=vertex.position[k]*resource.scale[k]+resource.bias[k];
   dump.write(reinterpret_cast<const char*>(position.data()),sizeof(position));dump.write(reinterpret_cast<const char*>(&vertex.normal),4);dump.write(reinterpret_cast<const char*>(&vertex.tangent),4);
  }}
 }
 unsigned changed=0,unchanged=0;
 for(unsigned i=0;i<4;i++){
  const auto& a=first->parts[i];const auto& b=next->parts[i];if(a.vertices.empty()||a.indices!=b.indices)throw std::runtime_error("Mutable or missing native topology");
  for(unsigned j=0;j<a.vertices.size();j++){if(a.vertices[j].position!=b.vertices[j].position)++changed;else ++unchanged;}
 }
 if(!changed||!unchanged)throw std::runtime_error("Mechanical objects not independently driven");
 // Physics may bend a proximal guide while the control/rest aperture stays
 // fixed. Rebuilding indices here would recut the body every simulation step.
 auto bent=state;bent.frames[2].origin[2]+=.1;
 const auto physical=renderer.Evaluate(bent);
 for(unsigned i=0;i<4;i++)if(physical->parts[i].indices!=first->parts[i].indices)throw std::runtime_error("Physics motion rebuilt the pelvic opening");
 if(shape){
  auto pulseOutput=output;pulseOutput.proximalRadius*=1.15f;pulseOutput.restLength*=1.08f;
  auto pulse=renderer.Drive(pulseOutput,pivot,radians,shape,argc==12?std::stod(argv[11]):50.);
  auto frame=renderer.Evaluate(pulse);unsigned changes=0;
  for(unsigned i=0;i<4;i++){
   if(frame->parts[i].indices!=first->parts[i].indices)throw std::runtime_error("Transient pulse rebuilt topology");
   for(unsigned j=0;j<frame->parts[i].vertices.size();j++)changes+=frame->parts[i].vertices[j].position!=first->parts[i].vertices[j].position;
  }
  if(!changes)throw std::runtime_error("Pulse strain never reached native vertices");
 }
 if(argc>=9){
  auto altered=output;for(auto& p:altered.anatomy.positions)if(p.x>30)p.z+=.03;
  auto alteredState=renderer.Drive(altered,pivot,radians);auto changedSurface=renderer.Evaluate(alteredState);bool saw=false;
  for(unsigned i=0;i<4;i++){
   const auto& a=first->parts[i];const auto& b=changedSurface->parts[i];
   saw|=a.vertices.size()!=b.vertices.size()||a.indices!=b.indices;
   for(unsigned j=0;j<(std::min)(a.vertices.size(),b.vertices.size());j++)saw|=a.vertices[j].position!=b.vertices[j].position;
  }
  if(!saw)throw std::runtime_error("Solver shape changes did not reach retained surface");
 }
 std::cout<<"{\"changedVertices\":"<<changed<<",\"unchangedVertices\":"<<unchanged<<",\"evaluationMs\":"<<first->milliseconds<<",\"cachedEvaluationMs\":"<<next->milliseconds<<",\"nativeObserved\":false}\n";
 return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
