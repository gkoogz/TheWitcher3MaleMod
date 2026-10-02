#include "pose_input.hpp"
#include "surface_pipeline.hpp"
#include <fstream>
#include <iostream>
#include <algorithm>

int wmain(int argc,wchar_t** argv){
 if(argc!=6)return 2;
 try{
  std::ifstream data(argv[1],std::ios::binary);if(!data)throw std::runtime_error("Missing owned pose packet");
  auto read=[&](auto& value){data.read(reinterpret_cast<char*>(&value),sizeof(value));if(!data)throw std::runtime_error("Truncated pose packet");};
  std::array<char,8> magic{};read(magic);if(std::string(magic.data(),8)!="MMPOSE01")throw std::runtime_error("Wrong pose packet version");
  malemod::surface::CoordinateCalibration c;read(c.basis);read(c.sourceRoot);read(c.targetRoot);read(c.targetUnitsPerSourceUnit);
  malemod::witcher::PoseMatrix bind{};read(bind);std::uint32_t count=0;read(count);if(!count||count>10000)throw std::runtime_error("Invalid pose count");
  malemod::witcher::PoseInput mapper(c,bind);
  std::wstring wide=argv[4];std::string pin;
  if(wide.size()!=40)throw std::invalid_argument("Invalid Base pin");
  for(auto digit:wide){if(!((digit>=L'0'&&digit<=L'9')||(digit>=L'a'&&digit<=L'f')))throw std::invalid_argument("Invalid Base pin");pin.push_back(static_cast<char>(digit));}
  malemod::witcher::SurfacePipeline pipeline(argv[2],argv[3],pin);
  std::ofstream report(argv[5]);if(!report)throw std::runtime_error("Cannot write replay proof");
  std::vector<double> sourceTimes,targetTimes;double forceMax=0,contactError=0;unsigned changingForces=0;
  for(unsigned i=0;i<count;i++){
   malemod::witcher::PoseSample sample;read(sample.seconds);read(sample.pelvisActorLocal);read(sample.thighsActorLocal);
   auto mapped=mapper.Map(sample);
   if(mapped.characterContactsCalibrated||mapped.frame.collision||mapped.frame.thighEndpoints||mapper.MotionState().motionCollisionBonesReady)throw std::runtime_error("Unavailable contacts advertised");
   for(unsigned j=0;j<4;j++){
    const auto p=mapped.measuredThighsSource[j];auto original=malemod::witcher::TransformPosePoint(mapped.pelvisSkinDeltaNative,c.PointToTarget({p.x,p.y,p.z}));
    for(unsigned k=0;k<3;k++)contactError=std::max(contactError,std::abs(original[k]-sample.thighsActorLocal[j][k]));
   }
   if(contactError>1e-6)throw std::runtime_error("Contact frame round trip differs");
   const auto pitch=mapped.frame.pitchForce,yaw=mapped.frame.yawForce;
   if(!std::isfinite(pitch)||!std::isfinite(yaw)||std::abs(pitch)>2.50001f||std::abs(yaw)>2.50001f)throw std::runtime_error("Invalid mapped source force");
   forceMax=std::max(forceMax,double(std::max(std::abs(pitch),std::abs(yaw))));if(std::abs(pitch)+std::abs(yaw)>.0001f)++changingForces;
   malemod::surface::wire::Request request;request.frame=mapped.frame;auto output=pipeline.Evaluate(request);
   for(const auto& lod:output.targetPositions)for(auto p:lod)for(double x:p)if(!std::isfinite(x))throw std::runtime_error("Nonfinite moving surface");
   sourceTimes.push_back(output.sourceMilliseconds);targetTimes.push_back(output.targetMilliseconds);
   report<<"{\"frame\":"<<i<<",\"pitch\":"<<pitch<<",\"yaw\":"<<yaw<<",\"sourceMs\":"<<output.sourceMilliseconds<<",\"bothLODsMs\":"<<output.targetMilliseconds<<"}\n";
  }
  char extra=0;if(data.read(&extra,1))throw std::runtime_error("Trailing pose packet data");
  if(!changingForces)throw std::runtime_error("Moving replay did not drive motion");
  std::sort(sourceTimes.begin(),sourceTimes.end());std::sort(targetTimes.begin(),targetTimes.end());
  report<<"{\"passed\":true,\"frames\":"<<count<<",\"movingForceFrames\":"<<changingForces<<",\"maximumForce\":"<<forceMax<<",\"contactRoundTripErrorNative\":"<<contactError<<",\"sourceMedianMs\":"<<sourceTimes[count/2]<<",\"bothLODsMedianMs\":"<<targetTimes[count/2]<<",\"characterContactsCalibrated\":false,\"diagnosticSourceDefaultContacts\":true,\"nativeVertexOutput\":false,\"observedGameplayOutput\":false}\n";
  std::cout<<"PASS: "<<count<<" observed poses mapped through the exact Base filter and complete two-LOD pipeline. Character contacts remain uncalibrated.\n";
 }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
