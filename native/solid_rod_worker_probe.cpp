#include "surface_transport.hpp"
#include <iostream>
#include <cmath>
#include <algorithm>
using namespace malemod;
double distance(surface::Point a,surface::Point b){return std::hypot(double(a.x-b.x),double(a.y-b.y),double(a.z-b.z));}
double curvature(const surface::Output& o){
 double sum=0;
 for(unsigned i=1;i+1<o.shaftGuide.size();i++){
  auto a=o.shaftGuide[i-1],b=o.shaftGuide[i],c=o.shaftGuide[i+1];
  double l=distance(a,b),m=distance(b,c);
  if(l<1e-6||m<1e-6)throw std::runtime_error("Collapsed rod section");
  double dot=((b.x-a.x)*(c.x-b.x)+(b.y-a.y)*(c.y-b.y)+(b.z-a.z)*(c.z-b.z))/(l*m);
  sum+=std::acos(std::clamp(dot,-1.,1.));
 }
 return sum;
}
int wmain(int argc,wchar_t** argv){try{
 if(argc!=3)throw std::runtime_error("Usage: solid_rod_worker_probe candidate previous-target-worker");
 for(unsigned state=0;state<3;state++){
  witcher::SurfaceClient current(argv[1]),previous(argv[2]);surface::wire::Request q;
  q.controls.values[0]=float(state);current.Initialize(q.controls);previous.Initialize(q.controls);
  double sum[2]{},peak[2]{},travel[2]{};surface::Point prior[2]{};double difference=0;
  for(unsigned i=0;i<480;i++){
   q.frame.seconds=1.f/60;q.frame.pitchForce=i<120?0.f:.3f*std::sin(i*.12f);q.frame.yawForce=i<120?0.f:.2f*std::cos(i*.09f);
   auto a=current.EvaluateMechanical(q,10000),b=previous.EvaluateMechanical(q,10000);
   if(state<2&&surface::wire::Encode(a)!=surface::wire::Encode(b))throw std::runtime_error("Firmer response changed another state");
   surface::Output samples[2]{std::move(a),std::move(b)};
   for(unsigned k=0;k<2;k++){double c=curvature(samples[k]);if(!std::isfinite(c))throw std::runtime_error("Nonfinite rod response");if(i>=120){sum[k]+=c;peak[k]=(std::max)(peak[k],c);travel[k]+=distance(samples[k].shaftGuide.back(),prior[k]);}prior[k]=samples[k].shaftGuide.back();}
   difference=(std::max)(difference,distance(samples[0].shaftGuide.back(),samples[1].shaftGuide.back()));
  }
  std::cout<<"{\"state\":"<<state<<",\"meanCurvature\":["<<sum[0]/360<<','<<sum[1]/360<<"],\"peakCurvature\":["<<peak[0]<<','<<peak[1]<<"],\"tipTravel\":["<<travel[0]<<','<<travel[1]<<"],\"maxTipDifference\":"<<difference<<"}\n";
  if(state==2&&(sum[0]>=sum[1]||travel[0]<1||difference<.01))throw std::runtime_error("Full floppy did not become firmer while retaining movement");
 }
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
