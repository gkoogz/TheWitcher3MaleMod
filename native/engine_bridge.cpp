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
bool overlayRequested=false;
std::atomic<unsigned> runtimeFlags{0};
surface::Controls ReadControls(){std::lock_guard<std::mutex> lock(controlsMutex);return controls;}
bool WriteControl(unsigned index,float value){
 if(index>=18)return false;std::lock_guard<std::mutex> lock(controlsMutex);auto candidate=controls;candidate.values[index]=value;
 try{surface::wire::Validate(candidate);controls=candidate;return true;}catch(const std::invalid_argument&){return false;}
}
void CreateOverlayForGame(){
 if(!overlayRequested||overlayPanel)return;
 struct Windows {HWND result=nullptr;unsigned count=0;} windows;
 EnumWindows([](HWND window,LPARAM data)->BOOL{DWORD pid=0;GetWindowThreadProcessId(window,&pid);RECT r{};
  if(pid==GetCurrentProcessId()&&!GetWindow(window,GW_OWNER)&&IsWindowVisible(window)&&GetClientRect(window,&r)&&r.right>=640&&r.bottom>=480){auto* list=reinterpret_cast<Windows*>(data);list->result=window;++list->count;}return TRUE;
 },reinterpret_cast<LPARAM>(&windows));
 if(windows.count==1)overlayPanel=new OverlayPanel(windows.result,ReadControls,WriteControl);
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
 const auto p=RuntimeProfile::Load(packet,MALEMOD_BASE_COMMIT);
 const auto worker=dir/L"surface_worker.exe",bindings=dir/L"geralt.bindings";
 if(!VerifyFile(worker,p.workerSHA256)||!VerifyFile(bindings,p.bindingsSHA256))throw std::runtime_error("Runtime worker/binding hash differs from profile");
 std::lock_guard<std::mutex> lock(runtimeMutex);
 runtimeHost=new RuntimeHost([p,worker,bindings]{return std::make_unique<RuntimeController>(worker.wstring(),bindings,p.revision,p.calibration,p.inverseBind,p.contacts,p.diagnosticSourceContacts);});
 overlayRequested=std::filesystem::exists(dir/L"malemod-overlay.enable");
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
 std::int32_t epoch=0;float seconds=0;bool paused=false;std::array<ScriptVector,8> v{};
 Parameter(frame,epoch);Parameter(frame,seconds);Parameter(frame,paused);for(auto& p:v)Parameter(frame,p);FinishParameters(frame);
 HostTick status=HostTick::Dormant;
 try{
 std::unique_lock<std::mutex> lock(runtimeMutex,std::try_to_lock);
 if(!lock.owns_lock())status=HostTick::Busy;
 else if(runtimeHost&&epoch>=0){
  if(epoch>0)CreateOverlayForGame();
  runtimeFlags.fetch_or(2);PoseSample sample;sample.seconds=seconds;sample.pelvisActorLocal[15]=1;
  for(unsigned column=0;column<4;column++){const std::array<float,3> xyz={v[column].x,v[column].y,v[column].z};for(unsigned r=0;r<3;r++)sample.pelvisActorLocal[r*4+column]=xyz[r];}
  for(unsigned i=0;i<4;i++)sample.thighsActorLocal[i]={v[i+4].x,v[i+4].y,v[i+4].z};
  const auto snapshot=ReadControls();
  std::uint64_t sequence=0;status=runtimeHost->Tick(std::uint32_t(epoch),sample,paused,snapshot,sequence);
  if(status==HostTick::Paused)runtimeFlags.fetch_or(8);
  if(status==HostTick::Busy||status==HostTick::Full)runtimeFlags.fetch_or(16);
  if(status==HostTick::Invalid||status==HostTick::Failed)runtimeFlags.fetch_or(32);
  if(runtimeHost->Poll(std::uint32_t(epoch)))runtimeFlags.fetch_or(4);
 }
 }catch(const std::exception&){
  // Allocation, window creation and publication failures cannot unwind through
  // REDengine's native VM callback. Report the fault to the script instead.
  status=HostTick::Failed;runtimeFlags.fetch_or(32);
  OutputDebugStringW(L"MaleMod: native frame integration failed; input stopped\n");
 }
 if(result)*static_cast<std::int32_t*>(result)=static_cast<std::int32_t>(status);
}
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
 for(const auto& entry:std::array<std::pair<const char*,NativeCallback>,8>{{
  {"MaleModNativeReady",Ready},{"MaleModNativeSetControl",SetControl},
  {"MaleModNativeGetControl",GetControl},{"MaleModNativeTypedProbe",TypedProbe},
  {"MaleModNativeTypedProbeResult",TypedProbeResult},{"MaleModNativePoseSample",ProbePoseSample},{"MaleModNativeFrame",RuntimeFrame},{"MaleModNativeOverlayOpen",OverlayOpen}}}){
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
extern "C" __declspec(dllexport) DWORD WINAPI MaleModShutdownRuntime(void*){
 using namespace malemod::witcher;RuntimeHost* retired=nullptr;OverlayPanel* ui=nullptr;
 {std::lock_guard<std::mutex> lock(runtimeMutex);retired=runtimeHost;runtimeHost=nullptr;ui=overlayPanel;overlayPanel=nullptr;runtimeFlags.store(0);}
 delete ui;delete retired;return 0; // Invoke outside engine/loader locks, never from DllMain.
}
BOOL WINAPI DllMain(HINSTANCE,DWORD,LPVOID){
 // Keep CRT thread notifications: this probe uses the static MSVC runtime.
 // Do not initialize hooks, launch workers or wait for graphics under loader lock.
 return TRUE;
}
