// Read-only SDK API observer. No vertex, shader, descriptor, skin or draw is
// changed. A device observation is not proof of an owned mesh output path.
#define NOMINMAX
#define CINTERFACE
#include <windows.h>
#include <d3d12.h>
#include <MinHook.h>
#include <atomic>
#include <cstdio>
#include <mutex>
#include <set>
#include <tuple>
#include <cstddef>
#include <share.h>
#include <array>
#include <utility>
#include "graphics_probe.hpp"

namespace malemod::witcher {
namespace {
using CreateDevice=HRESULT(WINAPI*)(IUnknown*,D3D_FEATURE_LEVEL,REFIID,void**);
using CreateResource=decltype(ID3D12DeviceVtbl::CreateCommittedResource);
using CreateList=decltype(ID3D12DeviceVtbl::CreateCommandList);
using CreateList1=decltype(ID3D12Device4Vtbl::CreateCommandList1);
using SetVertices=decltype(ID3D12GraphicsCommandListVtbl::IASetVertexBuffers);
using CopyBuffer=decltype(ID3D12GraphicsCommandListVtbl::CopyBufferRegion);
using DrawIndexed=decltype(ID3D12GraphicsCommandListVtbl::DrawIndexedInstanced);
using Draw=decltype(ID3D12GraphicsCommandListVtbl::DrawInstanced);
using Indirect=decltype(ID3D12GraphicsCommandListVtbl::ExecuteIndirect);
using RootSRV=decltype(ID3D12GraphicsCommandListVtbl::SetGraphicsRootShaderResourceView);
using CreateFactory=decltype(ID3D12SDKConfiguration1Vtbl::CreateDeviceFactory);
using FactoryDevice=decltype(ID3D12DeviceFactoryVtbl::CreateDevice);
CreateDevice originalCreateDevice=nullptr;
CreateResource originalCreateResource=nullptr;
CreateList originalCreateList=nullptr;
CreateList1 originalCreateList1=nullptr;
// Copy and direct lists, and interposer wrappers, can expose different SDK
// method addresses. Each detour needs its own trampoline; a single global
// trampoline silently observes only the first implementation encountered.
template<class Function> struct MethodHooks {
 static constexpr std::size_t capacity=16;
 std::array<Function,capacity> originals{};
 std::array<void*,capacity> targets{};
 std::size_t count=0;
};
MethodHooks<SetVertices> vertexHooks;
MethodHooks<CopyBuffer> copyHooks;
MethodHooks<DrawIndexed> indexedHooks;
MethodHooks<Draw> drawHooks;
MethodHooks<Indirect> indirectHooks;
MethodHooks<RootSRV> srvHooks;
PFN_D3D12_GET_INTERFACE originalGetInterface=nullptr;
CreateFactory originalCreateFactory=nullptr;
FactoryDevice originalFactoryDevice=nullptr;
std::atomic<unsigned> flags{0},resourceCount{0},copyCount{0};
std::mutex hookMutex,logMutex;
FILE* log=nullptr;
std::set<std::tuple<unsigned,unsigned>> formats;
std::set<std::tuple<unsigned,void*,void*>> listImplementations;
bool Hook(void* address,void* callback,void** original){
 auto status=MH_CreateHook(address,callback,original);
 if(status!=MH_OK)return false;
 if(MH_EnableHook(address)==MH_OK)return true;
 MH_RemoveHook(address);return false;
}
void OpenLog(){
 wchar_t path[32768]{};HMODULE module=nullptr;
 if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,reinterpret_cast<LPCWSTR>(&OpenLog),&module))return;
 if(!GetModuleFileNameW(module,path,32768))return;
 auto* last=wcsrchr(path,L'\\');if(!last)return;
 swprintf_s(last+1,32768-std::size_t(last+1-path),L"graphics-probe-%lu.jsonl",GetCurrentProcessId());
 log=_wfsopen(path,L"wb",_SH_DENYNO);
}
HRESULT STDMETHODCALLTYPE ResourceHook(ID3D12Device* device,const D3D12_HEAP_PROPERTIES* heap,D3D12_HEAP_FLAGS heapFlags,const D3D12_RESOURCE_DESC* desc,D3D12_RESOURCE_STATES state,const D3D12_CLEAR_VALUE* clear,REFIID iid,void** output){
 auto result=originalCreateResource(device,heap,heapFlags,desc,state,clear,iid,output);
 if(SUCCEEDED(result)&&desc&&desc->Dimension==D3D12_RESOURCE_DIMENSION_BUFFER&&heap&&resourceCount.fetch_add(1)<128){
  std::lock_guard<std::mutex> lock(logMutex);
  if(log){std::fprintf(log,"{\"event\":\"bufferCreated\",\"width\":%llu,\"heap\":%u,\"resourceFlags\":%u,\"initialState\":%u}\n",static_cast<unsigned long long>(desc->Width),unsigned(heap->Type),unsigned(desc->Flags),unsigned(state));std::fflush(log);}
 }
 return result;
}
template<std::size_t N> void STDMETHODCALLTYPE VerticesHook(ID3D12GraphicsCommandList* list,UINT first,UINT count,const D3D12_VERTEX_BUFFER_VIEW* views){
 vertexHooks.originals[N](list,first,count,views);
 flags.fetch_or(4);
 if(!views||count>32)return;
 std::lock_guard<std::mutex> lock(logMutex);
 for(UINT i=0;i<count;i++){
  if(formats.size()>=128||!formats.emplace(first+i,views[i].StrideInBytes).second)continue;
  if(log){std::fprintf(log,"{\"event\":\"vertexStreamFormat\",\"slot\":%u,\"stride\":%u,\"bytes\":%u}\n",first+i,views[i].StrideInBytes,views[i].SizeInBytes);std::fflush(log);}
 }
}
template<std::size_t N> void STDMETHODCALLTYPE CopyHook(ID3D12GraphicsCommandList* list,ID3D12Resource* destination,UINT64 destOffset,ID3D12Resource* source,UINT64 sourceOffset,UINT64 bytes){
 copyHooks.originals[N](list,destination,destOffset,source,sourceOffset,bytes);
 flags.fetch_or(8);
 if(copyCount.fetch_add(1)>=128)return;
 std::lock_guard<std::mutex> lock(logMutex);
 if(log){std::fprintf(log,"{\"event\":\"bufferCopy\",\"bytes\":%llu,\"sourceOffset\":%llu,\"destinationOffset\":%llu}\n",static_cast<unsigned long long>(bytes),static_cast<unsigned long long>(sourceOffset),static_cast<unsigned long long>(destOffset));std::fflush(log);}
}
void FirstCall(unsigned bit,const char* event){
 if(flags.fetch_or(bit)&bit)return;
 std::lock_guard<std::mutex> lock(logMutex);
 if(log){std::fprintf(log,"{\"event\":\"%s\"}\n",event);std::fflush(log);}
}
template<std::size_t N> void STDMETHODCALLTYPE IndexedHook(ID3D12GraphicsCommandList* list,UINT indices,UINT instances,UINT first,INT base,UINT firstInstance){
 indexedHooks.originals[N](list,indices,instances,first,base,firstInstance);FirstCall(16,"indexedDrawObserved");
}
template<std::size_t N> void STDMETHODCALLTYPE DrawHook(ID3D12GraphicsCommandList* list,UINT vertices,UINT instances,UINT first,UINT firstInstance){
 drawHooks.originals[N](list,vertices,instances,first,firstInstance);FirstCall(32,"drawObserved");
}
template<std::size_t N> void STDMETHODCALLTYPE IndirectHook(ID3D12GraphicsCommandList* list,ID3D12CommandSignature* signature,UINT maximum,ID3D12Resource* arguments,UINT64 offset,ID3D12Resource* counts,UINT64 countOffset){
 indirectHooks.originals[N](list,signature,maximum,arguments,offset,counts,countOffset);FirstCall(64,"indirectObserved");
}
template<std::size_t N> void STDMETHODCALLTYPE SRVHook(ID3D12GraphicsCommandList* list,UINT index,D3D12_GPU_VIRTUAL_ADDRESS address){
 srvHooks.originals[N](list,index,address);FirstCall(128,"rootSRVObserved");
}
template<std::size_t... N> auto VertexCallbacks(std::index_sequence<N...>){return std::array<SetVertices,sizeof...(N)>{&VerticesHook<N>...};}
template<std::size_t... N> auto CopyCallbacks(std::index_sequence<N...>){return std::array<CopyBuffer,sizeof...(N)>{&CopyHook<N>...};}
template<std::size_t... N> auto IndexedCallbacks(std::index_sequence<N...>){return std::array<DrawIndexed,sizeof...(N)>{&IndexedHook<N>...};}
template<std::size_t... N> auto DrawCallbacks(std::index_sequence<N...>){return std::array<Draw,sizeof...(N)>{&DrawHook<N>...};}
template<std::size_t... N> auto IndirectCallbacks(std::index_sequence<N...>){return std::array<Indirect,sizeof...(N)>{&IndirectHook<N>...};}
template<std::size_t... N> auto SRVCallbacks(std::index_sequence<N...>){return std::array<RootSRV,sizeof...(N)>{&SRVHook<N>...};}
template<class Function> bool HookMethod(MethodHooks<Function>& methods,Function target,const std::array<Function,16>& callbacks){
 auto* address=reinterpret_cast<void*>(target);
 for(std::size_t i=0;i<methods.count;i++)if(methods.targets[i]==address)return true;
 if(methods.count==methods.capacity)return false;
 auto i=methods.count;
 if(!Hook(address,reinterpret_cast<void*>(callbacks[i]),reinterpret_cast<void**>(&methods.originals[i])))return false;
 methods.targets[i]=address;methods.count++;return true;
}
void ObserveList(HRESULT result,D3D12_COMMAND_LIST_TYPE type,void** output){
 if(SUCCEEDED(result)&&output&&*output&&type!=D3D12_COMMAND_LIST_TYPE_BUNDLE){
  ID3D12GraphicsCommandList* list=nullptr;
  auto* unknown=static_cast<IUnknown*>(*output);
  if(SUCCEEDED(unknown->lpVtbl->QueryInterface(unknown,IID_ID3D12GraphicsCommandList,reinterpret_cast<void**>(&list)))){
   std::lock_guard<std::mutex> lock(hookMutex);
   const auto slots=std::make_index_sequence<16>{};
   if(!HookMethod(vertexHooks,list->lpVtbl->IASetVertexBuffers,VertexCallbacks(slots))||
      !HookMethod(copyHooks,list->lpVtbl->CopyBufferRegion,CopyCallbacks(slots))||
      !HookMethod(indexedHooks,list->lpVtbl->DrawIndexedInstanced,IndexedCallbacks(slots))||
      !HookMethod(drawHooks,list->lpVtbl->DrawInstanced,DrawCallbacks(slots))||
      !HookMethod(indirectHooks,list->lpVtbl->ExecuteIndirect,IndirectCallbacks(slots))||
      !HookMethod(srvHooks,list->lpVtbl->SetGraphicsRootShaderResourceView,SRVCallbacks(slots)))flags.fetch_or(0x8000);
   // Log implementation identity once, independent of the resource event cap.
   if(listImplementations.size()<48&&listImplementations.emplace(unsigned(type),reinterpret_cast<void*>(list->lpVtbl->IASetVertexBuffers),reinterpret_cast<void*>(list->lpVtbl->DrawIndexedInstanced)).second){
    std::lock_guard<std::mutex> logLock(logMutex);
    if(log){std::fprintf(log,"{\"event\":\"listImplementation\",\"type\":%u,\"vertexMethod\":\"%p\",\"indexedMethod\":\"%p\",\"vertexHookCount\":%zu}\n",unsigned(type),reinterpret_cast<void*>(list->lpVtbl->IASetVertexBuffers),reinterpret_cast<void*>(list->lpVtbl->DrawIndexedInstanced),vertexHooks.count);std::fflush(log);}
   }
   list->lpVtbl->Release(list);
  }
 }
}
HRESULT STDMETHODCALLTYPE ListHook(ID3D12Device* device,UINT nodeMask,D3D12_COMMAND_LIST_TYPE type,ID3D12CommandAllocator* allocator,ID3D12PipelineState* initial,REFIID iid,void** output){
 auto result=originalCreateList(device,nodeMask,type,allocator,initial,iid,output);ObserveList(result,type,output);return result;
}
HRESULT STDMETHODCALLTYPE List1Hook(ID3D12Device4* device,UINT nodeMask,D3D12_COMMAND_LIST_TYPE type,D3D12_COMMAND_LIST_FLAGS listFlags,REFIID iid,void** output){
 auto result=originalCreateList1(device,nodeMask,type,listFlags,iid,output);ObserveList(result,type,output);return result;
}
void ObserveDevice(HRESULT result,void** output){
 if(SUCCEEDED(result)&&output&&*output){
  ID3D12Device* device=nullptr;auto* unknown=static_cast<IUnknown*>(*output);
  if(SUCCEEDED(unknown->lpVtbl->QueryInterface(unknown,IID_ID3D12Device,reinterpret_cast<void**>(&device)))){
   flags.fetch_or(2);
   {std::lock_guard<std::mutex> logLock(logMutex);if(log){std::fprintf(log,"{\"event\":\"deviceObserved\"}\n");std::fflush(log);}}
   std::lock_guard<std::mutex> lock(hookMutex);
   if(!originalCreateResource&&!Hook(reinterpret_cast<void*>(device->lpVtbl->CreateCommittedResource),reinterpret_cast<void*>(&ResourceHook),reinterpret_cast<void**>(&originalCreateResource)))flags.fetch_or(0x8000);
   if(!originalCreateList&&!Hook(reinterpret_cast<void*>(device->lpVtbl->CreateCommandList),reinterpret_cast<void*>(&ListHook),reinterpret_cast<void**>(&originalCreateList)))flags.fetch_or(0x8000);
   ID3D12Device4* device4=nullptr;
   if(SUCCEEDED(device->lpVtbl->QueryInterface(device,IID_ID3D12Device4,reinterpret_cast<void**>(&device4)))){
    if(!originalCreateList1&&!Hook(reinterpret_cast<void*>(device4->lpVtbl->CreateCommandList1),reinterpret_cast<void*>(&List1Hook),reinterpret_cast<void**>(&originalCreateList1)))flags.fetch_or(0x8000);
    device4->lpVtbl->Release(device4);
   }
   device->lpVtbl->Release(device);
  }
 }
}
HRESULT WINAPI DeviceHook(IUnknown* adapter,D3D_FEATURE_LEVEL level,REFIID iid,void** output){
 auto result=originalCreateDevice(adapter,level,iid,output);ObserveDevice(result,output);return result;
}
HRESULT STDMETHODCALLTYPE FactoryDeviceHook(ID3D12DeviceFactory* factory,IUnknown* adapter,D3D_FEATURE_LEVEL level,REFIID iid,void** output){
 auto result=originalFactoryDevice(factory,adapter,level,iid,output);ObserveDevice(result,output);return result;
}
void ObserveFactory(HRESULT result,void** output){
 if(FAILED(result)||!output||!*output)return;
 auto* unknown=static_cast<IUnknown*>(*output);ID3D12DeviceFactory* factory=nullptr;
 if(SUCCEEDED(unknown->lpVtbl->QueryInterface(unknown,IID_ID3D12DeviceFactory,reinterpret_cast<void**>(&factory)))){
  std::lock_guard<std::mutex> lock(hookMutex);
  if(!originalFactoryDevice&&!Hook(reinterpret_cast<void*>(factory->lpVtbl->CreateDevice),reinterpret_cast<void*>(&FactoryDeviceHook),reinterpret_cast<void**>(&originalFactoryDevice)))flags.fetch_or(0x8000);
  factory->lpVtbl->Release(factory);
 }
}
HRESULT STDMETHODCALLTYPE CreateFactoryHook(ID3D12SDKConfiguration1* config,UINT version,LPCSTR path,REFIID iid,void** output){
 auto result=originalCreateFactory(config,version,path,iid,output);ObserveFactory(result,output);return result;
}
HRESULT WINAPI GetInterfaceHook(REFCLSID clsid,REFIID iid,void** output){
 auto result=originalGetInterface(clsid,iid,output);
 if(SUCCEEDED(result)&&output&&*output){
  ObserveFactory(result,output);
  auto* unknown=static_cast<IUnknown*>(*output);ID3D12SDKConfiguration1* config=nullptr;
  if(SUCCEEDED(unknown->lpVtbl->QueryInterface(unknown,IID_ID3D12SDKConfiguration1,reinterpret_cast<void**>(&config)))){
   std::lock_guard<std::mutex> lock(hookMutex);
   if(!originalCreateFactory&&!Hook(reinterpret_cast<void*>(config->lpVtbl->CreateDeviceFactory),reinterpret_cast<void*>(&CreateFactoryHook),reinterpret_cast<void**>(&originalCreateFactory)))flags.fetch_or(0x8000);
   config->lpVtbl->Release(config);
  }
 }
 return result;
}
}
bool InitializeGraphicsProbe(){
 OpenLog();
 // Resolve the system SDK factory; no DLL replacement or bootstrap device.
 auto library=LoadLibraryExW(L"d3d12.dll",nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);
 if(!library)return false;
 auto factory=GetProcAddress(library,"D3D12CreateDevice");
 if(!factory||!Hook(reinterpret_cast<void*>(factory),reinterpret_cast<void*>(&DeviceHook),reinterpret_cast<void**>(&originalCreateDevice)))return false;
 auto getInterface=GetProcAddress(library,"D3D12GetInterface");
 if(getInterface&&!Hook(reinterpret_cast<void*>(getInterface),reinterpret_cast<void*>(&GetInterfaceHook),reinterpret_cast<void**>(&originalGetInterface)))flags.fetch_or(0x8000);
 flags.fetch_or(1);return true;
}
std::uint32_t GraphicsProbeFlags(){return flags.load();}
}
