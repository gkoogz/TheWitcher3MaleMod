#include "surface_transport.hpp"
#include "modular_render.hpp"
#include "modular_mechanical_presentation.hpp"
#include "modular_service.hpp"
#include "fixed_collar_angle.hpp"
#include <iostream>
#include <iomanip>
int wmain(int argc,wchar_t** argv){try{
 using namespace malemod;using namespace witcher;
 if(argc<3||argc>5)throw std::runtime_error("Usage: modular_cadence_probe native-package output-directory [worker] [full|mechanical|retained|presentation]");
 const std::filesystem::path dir=argv[1],out=argv[2];std::filesystem::create_directories(out);
 const auto workerPath=argc>=4?std::filesystem::path(argv[3]):dir/"surface_worker.exe";
 const std::wstring mode=argc==5?argv[4]:L"full";
 const bool held=mode==L"presentation-held-walk",materialAudit=mode==L"material-audit",walk=mode==L"presentation-walk"||held,presentation=mode==L"presentation"||walk||materialAudit;
 if(mode!=L"full"&&mode!=L"mechanical"&&mode!=L"retained"&&!presentation)throw std::runtime_error("Unknown worker mode");
 auto read=[](auto p){std::ifstream f(p,std::ios::binary);if(!f)throw std::runtime_error("Missing input");return std::string(std::istreambuf_iterator<char>(f),{});};
 auto c=read(dir/"geralt.render"),n=read(dir/"geralt.modular-native"),m=read(dir/"geralt.modular-materials");
 RenderContract contract(dir/"geralt.render",c.substr(8,40),c.substr(48,64));
 ModularRenderer renderer(dir/"geralt.modular",dir/"geralt.modular-native",contract,n.substr(8,64),n.substr(72,64));
 renderer.EnableDynamic(dir/"geralt.modular-dynamic",dir/"geralt.modular-materials",m.substr(8,64),m.substr(72,64),m.substr(136,64));
 renderer.EnableTransfer(dir/"geralt.modular-transfer",n.substr(8,64));
 std::ofstream report(out/"timings.jsonl");report<<std::setprecision(12);
 using Clock=std::chrono::steady_clock;
 auto ms=[](auto a,auto b){return std::chrono::duration<double,std::milli>(b-a).count();};
 for(unsigned test=0;test<6;test++){
  const char* exactControls=std::getenv("MALEMOD_CADENCE_CONTROLS");
  if(exactControls&&test)continue;
  if(walk&&test%3!=2)continue;
  surface::Controls controls;controls.values[0]=float(test%3);
  if(test>=3)for(unsigned i:{1u,2u,3u,5u})controls.values[i]=90;
  double requestedAngle=test>=3?15:50;
  if(exactControls){std::ifstream input(exactControls);for(auto& value:controls.values)input>>value;if(!input)throw std::runtime_error("Invalid cadence controls");requestedAngle=controls.values[7];}
  controls.values[7]=FixedCollarReferenceAngle;
  if(materialAudit){auto trace=out/("source-"+std::to_string(test));std::filesystem::create_directories(trace);_putenv_s("MALEMOD_SOURCE_TRACE_DIRECTORY",trace.string().c_str());}
  SurfaceClient worker(workerPath.wstring());auto initial=worker.Initialize(controls);
  auto shape=std::make_shared<const surface::Output>(initial);
  if(walk)for(unsigned step=0;step<1080;step++){surface::wire::Request settle;settle.controls=controls;settle.frame.seconds=1.f/60;worker.EvaluateMechanical(settle,10000);}
  {
   auto materialSurface=std::make_shared<CompletedSurface>(),numericSurface=std::make_shared<CompletedSurface>();
   materialSurface->sequence=3;materialSurface->input.controls=controls;materialSurface->frame.modularShape=shape;
   numericSurface->sequence=8;numericSurface->input.controls=controls;numericSurface->frame.source.restLength=123;
   auto material=std::make_shared<RuntimeDelivery>(),numeric=std::make_shared<RuntimeDelivery>();material->surface=materialSurface;numeric->surface=numericSurface;numeric->simulationSeconds=2;
   auto joined=MechanicalWithPreparedMaterial(material,numeric);
   if(joined->surface->sequence!=8||joined->simulationSeconds!=2||joined->surface->frame.modularShape!=shape||joined->surface->frame.source.restLength!=123)throw std::runtime_error("Prepared geometry followed stale mechanics");
   numericSurface->input.controls.values[3]+=1;
   if(MechanicalWithPreparedMaterial(material,numeric)!=material)throw std::runtime_error("New mechanics mixed with another shape control state");
  }
  std::shared_ptr<const ModularFrame> prepared;
  const unsigned frameCount=materialAudit?1:walk?360:40;
  for(unsigned frame=0;frame<frameCount;frame++){
   surface::wire::Request q;q.controls=controls;q.frame.seconds=1.f/60;
   q.frame.pitchForce=float(std::sin(frame*.2)*.6);q.frame.yawForce=float(std::cos(frame*.17)*.3);
   if(walk){q.frame.pitchForce=float(std::sin(frame*.2)*1.36);q.frame.yawForce=float(std::cos(frame*.17)*2.2);}
   auto start=Clock::now();auto source=mode==L"mechanical"||presentation?worker.EvaluateMechanical(q,10000):mode==L"retained"?worker.EvaluateRetainedSkin(q,10000):worker.Evaluate(q,10000);auto solved=Clock::now();
   const auto pivot=surface::Precise(source.shaftGuide[0]);FixedAngleRegion region;region.origin=pivot;region.upwardDegrees=45;
   const double angle=requestedAngle;
   PresentFixedCollarSource(source,float(angle),region);
   auto state=renderer.Drive(source,pivot,FixedCollarFlow(region,float(angle)).Radians(),shape,controls.values[6]);auto driven=Clock::now();
   if(presentation&&(frame==0||(!held&&frame%10==0)))prepared=renderer.Evaluate(state);
   if(materialAudit&&frame==0){
    auto dump=[&](std::string label,const auto& points,const auto& faces){std::ofstream f(out/(label+"-"+std::to_string(test)+".obj"));f<<std::setprecision(17);for(auto p:points)f<<"v "<<p[0]<<' '<<p[1]<<' '<<p[2]<<'\n';for(auto t:faces)f<<"f "<<t[0]+1<<' '<<t[1]+1<<' '<<t[2]+1<<'\n';};
    surface::modular::Asset authored(dir/"geralt.modular");
    std::vector<std::array<unsigned,3>> shaftFaces;for(auto f:authored.faces){bool shaft=true;for(auto id:f)shaft&=surface::modular::ShaftBinding(authored.bindings[id]);if(shaft)shaftFaces.push_back(f);}
    dump("authored-shaft",authored.rest,shaftFaces);
    if(state.shaftMaterial)dump("material-shaft",*state.shaftMaterial,shaftFaces);
    dump("authored",authored.rest,authored.faces);
    if(state.shaftMaterial)dump("material",*state.shaftMaterial,authored.faces);
    std::ofstream frames(out/("material-frames-"+std::to_string(test)+".txt"));frames<<std::setprecision(17);
    for(unsigned j=1;j<=12;j++){for(auto x:state.shapeFrames[j].origin)frames<<x<<' ';for(auto a:state.shapeFrames[j].basis)for(auto x:a)frames<<x<<' ';frames<<'\n';}
    if(prepared)dump("prepared",prepared->controlPoints,prepared->controlTopology->faces);
   }
   auto presented=Clock::now();auto mesh=presentation?PresentMechanical(*prepared,source,renderer,contract):renderer.Evaluate(state);auto end=Clock::now();
   if(walk&&frame%90==89){std::ofstream f(out/("motion-"+std::to_string(test)+"-"+std::to_string(frame)+".obj"));f<<std::setprecision(17);for(auto p:mesh->controlPoints)f<<"v "<<p[0]<<' '<<p[1]<<' '<<p[2]<<'\n';for(auto t:mesh->controlTopology->faces)f<<"f "<<t[0]+1<<' '<<t[1]+1<<' '<<t[2]+1<<'\n';}
   std::uint64_t hash=14695981039346656037ull;
   for(const auto& part:mesh->parts)for(const auto& vertex:part.vertices)
    for(unsigned char b:std::string_view(reinterpret_cast<const char*>(&vertex),sizeof(vertex))){hash^=b;hash*=1099511628211ull;}
   report<<"{\"case\":"<<test<<",\"frame\":"<<frame<<",\"sourceMs\":"<<ms(start,solved)<<",\"driveMs\":"<<ms(solved,driven)<<",\"meshMs\":"<<ms(driven,end)<<",\"presentationMs\":"<<ms(presented,end)<<",\"rebuilt\":"<<(mesh->rebuilt?"true":"false")<<",\"stages\":[";
   for(unsigned i=0;i<6;i++)report<<(i?",":"")<<mesh->stageMilliseconds[i];
   report<<"],\"mechanicalStages\":[";for(unsigned i=0;i<6;i++)report<<(i?",":"")<<mesh->mechanicalMilliseconds[i];
   report<<"],\"compoundStages\":[";for(unsigned i=0;i<5;i++)report<<(i?",":"")<<mesh->compoundMilliseconds[i];
   report<<"],\"poseStages\":[";for(unsigned i=0;i<4;i++)report<<(i?",":"")<<mesh->poseMilliseconds[i];
   const auto rawFrames=surface::MaterialFrames(source);
   auto rootAngle=[&](const surface::PresentationFrames& f){return std::acos(std::clamp(surface::Dot(f[1].basis[0],state.shapeFrames[1].basis[0]),-1.,1.));};
   report<<"],\"rawRootRadians\":"<<rootAngle(rawFrames)<<",\"drivenRootRadians\":"<<rootAngle(state.frames)<<",\"hash\":\""<<hash<<"\"}\n";
   if(frame+1==frameCount){
    std::ofstream geometry(out/("shape-"+std::to_string(test)+".bin"),std::ios::binary);
    for(const auto& part:mesh->parts)geometry.write(reinterpret_cast<const char*>(part.vertices.data()),part.vertices.size()*sizeof(ModularVertex));
   }
  }
  report.flush();std::cout<<"Completed case "<<test<<std::endl;
 }
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
