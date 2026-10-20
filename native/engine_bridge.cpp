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
#include <malemod/surface/wire.hpp>
#include "game_profile.hpp"
#include "graphics_probe.hpp"
#include "runtime_profile.hpp"
#include "runtime_host.hpp"
#include "overlay_panel.hpp"
#include "overlay_parent.hpp"
#include "live_renderer.hpp"
#include "float_draw_renderer.hpp"
#include "control_store.hpp"
#include "clinical_service.hpp"
#include "fluid_renderer.hpp"
#include "garment_renderer.hpp"
#include "garment_service.hpp"

// All RVAs and allocation/bytecode layouts in this probe were observed in the
// hash-locked game executable. This is not a REDkit-address compatibility shim.
namespace malemod::witcher {
namespace {
std::uintptr_t engineBase=0;
using NativeCallback=void(*)(void*,void*,void*);
using RegisterGlobals=void(*)();
RegisterGlobals originalRegisterGlobals=nullptr;
std::atomic<bool> initialized{false},registered{false},registrationFailed{false},invoked{false};
std::atomic<unsigned> typedFlags{0};
std::mutex controlsMutex;
malemod::surface::Controls controls;
// REDengine Vector has four binary32 components. It is not Base's Point3.
struct alignas(16) ScriptVector {float x=0,y=0,z=0,w=0;};
static_assert(sizeof(ScriptVector)==16);
std::mutex poseMutex;
unsigned poseSamples=0;
float poseLastTime=0;
FILE* poseLog=nullptr;
void ProbePoseSample(void*,void* frame,void* result);
// Explicit shutdown owns deletion outside loader lock. Process exit reclaims
// these handles; never join workers from a CRT/DllMain teardown callback.
std::mutex runtimeMutex;
RuntimeHost* runtimeHost=nullptr;
OverlayPanel* overlayPanel=nullptr;
RenderContract* renderContract=nullptr;
RenderPoseInput* renderPose=nullptr;
RenderService* renderService=nullptr;
ClinicalService* clinicalService=nullptr;
GarmentService* garmentService=nullptr;
std::filesystem::path garmentPreferencePath;
unsigned renderEpoch=0;
bool overlayRequested=false;
std::atomic<unsigned> runtimeFlags{0};
std::atomic<unsigned> runtimeFrameCount{0};
std::atomic<unsigned> sealedFlags{0};
double verificationCallbackTotal=0,verificationCallbackMaximum=0;
unsigned verificationCallbackCount=0;
struct CallbackTimer {
 std::chrono::steady_clock::time_point begin=std::chrono::steady_clock::now();
 ~CallbackTimer(){if(sealedFlags.load()==3){const double ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-begin).count();verificationCallbackTotal+=ms;verificationCallbackMaximum=(std::max)(verificationCallbackMaximum,ms);++verificationCallbackCount;}}
};
surface::Controls ReadControls(){std::lock_guard<std::mutex> lock(controlsMutex);return controls;}
ControlStore* controlStore=nullptr;
bool IsSealedStation(){
 wchar_t expected[256]{},actual[256]{};DWORD bytes=0;USEROBJECTFLAGS stationFlags{};const auto station=GetProcessWindowStation();
 return GetEnvironmentVariableW(L"MALEMOD_SEALED_SESSION",expected,256)>0&&
  GetUserObjectInformationW(station,UOI_NAME,actual,sizeof(actual),&bytes)&&
  GetUserObjectInformationW(station,UOI_FLAGS,&stationFlags,sizeof(stationFlags),&bytes)&&
  !(stationFlags.dwFlags&WSF_VISIBLE)&&_wcsicmp(actual,L"WinSta0")&&_wcsicmp(actual,expected)==0;
}
bool WriteControl(unsigned index,float value){
 if(index>=18)return false;std::lock_guard<std::mutex> lock(controlsMutex);auto candidate=controls;candidate.values[index]=value;
 try{surface::wire::Validate(candidate);controls=candidate;}catch(const std::invalid_argument&){return false;}
 if(controlStore)try{controlStore->Save(candidate);}catch(const std::exception&){OutputDebugStringW(L"MaleMod: controls applied but preference save failed\n");}
 return true;
}
void CreateOverlayForGame(){
 if(!overlayRequested||overlayPanel)return;
 struct Windows {HWND result=nullptr;unsigned count=0;bool ownedProbeAuthorized=false;} windows;
 windows.ownedProbeAuthorized=IsSealedStation();
 EnumWindows([](HWND window,LPARAM data)->BOOL{auto* list=reinterpret_cast<Windows*>(data);
  if(EligibleOverlayParent(window,list->ownedProbeAuthorized)){list->result=window;++list->count;}return TRUE;
 },reinterpret_cast<LPARAM>(&windows));
 if(windows.count==1)overlayPanel=new OverlayPanel(windows.result,ReadControls,WriteControl,[]{auto p=clinicalService?clinicalService->Projection():surface::Frame::ClinicalProjection{};return std::array<float,3>{clinicalService?float(clinicalService->Mode()):0,p.active?1.f:0.f,garmentService?float(garmentService->Style()):0};},[](unsigned row,float v){if(clinicalService){if(row==18)clinicalService->SetMode(unsigned(v));else if(row==19)clinicalService->Action(v>0);}if(row==20&&garmentService){garmentService->Style(unsigned(v));if(!IsSealedStation())WritePrivateProfileStringW(L"Garment",L"Style",v>0?L"1":L"0",garmentPreferencePath.c_str());}},IsSealedStation());
}

bool VerifyFile(const std::filesystem::path& path,const std::string& expected){
 HANDLE file=CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
 if(file==INVALID_HANDLE_VALUE)return false;
 BCRYPT_ALG_HANDLE algorithm=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;
 bool ok=BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)>=0;
 DWORD size=0,written=0;if(ok)ok=BCryptGetProperty(algorithm,BCRYPT_OBJECT_LENGTH,reinterpret_cast<PUCHAR>(&size),sizeof(size),&written,0)>=0;
 std::vector<UCHAR> object(size),buffer(1024*1024);std::array<UCHAR,32> digest{};
 if(ok)ok=BCryptCreateHash(algorithm,&hash,object.data(),size,nullptr,0,0)>=0;
 while(ok){DWORD count=0;if(!ReadFile(file,buffer.data(),DWORD(buffer.size()),&count,nullptr)){ok=false;break;}if(!count)break;ok=BCryptHashData(hash,buffer.data(),count,0)>=0;}
 if(ok)ok=BCryptFinishHash(hash,digest.data(),DWORD(digest.size()),0)>=0;
 if(hash)BCryptDestroyHash(hash);if(algorithm)BCryptCloseAlgorithmProvider(algorithm,0);CloseHandle(file);
 if(!ok)return false;
 static const char hex[]="0123456789abcdef";std::string actual;
 for(auto x:digest){actual+=hex[x>>4];actual+=hex[x&15];}
 return actual==expected;
}
bool VerifyExecutable(){wchar_t path[32768]{};return GetModuleFileNameW(nullptr,path,32768)&&VerifyFile(path,profile::executableSHA256);}
void InitializeRuntime(){
 wchar_t path[32768]{};HMODULE module=nullptr;
 if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,reinterpret_cast<LPCWSTR>(&InitializeRuntime),&module)||!GetModuleFileNameW(module,path,32768))throw std::runtime_error("Cannot locate runtime module");
 const auto dir=std::filesystem::path(path).parent_path();const auto packet=dir/L"malemod-runtime.profile";
 if(!std::filesystem::exists(packet))return; // Existing observer-only mode.
 if(!IsSealedStation()){
  auto store=std::make_unique<ControlStore>(dir/L"malemod-controls.bin");
  try{auto saved=store->Load();if(saved)controls=*saved;controlStore=store.release();}
  catch(const std::exception&){OutputDebugStringW(L"MaleMod: malformed saved controls preserved; defaults active\n");}
 }
 const auto p=RuntimeProfile::Load(packet,MALEMOD_BASE_COMMIT);
 const auto worker=dir/L"surface_worker.exe",bindings=dir/L"geralt.bindings";
 if(!VerifyFile(worker,p.workerSHA256)||!VerifyFile(bindings,p.bindingsSHA256))throw std::runtime_error("Runtime worker/binding hash differs from profile");
 std::lock_guard<std::mutex> lock(runtimeMutex);
 const bool modularTopology=std::filesystem::exists(dir/L"geralt.modular-dynamic");
 runtimeHost=new RuntimeHost([p,worker,bindings,modularTopology]{return std::make_unique<RuntimeController>(worker.wstring(),bindings,p.revision,p.calibration,p.inverseBind,p.contacts,p.diagnosticSourceContacts,modularTopology);});
 overlayRequested=std::filesystem::exists(dir/L"malemod-overlay.enable");
 if(std::filesystem::exists(dir/L"geralt.render")){
  std::ifstream hashFile(dir/L"geralt.render.sha256");std::string hash;hashFile>>hash;
  if(hash.size()!=64||!VerifyFile(dir/L"geralt.render",hash))throw std::runtime_error("Render contract hash differs");
  renderContract=new RenderContract(dir/L"geralt.render",p.revision,p.bindingsSHA256);
  std::shared_ptr<ModularRenderer> modular;
  if(std::filesystem::exists(dir/L"geralt.modular")||std::filesystem::exists(dir/L"geralt.modular-native")){
   auto verified=[&](const wchar_t* name){auto file=dir/name;std::ifstream h(file.wstring()+L".sha256");std::string value;h>>value;if(value.size()!=64||!VerifyFile(file,value))throw std::runtime_error("Modular artifact hash differs");return value;};
   auto geometryHash=verified(L"geralt.modular");auto nativeHash=verified(L"geralt.modular-native");
   modular=std::make_shared<ModularRenderer>(dir/L"geralt.modular",dir/L"geralt.modular-native",*renderContract,geometryHash,hash);
   if(std::filesystem::exists(dir/L"geralt.modular-transfer")){verified(L"geralt.modular-transfer");modular->EnableTransfer(dir/L"geralt.modular-transfer",geometryHash);}
   if(std::filesystem::exists(dir/L"geralt.modular-dynamic")||std::filesystem::exists(dir/L"geralt.modular-materials")){
    auto dynamicHash=verified(L"geralt.modular-dynamic");verified(L"geralt.modular-materials");
    modular->EnableDynamic(dir/L"geralt.modular-dynamic",dir/L"geralt.modular-materials",geometryHash,dynamicHash,nativeHash);
   }
  }
  renderPose=new RenderPoseInput(*renderContract);renderService=new RenderService(*renderContract,std::move(modular));std::ifstream fluidHashFile(dir/L"clinical.render.sha256");std::string fluidHash;fluidHashFile>>fluidHash;
  if(fluidHash.size()!=64||!VerifyFile(dir/L"clinical.render",fluidHash))throw std::runtime_error("Clinical render hash differs");
  FluidRendererConfigure(dir/L"clinical.render");
  if(!VerifyFile(dir/L"splat_bakes.bin","b41046ee1083da7f0921706022893a7aed78b74a9ff931776f12e746ab405fb5"))throw std::runtime_error("Clinical source bake hash differs");
  clinicalService=new ClinicalService(p.calibration.targetUnitsPerSourceUnit,dir/L"splat_bakes.bin");
  if(std::filesystem::exists(dir/L"garment.bindings")){
   auto verified=[&](const wchar_t* name){auto file=dir/name;std::ifstream h(file.wstring()+L".sha256");std::string hash;h>>hash;if(hash.size()!=64||!VerifyFile(file,hash))throw std::runtime_error("Garment artifact hash differs");};
   verified(L"garment.bindings");verified(L"garment.render");verified(L"garment.reactions");
   GarmentRendererConfigure(dir/L"garment.render");garmentService=new GarmentService(*renderContract,GarmentBindings(dir/L"garment.bindings",p.revision,hash),p.contacts,IsSealedStation()?dir/(L"garment-failure-"+std::to_wstring(GetCurrentProcessId())):std::filesystem::path{});
   garmentPreferencePath=dir/L"malemod-preferences.ini";
   if(!IsSealedStation())garmentService->Style(GetPrivateProfileIntW(L"Garment",L"Style",0,garmentPreferencePath.c_str()));
  }
 }
 runtimeFlags.store(1u|(p.diagnosticSourceContacts?64u:0u));
}
template<class T>T Function(const profile::Function& f){return reinterpret_cast<T>(engineBase+f.rva);}
bool CheckPrefixes(){
 auto* dos=reinterpret_cast<const IMAGE_DOS_HEADER*>(engineBase);
 if(dos->e_magic!=IMAGE_DOS_SIGNATURE)return false;
 auto* pe=reinterpret_cast<const IMAGE_NT_HEADERS64*>(engineBase+dos->e_lfanew);
 if(pe->Signature!=IMAGE_NT_SIGNATURE||pe->OptionalHeader.SizeOfImage!=profile::imageSize)return false;
 for(const auto* f:{&profile::registerGlobals,&profile::allocate,&profile::namePool,&profile::internName,&profile::constructFunction,&profile::rtti,&profile::registerFunction})
  if(std::memcmp(reinterpret_cast<const void*>(engineBase+f->rva),f->prefix.data(),f->prefix.size()))return false;
 return true;
}
void FinishParameters(void* frame){
 // Native zero-argument wrappers advance past the EndParam opcode as well.
 auto& code=*reinterpret_cast<unsigned char**>(static_cast<unsigned char*>(frame)+0x30);++code;
}
template<class T> void Parameter(void* frame,T& value){
 auto& code=*reinterpret_cast<unsigned char**>(static_cast<unsigned char*>(frame)+0x30);
 const auto opcode=*code++;
 auto* table=reinterpret_cast<NativeCallback*>(engineBase+profile::opcodeTableRVA);
 if(table[opcode])table[opcode](*static_cast<void**>(frame),frame,&value);
}
void RuntimeFrame(void*,void* frame,void* result){
 CallbackTimer timer;
 runtimeFrameCount.fetch_add(1);
 invoked.store(true,std::memory_order_release);
 std::int32_t epoch=0;float seconds=0;bool paused=false;std::array<ScriptVector,8> v{};
 Parameter(frame,epoch);Parameter(frame,seconds);Parameter(frame,paused);for(auto& p:v)Parameter(frame,p);FinishParameters(frame);
 HostTick status=HostTick::Dormant;
 try{
 std::unique_lock<std::mutex> lock(runtimeMutex,std::try_to_lock);
 if(!lock.owns_lock())status=HostTick::Busy;
 else if(runtimeHost&&epoch>=0){
  CreateOverlayForGame();
  if(renderEpoch!=unsigned(epoch)){LiveRenderFeed({});renderEpoch=unsigned(epoch);}
  runtimeFlags.fetch_or(2);PoseSample sample;sample.seconds=seconds;sample.pelvisActorLocal[15]=1;
  for(unsigned column=0;column<4;column++){const std::array<float,3> xyz={v[column].x,v[column].y,v[column].z};for(unsigned r=0;r<3;r++)sample.pelvisActorLocal[r*4+column]=xyz[r];}
  for(unsigned i=0;i<4;i++)sample.thighsActorLocal[i]={v[i+4].x,v[i+4].y,v[i+4].z};
  const auto snapshot=ReadControls();
  if(overlayPanel&&overlayPanel->ConsumeFocusLoss()&&epoch>0){std::uint64_t pauseSequence=0;runtimeHost->Tick(std::uint32_t(epoch),sample,true,snapshot,pauseSequence);}
  std::uint64_t sequence=0;status=runtimeHost->Tick(std::uint32_t(epoch),sample,paused,snapshot,sequence,clinicalService?clinicalService->Projection():surface::Frame::ClinicalProjection{},garmentService?garmentService->Support(unsigned(epoch)):surface::Frame::GarmentSupport{});
  if(status==HostTick::Paused)runtimeFlags.fetch_or(8);
  if(status==HostTick::Busy||status==HostTick::Full)runtimeFlags.fetch_or(16);
  if(status==HostTick::Invalid||status==HostTick::Failed)runtimeFlags.fetch_or(32);
  const auto currentRenderPose=renderPose?(paused?renderPose->LastComplete(unsigned(epoch)):renderPose->Complete(unsigned(epoch),seconds)):std::optional<RenderPose>{};
  std::shared_ptr<const RenderDelivery> currentRenderDelivery;
  auto source=runtimeHost->Poll(std::uint32_t(epoch));
  if(source){runtimeFlags.fetch_or(4);if(renderService&&renderPose){if(currentRenderPose){runtimeFlags.fetch_or(128);renderService->Submit(source,*currentRenderPose,paused);}auto output=renderService->Latest();if(output&&output->epoch==unsigned(epoch)){
 currentRenderDelivery=output;LiveRenderFeed(output);
}if(!renderService->Error().empty()){
 runtimeFlags.fetch_or(256);static bool recorded=false;if(!recorded){recorded=true;wchar_t path[32768]{};HMODULE module=nullptr;
 if(GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,reinterpret_cast<LPCWSTR>(&RuntimeFrame),&module)&&GetModuleFileNameW(module,path,32768)){
  auto* tail=wcsrchr(path,L'\\');if(tail){swprintf_s(tail+1,32768-std::size_t(tail+1-path),L"render-error-%lu.txt",GetCurrentProcessId());auto* file=_wfsopen(path,L"wb",_SH_DENYNO);if(file){std::fprintf(file,"%s\n",renderService->Error().c_str());std::fclose(file);}}
 }
 }
}}}
  if(garmentService){if(currentRenderPose)garmentService->Submit(currentRenderDelivery,*currentRenderPose,paused);auto garment=garmentService->Latest();GarmentRendererFeed(garment);if(!garmentService->Error().empty()||(garment&&garment->output.style!=garments::Style::Naked&&(!garment->output.contactBudgetSatisfied||!garment->output.physics.materialBudgetSatisfied)))runtimeFlags.fetch_or(1024);}
  if(clinicalService){clinicalService->Submit(unsigned(epoch),seconds,paused,currentRenderDelivery);FluidRendererFeed(clinicalService->Latest(),clinicalService->Scale());if(!clinicalService->Error().empty())runtimeFlags.fetch_or(512);}
  if(!epoch){LiveRenderFeed({});if(renderPose)renderPose->Reset();}
  // Script ticks publish inputs independently of render-thread recording.
  // graphics_probe freezes body/effect output at the actual DXGI Present
  // boundary so depth and colour passes cannot select different poses.
 }
 }catch(const std::exception&){
  // Allocation, window creation and publication failures cannot unwind through
  // REDengine's native VM callback. Report the fault to the script instead.
  status=HostTick::Failed;runtimeFlags.fetch_or(32);
  OutputDebugStringW(L"MaleMod: native frame integration failed; input stopped\n");
 }
 if(result)*static_cast<std::int32_t*>(result)=static_cast<std::int32_t>(status);
}
void BonePose(void*,void* frame,void*){
 std::int32_t epoch=0,bone=-2;float seconds=0;std::array<ScriptVector,4> vectors{};
 Parameter(frame,epoch);Parameter(frame,bone);Parameter(frame,seconds);for(auto& v:vectors)Parameter(frame,v);FinishParameters(frame);
 PoseMatrix pose{};pose[15]=1;for(unsigned column=0;column<4;column++){const auto& v=vectors[column];pose[column]=v.x;pose[4+column]=v.y;pose[8+column]=v.z;}
 std::unique_lock<std::mutex> lock(runtimeMutex,std::try_to_lock);if(lock.owns_lock()&&renderPose&&epoch>0)renderPose->Add(unsigned(epoch),bone,seconds,pose);
}
void SurfaceActive(void*,void* frame,void* result){std::int32_t epoch=0;Parameter(frame,epoch);FinishParameters(frame);if(result)*static_cast<bool*>(result)=epoch>0&&!(runtimeFlags.load()&256)&&FloatDrawActive(unsigned(epoch));}
void FullMode(void*,void* frame,void* result){FinishParameters(frame);if(result)*static_cast<bool*>(result)=runtimeHost&&renderService&&renderContract;}
void OverlayOpen(void*,void* frame,void* result){bool open=false;{std::lock_guard<std::mutex> lock(runtimeMutex);open=overlayPanel&&overlayPanel->Open();}FinishParameters(frame);if(result)*static_cast<bool*>(result)=open;}
void ProbePoseSample(void*,void* frame,void* result){
 float seconds=0;bool paused=false;std::array<ScriptVector,8> vectors{};
 Parameter(frame,seconds);Parameter(frame,paused);
 for(auto& value:vectors)Parameter(frame,value);FinishParameters(frame);
 bool keepSampling=true;
 std::lock_guard<std::mutex> lock(poseMutex);
 if(poseSamples>=240)keepSampling=false;
 else if(!paused&&std::isfinite(seconds)){
  bool finite=true;
  for(const auto& v:vectors)for(float x:{v.x,v.y,v.z,v.w})if(!std::isfinite(x))finite=false;
  // Reject zero/degenerate bases during player/rig initialization. This is
  // observation only: no inferred bind transform, contacts or motion force.
  for(unsigned i=0;i<3;i++){const auto& v=vectors[i];const auto length=v.x*v.x+v.y*v.y+v.z*v.z;if(length<.25f||length>4.f)finite=false;}
  if(finite&&(poseSamples==0||seconds-poseLastTime>=.008f)){
   if(!poseLog){wchar_t path[32768]{};HMODULE module=nullptr;
    if(GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,reinterpret_cast<LPCWSTR>(&ProbePoseSample),&module)&&GetModuleFileNameW(module,path,32768)){
     auto* last=wcsrchr(path,L'\\');if(last){swprintf_s(last+1,32768-std::size_t(last+1-path),L"pose-probe-%lu.jsonl",GetCurrentProcessId());poseLog=_wfsopen(path,L"wb",_SH_DENYNO);}
    }
   }
   if(poseLog){std::fprintf(poseLog,"{\"sample\":%u,\"seconds\":%.9g,\"paused\":false,\"actorLocal\":[",poseSamples,seconds);
    for(unsigned i=0;i<vectors.size();i++){const auto& v=vectors[i];if(i)std::fputc(',',poseLog);std::fprintf(poseLog,"[%.9g,%.9g,%.9g,%.9g]",v.x,v.y,v.z,v.w);}
    std::fprintf(poseLog,"]}\n");std::fflush(poseLog);
   }
   ++poseSamples;poseLastTime=seconds;typedFlags.fetch_or(128);
  }
 }
 if(result)*static_cast<bool*>(result)=keepSampling;
}
void SetControl(void*,void* frame,void* result){
 std::int32_t index=-1;float value=0;
 Parameter(frame,index);Parameter(frame,value);FinishParameters(frame);
 const bool accepted=index>=0&&WriteControl(unsigned(index),value);
 if(result)*static_cast<bool*>(result)=accepted;
}
void GetControl(void*,void* frame,void* result){
 std::int32_t index=-1;Parameter(frame,index);FinishParameters(frame);
 float value=-1;
 if(index>=0&&index<18){std::lock_guard<std::mutex> lock(controlsMutex);value=controls.values[std::size_t(index)];}
 if(result)*static_cast<float*>(result)=value;
}
void TypedProbe(void*,void* frame,void* result){
 std::int32_t index=0;float scale=0;ScriptVector point;
 Parameter(frame,index);Parameter(frame,scale);Parameter(frame,point);FinishParameters(frame);
 const bool valid=index==-73&&scale==1.25f&&point.x==1.5f&&point.y==-2.25f&&point.z==3.75f&&point.w==0.5f;
 typedFlags.fetch_or(valid?16u:32u);
 const ScriptVector output{point.x*scale+float(index),point.y*scale,point.z*scale,point.w*scale};
 if(result)*static_cast<ScriptVector*>(result)=output;
}
void TypedProbeResult(void*,void* frame,void*){
 bool success=false;Parameter(frame,success);FinishParameters(frame);
 typedFlags.fetch_or(success?64u:32u);
}
void Ready(void*,void* frame,void* result){
 invoked.store(true,std::memory_order_release);
 if(result)*static_cast<bool*>(result)=registered.load(std::memory_order_acquire)&&!registrationFailed.load();
 FinishParameters(frame);
}
void SealedSession(void*,void* frame,void* result){
 const bool isolated=IsSealedStation();
 sealedFlags.store(isolated?3u:1u);
 FinishParameters(frame);if(result)*static_cast<bool*>(result)=isolated;
}
void TestCheckpoint(void*,void* frame,void* result){
 std::int32_t stage=-1;Parameter(frame,stage);FinishParameters(frame);bool success=false;
 // Authored game verification is enabled only inside the verified invisible
 // station. Ordinary gameplay cannot run this driver or create test captures.
 if(sealedFlags.load()==3&&stage>=0){
  const auto output=FloatDrawCompleted();const auto current=ReadControls();
  if(output&&output->controls.values==current.values&&FloatDrawActive(output->epoch)&&FloatDrawSequence()>=output->sequence){
   static FILE* log=nullptr;static int last=-1;
   if(!log){wchar_t path[32768]{};HMODULE module=nullptr;
    if(GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,reinterpret_cast<LPCWSTR>(&TestCheckpoint),&module)&&GetModuleFileNameW(module,path,32768)){
     auto* tail=wcsrchr(path,L'\\');if(tail){swprintf_s(tail+1,32768-std::size_t(tail+1-path),L"verification-%lu.jsonl",GetCurrentProcessId());log=_wfsopen(path,L"wb",_SH_DENYNO);}
    }
   }
   if(log&&last!=stage){
    std::array<double,3> low{1e9,1e9,1e9},high{-1e9,-1e9,-1e9};
    std::uint64_t hash=14695981039346656037ull;const auto* data=reinterpret_cast<const unsigned char*>(output->floatVertices.data());
    for(std::size_t i=0;i<output->floatVertices.size()*28;i++){hash^=data[i];hash*=1099511628211ull;}
    for(const auto& v:*output->vertices)for(unsigned a=0;a<3;a++){low[a]=(std::min)(low[a],double(v.position[a]));high[a]=(std::max)(high[a],double(v.position[a]));}
    std::fprintf(log,"{\"stage\":%d,\"epoch\":%u,\"sequence\":%llu,\"completedSequence\":%u,\"renderFlags\":%u,\"runtimeFlags\":%u,\"sourceMs\":%.9g,\"targetMs\":%.9g,\"prepareMs\":%.9g,\"vertices\":%zu,\"uploadFNV64\":\"%016llx\",\"attachmentCorrective\":[%.9g,%.9g],\"angleGain\":[%.9g,%.9g],\"controls\":[",stage,output->epoch,static_cast<unsigned long long>(output->sequence),FloatDrawSequence(),FloatDrawFlags(),runtimeFlags.load(),output->sourceMilliseconds,output->targetMilliseconds,output->preparationMilliseconds,output->floatVertices.size(),static_cast<unsigned long long>(hash),output->correctiveWeights[0],output->correctiveWeights[1],output->angleGains[0],output->angleGains[1]);
    // The angle cap is evidence, not a silent stationary-mesh fallback.

    for(unsigned i=0;i<18;i++)std::fprintf(log,"%s%.9g",i?",":"",current.values[i]);
    std::fprintf(log,"]");
    if(output->modular){
     std::size_t count=0;std::uint64_t modularHash=14695981039346656037ull;
     for(const auto& part:output->modular->parts){count+=part.vertices.size();const auto* p=reinterpret_cast<const unsigned char*>(part.vertices.data());for(std::size_t i=0;i<part.vertices.size()*sizeof(ModularVertex);i++){modularHash^=p[i];modularHash*=1099511628211ull;}}
     std::fprintf(log,",\"modular\":true,\"modularVertices\":%zu,\"modularMs\":%.9g,\"modularCompletedLODMask\":%u,\"modularUploadFNV64\":\"%016llx\"",count,output->modular->milliseconds,ModularDrawCompletedLODMask(),static_cast<unsigned long long>(modularHash));
     std::fprintf(log,",\"wallMilliseconds\":%llu,\"modularRebuilt\":%s,\"modularStrain\":[%.9g,%.9g,%.9g]",static_cast<unsigned long long>(GetTickCount64()),output->modular->rebuilt?"true":"false",output->modular->materialScale[0],output->modular->materialScale[1],output->modular->materialScale[2]);
     if(stage>=500&&stage<1000){
      wchar_t path[32768]{};HMODULE owner=nullptr;
      if(GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,reinterpret_cast<LPCWSTR>(&TestCheckpoint),&owner)&&GetModuleFileNameW(owner,path,32768)){
       auto file=std::filesystem::path(path).parent_path()/(L"modular-frame-"+std::to_wstring(GetCurrentProcessId())+L"-"+std::to_wstring(stage)+L".bin");std::ofstream captured(file,std::ios::binary);
       auto bytes=[&](const void* p,std::size_t n){captured.write(static_cast<const char*>(p),n);};bytes("MMMCAP01",8);bytes(&output->epoch,4);bytes(&output->sequence,8);bytes(output->pose.actorWorld.data(),128);
       unsigned paletteCount=unsigned(output->pose.skinDeltas.size());bytes(&paletteCount,4);bytes(output->pose.skinDeltas.data(),paletteCount*128);
       for(const auto& part:output->modular->parts){unsigned counts[4]{part.resource,part.lod,unsigned(part.vertices.size()),unsigned(part.indices->size())};bytes(counts,16);bytes(part.vertices.data(),part.vertices.size()*sizeof(ModularVertex));bytes(part.indices->data(),part.indices->size()*4);}
      }
     }
    }
    std::fprintf(log,",\"bounds\":[[%.9g,%.9g,%.9g],[%.9g,%.9g,%.9g]],\"actorOrigin\":[%.9g,%.9g,%.9g],\"poseSeconds\":%.9g,\"lightingMs\":%.9g,\"workerMs\":[%.9g,%.9g,%.9g],\"geometryMs\":[",low[0],low[1],low[2],high[0],high[1],high[2],output->pose.actorWorld[3],output->pose.actorWorld[7],output->pose.actorWorld[11],output->poseSeconds,output->lightingMilliseconds,output->workerMilliseconds[0],output->workerMilliseconds[1],output->workerMilliseconds[2]);
    for(unsigned i=0;i<16;i++)std::fprintf(log,"%s%.9g",i?",":"",output->geometryMilliseconds[i]);
    auto clinical=clinicalService?clinicalService->Latest():nullptr;auto collision=clinicalService?clinicalService->collisions.Counts():std::array<unsigned,3>{};
    std::fprintf(log,"],\"clinicalMode\":%u,\"clinicalActive\":%s,\"clinicalTime\":%.9g,\"emittedVolume\":%.9g,\"liquidIndices\":%zu,\"depositIndices\":%zu,\"clinicalMs\":%.9g,\"clinicalCueMask\":%u,\"fluidRenderFlags\":%u,\"fluidPublications\":%u,\"pendingQueries\":%u,\"sceneQueries\":%u,\"sceneHits\":%u,",clinicalService?clinicalService->Mode():0,clinical&&clinical->active?"true":"false",clinical?clinical->time:0,clinical?clinical->emittedVolume:0,clinical?clinical->mesh.indices.size():0,clinical?clinical->deposits.indices.size():0,clinical?clinical->milliseconds:0,clinical?clinical->cueMask:0,FluidDrawFlags(),FluidDrawPublications(),collision[0],collision[1],collision[2]);
    auto garment=garmentService?garmentService->Latest():nullptr;
    std::fprintf(log,"\"garmentContactBudgetSatisfied\":%s,\"garmentProjectedContacts\":%u,\"garmentCoverageMargin\":%.9g,\"garmentSupportEnabled\":%s,\"garmentServiceError\":%s,",garment&&garment->output.contactBudgetSatisfied?"true":"false",garment?garment->output.projectedContacts:0,garment?garment->output.coverageMargin:0,garment&&garment->support.enabled?"true":"false",garmentService&&!garmentService->Error().empty()?"true":"false");
    const auto cloth=garment?garment->output.physics:garments::ClothTelemetry{};
    const auto band=garment?garment->output.band:garments::BandTelemetry{};
    const auto layout=garment?garment->output.layout:garments::MaterialLayout{};
    const auto reaction=garment?garment->output.reaction:garments::ReactionTelemetry{};
    std::fprintf(log,"\"garmentReactionMode\":%s,\"clothReactionContacts\":%u,\"clothReactionRecords\":%u,\"clothReactionSeconds\":%.9g,\"clothMass\":%.9g,",garment&&garment->support.enabled&&garment->support.contactReaction?"true":"false",reaction.contacts,reaction.records,reaction.activeSeconds,reaction.clothMass);
    std::fprintf(log,"\"garmentMaterialOpacity\":[");for(unsigned i=0;i<4;i++)std::fprintf(log,"%s%.9g",i?",":"",garment?garment->output.materials[i].opacity:0);std::fprintf(log,"],");
    const std::array<const char*,8> reactionNames{"clothContactImpulse","anatomyContactImpulse","clothContactMoment","anatomyContactMoment","clothParticleContactImpulse","clothParticleContactMoment","clothPrescribedSupportImpulse","clothPrescribedSupportMoment"};
    const std::array<garments::Point,8> reactionVectors{reaction.clothImpulse,reaction.anatomyImpulse,reaction.clothMoment,reaction.anatomyMoment,reaction.particleImpulse,reaction.particleMoment,reaction.supportImpulse,reaction.supportMoment};
    for(unsigned i=0;i<reactionNames.size();i++)std::fprintf(log,"\"%s\":[%.9g,%.9g,%.9g],",reactionNames[i],reactionVectors[i][0],reactionVectors[i][1],reactionVectors[i][2]);
    std::fprintf(log,"\"garmentLayoutRevision\":%u,\"pouchUpperArcRadians\":%.9g,\"pouchSheetRows\":%u,\"pouchSheetColumns\":%u,\"pouchTopSeamVertices\":%zu,\"pouchBottomSeamVertices\":[%zu,%zu],",layout.revision,layout.upperArcRadians,layout.sheet.rows,layout.sheet.columns,layout.topSeam.size(),layout.bottomSeams[0].size(),layout.bottomSeams[1].size());
    std::fprintf(log,"\"pouchSideHemSections\":[%u,%u],\"pouchSideBoundaryVertices\":[%zu,%zu],",layout.sideHems[0].sections,layout.sideHems[1].sections,layout.sideBoundary[0].size(),layout.sideBoundary[1].size());
    std::fprintf(log,"\"bandTopAttachments\":%u,\"bandBottomAttachments\":%u,\"bandTopCircumference\":%.9g,\"bandBottomCircumference\":%.9g,\"bandPreferredClearance\":%.9g,\"bandMinimumInnerClearance\":%.9g,\"bandMaximumInnerClearance\":%.9g,",band.topAttachments,band.bottomAttachments,band.topCircumference,band.bottomCircumference,band.preferredClearance,band.minimumInnerClearance,band.maximumInnerClearance);
    std::fprintf(log,"\"clothActive\":%s,\"clothStateReady\":%s,\"clothMaterialBudgetSatisfied\":%s,\"clothResetCount\":%u,\"clothNodes\":%u,\"clothConstraints\":%u,\"clothSubsteps\":%u,\"clothAdvancedSeconds\":%.9g,\"clothAccumulatedSeconds\":%.9g,\"clothStretchRatio\":%.9g,\"clothBendError\":%.9g,\"clothSeamGap\":%.9g,\"clothDisplacement\":%.9g,\"clothRmsSpeed\":%.9g,\"clothMaxSpeed\":%.9g,\"clothSolverMs\":%.9g,",cloth.active?"true":"false",cloth.stateReady?"true":"false",cloth.materialBudgetSatisfied?"true":"false",cloth.resetCount,cloth.nodes,cloth.constraints,cloth.substeps,cloth.advancedSeconds,cloth.accumulatedSeconds,cloth.maxStretchRatio,cloth.maxBendError,cloth.maxSeamGap,cloth.maxDisplacement,cloth.rmsSpeed,cloth.maxSpeed,cloth.solverMilliseconds);
#ifdef MALEMOD_ATTACHMENT_CORRECTIVE
    if(output->correctiveSource){
     const auto& physics=*output->correctiveSource;const auto& source=physics.surface->frame.source;
     const auto a=source.lobeCenters[0],b=source.lobeCenters[1],tip=source.shaftGuide[11];
     std::fprintf(log,"\"anatomySimulationSeconds\":%.12g,\"anatomyPitchForce\":%.9g,\"anatomyYawForce\":%.9g,\"anatomyLobeCenters\":[[%.9g,%.9g,%.9g],[%.9g,%.9g,%.9g]],\"anatomyTip\":[%.9g,%.9g,%.9g],",physics.simulationSeconds,physics.surface->input.frame.pitchForce,physics.surface->input.frame.yawForce,a.x,a.y,a.z,b.x,b.y,b.z,tip.x,tip.y,tip.z);
    }
#endif
    std::fprintf(log,"\"garmentPresentationMs\":%.9g,\"garmentPoseSeconds\":%.9g,",garment?garment->presentationMilliseconds:0,garment?garment->poseSeconds:0);
    std::fprintf(log,"\"clothFineStretchRatio\":%.9g,\"clothWorstFineA\":%u,\"clothWorstFineB\":%u,",cloth.maxRenderStretchRatio,cloth.worstRenderA,cloth.worstRenderB);
    std::fprintf(log,"\"depositedVolume\":[%.9g,%.9g],\"depositedImpacts\":[%u,%u],\"finalPumpDepositedVolume\":%.9g,\"finalPumpDepositedImpacts\":%u,\"garmentStyle\":%u,\"garmentVertices\":%zu,\"garmentTriangles\":%zu,\"garmentMs\":%.9g,\"garmentFlags\":%u,\"garmentPublications\":%u,\"callbackCount\":",clinical?clinical->depositedVolume[0]:0,clinical?clinical->depositedVolume[1]:0,clinical?clinical->depositedImpacts[0]:0,clinical?clinical->depositedImpacts[1]:0,clinical?clinical->finalPumpDepositedVolume:0,clinical?clinical->finalPumpDepositedImpacts:0,garmentService?garmentService->Style():0,garment?garment->output.mesh.vertices.size():0,garment?garment->output.mesh.triangles.size():0,garment?garment->milliseconds:0,GarmentDrawFlags(),GarmentDrawPublications());
    std::fprintf(log,"%u,\"callbackMeanMs\":%.9g,\"callbackMaxMs\":%.9g,\"bodyResourceMask\":%u,\"displayPublications\":%u,\"presentationPhase\":%.9g,\"presentationIntervalMs\":%.9g}\n",verificationCallbackCount,verificationCallbackCount?verificationCallbackTotal/verificationCallbackCount:0,verificationCallbackMaximum,FloatDrawResourceMask(),FloatDrawPublicationCount(),output->presentationPhase,output->presentationIntervalMilliseconds);
    verificationCallbackCount=0;verificationCallbackTotal=verificationCallbackMaximum=0;
    std::fflush(log);last=stage;
    if(garment&&(stage==96||stage==97||stage==101||stage==105||stage==106)){
     wchar_t capture[32768]{};HMODULE owner=nullptr;
     if(GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,reinterpret_cast<LPCWSTR>(&TestCheckpoint),&owner)&&GetModuleFileNameW(owner,capture,32768)){
      auto* tail=wcsrchr(capture,L'\\');if(tail){swprintf_s(tail+1,32768-std::size_t(tail+1-capture),L"garment-frame-%lu-%d.obj",GetCurrentProcessId(),stage);FILE* file=nullptr;
       if(!_wfopen_s(&file,capture,L"wb")){
        const auto& mesh=garment->output.mesh;std::fprintf(file,"# epoch %u serial %llu pose %.9g\n",garment->epoch,static_cast<unsigned long long>(garment->serial),garment->poseSeconds);
        for(const auto& v:mesh.vertices)std::fprintf(file,"v %.12g %.12g %.12g\n",v.position[0]-output->pose.actorWorld[3],v.position[1]-output->pose.actorWorld[7],v.position[2]-output->pose.actorWorld[11]);
        for(const auto& v:mesh.vertices)std::fprintf(file,"vn %.12g %.12g %.12g\n",v.normal[0],v.normal[1],v.normal[2]);
        for(const auto& v:mesh.vertices)std::fprintf(file,"vt %.12g %.12g\n",v.uv[0],v.uv[1]);
        for(unsigned material=0;material<4;material++){std::fprintf(file,"usemtl garment%u\n",material);for(const auto& t:mesh.triangles)if(unsigned(t.material)==material){const auto a=t.vertices[0]+1,b=t.vertices[1]+1,c=t.vertices[2]+1;std::fprintf(file,"f %u/%u/%u %u/%u/%u %u/%u/%u\n",a,a,a,b,b,b,c,c,c);}}
        std::fclose(file);
       }
      }
     }
    }
    if(stage==75||stage==82||stage==83||(output->modular&&stage>=600&&stage<696&&(stage-600)%3==0)){
#ifdef MALEMOD_ATTACHMENT_CORRECTIVE
     if(output->correctiveSource){
      auto snapshot=output->correctiveSource;
      wchar_t modulePath[32768]{};HMODULE owner=nullptr;
      if(GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,reinterpret_cast<LPCWSTR>(&TestCheckpoint),&owner)&&GetModuleFileNameW(owner,modulePath,32768)){
       auto folder=std::filesystem::path(modulePath).parent_path();
       const auto prefix="attachment-frame-"+std::to_string(GetCurrentProcessId())+"-"+std::to_string(stage);
       auto bytes=surface::wire::Encode(snapshot->surface->frame.source);
       std::ofstream sourceFile(folder/(prefix+"-source.bin"),std::ios::binary);sourceFile.write(reinterpret_cast<const char*>(bytes.data()),bytes.size());
       if(snapshot->surface->frame.modularShape){auto shape=surface::wire::Encode(*snapshot->surface->frame.modularShape);std::ofstream file(folder/(prefix+"-shape.bin"),std::ios::binary);file.write(reinterpret_cast<const char*>(shape.data()),shape.size());}
       for(unsigned lod=0;lod<2;lod++){
        const auto& points=snapshot->surface->frame.targetPositions[lod];
        std::ofstream targetFile(folder/(prefix+"-lod"+std::to_string(lod)+".bin"),std::ios::binary);targetFile.write(reinterpret_cast<const char*>(points.data()),points.size()*sizeof(points[0]));
       }
      }
     }
#endif
     wchar_t capture[32768]{};HMODULE owner=nullptr;
     if(GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,reinterpret_cast<LPCWSTR>(&TestCheckpoint),&owner)&&GetModuleFileNameW(owner,capture,32768)){
      auto* tail=wcsrchr(capture,L'\\');if(tail){swprintf_s(tail+1,32768-std::size_t(tail+1-capture),L"body-frame-%lu-%d.bin",GetCurrentProcessId(),stage);FILE* file=nullptr;
       if(!_wfopen_s(&file,capture,L"wb")){std::fwrite(output->floatVertices.data(),28,output->floatVertices.size(),file);std::fclose(file);}
      }
     }
    }
   }
   success=log!=nullptr;
  }
 }
 if(result)*static_cast<bool*>(result)=success;
}
void GarmentControl(void*,void* frame,void*){std::int32_t style=0;Parameter(frame,style);FinishParameters(frame);if(garmentService&&style>=0&&style<2)garmentService->Style(unsigned(style));}
void GarmentState(void*,void* frame,void* result){FinishParameters(frame);ScriptVector v{};if(garmentService){auto d=garmentService->Latest();v={float(garmentService->Style()),d?float(d->output.mesh.triangles.size()):0,float(GarmentDrawFlags()),float(GarmentDrawPublications())};}if(result)std::memcpy(result,&v,sizeof(v));}
void GarmentCarrier(void*,void* frame,void*){ScriptVector origin{};bool valid=false;Parameter(frame,origin);Parameter(frame,valid);FinishParameters(frame);GarmentRendererOrigin({origin.x,origin.y,origin.z},valid&&std::isfinite(origin.x)&&std::isfinite(origin.y)&&std::isfinite(origin.z));}
void ClinicalControl(void*,void* frame,void*){std::int32_t row=0;float value=0;Parameter(frame,row);Parameter(frame,value);FinishParameters(frame);if(clinicalService&&std::isfinite(value)){if(row==0&&value>=0&&value<=3)clinicalService->SetMode(unsigned(value));if(row==1)clinicalService->Action(value>0);}}
void ClinicalQuery(void*,void* frame,void* result){std::int32_t which=0;Parameter(frame,which);FinishParameters(frame);ScriptVector v{};if(clinicalService){static thread_local ClinicalCollision::Query query;if(which==0){query=clinicalService->collisions.Next();v={float(query.from.x*clinicalService->Scale()),float(query.from.y*clinicalService->Scale()),float(query.from.z*clinicalService->Scale()),float(query.token)};}else if(which==2){v.w=float(query.token);}else if(which==1){v={float(query.to.x*clinicalService->Scale()),float(query.to.y*clinicalService->Scale()),float(query.to.z*clinicalService->Scale()),float(query.radius*clinicalService->Scale())};}}
 if(result)std::memcpy(result,&v,sizeof(v));}
void ClinicalHit(void*,void* frame,void*){std::int32_t token=0;bool hit=false;ScriptVector p{},n{};Parameter(frame,token);Parameter(frame,hit);Parameter(frame,p);Parameter(frame,n);FinishParameters(frame);if(clinicalService&&token>0&&std::isfinite(p.x)&&std::isfinite(p.y)&&std::isfinite(p.z)&&std::isfinite(n.x)&&std::isfinite(n.y)&&std::isfinite(n.z)){auto scale=clinicalService->Scale();clinicalService->collisions.Result(unsigned(token),hit,{float(p.x/scale),float(p.y/scale),float(p.z/scale)},{n.x,n.y,n.z});}}
void ClinicalCarrier(void*,void* frame,void*){ScriptVector origin{};bool valid=false;Parameter(frame,origin);Parameter(frame,valid);FinishParameters(frame);FluidRendererOrigin({origin.x,origin.y,origin.z},valid&&std::isfinite(origin.x)&&std::isfinite(origin.y)&&std::isfinite(origin.z));}
void ClinicalState(void*,void* frame,void* result){FinishParameters(frame);ScriptVector v{};if(clinicalService){auto p=clinicalService->Projection();auto out=clinicalService->Latest();v={float(clinicalService->Mode()),p.active?1.f:0.f,float(p.time),out?float(out->mesh.indices.size()+out->deposits.indices.size()):0.f};}if(result)std::memcpy(result,&v,sizeof(v));}
void ClinicalDeposits(void*,void* frame,void* result){FinishParameters(frame);ScriptVector v{};if(clinicalService){auto out=clinicalService->Latest();if(out)v={float(out->depositedVolume[0]),float(out->depositedVolume[1]),float(out->finalPumpDepositedVolume),float(out->finalPumpDepositedImpacts)};}if(result)std::memcpy(result,&v,sizeof(v));}
void ClinicalCue(void*,void* frame,void* result){FinishParameters(frame);ScriptVector v{};if(clinicalService){if(auto cue=clinicalService->PollCue())v={float(cue->phase+1),float(cue->seconds),float(cue->sequence),float(cue->epoch)};}if(result)std::memcpy(result,&v,sizeof(v));}
bool RegistryContains(void* registry,std::uint32_t nameID,void* function){
 // Actual RegisterGlobalFunction disassembly: bucket capacity/count at 40/44,
 // table at 60, nodes {name, function, hash, next} at 0/8/10/18.
 auto* bytes=static_cast<unsigned char*>(registry);
 const auto capacity=*reinterpret_cast<const std::uint32_t*>(bytes+0x40);
 const auto count=*reinterpret_cast<const std::uint32_t*>(bytes+0x44);
 if(!capacity||capacity>1000000||count>1000000)return false;
 auto** buckets=*reinterpret_cast<unsigned char***>(bytes+0x60);
 if(!buckets)return false;
 auto* node=buckets[nameID%capacity];
 for(std::uint32_t i=0;node&&i<=count;i++,node=*reinterpret_cast<unsigned char**>(node+0x18)){
  if(*reinterpret_cast<std::uint32_t*>(node)==nameID&&*reinterpret_cast<std::uint32_t*>(node+0x10)==nameID)
   return *reinterpret_cast<void**>(node+8)==function;
 }
 return false;
}
bool Register(const char* name,NativeCallback callback){
 struct Block {void* data;std::size_t size;};Block block{};
 Function<void(*)(Block*,std::size_t,std::size_t)>(profile::allocate)(&block,0xf8,0x10);
 if(!block.data||block.size<0xf8||block.size>4096)return false;
 std::memset(block.data,0,0xf8);
 void* pool=Function<void*(*)()>(profile::namePool)();
 // Actual game registration uses ASCII bytes. The pool hashes single bytes;
 // passing UTF-16 silently interns only the first character before its NUL.
 auto id=Function<std::uint32_t(*)(void*,const char*)>(profile::internName)(pool,name);
 if(!id)return false;
 auto* function=Function<void*(*)(void*,const std::uint32_t*,NativeCallback)>(profile::constructFunction)(block.data,&id,callback);
 if(!function)return false;
 // The engine RTTI registry owns the engine-allocated function for its lifetime.
 void* registry=Function<void*(*)()>(profile::rtti)();
 Function<void(*)(void*,void*)>(profile::registerFunction)(registry,function);
 return RegistryContains(registry,id,function);
}
void RegisterHook(){
 originalRegisterGlobals();
 if(registered.load()||registrationFailed.load())return;
 for(const auto& entry:std::array<std::pair<const char*,NativeCallback>,23>{{
  {"MaleModNativeClinicalDeposits",ClinicalDeposits},
  {"MaleModNativeGarmentControl",GarmentControl},{"MaleModNativeGarmentState",GarmentState},{"MaleModNativeGarmentCarrier",GarmentCarrier},{"MaleModNativeClinicalCue",ClinicalCue},{"MaleModNativeClinicalCarrier",ClinicalCarrier},{"MaleModNativeClinicalControl",ClinicalControl},{"MaleModNativeClinicalQuery",ClinicalQuery},{"MaleModNativeClinicalHit",ClinicalHit},{"MaleModNativeClinicalState",ClinicalState},{"MaleModNativeReady",Ready},{"MaleModNativeSetControl",SetControl},
  {"MaleModNativeGetControl",GetControl},{"MaleModNativeTypedProbe",TypedProbe},
  {"MaleModNativeTypedProbeResult",TypedProbeResult},{"MaleModNativePoseSample",ProbePoseSample},{"MaleModNativeFrame",RuntimeFrame},{"MaleModNativeOverlayOpen",OverlayOpen},{"MaleModNativeBonePose",BonePose},{"MaleModNativeSurfaceActive",SurfaceActive},{"MaleModNativeFullMode",FullMode},{"MaleModNativeSealedSession",SealedSession},{"MaleModNativeTestCheckpoint",TestCheckpoint}}}){
  if(!Register(entry.first,entry.second)){registrationFailed=true;OutputDebugStringW(L"MaleMod: native function registration/name readback failed\n");return;}
 }
 registered.store(true,std::memory_order_release);
 OutputDebugStringW(L"MaleMod: native function registered; live script invocation remains a separate gate\n");
}
}
}

extern "C" __declspec(dllexport) DWORD WINAPI MaleModInitialize(void*){
 using namespace malemod::witcher;
 if(initialized.load())return 1;
 engineBase=reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
 if(!VerifyExecutable()||!CheckPrefixes())return 2;
 if(MH_Initialize()!=MH_OK)return 3;
 if(MH_CreateHook(reinterpret_cast<void*>(engineBase+profile::registerGlobals.rva),RegisterHook,reinterpret_cast<void**>(&originalRegisterGlobals))!=MH_OK){MH_Uninitialize();return 4;}
 if(MH_EnableHook(reinterpret_cast<void*>(engineBase+profile::registerGlobals.rva))!=MH_OK){MH_RemoveHook(reinterpret_cast<void*>(engineBase+profile::registerGlobals.rva));MH_Uninitialize();return 5;}
 if(!InitializeGraphicsProbe())OutputDebugStringW(L"MaleMod: read-only graphics observer unavailable\n");
 try{InitializeRuntime();}catch(const std::exception&){runtimeFlags.fetch_or(32);OutputDebugStringW(L"MaleMod: runtime profile validation failed; full solver disabled\n");}
 initialized=true;return 0;
}
extern "C" __declspec(dllexport) DWORD WINAPI MaleModProbeStatus(void*){
 using namespace malemod::witcher;
 return (initialized.load()?4u:0u)|(registered.load()?1u:0u)|(registrationFailed.load()?2u:0u)|(invoked.load()?8u:0u)|typedFlags.load();
}
extern "C" __declspec(dllexport) DWORD WINAPI MaleModGraphicsProbeStatus(void*){
 return malemod::witcher::GraphicsProbeFlags();
}
extern "C" __declspec(dllexport) DWORD WINAPI MaleModRuntimeStatus(void*){return malemod::witcher::runtimeFlags.load();}
extern "C" __declspec(dllexport) DWORD WINAPI MaleModRuntimeFrameCount(void*){return malemod::witcher::runtimeFrameCount.load();}
extern "C" __declspec(dllexport) DWORD WINAPI MaleModSealedSessionStatus(void*){return malemod::witcher::sealedFlags.load();}
extern "C" __declspec(dllexport) DWORD WINAPI MaleModRenderStatus(void*){return malemod::witcher::FloatDrawFlags()|(malemod::witcher::LiveRenderFlags()&512);}
extern "C" __declspec(dllexport) DWORD WINAPI MaleModRenderSequence(void*){return malemod::witcher::FloatDrawSequence();}
extern "C" __declspec(dllexport) DWORD WINAPI MaleModShutdownRuntime(void*){
 using namespace malemod::witcher;RuntimeHost* retired=nullptr;OverlayPanel* ui=nullptr;
 {std::lock_guard<std::mutex> lock(runtimeMutex);retired=runtimeHost;runtimeHost=nullptr;ui=overlayPanel;overlayPanel=nullptr;runtimeFlags.store(0);}
 LiveRenderFeed({});GarmentRendererFeed({});delete garmentService;garmentService=nullptr;delete ui;delete clinicalService;clinicalService=nullptr;delete retired;delete renderService;renderService=nullptr;delete renderPose;renderPose=nullptr;delete renderContract;renderContract=nullptr;return 0; // Invoke outside engine/loader locks, never from DllMain.
}
BOOL WINAPI DllMain(HINSTANCE,DWORD,LPVOID){
 // Keep CRT thread notifications: this probe uses the static MSVC runtime.
 // Do not initialize hooks, launch workers or wait for graphics under loader lock.
 return TRUE;
}
