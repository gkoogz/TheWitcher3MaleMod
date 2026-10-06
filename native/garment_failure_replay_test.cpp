#include "garment_failure_capture.hpp"
#include "garment_shape_checks.hpp"
#include <iostream>
int wmain(int argc,wchar_t** argv){try{
 if(argc!=3)throw std::runtime_error("Usage: garment_failure_replay_test input outputDirectory");
 auto input=malemod::witcher::garment_capture::ReadInput(argv[1]);malemod::garments::Parameters parameters;parameters.simulate=false;malemod::garments::Session session(parameters);
 const auto& out=session.Update(malemod::garments::Style::WhiteJockstrap,input);auto dir=std::filesystem::path(argv[2]);std::filesystem::create_directories(dir);
 malemod::witcher::garment_capture::WriteOutput(dir/L"replayed.obj",out);malemod::witcher::garment_capture::WriteDiagnostics(dir/L"replayed.json",input,out,0,0);
 auto metrics=garment_shape::Measure(input,out);std::cout<<"contact="<<out.contactBudgetSatisfied<<" signed="<<metrics.minSignedDistance<<" bandSurfaceGap="<<metrics.bandSurfaceGap<<" hemSurfaceGap="<<metrics.hemSurfaceGap<<" maxRibbonEdge="<<metrics.strapEdge<<" spacing="<<metrics.spacingRatio<<'\n';
 // Real captured poses remain ignored/private. Replay their geometry at a
 // pelvic local origin and kilometre translations, and in scaled caller units.
 // Fresh sessions ensure success is not an accidental warm-state dependency.
 std::ofstream report(dir/L"covariance.jsonl");report<<std::setprecision(17);
 for(unsigned variant=0;variant<4;variant++){
  auto transformed=input;double scale=variant==3?100:1;malemod::garments::Point offset{};
  if(variant==0)offset=malemod::garments::Mul(input.frame.origin,-1);
  else if(variant<3)offset={variant==1?1000.:-1000.,variant==1?1000.:-1000.,variant==1?1000.:-1000.};
  auto point=[&](malemod::garments::Point p){return malemod::garments::Add(malemod::garments::Mul(p,scale),offset);};
  transformed.frame.origin=point(input.frame.origin);transformed.gravity=malemod::garments::Mul(input.gravity,scale);
  for(auto* samples:{&transformed.waist,&transformed.opening,&transformed.anatomy,&transformed.rearStraps[0],&transformed.rearStraps[1],&transformed.bodySurface})for(auto& s:*samples)s.position=point(s.position);
  for(auto& c:transformed.bodyContacts){c.a=point(c.a);c.b=point(c.b);c.radius*=scale;}
  malemod::garments::Session replay(parameters);const auto& result=replay.Update(malemod::garments::Style::WhiteJockstrap,transformed);
  auto shape=garment_shape::Measure(transformed,result);if(!result.contactBudgetSatisfied||result.mesh.vertices.size()!=out.mesh.vertices.size())throw std::runtime_error("Captured movement seam covariance/contact failure");
  double maximum=0;for(unsigned i=0;i<out.mesh.vertices.size();i++)maximum=(std::max)(maximum,malemod::garments::Length(malemod::garments::Sub(result.mesh.vertices[i].position,point(out.mesh.vertices[i].position))));
  if(maximum>1e-8*scale)throw std::runtime_error("Captured movement garment coordinate covariance failure");
  report<<"{\"variant\":"<<variant<<",\"scale\":"<<scale<<",\"maximumPositionDifference\":"<<maximum<<",\"signedDistance\":"<<shape.minSignedDistance<<",\"hemSurfaceGap\":"<<shape.hemSurfaceGap<<",\"bandSurfaceGap\":"<<shape.bandSurfaceGap<<",\"maxRibbonEdge\":"<<shape.strapEdge<<",\"spacing\":"<<shape.spacingRatio<<"}\n";
 }
 return out.contactBudgetSatisfied?0:1;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}}
