#define NOMINMAX
#include <windows.h>
#include <bcrypt.h>
#include <MinHook.h>
#include <array>
#include <atomic>
#include <cstring>
#include <string>
#include <vector>
#include <mutex>
#include <cmath>
#include <cstdio>
#include <share.h>
#include <chrono>
#include <memory>
#include "engine/game_profile.hpp"
#include "engine/graphics_probe.hpp"
#include "engine/float_draw_renderer.hpp"
#include "source_host.hpp"
#include "source_binding.hpp"
#include "meridian_adapter.hpp"
#include "render_pose_publication.hpp"
#include "clinical_adapter.hpp"
#include "clinical_collision.hpp"
#include "clinical_body.hpp"
#include "engine/clinical_audio.hpp"
#include "engine/garment_renderer.hpp"
#include "engine/fluid_renderer.hpp"
#include "runtime_identity.inc"
#include <malemod/motion_filter.hpp>
#include <malemod/controls/canonical_order.hpp>
#include <malemod/controls/menu_preferences.hpp>
#include "engine/overlay_panel.hpp"
#include "engine/overlay_input.hpp"
#include "engine/overlay_parent.hpp"
#include "engine/frame_publication.hpp"
#include "engine/startup_diagnostics.hpp"
#include "engine/position_capture.hpp"

namespace malemod::witcher {
namespace {
std::uintptr_t engineBase=0;
using NativeCallback=void(*)(void*,void*,void*);
using RegisterGlobals=void(*)();RegisterGlobals originalRegisterGlobals=nullptr;
std::atomic<bool> initialized{false},registered{false},registrationFailed{false},invoked{false};
std::atomic<unsigned> runtimeFlags{0},frameCount{0},sealedFlags{0};
std::uint64_t activeTicks=0,visibleTicks=0,visibleServices=0,hiddenSkips=0;
struct alignas(16) ScriptVector {float x=0,y=0,z=0,w=0;};
std::array<float,18> controls{2,50,50,50,50,50,50,50,50,50,50,50,50,50,50,50,50,50};
std::mutex mutex,menuMutex;
v2::SourceHost* host=nullptr;v2::SourceBinding* binding=nullptr;
v2::MeridianAdapter* garment=nullptr;std::atomic<unsigned> garmentStyle{0};std::shared_ptr<const GarmentDelivery> garmentOutput;
v2::ClinicalAdapter* clinical=nullptr;ClinicalCollision clinicalCollision;ClinicalAudio clinicalAudio;
v2::ClinicalBody* clinicalBody=nullptr;double clinicalLastClock=0;
std::shared_ptr<const ClinicalDelivery> clinicalOutput;
v2::RenderPosePublication<RenderDelivery,ClinicalDelivery> renderPublication;
std::uint64_t poseRevision=0,renderPosePublications=0;
std::uint64_t publishedSourceSerial=0,publishedPoseRevision=0;
std::uint64_t clinicalAfterServices=0;
v2::SealedCheckpointRequests pendingCheckpoints;
std::chrono::steady_clock::time_point pendingFrameBegan,pendingMainEnded;
double pendingSourceWaitMs=0,pendingBindingMs=0,pendingMainCallbackMs=0;
v2::Matrix pendingActorWorld{};
using FeatureAction=malemod::controls::menu::Action;
std::vector<std::pair<FeatureAction,float>> featureActions;
std::atomic<unsigned> throbMode{0};std::atomic<bool> idleChatter{false},correctedLighting{true};
std::shared_ptr<const malemod::controls::menu::State> featureSnapshot;
HWND overlayParent=nullptr;unsigned clinicalCueMask=0,clinicalCueSerial=0;std::vector<ScriptVector> clinicalCues;
malemod::motion::Tracker tracker;
float lastSeconds=0;unsigned lastEpoch=0,simulationEpoch=0;bool resetRequested=false;
std::array<v2::Matrix,94> bonePoses{};v2::Matrix actorWorld{};std::array<bool,94> boneReady{};bool actorReady=false;unsigned poseEpoch=0;float poseSeconds=0;
FILE* trace=nullptr;std::filesystem::path moduleDirectory;
bool WriteCheckpoint(std::int32_t stage);
void DiscardCheckpoints(const char* reason){
 for(auto stage:pendingCheckpoints.Take())if(trace)std::fprintf(trace,"{\"checkpointCancelled\":%d,\"reason\":\"%s\"}\n",stage,reason);
 if(trace)std::fflush(trace);
}
#include "engine/observed_api.inc"
bool IsSealedStation(){
 wchar_t expected[256]{},actual[256]{};DWORD bytes=0;USEROBJECTFLAGS flags{};auto station=GetProcessWindowStation();
 return GetEnvironmentVariableW(L"MALEMOD_SEALED_SESSION",expected,256)>0&&GetUserObjectInformationW(station,UOI_NAME,actual,sizeof(actual),&bytes)&&GetUserObjectInformationW(station,UOI_FLAGS,&flags,sizeof(flags),&bytes)&&!(flags.dwFlags&WSF_VISIBLE)&&_wcsicmp(actual,L"WinSta0")&&_wcsicmp(actual,expected)==0;
}
OverlayPanel* overlayPanel=nullptr;std::filesystem::path preferencePath;
void SavePreferences(){
 if(IsSealedStation()||preferencePath.empty())return;
 try{std::filesystem::create_directories(preferencePath.parent_path());auto temp=preferencePath;temp+=L".pending";{std::ofstream f(temp);malemod::controls::WritePreferences(f,{controls,garmentStyle,throbMode,idleChatter});f.close();if(!f)throw std::runtime_error("Cannot save v2 settings");}if(!MoveFileExW(temp.c_str(),preferencePath.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))throw std::runtime_error("Cannot replace v2 settings");}catch(...){OutputDebugStringW(L"MaleMod v2: settings could not be saved\n");}
}
void LoadPreferences(){
 if(IsSealedStation())return;wchar_t local[32768]{};auto n=GetEnvironmentVariableW(L"LOCALAPPDATA",local,32768);if(!n||n>=32768)return;
 preferencePath=std::filesystem::path(local)/L"MaleMod"/L"Witcher3"/L"v2.settings";std::ifstream f(preferencePath);malemod::controls::MenuPreferences p;if(f&&malemod::controls::ReadPreferences(f,p)){controls=p.controls;garmentStyle=p.garment;throbMode=p.throbMode;idleChatter=p.idleChatter;}
}
surface::Controls ReadMenu(){std::lock_guard<std::mutex> lock(menuMutex);surface::Controls result;result.values=controls;return result;}
void QueueFeature(FeatureAction action,float value=0){
 std::lock_guard<std::mutex> lock(menuMutex);
 if(action==FeatureAction::SetThrob){if(!std::isfinite(value)||value<0||value>3||value!=unsigned(value))return;throbMode=unsigned(value);}
 else if(action==FeatureAction::SetIdleChatter)idleChatter=value>0;
 else if(action==FeatureAction::SetGarment){garmentStyle=value>0?1u:0u;SavePreferences();return;}
 else if(action==FeatureAction::ToggleLighting){correctedLighting=!correctedLighting;return;}
 else if(action==FeatureAction::ResetDefaults){controls.fill(50);controls[0]=2;garmentStyle=0;throbMode=0;idleChatter=false;resetRequested=true;featureActions.clear();}
 if(action!=FeatureAction::CancelTeaching||featureActions.empty()||featureActions.back().first!=action)featureActions.emplace_back(action,value);
 SavePreferences();
}
bool WriteMenu(unsigned i,float value){if(!malemod::controls::ValidMenuValue(i,value))return false;std::lock_guard<std::mutex> lock(menuMutex);controls[i]=value;featureActions.emplace_back(FeatureAction::CancelTeaching,0);SavePreferences();return true;}
malemod::controls::menu::State ReadFeatures(){auto p=std::atomic_load(&featureSnapshot);auto result=p?*p:malemod::controls::menu::State{};result.throbMode=throbMode;result.idleChatter=idleChatter;result.garment=garmentStyle;result.anatomyVisible=FloatDrawRecentlySeen(0);return result;}
void TraceFeatures(FILE* file){
 if(!file||!host)return;const auto& p=host->Input();const auto counts=clinicalCollision.Counts();const auto* engine=clinical?&clinical->Runtime().Engine():nullptr;
 const auto input=OverlayInputStatus();std::fprintf(file,",\"inputFence\":{\"imports\":%u,\"async\":%u,\"raw\":%u,\"messages\":%u,\"direct\":%u,\"keyboards\":%u}",input.imports,input.asyncKeys,input.rawKeys,input.messages,input.directKeys,input.keyboards);
 const auto visibility=FloatDrawVisibility(0);std::fprintf(file,",\"visibility\":{\"present\":%llu,\"lastDrawPresent\":%llu,\"lastDrawAgeMs\":%llu,\"menuVisible\":%s}",visibility[0],visibility[1],visibility[2],ReadFeatures().anatomyVisible?"true":"false");
 std::fprintf(file,",\"clinicalAfterServices\":%llu",clinicalAfterServices);
 std::fprintf(file,",\"activeSDKTicks\":%llu,\"visibleSDKTicks\":%llu,\"visiblePhysicsServices\":%llu,\"hiddenSkippedTicks\":%llu,\"nativeDrawFlags\":%u,\"nativeRendererFailed\":%s",activeTicks,visibleTicks,visibleServices,hiddenSkips,FloatDrawFlags(),((FloatDrawFlags()|GarmentDrawFlags()|FluidDrawFlags())&128)?"true":"false");
 if(clinical){std::fprintf(file,",\"clinicalErrorSerial\":%llu,\"clinicalRetryPending\":%s,\"clinicalLastError\":\"",static_cast<unsigned long long>(clinical->Runtime().ErrorSerial()),clinical->Runtime().PassiveRetryPending()?"true":"false");for(unsigned char ch:clinical->Runtime().LastError()){if(ch=='"'||ch=='\\')std::fputc('\\',file);if(ch>=32)std::fputc(ch,file);else std::fprintf(file,"\\u%04x",unsigned(ch));}std::fprintf(file,"\"");}
 std::fprintf(file,",\"features\":{\"throb\":%u,\"milliseconds\":%u,\"resetClock\":%u,\"active\":%u,\"time\":%.9g,\"end\":%.9g,\"rootJoint\":%u,\"wobble\":%.9g,\"angleGain\":[",p.features.throbMode,p.features.milliseconds,p.features.resetClock,p.features.teachingActive,p.features.teachingTime,p.features.teachingEnd,p.features.rootJointRequested,p.features.lateralWobbleDegrees);
 for(unsigned i=0;i<4;i++)std::fprintf(file,"%s%.9g",i?",":"",p.features.angleGain[i]);std::fprintf(file,"],\"lateralGain\":[");for(unsigned i=0;i<4;i++)std::fprintf(file,"%s%.9g",i?",":"",p.features.lateralGain[i]);
 std::fprintf(file,"]},\"clinical\":{\"mode\":%u,\"active\":%s,\"time\":%.9g,\"liquidIndices\":%zu,\"depositIndices\":%zu,\"emittedVolume\":%.9g,\"depositedClear\":%.9g,\"depositedOpaque\":%.9g,\"finalPumpVolume\":%.9g,\"finalPumpImpacts\":%u,\"cueMask\":%u,\"rendererFlags\":%u,\"publications\":%u,\"pendingQueries\":%u,\"sceneQueries\":%u,\"sceneHits\":%u,\"audioPhaseCounts\":[%u,%u],\"audioIdleCount\":%u,\"audioPlayed\":%u,\"audioFailed\":%u},\"correctedLighting\":%s",throbMode.load(),clinical&&clinical->Runtime().Active()?"true":"false",clinical?clinical->Runtime().Seconds():0,clinicalOutput?clinicalOutput->liquid.indices.size():0,clinicalOutput?clinicalOutput->deposits.indices.size():0,engine?engine->fluid.emittedVolume:0,engine?engine->depositedVolume[0]:0,engine?engine->depositedVolume[1]:0,engine?engine->finalPumpDepositedVolume:0,engine?engine->finalPumpDepositedImpacts:0,clinicalCueMask,FluidDrawFlags(),FluidDrawPublications(),counts[0],counts[1],counts[2],clinicalAudio.PhaseCount(0),clinicalAudio.PhaseCount(1),clinicalAudio.IdleCount(),clinicalAudio.Played(),clinicalAudio.Failed(),correctedLighting?"true":"false");
}
void EnsureOverlay(){
 if(overlayPanel)return;struct Windows{HWND result=nullptr;unsigned count=0;bool probe=false;} windows;windows.probe=IsSealedStation();
 EnumWindows([](HWND w,LPARAM data)->BOOL{auto* p=reinterpret_cast<Windows*>(data);if(EligibleOverlayParent(w,p->probe)){p->result=w;++p->count;}return TRUE;},reinterpret_cast<LPARAM>(&windows));
 if(windows.count==1){overlayParent=windows.result;overlayPanel=new OverlayPanel(windows.result,ReadMenu,WriteMenu,ReadFeatures,QueueFeature,windows.probe);}
}
void RuntimeFrame(void*,void* frame,void* result){
 const auto mainBegan=std::chrono::steady_clock::now();
 invoked=true;std::int32_t epoch=0;float seconds=0;bool paused=false;std::array<ScriptVector,8> v{};
 Parameter(frame,epoch);Parameter(frame,seconds);Parameter(frame,paused);for(auto& p:v)Parameter(frame,p);FinishParameters(frame);
 int status=0;
 try{
  std::lock_guard<std::mutex> lock(mutex);
  if(!epoch||paused){renderPublication.Clear();DiscardCheckpoints("suspend");lastSeconds=0;if(clinical)clinical->Suspend(GetTickCount());if(!epoch){if(clinical){clinical->Cancel();clinical->Runtime().Engine().deposits.marks.clear();}clinicalCollision.Clear();clinicalOutput={};garmentOutput={};clinicalCues.clear();std::atomic_store(&featureSnapshot,std::shared_ptr<const malemod::controls::menu::State>{});FramePublicationLock publish(FramePublicationMutex());LiveRenderFeed({});GarmentRendererFeed({});FluidRendererFeed({},.01);}status=paused?1:0;}
  else if(host&&binding&&epoch>0&&std::isfinite(seconds)){
   if(lastEpoch!=unsigned(epoch)){renderPublication.Clear();DiscardCheckpoints("actor-change");}
   if(renderPublication.Pending())throw std::runtime_error("Previous completed frame has no post-Step pose publication");
   EnsureOverlay();std::array<float,18> frameControls;unsigned frameStyle;bool reset;std::vector<std::pair<FeatureAction,float>> actions;{std::lock_guard<std::mutex> menu(menuMutex);frameControls=controls;frameStyle=garmentStyle.load();reset=resetRequested;resetRequested=false;actions.swap(featureActions);}
   const auto now=GetTickCount();const bool visible=FloatDrawRecentlySeen(0),focused=IsSealedStation()||(overlayParent&&GetForegroundWindow()==overlayParent);
   ++activeTicks;if(visible)++visibleTicks;
   if(clinical){
    if(lastEpoch!=unsigned(epoch)){clinical->Cancel();clinical->Suspend(now);clinicalCollision.Clear();clinical->Runtime().Engine().deposits.marks.clear();clinicalOutput={};clinicalCues.clear();clinicalCueMask=0;}
    for(const auto& action:actions){switch(action.first){case FeatureAction::SetThrob:clinical->Runtime().SetThrob(unsigned(action.second));break;case FeatureAction::SetIdleChatter:clinical->Runtime().SetIdleChatter(action.second>0);break;case FeatureAction::ToggleTeaching:clinicalCollision.Clear();clinicalCueMask=0;clinical->Runtime().Toggle(now^(++clinicalCueSerial*0x9e3779b9u));break;case FeatureAction::CancelTeaching:clinical->Cancel();clinicalCollision.Clear();break;case FeatureAction::ResetDefaults:clinical->Reset();clinicalCollision.Clear();clinicalCueMask=0;break;default:break;}}
    clinical->Before(host->Input(),now,focused,visible);
    auto state=std::make_shared<malemod::controls::menu::State>();state->throbMode=throbMode;state->idleChatter=idleChatter;state->garment=frameStyle;state->teachingActive=clinical->Runtime().Active();state->teachingSeconds=clinical->Runtime().Seconds();state->anatomyVisible=visible;state->transformAvailable=actorReady;std::atomic_store(&featureSnapshot,std::shared_ptr<const malemod::controls::menu::State>(state));
   }
   if(!reset&&lastEpoch==unsigned(epoch)&&!visible&&host->Input().controls==malemod::controls::CanonicalPacketOrder(frameControls)){++hiddenSkips;lastSeconds=0;tracker.Reset();if(result)*static_cast<std::int32_t*>(result)=1;return;}
   if(poseEpoch!=unsigned(epoch)||poseSeconds!=seconds||!actorReady)throw std::runtime_error("Missing current actor pose");
   for(const auto& bone:binding->Bones())if(!boneReady[bone.id])throw std::runtime_error("Incomplete current native pose");
   auto began=std::chrono::steady_clock::now();auto& p=host->Input();
   if(lastEpoch!=unsigned(epoch)||reset){tracker.Reset();lastSeconds=0;lastEpoch=unsigned(epoch);++simulationEpoch;}
   float dt=lastSeconds?seconds-lastSeconds:1.f/60;lastSeconds=seconds;
   if(dt<=0||dt>.15f)dt=1.f/60;
   p.epoch=simulationEpoch;p.garmentStyle=frameStyle&&GarmentRendererReady()?1u:0u;p.controls=malemod::controls::CanonicalPacketOrder(frameControls);p.seconds=dt;
   // Feed the observed pelvis basis/translation through the exact canonical
   // motion filter in source coordinates. Actor movement is not camera input.
   const auto pelvis=binding->PelvisDelta(bonePoses[9]);const auto inverse=v2::Inverse(pelvis);auto motion=binding->MotionDelta(pelvis);
   tracker.TrackPoseOnly(GetTickCount(),motion);p.pitchForce=tracker.Read().motionPitchForce;p.yawForce=tracker.Read().motionYawForce;
   p.collisionOverride=1;for(unsigned i=0;i<4;i++){auto q=binding->ToSource(v2::Transform(inverse,{v[i+4].x,v[i+4].y,v[i+4].z}));p.thighs[i]={q[0],q[1],q[2]};}
   const auto& out=host->Step();if(visible)++visibleServices;auto sampled=std::chrono::steady_clock::now();auto render=binding->Evaluate(out,correctedLighting);auto converted=std::chrono::steady_clock::now();
   {auto state=std::make_shared<malemod::controls::menu::State>(ReadFeatures());state->displayAnimated=out.features.throbMode!=0||out.features.teachingActive!=0;state->displayControls=out.featureOutput.effectiveControls;std::atomic_store(&featureSnapshot,std::shared_ptr<const malemod::controls::menu::State>(state));}
   pendingFrameBegan=mainBegan;pendingSourceWaitMs=std::chrono::duration<double,std::milli>(sampled-began).count();pendingBindingMs=std::chrono::duration<double,std::milli>(converted-sampled).count();pendingActorWorld=actorWorld;
   renderPublication.Stage({unsigned(epoch),frameStyle,seconds,out.completed,poseRevision,render,{},now,dt});
   ++frameCount;runtimeFlags.fetch_or(2);status=2;
   pendingMainEnded=std::chrono::steady_clock::now();pendingMainCallbackMs=std::chrono::duration<double,std::milli>(pendingMainEnded-mainBegan).count();

  }
 }catch(const std::exception& e){std::lock_guard<std::mutex> failure(mutex);renderPublication.Clear();DiscardCheckpoints("failure");runtimeFlags.fetch_or(32);status=6;if(clinical)clinical->Cancel();clinicalCollision.Clear();clinicalOutput={};garmentOutput={};clinicalCues.clear();{FramePublicationLock publish(FramePublicationMutex());LiveRenderFeed({});GarmentRendererFeed({});FluidRendererFeed({},.01);}if(trace){std::fprintf(trace,"{\"failed\":true,\"error\":\"%s\"}\n",e.what());std::fflush(trace);}}
 if(result)*static_cast<std::int32_t*>(result)=status;
}
void RefreshRenderPose(void*,void* frame,void* result){
 const auto lateBegan=std::chrono::steady_clock::now();
 std::int32_t epoch=0;float seconds=0;Parameter(frame,epoch);Parameter(frame,seconds);FinishParameters(frame);bool success=false;
 try{
  std::lock_guard<std::mutex> lock(mutex);
  if(!renderPublication.Pending())throw std::runtime_error("Render-pose refresh has no pending source frame");
  if(!host||!binding)throw std::runtime_error("Render-pose refresh has no source");
  const auto& p=host->Input();
  const bool complete=epoch>0&&unsigned(epoch)==lastEpoch&&poseEpoch==unsigned(epoch)&&poseSeconds==seconds&&actorReady&&
   std::all_of(binding->Bones().begin(),binding->Bones().end(),[](const auto& bone){return boneReady[bone.id];});
  unsigned frameStyle=0;std::uint32_t mainClockMs=0;float mainCoreSeconds=0;
  struct Presentation {std::shared_ptr<const GarmentDelivery> garment;std::shared_ptr<const ClinicalDelivery> fluid;};
  success=renderPublication.Refresh(unsigned(epoch),seconds,p.completed,poseRevision,complete,
   [&](const auto& pending){
    frameStyle=pending.style;mainClockMs=pending.milliseconds;mainCoreSeconds=pending.coreSeconds;
    Presentation presentation;
    if(frameStyle&&garment){
     try{presentation.garment=garment->Evaluate(*binding,*pending.surface,bonePoses,actorWorld,p);}
     catch(const std::exception& e){runtimeFlags.fetch_or(1024);if(trace){std::fprintf(trace,"{\"garmentFailed\":true,\"error\":\"%s\"}\n",e.what());std::fflush(trace);}}
    }
    if(clinical){
     const auto now=pending.milliseconds;const double clock=double(now)*.001;
     if(clock<clinicalLastClock)clinicalCollision.Clear();clinicalLastClock=clock;clinicalCollision.AdvanceTime(clock);
     const auto& e=clinical->Runtime().Engine();
     if(clinicalBody&&(clinical->Runtime().Active()||throbMode||e.fluid.Live()||!e.deposits.marks.empty()))clinicalBody->Update(*binding,*pending.surface,bonePoses,actorWorld,p);
     const auto pelvis=binding->PelvisDelta(bonePoses[9]);
     clinicalOutput=clinical->After(p,*binding,pelvis,actorWorld,pending.coreSeconds,now);++clinicalAfterServices;
    }
    PositionCapturePose(pending.surface,presentation.garment,poseRevision,actorWorld.data(),bonePoses[0].data());
    presentation.fluid=clinicalOutput;return presentation;
   },[&](const auto& pending,auto presentation){
    FramePublicationLock publish(FramePublicationMutex());
    try{garmentOutput=std::move(presentation.garment);LiveRenderFeed(pending.surface);GarmentRendererFeed(garmentOutput);FluidRendererFeed(presentation.fluid,.01);}
    catch(...){LiveRenderFeed({});GarmentRendererOrigin({},false);FluidRendererOrigin({},false);throw;}
   });
  if(!success)throw std::runtime_error("Incomplete, stale or mismatched post-Step render pose");
  ++renderPosePublications;publishedSourceSerial=p.completed;publishedPoseRevision=poseRevision;runtimeFlags.fetch_or(4);
  auto checkpoints=pendingCheckpoints.Take();
  for(auto stage:checkpoints){const bool written=WriteCheckpoint(stage);if(trace)std::fprintf(trace,"{\"checkpointDeferred\":%d,\"written\":%s,\"sourceSerial\":%llu}\n",stage,written?"true":"false",publishedSourceSerial);}
  const float dt=p.seconds;double actorDelta=0;for(unsigned a=0;a<3;a++){double d=actorWorld[a*4+3]-pendingActorWorld[a*4+3];actorDelta+=d*d;}actorDelta=std::sqrt(actorDelta);
   const auto lateEnded=std::chrono::steady_clock::now();
   const double lateCallbackMs=std::chrono::duration<double,std::milli>(lateEnded-lateBegan).count();
   const double renderPoseWallDelayMs=std::chrono::duration<double,std::milli>(lateBegan-pendingMainEnded).count();
   const double simToRenderWallMs=std::chrono::duration<double,std::milli>(lateEnded-pendingFrameBegan).count();
   if(trace){double ms=pendingMainCallbackMs+lateCallbackMs;std::fprintf(trace,"{\"frame\":%u,\"epoch\":%u,\"request\":%llu,\"completed\":%llu,\"seconds\":%.9g,\"dt\":%.9g,\"physicsServices\":%llu,\"surfaceServices\":%llu,\"physicsMs\":%.6g,\"surfaceMs\":%.6g,\"callbackMs\":%.6g,\"sourceWaitMs\":%.6g,\"bindingMs\":%.6g,\"drawSequence\":%u,\"resourceMask\":%u,\"lodMask\":%u,\"coverageDraws\":%u,\"garmentStyle\":%u,\"garmentTriangles\":%u,\"garmentFlags\":%u,\"garmentPublications\":%u,\"input\":[",frameCount.load(),p.epoch,p.request,p.completed,seconds,dt,p.physicsServices,p.surfaceServices,p.physicsMilliseconds,p.surfaceMilliseconds,ms,pendingSourceWaitMs,pendingBindingMs,FloatDrawSequence(),FloatDrawResourceMask(),ModularDrawCompletedLODMask(),FloatDrawCoverageCount(),frameStyle,garmentOutput?unsigned(garmentOutput->output.mesh.triangles.size()):0,GarmentDrawFlags(),GarmentDrawPublications());for(unsigned i=0;i<18;i++)std::fprintf(trace,"%s%.9g",i?",":"",p.controls[i]);std::fprintf(trace,",%.9g,%.9g,%.9g,%u",p.seconds,p.pitchForce,p.yawForce,p.collisionOverride);for(const auto& q:p.thighs)std::fprintf(trace,",%.9g,%.9g,%.9g",q.x,q.y,q.z);std::fprintf(trace,",%u]",p.garmentStyle);std::fprintf(trace,",\"renderPoseRevision\":%llu,\"renderPosePublications\":%llu,\"renderPoseActorDeltaMeters\":%.9g",poseRevision,renderPosePublications,actorDelta);std::fprintf(trace,",\"mainCallbackMs\":%.6g,\"lateCallbackMs\":%.6g,\"renderPoseWallDelayMs\":%.6g,\"simToRenderWallMs\":%.6g",pendingMainCallbackMs,lateCallbackMs,renderPoseWallDelayMs,simToRenderWallMs);std::fprintf(trace,",\"mainCapturedMilliseconds\":%u,\"mainCapturedDt\":%.9g",mainClockMs,mainCoreSeconds);TraceFeatures(trace);std::fprintf(trace,"}\n");std::fflush(trace);}
 }catch(const std::exception& e){std::lock_guard<std::mutex> failure(mutex);renderPublication.Clear();DiscardCheckpoints("failure");runtimeFlags.fetch_or(32);if(clinical)clinical->Cancel();clinicalCollision.Clear();clinicalOutput={};garmentOutput={};clinicalCues.clear();{FramePublicationLock publish(FramePublicationMutex());LiveRenderFeed({});GarmentRendererFeed({});FluidRendererFeed({},.01);}if(trace){std::fprintf(trace,"{\"failed\":true,\"renderPoseFailed\":true,\"error\":\"%s\"}\n",e.what());std::fflush(trace);}}
 if(result)*static_cast<bool*>(result)=success;
}
void BonePose(void*,void* frame,void*){
 std::int32_t epoch=0,bone=0;float seconds=0;std::array<ScriptVector,4> v{};Parameter(frame,epoch);Parameter(frame,bone);Parameter(frame,seconds);for(auto& p:v)Parameter(frame,p);FinishParameters(frame);
 if(epoch<=0||bone<-1||bone>=94||!std::isfinite(seconds))return;
 std::lock_guard<std::mutex> lock(mutex);if(bone<0||poseEpoch!=unsigned(epoch)||poseSeconds!=seconds){poseEpoch=unsigned(epoch);poseSeconds=seconds;boneReady.fill(false);actorReady=false;if(bone<0)++poseRevision;}
 v2::Matrix m{};m[15]=1;for(unsigned c=0;c<4;c++){m[c]=v[c].x;m[4+c]=v[c].y;m[8+c]=v[c].z;}
 try{v2::Inverse(m);}catch(...){return;}if(bone<0){actorWorld=m;actorReady=true;}else{bonePoses[bone]=m;boneReady[bone]=true;}
}
void SurfaceActive(void*,void* frame,void* result){std::int32_t epoch=0;Parameter(frame,epoch);FinishParameters(frame);if(result)*static_cast<bool*>(result)=epoch>0&&unsigned(epoch)==lastEpoch&&FloatDrawActive(simulationEpoch)&&FloatDrawRecentlySeen(0);}
void FullMode(void*,void* frame,void* result){FinishParameters(frame);if(result)*static_cast<bool*>(result)=host&&binding;}
void OverlayOpen(void*,void* frame,void* result){FinishParameters(frame);if(result)*static_cast<bool*>(result)=overlayPanel&&overlayPanel->Open();}
void ProbePoseSample(void*,void* frame,void* result){float seconds=0;bool paused=false;std::array<ScriptVector,8> v{};Parameter(frame,seconds);Parameter(frame,paused);for(auto& p:v)Parameter(frame,p);FinishParameters(frame);bool valid=IsSealedStation()&&std::isfinite(seconds);for(const auto& p:v)valid=valid&&std::isfinite(p.x)&&std::isfinite(p.y)&&std::isfinite(p.z)&&std::isfinite(p.w);if(valid){std::lock_guard<std::mutex> lock(mutex);if(trace){std::fprintf(trace,"{\"iterationReadback\":true,\"seconds\":%.9g,\"paused\":%s,\"vectors\":[",seconds,paused?"true":"false");for(unsigned i=0;i<v.size();i++)std::fprintf(trace,"%s[%.9g,%.9g,%.9g,%.9g]",i?",":"",v[i].x,v[i].y,v[i].z,v[i].w);std::fprintf(trace,"]}\n");std::fflush(trace);}else valid=false;}if(result)*static_cast<bool*>(result)=valid;}
void SetControl(void*,void* frame,void* result){std::int32_t index=0;float value=0;Parameter(frame,index);Parameter(frame,value);FinishParameters(frame);bool valid=index>=0&&malemod::controls::ValidMenuValue(unsigned(index),value);if(valid){std::lock_guard<std::mutex> lock(menuMutex);controls[index]=value;}if(result)*static_cast<bool*>(result)=valid;}
void GetControl(void*,void* frame,void* result){std::int32_t index=0;Parameter(frame,index);FinishParameters(frame);std::lock_guard<std::mutex> lock(menuMutex);if(result)*static_cast<float*>(result)=index>=0&&index<18?controls[index]:-1;}
void TypedProbe(void*,void* frame,void* result){std::int32_t index=0;float scale=0;ScriptVector p;Parameter(frame,index);Parameter(frame,scale);Parameter(frame,p);FinishParameters(frame);if(result)*static_cast<ScriptVector*>(result)={p.x*scale+index,p.y*scale,p.z*scale,p.w*scale};}
void TypedProbeResult(void*,void* frame,void*){bool success=false;Parameter(frame,success);FinishParameters(frame);}
void Ready(void*,void* frame,void* result){invoked=true;FinishParameters(frame);if(result)*static_cast<bool*>(result)=registered&&!registrationFailed;}
void SealedSession(void*,void* frame,void* result){const bool ok=IsSealedStation();sealedFlags=ok?3:1;FinishParameters(frame);if(result)*static_cast<bool*>(result)=ok;}
bool WriteCheckpoint(std::int32_t stage){
 auto output=FloatDrawCompleted();bool ok=stage>=0&&stage<1000&&host&&IsSealedStation()&&output&&FloatDrawActive(output->epoch)&&FloatDrawResourceMask()==3&&!(runtimeFlags&32)&&!((FloatDrawFlags()|GarmentDrawFlags()|FluidDrawFlags())&128);
 if(ok&&stage>=0&&stage<1000&&host){
  auto prefix=moduleDirectory/(L"v2-checkpoint-"+std::to_wstring(stage));auto path=prefix;path+=L".json";std::ofstream metadata(path);metadata<<"{\"stage\":"<<stage<<",\"sequence\":"<<host->Input().completed<<",\"hostSourceSerial\":"<<host->Input().completed<<",\"garmentSerial\":"<<(garmentOutput?garmentOutput->serial:0)<<",\"publishedSerial\":"<<publishedSourceSerial<<",\"poseRevision\":"<<poseRevision<<",\"publishedPoseRevision\":"<<publishedPoseRevision<<",\"serialsMatch\":"<<((host->Input().completed==publishedSourceSerial&&(!garmentOutput||garmentOutput->serial==publishedSourceSerial))?"true":"false")<<",\"controls\":[";for(unsigned i=0;i<18;i++)metadata<<(i?",":"")<<ReadMenu().values[i];metadata<<"],\"garment\":"<<garmentStyle.load()<<",\"lodMask\":"<<ModularDrawCompletedLODMask()<<",\"throb\":"<<throbMode.load()<<",\"idleChatter\":"<<(idleChatter?"true":"false")<<",\"clinicalActive\":"<<(clinical&&clinical->Runtime().Active()?"true":"false")<<",\"clinicalSeconds\":"<<(clinical?clinical->Runtime().Seconds():0)<<",\"actorWorld\":[";for(unsigned a=0;a<16;a++)metadata<<(a?",":"")<<actorWorld[a];metadata<<"],\"effectiveControls\":[";for(unsigned i=0;i<18;i++)metadata<<(i?",":"")<<host->Input().featureOutput.effectiveControls[i];metadata<<"]}\n";
  path=prefix;path+=L".source";std::ofstream data(path,std::ios::binary);const auto& p=host->Input();data.write(reinterpret_cast<const char*>(p.anatomy.data()),p.anatomy.size());data.write(reinterpret_cast<const char*>(p.body0.data()),p.body0.size());data.write(reinterpret_cast<const char*>(p.body1.data()),p.body1.size());
  // Sealed checkpoints retain the actual source guides and CPU garment feed,
  // avoiding approximate reconstruction of pressure controls during diagnosis.
  path=prefix;path+=L".packet";std::ofstream packet(path,std::ios::binary);packet.write(reinterpret_cast<const char*>(&p),sizeof(p));
  path=prefix;path+=L".pose";std::ofstream pose(path,std::ios::binary);pose.write(reinterpret_cast<const char*>(actorWorld.data()),sizeof(actorWorld));pose.write(reinterpret_cast<const char*>(bonePoses.data()),sizeof(bonePoses));
  if(garmentOutput){
   path=prefix;path+=L".garment";std::ofstream garmentData(path,std::ios::binary);const auto& mesh=garmentOutput->output.mesh;
   static_assert(sizeof(GarmentDelivery::Vertex)==48&&sizeof(GarmentDelivery::Triangle)==16);
   const std::uint32_t header[]{0x3143474du,garmentOutput->epoch,std::uint32_t(garmentOutput->serial),std::uint32_t(garmentOutput->serial>>32),std::uint32_t(mesh.vertices.size()),std::uint32_t(mesh.triangles.size())};
   garmentData.write(reinterpret_cast<const char*>(header),sizeof(header));garmentData.write(reinterpret_cast<const char*>(mesh.vertices.data()),mesh.vertices.size()*sizeof(GarmentDelivery::Vertex));garmentData.write(reinterpret_cast<const char*>(mesh.triangles.data()),mesh.triangles.size()*sizeof(GarmentDelivery::Triangle));
  }else{path=prefix;path+=L".garment";std::ofstream garmentData(path,std::ios::binary);const std::uint32_t header[]{0x3143474du,p.epoch,std::uint32_t(p.completed),std::uint32_t(p.completed>>32),0,0};garmentData.write(reinterpret_cast<const char*>(header),sizeof(header));}
  GraphicsMaterialCaptureCheckpoint(unsigned(stage),p.epoch,p.completed);
  PositionCaptureCheckpoint(unsigned(stage),p.epoch,p.completed);
 }
 return ok;
}
void TestCheckpoint(void*,void* frame,void* result){
 std::int32_t stage=0;Parameter(frame,stage);FinishParameters(frame);std::lock_guard<std::mutex> lock(mutex);bool ok=false;
 if(IsSealedStation()&&host&&stage>=0&&stage<1000&&!(runtimeFlags&32)){
  if(renderPublication.Pending()){
   ok=pendingCheckpoints.Queue(stage);
  }else ok=WriteCheckpoint(stage);
 }
 if(result)*static_cast<bool*>(result)=ok;
}

void GarmentControl(void*,void* f,void*){std::int32_t style=0;Parameter(f,style);FinishParameters(f);if(style>=0&&style<=1){std::lock_guard<std::mutex> lock(menuMutex);garmentStyle=unsigned(style);}}
void GarmentState(void*,void* f,void* result){FinishParameters(f);std::lock_guard<std::mutex> lock(mutex);if(result)*static_cast<ScriptVector*>(result)={float(garmentStyle),garmentOutput?float(garmentOutput->output.mesh.triangles.size()):0,float(GarmentDrawFlags()),float(GarmentDrawPublications())};}
void GarmentCarrier(void*,void* f,void*){ScriptVector p;bool valid=false;Parameter(f,p);Parameter(f,valid);FinishParameters(f);GarmentRendererOrigin({p.x,p.y,p.z},valid);}
void ClinicalCarrier(void*,void* f,void*){ScriptVector p;bool valid=false;Parameter(f,p);Parameter(f,valid);FinishParameters(f);FluidRendererOrigin({p.x,p.y,p.z},valid&&std::isfinite(p.x)&&std::isfinite(p.y)&&std::isfinite(p.z));}
void ClinicalControl(void*,void* f,void*){std::int32_t i=0;float v=0;Parameter(f,i);Parameter(f,v);FinishParameters(f);if(!std::isfinite(v))return;if(i==0&&v>=0&&v<=3&&v==unsigned(v))QueueFeature(FeatureAction::SetThrob,v);else if(i==1){if(v>0)QueueFeature(FeatureAction::ToggleTeaching);else QueueFeature(FeatureAction::CancelTeaching);}else if(i==2)QueueFeature(FeatureAction::SetIdleChatter,v);else if(i==3&&v>0){std::lock_guard<std::mutex> lock(mutex);if(idleChatter&&clinical&&!clinical->Runtime().Active())clinicalAudio.Idle();}}
void ClinicalQuery(void*,void* f,void* result){std::int32_t i=0;Parameter(f,i);FinishParameters(f);ScriptVector v{};static thread_local ClinicalCollision::Query q;if(i==0){q=clinicalCollision.Next();v={q.from.x*.01f,q.from.y*.01f,q.from.z*.01f,float(q.token)};}else if(i==1)v={q.to.x*.01f,q.to.y*.01f,q.to.z*.01f,q.radius*.01f};else if(i==2)v.w=float(q.token);if(result)*static_cast<ScriptVector*>(result)=v;}
void ClinicalHit(void*,void* f,void*){std::int32_t token=0;bool hit=false;ScriptVector p,n;Parameter(f,token);Parameter(f,hit);Parameter(f,p);Parameter(f,n);FinishParameters(f);if(token>0&&std::isfinite(p.x)&&std::isfinite(p.y)&&std::isfinite(p.z)&&std::isfinite(n.x)&&std::isfinite(n.y)&&std::isfinite(n.z))clinicalCollision.Result(unsigned(token),hit,{p.x*100,p.y*100,p.z*100},{n.x,n.y,n.z});}
void ClinicalState(void*,void* f,void* result){FinishParameters(f);std::lock_guard<std::mutex> lock(mutex);ScriptVector v{};if(clinical)v={float(throbMode),clinical->Runtime().Active()?1.f:0.f,clinical->Runtime().Seconds(),clinicalOutput?float(clinicalOutput->liquid.indices.size()+clinicalOutput->deposits.indices.size()):0};if(result)*static_cast<ScriptVector*>(result)=v;}
void ClinicalDeposits(void*,void* f,void* result){FinishParameters(f);std::lock_guard<std::mutex> lock(mutex);ScriptVector v{};if(clinical){const auto& e=clinical->Runtime().Engine();v={float(e.depositedVolume[0]),float(e.depositedVolume[1]),float(e.finalPumpDepositedVolume),float(e.finalPumpDepositedImpacts)};}if(result)*static_cast<ScriptVector*>(result)=v;}
void ClinicalCue(void*,void* f,void* result){FinishParameters(f);std::lock_guard<std::mutex> lock(mutex);ScriptVector v{};if(!clinicalCues.empty()){v=clinicalCues.front();clinicalCues.erase(clinicalCues.begin());}if(result)*static_cast<ScriptVector*>(result)=v;}
void RegisterHook(){
 originalRegisterGlobals();if(registered||registrationFailed)return;
 for(const auto& item:std::array<std::pair<const char*,NativeCallback>,24>{{
  {"MaleModNativeClinicalDeposits",ClinicalDeposits},{"MaleModNativeGarmentControl",GarmentControl},{"MaleModNativeGarmentState",GarmentState},{"MaleModNativeGarmentCarrier",GarmentCarrier},{"MaleModNativeClinicalCue",ClinicalCue},{"MaleModNativeClinicalCarrier",ClinicalCarrier},{"MaleModNativeClinicalControl",ClinicalControl},{"MaleModNativeClinicalQuery",ClinicalQuery},{"MaleModNativeClinicalHit",ClinicalHit},{"MaleModNativeClinicalState",ClinicalState},{"MaleModNativeReady",Ready},{"MaleModNativeSetControl",SetControl},{"MaleModNativeGetControl",GetControl},{"MaleModNativeTypedProbe",TypedProbe},{"MaleModNativeTypedProbeResult",TypedProbeResult},{"MaleModNativePoseSample",ProbePoseSample},{"MaleModNativeFrame",RuntimeFrame},{"MaleModNativeRefreshRenderPose",RefreshRenderPose},{"MaleModNativeOverlayOpen",OverlayOpen},{"MaleModNativeBonePose",BonePose},{"MaleModNativeSurfaceActive",SurfaceActive},{"MaleModNativeFullMode",FullMode},{"MaleModNativeSealedSession",SealedSession},{"MaleModNativeTestCheckpoint",TestCheckpoint}}})if(!Register(item.first,item.second)){registrationFailed=true;return;}
 registered=true;
}
}
}
extern "C" __declspec(dllexport) DWORD WINAPI MaleModInitialize(void*){
 using namespace malemod::witcher;const auto diagnosticError=GetLastError();const bool diagnosticSealed=IsSealedStation();SetLastError(diagnosticError);StartupDiagnostics diagnostic(diagnosticSealed,reinterpret_cast<const void*>(&MaleModInitialize));diagnostic.Step("entry");
 if(initialized)return diagnostic.Return(0,"already-initialized");engineBase=reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
 if(!VerifyExecutable())return diagnostic.Return(2,"executable-guard");
 if(!CheckPrefixes())return diagnostic.Return(2,"code-prefix-guard");diagnostic.Step("profile-guards-passed");
 if(!OverlayInputInstall(GetModuleHandleW(nullptr)))return diagnostic.Return(9,"input-import-guard");diagnostic.Step("input-imports-installed");
 try{
  wchar_t path[32768]{};HMODULE module=nullptr;GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,reinterpret_cast<LPCWSTR>(&MaleModInitialize),&module);GetModuleFileNameW(module,path,32768);moduleDirectory=std::filesystem::path(path).parent_path();LoadPreferences();
  diagnostic.Step("module-and-preferences-ready");
  if(!VerifyFile(moduleDirectory/L"canonical_worker.exe",v2::identity::worker)||!VerifyFile(moduleDirectory/L"geralt-source-binding.bin",v2::identity::binding)||!VerifyFile(moduleDirectory/L"graphics-owned-fingerprints.bin",v2::identity::fingerprints))return diagnostic.Return(7,"core-file-identity");
  if(!VerifyFile(moduleDirectory/L"geralt-meridian-coverage.bin",v2::identity::coverage))return diagnostic.Return(7,"coverage-file-identity");
  if(!VerifyFile(moduleDirectory/L"geralt-meridian-binding.bin",v2::identity::garment)||!VerifyFile(moduleDirectory/L"garment.render",v2::identity::garmentRender))return diagnostic.Return(7,"garment-file-identity");
  if(!VerifyFile(moduleDirectory/L"geralt-clinical-topology.bin",v2::identity::clinicalTopology)||!VerifyFile(moduleDirectory/L"clinical.render",v2::identity::clinicalRender)||!VerifyFile(moduleDirectory/L"clinical-splat-bakes.bin",v2::identity::clinicalBakes))return diagnostic.Return(7,"clinical-file-identity");diagnostic.Step("all-file-identities-passed");
  diagnostic.Step("garment-adapter-start");garment=new v2::MeridianAdapter(moduleDirectory/L"geralt-meridian-binding.bin");diagnostic.Step("garment-renderer-start");GarmentRendererConfigure(moduleDirectory/L"garment.render");
  diagnostic.Step("source-binding-start");binding=new v2::SourceBinding(moduleDirectory/L"geralt-source-binding.bin");diagnostic.Step("coverage-load-start");binding->LoadCoverage(moduleDirectory/L"geralt-meridian-coverage.bin");diagnostic.Step("source-host-start");host=new v2::SourceHost(moduleDirectory/L"canonical_worker.exe");diagnostic.Step("clinical-adapter-start");
  clinical=new v2::ClinicalAdapter();clinicalBody=new v2::ClinicalBody(moduleDirectory/L"geralt-clinical-topology.bin");
  diagnostic.Step("clinical-bakes-settings-start");
  if(!clinical->LoadBakes(moduleDirectory/L"clinical-splat-bakes.bin"))throw std::runtime_error("Canonical splat data is unavailable");
  std::string settingsError;if(!clinical->LoadSettings(moduleDirectory/L"TeachingFluid.ini",settingsError))throw std::runtime_error(settingsError);
  diagnostic.Step("fluid-renderer-start");FluidRendererConfigure(moduleDirectory/L"clinical.render");diagnostic.Step("clinical-audio-start");clinicalAudio.Load(moduleDirectory);diagnostic.Step("clinical-callbacks-start");
  auto& engine=clinical->Runtime().Engine();
  engine.fluid.collisionQuery.callback=[](auto from,auto to,float radius,auto& hit){using R=malemod::clinical::volumeFluid::SweepResult;float best=1.0001f;malemod::clinical::volumeFluid::FluidImpact bodyHit;const bool body=clinicalBody&&clinicalBody->Body().Sweep(from,to,radius,bodyHit,best);malemod::clinical::volumeFluid::FluidImpact worldHit;const auto world=clinicalCollision.Sweep(from,to,radius,worldHit);if(world==R::hit){const auto delta=to-from;const auto d=Dot(delta,delta);const float t=d>1e-12f?Dot(worldHit.p-from,delta)/d:0;if(t<best){hit=worldHit;return R::hit;}}if(body){hit=bodyHit;return R::hit;}return world;};
  clinicalBody->Body().worldProject=[](const auto& receiver,auto candidate,auto& out){auto from=candidate+receiver.n*1.2f,to=candidate-receiver.n*1.2f;return clinicalCollision.Sweep(from,to,.02f,out,true)==malemod::clinical::volumeFluid::SweepResult::hit;};
  engine.deposits.resolve=[](const auto& anchor,auto& point,auto& normal){return clinicalBody&&clinicalBody->Body().Resolve(anchor,point,normal);};
  engine.deposits.project=[](const auto& anchor,auto candidate,auto& out){return clinicalBody&&clinicalBody->Body().Project(anchor,candidate,out);};
  clinical->Runtime().SetAudio([](unsigned phase){clinicalCueMask|=1u<<phase;clinicalCues.push_back({float(phase+1),clinical?clinical->Runtime().Seconds():0,float(++clinicalCueSerial),float(simulationEpoch)});clinicalAudio.Phase(phase);},[]{clinicalAudio.Stop();});
  clinical->Runtime().SetThrob(throbMode);clinical->Runtime().SetIdleChatter(idleChatter);
  diagnostic.Step("initial-source-step-start");auto& p=host->Input();p.epoch=0xffffffffu;p.controls=malemod::controls::CanonicalPacketOrder(controls);p.seconds=1.f/60;host->Step();runtimeFlags=1;diagnostic.Step("initial-source-step-passed");
  if(IsSealedStation())trace=_wfsopen((moduleDirectory/(L"v2-frames-"+std::to_wstring(GetCurrentProcessId())+L".jsonl")).c_str(),L"wb",_SH_DENYNO);
 }catch(const std::exception& e){diagnostic.Step("initialization-exception",8,e.what());delete host;host=nullptr;delete binding;binding=nullptr;delete garment;garment=nullptr;return diagnostic.Return(8,"exception-return");}
 catch(...){diagnostic.Step("initialization-unknown-exception",8);delete host;host=nullptr;delete binding;binding=nullptr;delete garment;garment=nullptr;return diagnostic.Return(8,"unknown-exception-return");}
 auto hookStatus=MH_Initialize();diagnostic.Step("minhook-initialize-status",int(hookStatus));if(hookStatus!=MH_OK)return diagnostic.Return(3,"minhook-initialize-return");
 hookStatus=MH_CreateHook(reinterpret_cast<void*>(engineBase+profile::registerGlobals.rva),RegisterHook,reinterpret_cast<void**>(&originalRegisterGlobals));diagnostic.Step("registration-create-status",int(hookStatus));if(hookStatus!=MH_OK)return diagnostic.Return(4,"registration-create-return");
 hookStatus=MH_EnableHook(reinterpret_cast<void*>(engineBase+profile::registerGlobals.rva));diagnostic.Step("registration-enable-status",int(hookStatus));if(hookStatus!=MH_OK)return diagnostic.Return(5,"registration-enable-return");
 diagnostic.Step("graphics-probe-start");if(!InitializeGraphicsProbe())return diagnostic.Return(6,"graphics-probe-return");
 initialized=true;return diagnostic.Return(0,"initialized");
}
extern "C" __declspec(dllexport) DWORD WINAPI MaleModProbeStatus(void*){using namespace malemod::witcher;return (initialized?4:0)|(registered?1:0)|(registrationFailed?2:0)|(invoked?8:0);}
extern "C" __declspec(dllexport) DWORD WINAPI MaleModGraphicsProbeStatus(void*){return malemod::witcher::GraphicsProbeFlags();}
extern "C" __declspec(dllexport) DWORD WINAPI MaleModRuntimeStatus(void*){return malemod::witcher::runtimeFlags;}
extern "C" __declspec(dllexport) DWORD WINAPI MaleModRuntimeFrameCount(void*){return malemod::witcher::frameCount;}
extern "C" __declspec(dllexport) DWORD WINAPI MaleModSealedSessionStatus(void*){return malemod::witcher::sealedFlags;}
extern "C" __declspec(dllexport) DWORD WINAPI MaleModRenderStatus(void*){return malemod::witcher::FloatDrawFlags();}
extern "C" __declspec(dllexport) DWORD WINAPI MaleModRenderSequence(void*){return malemod::witcher::FloatDrawSequence();}
extern "C" __declspec(dllexport) DWORD WINAPI MaleModShutdownRuntime(void*){using namespace malemod::witcher;OverlayPanel* panel=nullptr;{std::lock_guard<std::mutex> lock(mutex);renderPublication.Clear();DiscardCheckpoints("shutdown");LiveRenderFeed({});GarmentRendererFeed({});FluidRendererFeed({},.01);clinicalAudio.Stop();delete host;host=nullptr;delete binding;binding=nullptr;delete garment;garment=nullptr;delete clinical;clinical=nullptr;delete clinicalBody;clinicalBody=nullptr;panel=overlayPanel;overlayPanel=nullptr;runtimeFlags=0;}delete panel;OverlayInputShutdown();return 0;}
BOOL WINAPI DllMain(HINSTANCE,DWORD,LPVOID){return TRUE;}
