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
#include <malemod/surface/wire.hpp>
#include "game_profile.hpp"
#include "graphics_probe.hpp"

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

bool VerifyExecutable(){
 wchar_t path[32768]{};if(!GetModuleFileNameW(nullptr,path,32768))return false;
 HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
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
 return actual==profile::executableSHA256;
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
void SetControl(void*,void* frame,void* result){
 std::int32_t index=-1;float value=0;
 Parameter(frame,index);Parameter(frame,value);FinishParameters(frame);
 bool accepted=false;
 if(index>=0&&index<18){
  std::lock_guard<std::mutex> lock(controlsMutex);
  auto candidate=controls;candidate.values[std::size_t(index)]=value;
  try{malemod::surface::wire::Validate(candidate);controls=candidate;accepted=true;}
  catch(const std::invalid_argument&){} // Preserve the last valid preference set.
 }
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
 for(const auto& entry:std::array<std::pair<const char*,NativeCallback>,5>{{
  {"MaleModNativeReady",Ready},{"MaleModNativeSetControl",SetControl},
  {"MaleModNativeGetControl",GetControl},{"MaleModNativeTypedProbe",TypedProbe},
  {"MaleModNativeTypedProbeResult",TypedProbeResult}}}){
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
 initialized=true;return 0;
}
extern "C" __declspec(dllexport) DWORD WINAPI MaleModProbeStatus(void*){
 using namespace malemod::witcher;
 return (initialized.load()?4u:0u)|(registered.load()?1u:0u)|(registrationFailed.load()?2u:0u)|(invoked.load()?8u:0u)|typedFlags.load();
}
extern "C" __declspec(dllexport) DWORD WINAPI MaleModGraphicsProbeStatus(void*){
 return malemod::witcher::GraphicsProbeFlags();
}
BOOL WINAPI DllMain(HINSTANCE,DWORD,LPVOID){
 // Keep CRT thread notifications: this probe uses the static MSVC runtime.
 // Do not initialize hooks, launch workers or wait for graphics under loader lock.
 return TRUE;
}
