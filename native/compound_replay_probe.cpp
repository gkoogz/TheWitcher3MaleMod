#include "modular_render.hpp"
#include "live_modular_controls.hpp"
#include <malemod/surface/wire.hpp>
#include <iostream>

// Replay the adapter's actual live/zero-motion pair. The older probe assumes
// a fixed shaft rim; this contract instead preserves the complete body surface
// while the root follows the accepted material-motion model.
int main(int argc,char** argv){try{
 if(argc!=11&&argc!=12)throw std::invalid_argument("geometry native carrier live dynamic materials transfer slider shape output-prefix [captured-state]");
 auto read=[](const char* path){std::ifstream f(path,std::ios::binary);if(!f)throw std::invalid_argument("Missing replay input");return std::string((std::istreambuf_iterator<char>(f)),{});};
 auto native=read(argv[2]),carrier=read(argv[3]),live=read(argv[4]),material=read(argv[6]),shapeBytes=read(argv[9]);
 using namespace malemod;using namespace surface;
 witcher::RenderContract contract(argv[3],carrier.substr(8,40),carrier.substr(48,64));
 witcher::ModularRenderer renderer(argv[1],argv[2],contract,native.substr(8,64),native.substr(72,64));
 renderer.EnableDynamic(argv[5],argv[6],material.substr(8,64),material.substr(72,64),material.substr(136,64));renderer.EnableTransfer(argv[7],native.substr(8,64));
 auto source=wire::DecodeOutput({live.begin(),live.end()});auto shape=std::make_shared<const Output>(wire::DecodeOutput({shapeBytes.begin(),shapeBytes.end()}));
 Controls authored;authored.values[7]=float(std::stod(argv[8]));
 auto pivot=Precise(shape->shaftGuide[0]);double radians=ControlAngle(std::stod(argv[8])),hang=50;
 if(argc==12){std::ifstream input(argv[11]);std::string error;std::getline(input,error);input>>radians;for(auto& x:pivot)input>>x;for(auto& x:authored.values)input>>x;if(!input)throw std::runtime_error("Invalid captured controls");hang=authored.values[6];}
 auto state=renderer.Drive(source,pivot,radians,shape,hang);
 if(std::getenv("MALEMOD_REPLAY_SUPPORT")){
  modular::Asset asset(argv[1]);auto plan=asset.MakePlan();modular::DynamicMount mount(argv[5]);CompoundDynamicPlan compound(mount.compoundData,asset,mount);
  auto geometry=modular::RestMaterialState(asset.bindings,state);
  auto support=mount.Evaluate(asset,plan,geometry);auto input=compound.PrepareSupport(support,asset,geometry);
  std::cerr<<"Support anchor "<<support.anchor[0]<<','<<support.anchor[1]<<','<<support.anchor[2]<<" authored "<<mount.origin[0]<<','<<mount.origin[1]<<','<<mount.origin[2]<<'\n';
  std::ofstream out(std::string(argv[10])+"-cut.bin",std::ios::binary);std::array<unsigned,3> n{unsigned(support.surface.points.size()),unsigned(input.faces.size()),unsigned(compound.reference.footprint.size())};out.write(reinterpret_cast<const char*>(n.data()),12);
  out.write(reinterpret_cast<const char*>(support.surface.points.data()),n[0]*24);out.write(reinterpret_cast<const char*>(input.faces.data()),n[1]*12);out.write(reinterpret_cast<const char*>(input.chart.data()),n[0]*16);for(bool b:input.eligible){unsigned char e=b;out.write(reinterpret_cast<const char*>(&e),1);}out.write(reinterpret_cast<const char*>(compound.reference.footprint.data()),n[2]*16);
  std::ofstream supportRings(std::string(argv[10])+"-support-rings.bin",std::ios::binary);std::array<unsigned,2> ringDimensions{unsigned(support.surface.rings.size()),unsigned(support.surface.rings.front().size())};supportRings.write(reinterpret_cast<const char*>(ringDimensions.data()),8);for(auto& ring:support.surface.rings)supportRings.write(reinterpret_cast<const char*>(ring.data()),ring.size()*4);
  std::ofstream supportDomains(std::string(argv[10])+"-support-domains.bin",std::ios::binary);for(auto face:support.surface.faces){unsigned char d=face[0].domain;supportDomains.write(reinterpret_cast<const char*>(&d),1);}
  auto posed=mount.Pose(asset,plan,geometry,support.fitTranslation,support.advances,support.suspensionTranslation,support.clearedBindings,support.materialRoot);
  std::ofstream stages(std::string(argv[10])+"-source-stages.bin",std::ios::binary);
  unsigned sourceCount=unsigned(compound.sourceVertices.size());stages.write(reinterpret_cast<const char*>(&sourceCount),4);
  for(auto id:compound.sourceVertices){for(auto p:{asset.rest[id],state.shaftMaterial?state.shaftMaterial->at(id):asset.rest[id],modular::Point(asset.bindings[id],geometry),posed[id]})stages.write(reinterpret_cast<const char*>(p.data()),24);}
  auto cache=compound.Build(support,asset,geometry,posed);
  auto writeMesh=[&](const std::string& suffix,const std::vector<PresentationPoint>& points){std::ofstream file(std::string(argv[10])+suffix);file.precision(17);for(auto p:points)file<<"v "<<p[0]<<' '<<p[1]<<' '<<p[2]<<'\n';for(auto f:cache.faces)file<<"f "<<f[0].vertex+1<<' '<<f[1].vertex+1<<' '<<f[2].vertex+1<<'\n';};
  writeMesh("-rest.obj",cache.rest);
  std::vector<PresentationPoint> trace;cache.graft->Evaluate(cache.SourceDifferentialPoints(compound.Source(posed,geometry)),cache.DifferentialPoints(support.surface.points),&trace);
  auto simple=cache.rest;for(unsigned row=0;row<cache.rings.size();row++)for(unsigned col=0;col<cache.rings[row].size();col++)simple[cache.rings[row][col]]=trace[row*cache.rings[row].size()+col];writeMesh("-hermite.obj",simple);
  std::ofstream ringFile(std::string(argv[10])+"-rings.bin",std::ios::binary);std::array<unsigned,2> dimensions{unsigned(cache.rings.size()),unsigned(cache.rings[0].size())};ringFile.write(reinterpret_cast<const char*>(dimensions.data()),8);for(auto& ring:cache.rings)ringFile.write(reinterpret_cast<const char*>(ring.data()),ring.size()*4);
  std::ofstream domains(std::string(argv[10])+"-domains.bin",std::ios::binary);for(auto f:cache.faces){unsigned char domain=f[0].domain;domains.write(reinterpret_cast<const char*>(&domain),1);}
  std::vector<PresentationPoint> liveAsset;auto liveSupport=mount.Repose(support,asset,plan,state,nullptr,nullptr,nullptr,&liveAsset);
  auto liveSourceFrames=cache.SourceDifferentialPoints(compound.Source(liveAsset,state)),liveSupportFrames=cache.DifferentialPoints(liveSupport);
  std::vector<PresentationPoint> firstHandle,lastHandle;
  cache.graft->Evaluate(liveSourceFrames,liveSupportFrames,nullptr,&firstHandle,&lastHandle);
  std::ofstream differentialFile(std::string(argv[10])+"-differentials.bin",std::ios::binary);
  unsigned columns=unsigned(firstHandle.size());differentialFile.write(reinterpret_cast<const char*>(&columns),4);
  for(const auto* field:{&liveSourceFrames,&liveSupportFrames,&firstHandle,&lastHandle})differentialFile.write(reinterpret_cast<const char*>(field->data()),field->size()*24);
  writeMesh("-posed.obj",cache.Evaluate(compound.Source(liveAsset,state),liveSupport));
  std::cerr<<"Root scale "<<geometry.scales[1][1]/asset.reference.scales[1][1]<<"\n";
 }
 auto first=renderer.Evaluate(state);auto moving=state;moving.frames[13].origin[2]-=.4;auto second=renderer.Evaluate(moving);
 unsigned changed=0,fixed=0;
 for(unsigned i=0;i<4;i++){auto& a=first->parts[i];auto& b=second->parts[i];if(a.vertices.empty()||a.indices!=b.indices)throw std::runtime_error("Physics rebuilt or lost native topology");
  for(unsigned j=0;j<a.vertices.size();j++){for(auto x:a.vertices[j].position)if(!std::isfinite(x))throw std::runtime_error("Nonfinite native position");if(a.vertices[j].position!=b.vertices[j].position)changed++;else fixed++;}}
 if(!changed||!fixed)throw std::runtime_error("Suspended and retained regions are not independent");
 if(first->controlTopology->lofts.size()!=first->controlTangents.size())throw std::runtime_error("Live-control differential count differs");
 if(std::getenv("MALEMOD_REPLAY_CONTROLS"))for(unsigned control:{3u,6u,7u}){
  auto requested=authored;requested.values[control]+=requested.values[control]>=100?-1:1;
  auto displayed=witcher::PresentLiveControls(first,authored,requested,contract);
  if(displayed==first)throw std::runtime_error("Live-control edit was ignored");
  for(unsigned part=0;part<4;part++)if(displayed->parts[part].indices!=first->parts[part].indices)throw std::runtime_error("Live control rebuilt native topology");
  std::cerr<<"Live control "<<control<<" advanced\n";
 }
 std::ofstream attrs(std::string(argv[10])+"-native-attributes.bin",std::ios::binary),triangles(std::string(argv[10])+"-native-triangles.bin",std::ios::binary);unsigned offset=0;
 for(auto& part:first->parts)if(part.lod==0){const auto& resource=contract.resources[part.resource];for(auto& v:part.vertices){std::array<double,3> p;for(unsigned k=0;k<3;k++)p[k]=v.position[k]*resource.scale[k]+resource.bias[k];attrs.write(reinterpret_cast<const char*>(p.data()),24);attrs.write(reinterpret_cast<const char*>(&v.normal),4);attrs.write(reinterpret_cast<const char*>(&v.tangent),4);attrs.write(reinterpret_cast<const char*>(v.uv.data()),4);}for(auto i:*part.indices){i+=offset;triangles.write(reinterpret_cast<const char*>(&i),4);}offset+=unsigned(part.vertices.size());}
 std::cout<<"{\"changedVertices\":"<<changed<<",\"fixedVertices\":"<<fixed<<",\"buildMs\":"<<first->milliseconds<<",\"poseMs\":"<<second->milliseconds<<",\"nativeGameObserved\":false}\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
