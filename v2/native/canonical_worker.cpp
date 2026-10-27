#define NOMINMAX
#include <windows.h>
#include <malemod/surface/canonical_packet.hpp>
#include "canonical-kernel.inc"
#include <string>

namespace C=malemod::surface::canonical;
namespace K=malemod::surface::source;
int wmain(int argc,wchar_t** argv){
 if(argc!=3)return 2;
 const std::wstring name=argv[1];
 HANDLE map=OpenFileMappingW(FILE_MAP_ALL_ACCESS,FALSE,(name+L".map").c_str());
 HANDLE input=OpenEventW(SYNCHRONIZE,FALSE,(name+L".input").c_str());
 HANDLE output=OpenEventW(EVENT_MODIFY_STATE,FALSE,(name+L".output").c_str());
 HANDLE parent=OpenProcess(SYNCHRONIZE,FALSE,std::stoul(argv[2]));
 if(!map||!input||!output||!parent)return 3;
 auto* packet=static_cast<C::Packet*>(MapViewOfFile(map,FILE_MAP_ALL_ACCESS,0,0,sizeof(C::Packet)));
 if(!packet||packet->magic!=C::Magic||packet->bytes!=sizeof(C::Packet)||packet->version!=4)return 4;
 std::vector<unsigned char> buffer(50915*32);unsigned epoch=0,epochFrame=0,clockReset=0;std::array<float,18> previousControls{};unsigned previousStyle=~0u,previousThrob=0;
 for(;;){
  HANDLE handles[]={input,parent};
  if(WaitForMultipleObjects(2,handles,FALSE,INFINITE)!=WAIT_OBJECT_0)break;
  if(packet->stop)break;
  try{
   if(packet->epoch==0||packet->controls[0]!=int(packet->controls[0])||packet->controls[0]<0||packet->controls[0]>2)throw std::invalid_argument("Invalid source state");
   for(unsigned i=1;i<18;i++)if(!std::isfinite(packet->controls[i])||packet->controls[i]<0||packet->controls[i]>100)throw std::invalid_argument("Invalid source control");
   if(!std::isfinite(packet->seconds)||packet->seconds<0||packet->seconds>.25f)throw std::invalid_argument("Invalid source clock");
   if(packet->garmentStyle>1)throw std::invalid_argument("Invalid garment mode");
   const auto& f=packet->features;
   if(f.throbMode>3||f.teachingActive>1||f.rootJointRequested>1||!std::isfinite(f.teachingTime)||f.teachingTime<0||!std::isfinite(f.teachingEnd)||f.teachingEnd<0||f.teachingTime>f.teachingEnd||!std::isfinite(f.lateralWobbleDegrees)||f.lateralWobbleDegrees<0||f.lateralWobbleDegrees>8)throw std::invalid_argument("Invalid source feature state");
   for(unsigned i=0;i<4;i++)if(!std::isfinite(f.angleGain[i])||!std::isfinite(f.lateralGain[i]))throw std::invalid_argument("Invalid source feature gain");
   K::sourceMilliseconds=f.milliseconds;K::sourceRootJointRequested=f.rootJointRequested!=0;
   const bool featureDirty=clockReset!=f.resetClock||previousThrob!=f.throbMode;
   if(clockReset!=f.resetClock||previousThrob!=f.throbMode){K::ResetThrobClock();clockReset=f.resetClock;}
   previousThrob=K::throbMode=f.throbMode;
   K::teachingTimeline.active=f.teachingActive!=0;K::teachingTimeline.time=f.teachingTime;K::teaching::sequenceEnd=f.teachingEnd;
   for(unsigned i=0;i<4;i++){K::teachingFluid.angleGain[i]=f.angleGain[i];K::teachingFluid.lateralGain[i]=f.lateralGain[i];}
   K::teachingFluid.settings.lateralWobbleDegrees=f.lateralWobbleDegrees;
   K::clothingStyle=packet->garmentStyle;
   K::physicsState=int(packet->controls[0]);for(unsigned i=0;i<7;i++)K::sliderUI[i]=packet->controls[i+1];
   K::glansUI=packet->controls[8];K::hangUI=packet->controls[9];for(unsigned i=0;i<8;i++)K::physUI[i]=packet->controls[i+10];K::UpdateThrob();
   K::collisionCapsuleOverride=packet->collisionOverride!=0;
   if(K::collisionCapsuleOverride){
    auto p=packet->thighs;
    K::overrideLeftA={p[0].x,p[0].y,p[0].z};K::overrideLeftB={p[1].x,p[1].y,p[1].z};
    K::overrideRightA={p[2].x,p[2].y,p[2].z};K::overrideRightB={p[3].x,p[3].y,p[3].z};
   }
   auto* raw=buffer.data();
   if(epoch!=packet->epoch){
    std::fill(buffer.begin(),buffer.end(),0);K::PrepareMenuRetargetBodyBasis(raw);
    for(unsigned i=0;i<K::collarNormalTriangleCount*3;i++)memcpy(raw+K::collarNormalTriangleIndices[i]*32,K::collarNormalTriangleBasePositions+i*3,12);
    for(unsigned i=0;i<K::pelvisControlCount;i++)memcpy(raw+K::pelvisControlIndices[i]*32,K::pelvisControlBasePositions+i*3,12);
    for(unsigned i=0;i<K::graftCount;i++)memcpy(raw+(47050+i)*32,K::morph_base+i*3,12);
    K::preparedShapeReady=K::shaftRestFrameReady=K::eggRestReady=K::constraintSolverReady=false;
    K::paBasisSaved=false;K::ResetCompliantDynamics();K::ResetPelvicAttachmentBody(raw);K::EvaluateAnatomy(raw,47050);epoch=packet->epoch;epochFrame=0;previousStyle=~0u;
   }
   double start=K::PerfClock();K::UpdateConstraintSolver(packet->seconds,packet->pitchForce,packet->yawForce);
   packet->physicsMilliseconds=K::PerfClock()-start;++packet->physicsServices;
   const bool dirty=previousControls!=packet->controls||previousStyle!=packet->garmentStyle||featureDirty;
   const bool surface=malemod::garments::UpdatePouchCoveredSurface(packet->garmentStyle==1,dirty,K::teachingTimeline.active,++epochFrame);
   start=K::PerfClock();
   if(surface){
    K::ResetPelvicAttachmentBody(raw);K::EvaluateAnatomy(raw,47050);++packet->surfaceServices;
    static_assert(sizeof(K::nrPacked)==sizeof(packet->anatomy));
    memcpy(packet->anatomy.data(),K::nrPacked,sizeof(K::nrPacked));
    memcpy(packet->body0.data(),K::sharedBodyOutput[0],packet->body0.size());
    memcpy(packet->body1.data(),K::sharedBodyOutput[1],packet->body1.size());
   }
   packet->surfaceMilliseconds=K::PerfClock()-start;previousControls=packet->controls;previousStyle=packet->garmentStyle;
   memcpy(packet->guide.data(),K::shaftNodes,sizeof(K::shaftNodes));
   auto& feature=packet->featureOutput;feature.sizePulse=K::throbSizePulse;feature.twitchPulse=K::throbTwitchPulse;feature.angleSizePulse=K::throbAngleSizePulse;
   feature.effectiveControls={float(K::physicsState),K::effectiveShapeUI[0],K::effectiveShapeUI[1],K::effectiveShapeUI[2],K::effectiveGlansUI,K::effectiveShapeUI[3],K::teachingTimeline.active?K::effectiveHangUI:K::hangUI,K::effectiveShapeUI[4],K::effectiveShapeUI[5],K::effectiveShapeUI[6],K::physUI[0],K::physUI[1],K::physUI[2],K::physUI[3],K::physUI[4],K::physUI[5],K::physUI[6],K::physUI[7]};
   // Exact canonical TeachingEmitter lip/back-ring selection, before native
   // pelvis/world conversion. The recessed cap is intentionally not the outlet.
   feature.nozzleValid=0;
   if(K::r14Ready){
    auto ring=[](unsigned r){K::V3 sum{};for(unsigned i=0;i<K::r14SegmentCount;i++)sum=sum+K::r14Positions[K::r14NewStart+r*K::r14SegmentCount+i];return sum/float(K::r14SegmentCount);};
    auto lip=ring(K::r14RingCount-6),back=ring(K::r14CrownRing+(K::r14RingCount-K::r14CrownRing)/2);auto direction=K::Unit(lip-back);
    if(std::isfinite(lip.x)&&std::isfinite(lip.y)&&std::isfinite(lip.z)&&K::Length(lip-back)>=.001f){lip=lip+direction*.06f;feature.nozzlePosition={lip.x,lip.y,lip.z};feature.nozzleDirection={direction.x,direction.y,direction.z};feature.nozzleValid=1;}
   }
   // Source MeridianAdapter::Update outer controls, with no changed constants.
   if(surface)for(unsigned side=0;side<2;side++)for(unsigned control=0;control<6;control++){
    auto center=K::CPCenter(side),r=K::CPRadii(side),scale=K::CPDiv(r,side?K::V3{5.724f,4.86f,7.81f}:K::V3{5.724f,4.86f,7.93f});
    K::V3 outer=r+K::CPMul({.80f,.95f,.65f},scale);unsigned axis=control<2?2:(control<4?0:1);float sign=control%2?-1.f:1.f;
    K::V3 local=axis==0?K::V3{outer.x,0,0}:axis==1?K::V3{0,outer.y,0}:K::V3{0,0,outer.z};
    auto point=center+K::CPTransform(local*(1.03f*sign),side);packet->garmentLobeControls[side*6+control]={point.x,point.y,point.z};
   }
   packet->status=1;packet->completed=packet->request;
  }catch(...){packet->status=2;packet->completed=packet->request;}
  MemoryBarrier();SetEvent(output);
 }
 UnmapViewOfFile(packet);CloseHandle(map);CloseHandle(input);CloseHandle(output);CloseHandle(parent);return 0;
}
