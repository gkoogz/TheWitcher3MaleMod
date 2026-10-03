#include "render_service.hpp"
#include <iostream>
#include <set>
using namespace malemod::witcher;
namespace surface=malemod::surface;
static void Check(bool v,const char* s){if(!v)throw std::runtime_error(s);}
static void Boundary(const RenderContract& c,const std::vector<SourceRenderVertex>& v){
 std::map<unsigned,std::array<float,3>> points;std::map<std::pair<unsigned,unsigned>,std::array<float,3>> normals;
 std::map<unsigned,std::array<unsigned,104>> weights;unsigned count=0;
 for(const auto& l:c.lods)for(unsigned i=0;i<l.vertices.size();i++)if(auto k=l.vertices[i].boundary){
  const auto& row=v[l.firstVertex+i];auto p=points.emplace(k,row.position);Check(p.second||p.first->second==row.position,"Part/LOD positional waist opened");
  auto n=normals.emplace(std::make_pair(l.lod,k),row.normal);Check(n.second||n.first->second==row.normal,"Part shading waist differs");
  std::array<unsigned,104> w{};std::array<std::uint8_t,4> b{},amount{};std::memcpy(b.data(),&row.bones,4);std::memcpy(amount.data(),&row.weights,4);
  for(unsigned j=0;j<4;j++)w[c.nativeBones[b[j]]]+=amount[j];auto a=weights.emplace(k,w);Check(a.second||a.first->second==w,"Part/LOD named waist weight bytes differ");++count;
 }
 Check(points.size()>16&&count>=points.size()*4,"Missing common waist samples");
 for(const auto& l:c.lods){std::set<unsigned> knots;for(auto v:l.vertices)if(v.boundary)knots.insert(v.boundary);Check(knots.size()==points.size(),"A body part/LOD dropped a common waist knot");}
}
int wmain(int argc,wchar_t** argv){try{
 const surface::LightingFrame generic{{0,0,1},{0,1,0},-1},native{{0,0,1},{1,0,0},1};
 auto unchanged=TransportCookedLighting(generic,generic,native);
 Check(unchanged.normal==native.normal&&unchanged.tangent==native.tangent&&unchanged.sign==native.sign,"Static native UV tangent frame changed");
 auto rotated=TransportCookedLighting(generic,{{0,0,1},{1,0,0},-1},native);
 Check(rotated.normal==native.normal&&rotated.tangent==surface::LightingPoint{0,-1,0}&&rotated.sign==1,"Native tangent fails to follow geometric rotation");
 Check(argc==6,"Usage: body_render_test render worker binding pin bindingHash");std::wstring p=argv[4],h=argv[5];std::string pin(p.begin(),p.end()),hash(h.begin(),h.end());RenderContract c(argv[1],pin,hash);Check(c.resources.size()==2&&c.lods.size()==4,"Both resources/LODs required");
 // Restore native rest input exactly for every body/module alias and LOD.
 // This detects ULP loss from decoding then inversely quantizing float rest.
 std::vector<SourceRenderVertex> rest;
 for(const auto& lod:c.lods)for(const auto& native:lod.vertices){SourceRenderVertex row{};std::memcpy(&row.bones,native.bones.data(),4);std::memcpy(&row.weights,native.weights.data(),4);for(unsigned a=0;a<3;a++)row.position[a]=row.reference[a]=float(native.reference[a]);row.normal={0,0,1};row.tangent={1,0,0};row.sign=1;rest.push_back(row);}
 auto encodedRest=PrepareFloatVertices(rest,c);
 for(unsigned i=0;i<encodedRest.size();i++)Check(encodedRest[i].position==c.encodedReference[i],"Static native UNORM input changed");
 auto reference=PrepareMorphReference(c);Check(reference->size()==c.VertexCount(),"Native morph baseline omits aliases");for(const auto& lod:c.lods)for(unsigned i=0;i<lod.vertices.size();i++){const auto at=lod.firstVertex+i;Check(reference->at(at).position==c.encodedReference[at],"Morph reference position differs from observed native decode");Check(reference->at(at).boundary==lod.vertices[i].boundary,"Canonical waist alias lost its absolute morph publication");}
 SurfacePipeline pipeline(argv[2],argv[3],pin);pipeline.Initialize({});surface::wire::Request r;unsigned cases=0;
 SurfaceFrame frame;std::vector<SourceRenderVertex> neutral;double upperMaximum=0,waistMaximum=0;
 auto run=[&]{frame=pipeline.Evaluate(r);auto vertices=ComposeRenderVertices(c,frame.targetPositions);Boundary(c,vertices);if(neutral.empty())neutral=vertices;else if(r.controls.values[1]==100){double upper=0,waist=0;for(const auto& l:c.lods)if(l.resource==1)for(unsigned i=0;i<l.vertices.size();i++){auto j=l.firstVertex+i;double d=0;for(unsigned a=0;a<3;a++)d+=(vertices[j].position[a]-neutral[j].position[a])*(vertices[j].position[a]-neutral[j].position[a]);if(!l.vertices[i].calibration&&!l.vertices[i].boundary)upper=(std::max)(upper,std::sqrt(d));if(l.vertices[i].boundary)waist=(std::max)(waist,std::sqrt(d));}Check(upper>1e-5&&waist>1e-5,"Overall fails to recruit torso across waist");upperMaximum=(std::max)(upperMaximum,upper);waistMaximum=(std::max)(waistMaximum,waist);}auto serial=ComposeRenderVertices(c,frame.targetPositions,false);Check(!std::memcmp(vertices.data(),serial.data(),vertices.size()*sizeof(SourceRenderVertex)),"Parallel output differs");auto prepared=PrepareFloatVertices(vertices,c);Check(prepared.size()==c.VertexCount(),"Missing native rows");++cases;};
 run();for(unsigned control=0;control<18;control++)for(unsigned side=0;side<2;side++){r.controls={};r.controls.values[control]=control==0?float(side*2):(side?100.f:((control==2||control==4)?0.f:1.f));run();}
 r.controls={};for(unsigned i=1;i<18;i++)r.controls.values[i]=100;run();r.controls={};run();
 RenderPose pose;pose.epoch=1;pose.seconds=1;pose.actorWorld={1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1};pose.skinDeltas.assign(c.nativeBones.size(),pose.actorWorld);RenderService service(c);
 auto delivery=[&](std::uint64_t sequence,SurfaceFrame f){auto s=std::make_shared<CompletedSurface>();s->sequence=sequence;s->input=r;s->frame=std::move(f);auto d=std::make_shared<RuntimeDelivery>();d->surface=s;d->simulationSeconds=sequence/20.;return d;};
 service.Submit(delivery(1,frame),pose);auto wait=[&](unsigned seq){for(unsigned i=0;i<1000;i++){if(!service.Error().empty())throw std::runtime_error(service.Error());auto out=service.Latest();if(out&&out->sequence==seq)return out;std::this_thread::sleep_for(std::chrono::milliseconds(1));}throw std::runtime_error("Presentation timed out");};wait(1);
 std::this_thread::sleep_for(std::chrono::milliseconds(80));r.frame.seconds=.08f;r.frame.yawForce=10;auto changed=pipeline.Evaluate(r);service.Submit(delivery(2,changed),pose);std::set<double> phases;unsigned presented=0;auto started=std::chrono::steady_clock::now();
 while(std::chrono::steady_clock::now()-started<std::chrono::milliseconds(160)){auto out=wait(2);if(out->presentationPhase<1){phases.insert(out->presentationPhase);Boundary(c,*out->vertices);++presented;}std::this_thread::sleep_for(std::chrono::milliseconds(2));}
 Check(phases.size()>=3,"No intermediate material-frame cadence");
 r.controls.values[1]=100;auto edited=pipeline.Evaluate(r);service.Submit(delivery(3,edited),pose,true);auto paused=wait(3);Check(paused->presentationPhase==1&&paused->controls.values==r.controls.values,"Paused control edit mixes states");Boundary(c,*paused->vertices);
 pose.epoch=2;service.Submit(delivery(4,frame),pose);Check(wait(4)->presentationPhase==1,"Character epoch interpolates old geometry");
 std::set<unsigned> knots;for(auto v:c.lods[0].vertices)if(v.boundary)knots.insert(v.boundary);
 std::cout<<"PASS: "<<cases<<" full source cases; both separate body resources/LODs share "<<knots.size()<<" exact waist positions, named weight bytes and shading; parallel bytes match; "<<phases.size()<<" intermediate presentation phases; torso displacement "<<upperMaximum<<"; waist displacement "<<waistMaximum<<"; pause/control/epoch snap\n";
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
