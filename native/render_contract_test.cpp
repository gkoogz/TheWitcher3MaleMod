#include "render_service.hpp"
#include "surface_pipeline.hpp"
#include <iostream>
using namespace malemod::witcher;
static void Check(bool b,const char* message){if(!b)throw std::runtime_error(message);}
int wmain(int argc,wchar_t** argv){try{
 Check(argc==6,"Usage: render_contract_test contract worker binding pin bindingHash");
 std::wstring wp=argv[4],wh=argv[5];std::string pin(wp.begin(),wp.end()),hash(wh.begin(),wh.end());RenderContract contract(argv[1],pin,hash);Check(contract.VertexCount()==36547,"Native LOD dimensions changed");
 RenderPoseInput staging(contract);PoseMatrix world{1,0,0,100,0,1,0,-20,0,0,1,30,0,0,0,1};
 Check(staging.Add(1,-1,1,world),"World pose rejected");Check(!staging.Complete(1,1),"Partial pose published");
 std::map<unsigned,PoseMatrix> stock;for(unsigned i=0;i<46;i++)stock.emplace(contract.nativeBones[i],InversePose(contract.inverseBind[i]));
 for(const auto& entry:stock)Check(staging.Add(1,int(entry.first),1,entry.second),"Observed stock pose rejected");
 auto pose=staging.Complete(1,1);Check(pose.has_value(),"Complete observed palette did not publish");
 for(auto m:pose->skinDeltas)for(unsigned i=0;i<16;i++)Check(std::abs(m[i]-double(i%5==0))<1e-10,"Rest native skin delta is not identity");
 Check(!staging.Add(1,104,1,world),"Unknown skeleton joint entered the full surface palette");
 Check(!staging.Add(1,9,.5,world)&&staging.Complete(1,1).has_value(),"Older packet poisoned published pose");Check(staging.Add(2,-1,2,world)&&!staging.Complete(1,1)&&!staging.Complete(2,2),"Character pose replacement retained old joints");
 SurfacePipeline pipeline(argv[2],argv[3],pin);pipeline.Initialize({});malemod::surface::wire::Request request;
 auto frame=pipeline.Evaluate(request);auto vertices=ComposeRenderVertices(contract,frame.targetPositions);Check(vertices.size()==36547,"Source/native remap count differs");
 const auto serialLight=ComposeRenderVertices(contract,frame.targetPositions,false);
 Check(serialLight.size()==vertices.size()&&!std::memcmp(serialLight.data(),vertices.data(),vertices.size()*sizeof(SourceRenderVertex)),"Parallel LOD lighting changed bytes");
 unsigned calibration=0;for(const auto& v:vertices){calibration+=v.calibration;for(float x:v.position)Check(std::isfinite(x),"Invalid native position");double nn=0,tt=0,nt=0;for(unsigned a=0;a<3;a++){nn+=v.normal[a]*v.normal[a];tt+=v.tangent[a]*v.tangent[a];nt+=v.normal[a]*v.tangent[a];}Check(v.calibration||(std::abs(nn-1)<1e-5&&std::abs(tt-1)<1e-5&&std::abs(nt)<1e-5),"Final target lighting frame is not orthonormal");}
 Check(calibration>=16,"Protected body support count differs");
 request.controls.values[2]=100;auto changed=pipeline.Evaluate(request);auto next=ComposeRenderVertices(contract,changed.targetPositions);double maximum=0;for(unsigned i=0;i<next.size();i++)for(unsigned a=0;a<3;a++)maximum=(std::max)(maximum,double(std::abs(next[i].position[a]-vertices[i].position[a])));Check(maximum>.01,"Length slider did not change native vertex output");
 auto posed=SkinRenderVertices(next,*pose,false);Check(posed.size()==next.size(),"Native skin output missed a LOD");
 // One immutable upload must track later native poses without a CPU inverse.
 // Test both LODs, mixed collar weights and singular added-joint palettes.
 const auto prepared=PrepareFloatVertices(next,contract);
 // Exact cooked open-boundary attributes must survive every morphology state.
 auto checkBoundary=[&](const std::vector<SourceRenderVertex>& rows){
  const auto upload=PrepareFloatVertices(rows,contract);unsigned offset=0,count=0;
  for(const auto& lod:contract.lods){for(unsigned j=0;j<lod.vertices.size();j++){
   const auto& b=lod.vertices[j];if(!b.calibration)continue;const auto& row=rows[offset+j];
   for(unsigned a=0;a<3;a++)Check(row.position[a]==float(b.reference[a]),"Cooked waist/ankle position changed");
   skin::Point n{},t{};for(unsigned a=0;a<3;a++){n[a]=float(b.fallback.normal[a]);t[a]=float(b.fallback.tangent[a]);}
   Check(upload[offset+j].normal==PackDirection(n,1,false)&&upload[offset+j].tangent==PackDirection(t,b.fallback.sign<0?0:3,false),"Cooked boundary lighting changed");
   Check(row.bones==vertices[offset+j].bones&&row.weights==vertices[offset+j].weights,"Boundary native skin changed");++count;
  }offset+=unsigned(lod.vertices.size());}Check(count==calibration,"Boundary aliases missing");
 };
 checkBoundary(vertices);checkBoundary(next);
 for(unsigned control=1;control<18;control++)for(unsigned side=0;side<2;side++){
  request.controls={};request.controls.values[control]=side?100.f:((control==2||control==4)?0.f:1.f);
  checkBoundary(ComposeRenderVertices(contract,pipeline.Evaluate(request).targetPositions));
 }
 request.controls={};for(unsigned i=1;i<18;i++)request.controls.values[i]=100;
 checkBoundary(ComposeRenderVertices(contract,pipeline.Evaluate(request).targetPositions));
 const skin::Point qs{.41360682249f,.45207571983f,.91064155102f},qb{-.2066219449f,-.16102458537f,.17968167365f};double error=0;
 for(unsigned sample=0;sample<3;sample++){
 auto differing=*pose;
 for(unsigned i=0;i<46;i++){
  const double a=.2+.01*i+.17*sample;
  auto& m=differing.nativeSkinDeltas[i];m={std::cos(a),-std::sin(a),0,.03*sample,std::sin(a),std::cos(a),0,-.04*sample,0,0,1,.02*sample,0,0,0,1};
  if(contract.nativeBones[i]>=94&&sample==2)m.fill(0);
 }
 for(unsigned i=0;i<46;i++){
  unsigned pelvis=(i/23)*23;while(contract.nativeBones[pelvis]!=9)++pelvis;
  differing.skinDeltas[i]=differing.nativeSkinDeltas[contract.nativeBones[i]>=94?pelvis:i];
 }
 const auto expected=SkinRenderVertices(next,differing,false);std::vector<skin::Matrix> palette;
 for(const auto& m:differing.nativeSkinDeltas){skin::Matrix f{};for(unsigned i=0;i<16;i++)f[i]=float(m[i]);palette.push_back(f);}
 for(unsigned i=0;i<prepared.size();i++){
  const auto& v=prepared[i];skin::Vertex decoded{v.position,skin::Dec10(v.normal),skin::Dec10(v.tangent),next[i].sign,{},{}};
  std::memcpy(decoded.bones.data(),&v.bones,4);std::memcpy(decoded.weights.data(),&v.weights,4);
  for(unsigned a=0;a<3;a++)decoded.position[a]=decoded.position[a]*qs[a]+qb[a];
  const auto transform=skin::Blend(decoded,palette);const auto result=skin::Transform(transform,decoded.position);
  for(unsigned a=0;a<3;a++)error=(std::max)(error,double(std::abs(result[a]-expected[i].position[a])));
  Check(v.normal>>30==1,"Native normal metadata differs");
  Check(v.weights==next[i].weights,"Native weight bytes changed");
 }
 }
 Check(error<2e-6,"Live native skin remapping differs from desired source surface");
 std::cout<<"PASS: exact 46-entry palette/both LODs, coherent 23-joint epoch staging, complete lineage/lighting, Length deformation "<<maximum<<" native units, immutable output tracks three different native palettes including singular added joints; error="<<error<<"; cooked boundary positions/lighting invariant at all slider extremes; protected supports="<<calibration<<"\n";return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
