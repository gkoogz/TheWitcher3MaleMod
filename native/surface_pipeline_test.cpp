#include "surface_pipeline.hpp"
#include <cmath>
#include <fstream>
#include <iostream>
#include <algorithm>
#include <numeric>

int wmain(int argc,wchar_t** argv){
 if(argc!=5)return 2;
 try{
  std::wstring wideRevision=argv[3];std::string revision;
  if(wideRevision.size()!=40)throw std::invalid_argument("Expected a pinned Base commit");
  for(auto c:wideRevision){if(!((c>=L'0'&&c<=L'9')||(c>=L'a'&&c<=L'f')))throw std::invalid_argument("Invalid Base revision");revision.push_back(static_cast<char>(c));}
  malemod::witcher::SurfacePipeline pipeline(argv[1],argv[2],revision);
  std::ofstream log(argv[4]);if(!log)throw std::runtime_error("Cannot write numerical pipeline report");
  malemod::surface::wire::Request q;std::vector<double> sourceTimes,targetTimes;
  unsigned yawedFrames=0,comparisons=0,metricBuilds=0;std::uint32_t lastMetric=0;
  for(unsigned frame=0;frame<180;frame++){
   if(frame%15==0){
    q.controls=malemod::surface::Controls{};unsigned phase=frame/15;
    if(phase==1)for(unsigned i:{1u,2u,3u,4u,5u})q.controls.values[i]=100;
    if(phase==2){q.controls.values[2]=0;q.controls.values[4]=0;q.controls.values[5]=1;}
    if(phase==3){q.controls.values[0]=0;q.controls.values[7]=1;}
    if(phase==4){q.controls.values[8]=100;q.controls.values[9]=100;}
    if(phase==5){q.controls.values[1]=1;q.controls.values[3]=1;}
    if(phase==6){q.controls.values[0]=1;q.controls.values[6]=100;}
    if(phase>=7&&phase<=10)for(unsigned i=10;i<18;i++)q.controls.values[i]=phase%2?1.f:100.f;
   }
   q.frame.pitchForce=.2f*std::sin(frame*.15f);q.frame.yawForce=.15f*std::cos(frame*.1f);
   const float sway=3.f*std::sin(frame*.04f);
   q.frame.thighEndpoints=std::array<malemod::surface::Point,4>{{{2,-7.8f,79},{1+sway,-8.2f,43},{2,7.8f,79},{1-sway,8.2f,43}}};
   auto result=pipeline.Evaluate(q);
   if(result.source.collarMetric.generation!=lastMetric){lastMetric=result.source.collarMetric.generation;++metricBuilds;}
   if(std::abs(result.source.rootDirection.y)>1e-5)++yawedFrames;
   // Compare a continually updated character plan with a fresh plan across
   // discontinuous controls, state changes and lateral root motion.
   if(frame%15==0||frame%15==14){
    malemod::witcher::TargetSurface fresh(argv[2],revision);
    for(unsigned lod=0;lod<2;lod++){
     if(fresh.Evaluate(lod,result.source)!=result.targetPositions[lod])throw std::runtime_error("Dynamic target plan differs from a fresh exact plan");
     ++comparisons;
    }
   }
   for(const auto& lod:result.targetPositions)for(auto p:lod)for(auto component:p)if(!std::isfinite(component))throw std::runtime_error("Non-finite pipeline surface");
   sourceTimes.push_back(result.sourceMilliseconds);targetTimes.push_back(result.targetMilliseconds);
   log<<"{\"frame\":"<<frame<<",\"sourceMs\":"<<result.sourceMilliseconds<<",\"targetBothLODsMs\":"<<result.targetMilliseconds<<",\"rootYawComponent\":"<<result.source.rootDirection.y<<",\"sourceMetricGeneration\":"<<lastMetric<<"}\n";
  }
  if(!yawedFrames||comparisons!=48)throw std::runtime_error("Dynamic pipeline coverage is incomplete");
  if(metricBuilds>=180)throw std::runtime_error("Source metric was rebuilt for every moving frame");
  std::sort(sourceTimes.begin(),sourceTimes.end());std::sort(targetTimes.begin(),targetTimes.end());
  log<<"{\"passed\":true,\"frames\":180,\"yawedFrames\":"<<yawedFrames<<",\"sourceMetricBuilds\":"<<metricBuilds<<",\"exactFreshPlanComparisons\":"<<comparisons<<",\"sourceMedianMs\":"<<sourceTimes[90]<<",\"sourceP95Ms\":"<<sourceTimes[171]<<",\"targetMedianBothLODsMs\":"<<targetTimes[90]<<",\"targetP95BothLODsMs\":"<<targetTimes[171]<<",\"observedGameplay\":false,\"nativeVertexOutput\":false}\n";
  std::cout<<"PASS complete numerical pipeline: 180 dynamic frames, "<<yawedFrames<<" yawed roots, 48 exact target comparisons.\n";
 }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
