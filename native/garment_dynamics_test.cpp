// Actual adapter pipeline + measured Geralt donors/capsules + shared fabric.
// Offline native test: no game launch, focus, input, audio or installation.
#include "garment_service.hpp"
#include "runtime_profile.hpp"
#include <iostream>
#include <iomanip>
using namespace malemod::witcher;
using Point=malemod::garments::Point;
static void Check(bool b,const char* t){if(!b)throw std::runtime_error(t);}
static PoseMatrix Identity(){return {1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1};}
static PoseMatrix RotateX(Point p,double a){double c=std::cos(a),s=std::sin(a);return {1,0,0,0,0,c,-s,p[1]*(1-c)+p[2]*s,0,s,c,p[2]*(1-c)-p[1]*s,0,0,0,1};}
int wmain(int argc,wchar_t** argv){try{
 Check(argc==9,"Usage: garment_dynamics_test render worker binding pin bindingHash garmentBinding runtimeProfile reportDirectory");
 std::wstring ps=argv[4],hs=argv[5];std::string pin(ps.begin(),ps.end()),hash(hs.begin(),hs.end());RenderContract c(argv[1],pin,hash);
 std::ifstream digest(std::filesystem::path(argv[1]).wstring()+L".sha256");std::string renderHash;digest>>renderHash;
 GarmentBindings binding(argv[6],pin,renderHash);auto profile=RuntimeProfile::Load(argv[7],pin);Check(bool(profile.contacts),"Measured capsule contacts absent");
 auto dir=std::filesystem::path(argv[8]);std::filesystem::create_directories(dir);std::ofstream report(dir/L"dynamics-cases.jsonl");report<<std::setprecision(15);
 SurfacePipeline pipeline(argv[2],argv[3],pin);pipeline.Initialize({});GarmentService service(c,std::move(binding),profile.contacts,dir);service.Style(1);
 auto palette=[&](unsigned bone){unsigned k=0;while(k<c.nativeBones.size()&&c.nativeBones[k]!=bone)++k;Check(k<c.nativeBones.size(),"Measured body joint missing");return k;};
 auto restPoint=[&](unsigned bone){return TransformPosePoint(InversePose(c.inverseBind[palette(bone)]),{0,0,0});};
 double seconds=0,maximum=0,totalActive=0;unsigned count=0,steps=0,steadyCount=0;double steadyWorkMs=0,steadyActiveMs=0,backlogMs=0,maximumBacklogMs=0;std::uint64_t revision=0;
 malemod::surface::wire::Request q;
 for(unsigned morphology=0;morphology<3;morphology++){
  q.controls={};q.controls.values[0]=float(morphology);if(morphology==1){q.controls.values[1]=80;q.controls.values[2]=75;q.controls.values[3]=90;q.controls.values[5]=95;}if(morphology==2){q.controls.values[1]=100;q.controls.values[7]=100;}
  // Evaluate the actual shared source and target geometry, not just a changed
  // header/control revision on vertices from a different shape.
  auto surface=pipeline.Evaluate(q);auto render=std::make_shared<RenderDelivery>();render->epoch=1;render->sequence=morphology+1;render->controls=q.controls;render->vertices=std::make_shared<const std::vector<SourceRenderVertex>>(ComposeRenderVertices(c,surface.targetPositions));
  for(unsigned frame=0;frame<16;frame++){
   const double dt=frame%3==0?1./120:frame%3==1?1./60:1./40;
   if(count)seconds+=dt;RenderPose pose;pose.epoch=1;pose.seconds=seconds;double yaw=.035*std::sin(count*.13);pose.actorWorld={std::cos(yaw),-std::sin(yaw),0,0,std::sin(yaw),std::cos(yaw),0,0,0,0,1,0,0,0,0,1};pose.actorWorld=MultiplyPose(pose.actorWorld,RotateX({0,0,1},.018*std::sin(count*.11)));pose.actorWorld[3]+=.003*std::sin(count*.17);pose.actorWorld[11]+=.002*std::sin(count*.23);pose.skinDeltas.assign(c.nativeBones.size(),Identity());
   for(unsigned side=0;side<2;side++){unsigned hip=side?18:15,knee=hip+1,foot=hip+2;auto hipRotation=RotateX(restPoint(hip),(side?1:-1)*.10*std::sin(count*.19));auto shin=MultiplyPose(hipRotation,RotateX(restPoint(knee),.07*(1+std::sin(count*.19+.4))));for(unsigned k=0;k<c.nativeBones.size();k++)if(c.nativeBones[k]==hip)pose.skinDeltas[k]=hipRotation;else if(c.nativeBones[k]==knee||c.nativeBones[k]==foot)pose.skinDeltas[k]=shin;}
   auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(15);std::shared_ptr<const GarmentDelivery> out;
   do{service.Submit(render,pose);Check(service.Error().empty(),"Actual articulated cloth worker rejected input");out=service.Latest();if(out&&out->sourceRender->poseSeconds==seconds&&out->sourceRender->sequence==render->sequence)break;std::this_thread::sleep_for(std::chrono::milliseconds(1));}while(std::chrono::steady_clock::now()<deadline);
   Check(out&&out->sourceRender->poseSeconds==seconds&&out->sourceRender->sequence==render->sequence,"Actual articulated cloth timed out");
   auto p=out->output.physics;const double healthyWorkerMs=out->milliseconds-out->diagnosticMilliseconds;if(frame){steadyCount++;steadyWorkMs+=healthyWorkerMs;steadyActiveMs+=dt*1000;backlogMs=(std::max)(0.,backlogMs+healthyWorkerMs-dt*1000);maximumBacklogMs=(std::max)(maximumBacklogMs,backlogMs);}maximum=(std::max)(maximum,out->milliseconds);steps+=p.substeps;
   report<<"{\"case\":"<<count<<",\"morphology\":"<<morphology<<",\"restRevision\":"<<out->restRevision<<",\"time\":"<<seconds<<",\"contactBudget\":"<<(out->output.contactBudgetSatisfied?"true":"false")<<",\"materialBudget\":"<<(p.materialBudgetSatisfied?"true":"false")<<",\"substeps\":"<<p.substeps<<",\"advancedSeconds\":"<<p.advancedSeconds<<",\"accumulatedSeconds\":"<<p.accumulatedSeconds<<",\"maximumStretch\":"<<p.maxStretchRatio<<",\"maxRenderStretchRatio\":"<<p.maxRenderStretchRatio<<",\"worstRenderA\":"<<p.worstRenderA<<",\"worstRenderB\":"<<p.worstRenderB<<",\"maximumSeamGap\":"<<p.maxSeamGap<<",\"coverage\":"<<out->output.coverageMargin<<",\"rmsSpeed\":"<<p.rmsSpeed<<",\"solverMs\":"<<p.solverMilliseconds<<",\"sampleMs\":"<<out->samplingMilliseconds<<",\"sharedUpdateMs\":"<<out->updateMilliseconds<<",\"presentationBuildMs\":"<<out->presentationBuildMilliseconds<<",\"displayMs\":"<<out->presentationMilliseconds<<",\"diagnosticMs\":"<<out->diagnosticMilliseconds<<",\"worstStretchA\":"<<p.worstStretchA<<",\"worstStretchB\":"<<p.worstStretchB<<",\"worstStretchRest\":"<<p.worstStretchRestLength<<",\"worstStretchLength\":"<<p.worstStretchCurrentLength<<",\"workerMs\":"<<out->milliseconds<<"}\n";report.flush();
   std::cout<<"actual Geralt cloth case="<<count<<" contacts="<<out->output.contactBudgetSatisfied<<" material="<<p.materialBudgetSatisfied<<" steps="<<p.substeps<<" stretch="<<p.maxStretchRatio<<" seam="<<p.maxSeamGap<<" coverage="<<out->output.coverageMargin<<" solver="<<p.solverMilliseconds<<"ms\n";
   Check(p.active&&p.stateReady&&p.nodes&&p.constraints,"Actual material solver inactive");Check(out->output.contactBudgetSatisfied,"Actual moving Geralt cloth collision/coverage budget failed");Check(p.materialBudgetSatisfied,"Actual moving Geralt cloth material/sewing budget failed");
   if(count){totalActive+=dt;Check(std::abs(p.accumulatedSeconds-totalActive)<1./120+1e-8,"Variable active time lost");}
   if(frame==0){Check(out->restRevision>revision,"New evaluated morphology not refitted");revision=out->restRevision;}else Check(out->restRevision==revision,"Motion invalidates rest topology cache");
   for(auto v:out->output.mesh.vertices)Check(malemod::garments::Finite(v.position)&&malemod::garments::Finite(v.normal),"Nonfinite dynamic fabric");++count;
  }
 }
 Check(steps>60,"Fabric never truly advanced");std::ofstream perf(dir/L"steady-performance.json");perf<<std::setprecision(15)<<"{\"steadySamples\":"<<steadyCount<<",\"workerMeanMilliseconds\":"<<steadyWorkMs/steadyCount<<",\"activeIntervalMeanMilliseconds\":"<<steadyActiveMs/steadyCount<<",\"maximumAccumulatedLagMilliseconds\":"<<maximumBacklogMs<<",\"finalAccumulatedLagMilliseconds\":"<<backlogMs<<",\"initialAndMorphologyRefitsExcluded\":true,\"diagnosticWritesExcluded\":true}\n";perf.close();Check(steadyWorkMs<steadyActiveMs,"Steady cloth worker is slower than retained active time");Check(backlogMs<=100&&maximumBacklogMs<=250,"Cloth worker creates unbounded presentation age");std::cout<<"PASS "<<count<<" actual Geralt dynamic calibrated-contact cases; steps="<<steps<<" active="<<totalActive<<"s maximum worker="<<maximum<<"ms; offline only\n";return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
