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
#include <vector>
#include <map>
#include <algorithm>
#include "graphics_probe.hpp"
#include "graphics_fingerprints.hpp"

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
using CreateSignature=decltype(ID3D12DeviceVtbl::CreateCommandSignature);
using CreateQueue=decltype(ID3D12DeviceVtbl::CreateCommandQueue);
using ExecuteLists=decltype(ID3D12CommandQueueVtbl::ExecuteCommandLists);
using CreatePSO=decltype(ID3D12DeviceVtbl::CreateGraphicsPipelineState);
using ResetList=decltype(ID3D12GraphicsCommandListVtbl::Reset);
using SetIndices=decltype(ID3D12GraphicsCommandListVtbl::IASetIndexBuffer);
using CreateFactory=decltype(ID3D12SDKConfiguration1Vtbl::CreateDeviceFactory);
using FactoryDevice=decltype(ID3D12DeviceFactoryVtbl::CreateDevice);
CreateDevice originalCreateDevice=nullptr;



// Copy and direct lists, and interposer wrappers, can expose different SDK
// method addresses. Each detour needs its own trampoline; a single global
// trampoline silently observes only the first implementation encountered.
template<class Function> struct MethodHooks {
 static constexpr std::size_t capacity=16;
 std::array<Function,capacity> originals{};
 std::array<void*,capacity> targets{};
 std::size_t count=0;
};
MethodHooks<CreateResource> resourceCreateHooks;
MethodHooks<CreateList> listCreateHooks;
MethodHooks<CreateList1> list1CreateHooks;
MethodHooks<CreateSignature> signatureCreateHooks;
MethodHooks<CreateQueue> queueCreateHooks;
MethodHooks<CreatePSO> psoCreateHooks;
MethodHooks<SetVertices> vertexHooks;
MethodHooks<CopyBuffer> copyHooks;
MethodHooks<DrawIndexed> indexedHooks;
MethodHooks<Draw> drawHooks;
MethodHooks<Indirect> indirectHooks;
MethodHooks<RootSRV> srvHooks;
MethodHooks<ExecuteLists> executeHooks;
MethodHooks<ResetList> resetHooks;
MethodHooks<SetIndices> indexHooks;



PFN_D3D12_GET_INTERFACE originalGetInterface=nullptr;
CreateFactory originalCreateFactory=nullptr;
FactoryDevice originalFactoryDevice=nullptr;
std::atomic<unsigned> flags{0},resourceCount{0},copyCount{0};
std::mutex hookMutex,logMutex;
FILE* log=nullptr;
std::set<std::tuple<unsigned,unsigned>> formats;
std::set<std::tuple<unsigned,void*,void*>> listImplementations;
std::mutex metadataMutex;
struct Signature {UINT stride;std::vector<D3D12_INDIRECT_ARGUMENT_DESC> arguments;};
std::map<ID3D12CommandSignature*,Signature> signatures;
std::set<ID3D12CommandSignature*> indirectSeen;
std::atomic<unsigned> psoCount{0},queueCount{0};
GraphicsFingerprints fingerprints;
std::atomic<unsigned> fingerprintSamples{0};
std::set<std::tuple<ID3D12Resource*,UINT64,std::string>> fingerprintSeen;
struct OwnedRange {UINT64 begin,bytes;std::string label;};
std::vector<OwnedRange> ownedRanges;
// Retain exactly identified resources for the diagnostic process lifetime so
// their GPU addresses cannot be recycled and mistaken for a different mesh.
std::set<ID3D12Resource*> pinnedOwnedResources;
struct ListBindings {std::array<D3D12_VERTEX_BUFFER_VIEW,32> vertices{};D3D12_INDEX_BUFFER_VIEW indices{};std::map<UINT,UINT64> rootSRVs;};
std::map<ID3D12GraphicsCommandList*,ListBindings> bindings;
std::set<std::tuple<UINT64,UINT64,UINT,UINT,INT>> ownedDraws;
void ObserveOwnedDraw(ID3D12GraphicsCommandList* list,UINT count,UINT first,INT base)noexcept{
 try{
  std::lock_guard<std::mutex> lock(metadataMutex);auto found=bindings.find(list);if(found==bindings.end()||ownedDraws.size()>=128)return;
  const auto& state=found->second;
  for(unsigned slot=0;slot<state.vertices.size();slot++){
   const auto& view=state.vertices[slot];if(!view.BufferLocation||!view.SizeInBytes)continue;
   std::vector<std::string> labels;
   for(const auto& range:ownedRanges)if(view.BufferLocation>=range.begin&&view.BufferLocation-range.begin<range.bytes)labels.push_back(range.label);
   if(labels.empty()||!ownedDraws.emplace(view.BufferLocation,state.indices.BufferLocation,count,first,base).second)continue;
   std::lock_guard<std::mutex> logLock(logMutex);
   if(log){std::fprintf(log,"{\"event\":\"ownedIndexedDraw\",\"indexCount\":%u,\"firstIndex\":%u,\"baseVertex\":%d,\"matchedSlot\":%u,\"matchedStride\":%u,\"matchedGPUAddress\":\"%llx\",\"labels\":[",count,first,base,slot,view.StrideInBytes,static_cast<unsigned long long>(view.BufferLocation));
    for(unsigned i=0;i<labels.size();i++)std::fprintf(log,"%s\"%s\"",i?",":"",labels[i].c_str());
    std::fprintf(log,"],\"vertexViews\":[");bool separator=false;
    for(unsigned i=0;i<state.vertices.size();i++){const auto& v=state.vertices[i];if(!v.BufferLocation||!v.SizeInBytes)continue;
     std::fprintf(log,"%s{\"slot\":%u,\"address\":\"%llx\",\"bytes\":%u,\"stride\":%u}",separator?",":"",i,static_cast<unsigned long long>(v.BufferLocation),v.SizeInBytes,v.StrideInBytes);separator=true;}
    std::fprintf(log,"],\"indexView\":{\"address\":\"%llx\",\"bytes\":%u,\"format\":%u},\"rootSRVs\":[",static_cast<unsigned long long>(state.indices.BufferLocation),state.indices.SizeInBytes,unsigned(state.indices.Format));separator=false;
    for(auto [index,address]:state.rootSRVs){std::fprintf(log,"%s{\"index\":%u,\"address\":\"%llx\"}",separator?",":"",index,static_cast<unsigned long long>(address));separator=true;}
    std::fprintf(log,"]}\n");std::fflush(log);flags.fetch_or(4096);
   }
  }
 }catch(...){flags.fetch_or(0x8000);}
}
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
 const auto ownedPath=std::filesystem::path(path).parent_path()/L"graphics-owned-fingerprints.bin";
 auto* last=wcsrchr(path,L'\\');if(!last)return;
 swprintf_s(last+1,32768-std::size_t(last+1-path),L"graphics-probe-%lu.jsonl",GetCurrentProcessId());
 log=_wfsopen(path,L"wb",_SH_DENYNO);
 if(std::filesystem::exists(ownedPath)){
  try{fingerprints.Load(ownedPath);if(log){std::fprintf(log,"{\"event\":\"ownedFingerprintsLoaded\",\"count\":%zu}\n",fingerprints.Count());std::fflush(log);}}
  catch(const std::exception&){flags.fetch_or(0x8000);}
 }
}
void FingerprintCopy(ID3D12Resource* destination,UINT64 destOffset,ID3D12Resource* source,UINT64 offset,UINT64 bytes)noexcept{
 if(!source||!destination||!fingerprints.HasSize(bytes)||fingerprintSamples.fetch_add(1)>=512)return;
 try{
  D3D12_RESOURCE_DESC desc{};source->lpVtbl->GetDesc(source,&desc);
  D3D12_HEAP_PROPERTIES heap{};D3D12_HEAP_FLAGS heapFlags{};
  if(desc.Dimension!=D3D12_RESOURCE_DIMENSION_BUFFER||offset>desc.Width||bytes>desc.Width-offset||
     FAILED(source->lpVtbl->GetHeapProperties(source,&heap,&heapFlags))||heap.Type!=D3D12_HEAP_TYPE_UPLOAD)return;
  void* mapped=nullptr;D3D12_RANGE read{static_cast<SIZE_T>(offset),static_cast<SIZE_T>(offset+bytes)};
  if(FAILED(source->lpVtbl->Map(source,0,&read,&mapped))||!mapped)return;
  std::vector<std::string> hits;
  try{hits=fingerprints.Match(static_cast<const unsigned char*>(mapped)+offset,static_cast<std::uint32_t>(bytes));}
  catch(...){D3D12_RANGE written{0,0};source->lpVtbl->Unmap(source,0,&written);throw;}
  D3D12_RANGE written{0,0};source->lpVtbl->Unmap(source,0,&written);
  if(hits.empty())return;flags.fetch_or(512);
  const auto address=destination->lpVtbl->GetGPUVirtualAddress(destination);
  {
   std::lock_guard<std::mutex> lock(metadataMutex);
   if(pinnedOwnedResources.size()<128||pinnedOwnedResources.count(destination)){
    if(pinnedOwnedResources.emplace(destination).second)destination->lpVtbl->AddRef(destination);
    for(const auto& label:hits)if(ownedRanges.size()<512&&std::none_of(ownedRanges.begin(),ownedRanges.end(),[&](const auto& r){return r.begin==address+destOffset&&r.bytes==bytes&&r.label==label;}))ownedRanges.push_back({address+destOffset,bytes,label});
   }
  }
  std::lock_guard<std::mutex> lock(logMutex);
  for(const auto& label:hits)if(fingerprintSeen.size()<256&&fingerprintSeen.emplace(destination,destOffset,label).second&&log){
   std::fprintf(log,"{\"event\":\"ownedBufferFingerprint\",\"label\":\"%s\",\"destination\":\"%p\",\"gpuAddress\":\"%llx\",\"offset\":%llu,\"bytes\":%llu}\n",label.c_str(),destination,static_cast<unsigned long long>(address),static_cast<unsigned long long>(destOffset),static_cast<unsigned long long>(bytes));std::fflush(log);
  }
 }catch(...){flags.fetch_or(0x8000);}
}
template<std::size_t N> HRESULT STDMETHODCALLTYPE ResourceHook(ID3D12Device* device,const D3D12_HEAP_PROPERTIES* heap,D3D12_HEAP_FLAGS heapFlags,const D3D12_RESOURCE_DESC* desc,D3D12_RESOURCE_STATES state,const D3D12_CLEAR_VALUE* clear,REFIID iid,void** output){
 auto result=resourceCreateHooks.originals[N](device,heap,heapFlags,desc,state,clear,iid,output);
 if(SUCCEEDED(result)&&desc&&desc->Dimension==D3D12_RESOURCE_DIMENSION_BUFFER&&heap&&resourceCount.fetch_add(1)<128){
  std::lock_guard<std::mutex> lock(logMutex);
  if(log){std::fprintf(log,"{\"event\":\"bufferCreated\",\"width\":%llu,\"heap\":%u,\"resourceFlags\":%u,\"initialState\":%u}\n",static_cast<unsigned long long>(desc->Width),unsigned(heap->Type),unsigned(desc->Flags),unsigned(state));std::fflush(log);}
 }
 return result;
}
template<std::size_t N> void STDMETHODCALLTYPE VerticesHook(ID3D12GraphicsCommandList* list,UINT first,UINT count,const D3D12_VERTEX_BUFFER_VIEW* views){
 vertexHooks.originals[N](list,first,count,views);
 flags.fetch_or(4);
 if(list->lpVtbl->GetType(list)==D3D12_COMMAND_LIST_TYPE_BUNDLE)flags.fetch_or(1024);
 if(!views||count>32)return;
 try{std::lock_guard<std::mutex> lock(metadataMutex);if(first<=32&&count<=32-first&&(bindings.size()<512||bindings.count(list))){auto& state=bindings[list];for(UINT i=0;i<count;i++)state.vertices[first+i]=views[i];}}
 catch(...){flags.fetch_or(0x8000);}
 std::lock_guard<std::mutex> lock(logMutex);
 for(UINT i=0;i<count;i++){
  if(formats.size()>=128||!formats.emplace(first+i,views[i].StrideInBytes).second)continue;
  if(log){std::fprintf(log,"{\"event\":\"vertexStreamFormat\",\"slot\":%u,\"stride\":%u,\"bytes\":%u}\n",first+i,views[i].StrideInBytes,views[i].SizeInBytes);std::fflush(log);}
 }
}
template<std::size_t N> void STDMETHODCALLTYPE CopyHook(ID3D12GraphicsCommandList* list,ID3D12Resource* destination,UINT64 destOffset,ID3D12Resource* source,UINT64 sourceOffset,UINT64 bytes){
 copyHooks.originals[N](list,destination,destOffset,source,sourceOffset,bytes);
 FingerprintCopy(destination,destOffset,source,sourceOffset,bytes);
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
 ObserveOwnedDraw(list,indices,first,base);
}
template<std::size_t N> void STDMETHODCALLTYPE DrawHook(ID3D12GraphicsCommandList* list,UINT vertices,UINT instances,UINT first,UINT firstInstance){
 drawHooks.originals[N](list,vertices,instances,first,firstInstance);FirstCall(32,"drawObserved");
}
template<std::size_t N> void STDMETHODCALLTYPE IndirectHook(ID3D12GraphicsCommandList* list,ID3D12CommandSignature* signature,UINT maximum,ID3D12Resource* arguments,UINT64 offset,ID3D12Resource* counts,UINT64 countOffset){
 indirectHooks.originals[N](list,signature,maximum,arguments,offset,counts,countOffset);FirstCall(64,"indirectObserved");
 std::lock_guard<std::mutex> metadataLock(metadataMutex);
 if(indirectSeen.size()<64&&indirectSeen.emplace(signature).second){
  D3D12_RESOURCE_DESC desc{};if(arguments)arguments->lpVtbl->GetDesc(arguments,&desc);
  const auto found=signatures.find(signature);
  std::lock_guard<std::mutex> logLock(logMutex);
  if(log){std::fprintf(log,"{\"event\":\"indirectSignatureUsed\",\"signature\":\"%p\",\"maximumCount\":%u,\"argumentBufferBytes\":%llu,\"argumentOffset\":%llu,\"countBufferPresent\":%s,\"descriptorObserved\":%s,\"recordStride\":%u}\n",signature,maximum,static_cast<unsigned long long>(desc.Width),static_cast<unsigned long long>(offset),counts?"true":"false",found!=signatures.end()?"true":"false",found!=signatures.end()?found->second.stride:0);std::fflush(log);}
 }
}
template<std::size_t N> void STDMETHODCALLTYPE SRVHook(ID3D12GraphicsCommandList* list,UINT index,D3D12_GPU_VIRTUAL_ADDRESS address){
 srvHooks.originals[N](list,index,address);FirstCall(128,"rootSRVObserved");
 try{std::lock_guard<std::mutex> lock(metadataMutex);if(index<64&&(bindings.size()<512||bindings.count(list)))bindings[list].rootSRVs[index]=address;}catch(...){flags.fetch_or(0x8000);}
}
template<std::size_t N> void STDMETHODCALLTYPE IndexHook(ID3D12GraphicsCommandList* list,const D3D12_INDEX_BUFFER_VIEW* view){
 indexHooks.originals[N](list,view);
 try{std::lock_guard<std::mutex> lock(metadataMutex);if(bindings.size()<512||bindings.count(list))bindings[list].indices=view?*view:D3D12_INDEX_BUFFER_VIEW{};}catch(...){flags.fetch_or(0x8000);}
}
template<std::size_t... N> auto IndexCallbacks(std::index_sequence<N...>){return std::array<SetIndices,sizeof...(N)>{&IndexHook<N>...};}
template<std::size_t... N> auto VertexCallbacks(std::index_sequence<N...>){return std::array<SetVertices,sizeof...(N)>{&VerticesHook<N>...};}
template<std::size_t... N> auto CopyCallbacks(std::index_sequence<N...>){return std::array<CopyBuffer,sizeof...(N)>{&CopyHook<N>...};}
template<std::size_t... N> auto IndexedCallbacks(std::index_sequence<N...>){return std::array<DrawIndexed,sizeof...(N)>{&IndexedHook<N>...};}
template<std::size_t... N> auto DrawCallbacks(std::index_sequence<N...>){return std::array<Draw,sizeof...(N)>{&DrawHook<N>...};}
template<std::size_t... N> auto IndirectCallbacks(std::index_sequence<N...>){return std::array<Indirect,sizeof...(N)>{&IndirectHook<N>...};}
template<std::size_t... N> auto SRVCallbacks(std::index_sequence<N...>){return std::array<RootSRV,sizeof...(N)>{&SRVHook<N>...};}
template<std::size_t N> void STDMETHODCALLTYPE ExecuteHook(ID3D12CommandQueue* queue,UINT count,ID3D12CommandList* const* lists){
 executeHooks.originals[N](queue,count,lists);FirstCall(256,"queueSubmissionObserved");
}
template<std::size_t... N> auto ExecuteCallbacks(std::index_sequence<N...>){return std::array<ExecuteLists,sizeof...(N)>{&ExecuteHook<N>...};}
template<class Function> bool HookMethod(MethodHooks<Function>& methods,Function target,const std::array<Function,16>& callbacks){
 auto* address=reinterpret_cast<void*>(target);
 for(std::size_t i=0;i<methods.count;i++)if(methods.targets[i]==address)return true;
 if(methods.count==methods.capacity)return false;
 auto i=methods.count;
 if(!Hook(address,reinterpret_cast<void*>(callbacks[i]),reinterpret_cast<void**>(&methods.originals[i])))return false;
 methods.targets[i]=address;methods.count++;return true;
}
void ObserveList(HRESULT result,D3D12_COMMAND_LIST_TYPE type,REFIID iid,void** output);
template<std::size_t N> HRESULT STDMETHODCALLTYPE ResetHook(ID3D12GraphicsCommandList* list,ID3D12CommandAllocator* allocator,ID3D12PipelineState* initial){
 auto result=resetHooks.originals[N](list,allocator,initial);
 if(SUCCEEDED(result)){flags.fetch_or(2048);{std::lock_guard<std::mutex> lock(metadataMutex);bindings.erase(list);}void* output=list;ObserveList(result,list->lpVtbl->GetType(list),IID_ID3D12GraphicsCommandList,&output);}
 return result;
}
template<std::size_t... N> auto ResetCallbacks(std::index_sequence<N...>){return std::array<ResetList,sizeof...(N)>{&ResetHook<N>...};}
bool GraphicsListIID(REFIID iid){
 return IsEqualGUID(iid,IID_ID3D12GraphicsCommandList)||IsEqualGUID(iid,IID_ID3D12GraphicsCommandList1)||
  IsEqualGUID(iid,IID_ID3D12GraphicsCommandList2)||IsEqualGUID(iid,IID_ID3D12GraphicsCommandList3)||
  IsEqualGUID(iid,IID_ID3D12GraphicsCommandList4)||IsEqualGUID(iid,IID_ID3D12GraphicsCommandList5)||
  IsEqualGUID(iid,IID_ID3D12GraphicsCommandList6)||IsEqualGUID(iid,IID_ID3D12GraphicsCommandList7)||
  IsEqualGUID(iid,IID_ID3D12GraphicsCommandList8)||IsEqualGUID(iid,IID_ID3D12GraphicsCommandList9)||
  IsEqualGUID(iid,IID_ID3D12GraphicsCommandList10);
}
void ObserveList(HRESULT result,D3D12_COMMAND_LIST_TYPE type,REFIID iid,void** output){
  if(SUCCEEDED(result)&&output&&*output){
  ID3D12GraphicsCommandList* list=nullptr;
  auto* unknown=static_cast<IUnknown*>(*output);
  if(SUCCEEDED(unknown->lpVtbl->QueryInterface(unknown,IID_ID3D12GraphicsCommandList,reinterpret_cast<void**>(&list)))){
   std::lock_guard<std::mutex> lock(hookMutex);
   auto attach=[&](ID3D12GraphicsCommandList* list,const char* interfaceSource){
   const auto slots=std::make_index_sequence<16>{};
   if(!HookMethod(vertexHooks,list->lpVtbl->IASetVertexBuffers,VertexCallbacks(slots))||
      !HookMethod(copyHooks,list->lpVtbl->CopyBufferRegion,CopyCallbacks(slots))||
      !HookMethod(indexedHooks,list->lpVtbl->DrawIndexedInstanced,IndexedCallbacks(slots))||
      !HookMethod(drawHooks,list->lpVtbl->DrawInstanced,DrawCallbacks(slots))||
      !HookMethod(indirectHooks,list->lpVtbl->ExecuteIndirect,IndirectCallbacks(slots))||
      !HookMethod(srvHooks,list->lpVtbl->SetGraphicsRootShaderResourceView,SRVCallbacks(slots))||
      !HookMethod(resetHooks,list->lpVtbl->Reset,ResetCallbacks(slots)))flags.fetch_or(0x8000);
   if(!HookMethod(indexHooks,list->lpVtbl->IASetIndexBuffer,IndexCallbacks(slots)))flags.fetch_or(0x8000);
   // Log implementation identity once, independent of the resource event cap.
   if(listImplementations.size()<48&&listImplementations.emplace(unsigned(type),reinterpret_cast<void*>(list->lpVtbl->IASetVertexBuffers),reinterpret_cast<void*>(list->lpVtbl->DrawIndexedInstanced)).second){
    std::lock_guard<std::mutex> logLock(logMutex);
    if(log){std::fprintf(log,"{\"event\":\"listImplementation\",\"type\":%u,\"interfaceSource\":\"%s\",\"vertexMethod\":\"%p\",\"indexedMethod\":\"%p\",\"vertexHookCount\":%zu}\n",unsigned(type),interfaceSource,reinterpret_cast<void*>(list->lpVtbl->IASetVertexBuffers),reinterpret_cast<void*>(list->lpVtbl->DrawIndexedInstanced),vertexHooks.count);std::fflush(log);}
   }
   };
   attach(list,"queriedBase");
   // A wrapper may return a derived graphics interface with different method
   // addresses from QueryInterface(base). COM graphics inheritance guarantees
   // this SDK prefix only for the explicitly requested graphics IIDs.
   if(GraphicsListIID(iid))attach(static_cast<ID3D12GraphicsCommandList*>(*output),"returnedGraphics");
   // Query supported SDK graphics versions too. Engines may switch interfaces
   // after creation, and recording methods may change after Reset.
   for(const auto* version:{&IID_ID3D12GraphicsCommandList1,&IID_ID3D12GraphicsCommandList2,&IID_ID3D12GraphicsCommandList3,
       &IID_ID3D12GraphicsCommandList4,&IID_ID3D12GraphicsCommandList5,&IID_ID3D12GraphicsCommandList6,
       &IID_ID3D12GraphicsCommandList7,&IID_ID3D12GraphicsCommandList8,&IID_ID3D12GraphicsCommandList9,&IID_ID3D12GraphicsCommandList10}){
    ID3D12GraphicsCommandList* derived=nullptr;
    if(SUCCEEDED(unknown->lpVtbl->QueryInterface(unknown,*version,reinterpret_cast<void**>(&derived)))){
     attach(derived,"queriedGraphicsVersion");derived->lpVtbl->Release(derived);
    }
   }
   list->lpVtbl->Release(list);
  }
 }
}
template<std::size_t N> HRESULT STDMETHODCALLTYPE ListHook(ID3D12Device* device,UINT nodeMask,D3D12_COMMAND_LIST_TYPE type,ID3D12CommandAllocator* allocator,ID3D12PipelineState* initial,REFIID iid,void** output){
 auto result=listCreateHooks.originals[N](device,nodeMask,type,allocator,initial,iid,output);ObserveList(result,type,iid,output);return result;
}
template<std::size_t N> HRESULT STDMETHODCALLTYPE List1Hook(ID3D12Device4* device,UINT nodeMask,D3D12_COMMAND_LIST_TYPE type,D3D12_COMMAND_LIST_FLAGS listFlags,REFIID iid,void** output){
 auto result=list1CreateHooks.originals[N](device,nodeMask,type,listFlags,iid,output);ObserveList(result,type,iid,output);return result;
}
template<std::size_t N> HRESULT STDMETHODCALLTYPE SignatureHook(ID3D12Device* device,const D3D12_COMMAND_SIGNATURE_DESC* desc,ID3D12RootSignature* root,REFIID iid,void** output){
 auto result=signatureCreateHooks.originals[N](device,desc,root,iid,output);
 if(SUCCEEDED(result)&&desc&&output&&*output&&desc->NumArgumentDescs<=32&&desc->pArgumentDescs){
  auto* unknown=static_cast<IUnknown*>(*output);ID3D12CommandSignature* signature=nullptr;
  if(SUCCEEDED(unknown->lpVtbl->QueryInterface(unknown,IID_ID3D12CommandSignature,reinterpret_cast<void**>(&signature)))){
   std::lock_guard<std::mutex> metadataLock(metadataMutex);
   if(signatures.size()<256){
    signatures[signature]={desc->ByteStride,{desc->pArgumentDescs,desc->pArgumentDescs+desc->NumArgumentDescs}};indirectSeen.erase(signature);
    std::lock_guard<std::mutex> logLock(logMutex);
    if(log){std::fprintf(log,"{\"event\":\"commandSignatureCreated\",\"signature\":\"%p\",\"recordStride\":%u,\"arguments\":[",signature,desc->ByteStride);
     for(UINT i=0;i<desc->NumArgumentDescs;i++){const auto& a=desc->pArgumentDescs[i];if(i)std::fputc(',',log);std::fprintf(log,"{\"type\":%u",unsigned(a.Type));
      if(a.Type==D3D12_INDIRECT_ARGUMENT_TYPE_VERTEX_BUFFER_VIEW)std::fprintf(log,",\"slot\":%u",a.VertexBuffer.Slot);
      if(a.Type==D3D12_INDIRECT_ARGUMENT_TYPE_CONSTANT)std::fprintf(log,",\"rootParameter\":%u,\"destinationOffset\":%u,\"values\":%u",a.Constant.RootParameterIndex,a.Constant.DestOffsetIn32BitValues,a.Constant.Num32BitValuesToSet);
      if(a.Type==D3D12_INDIRECT_ARGUMENT_TYPE_CONSTANT_BUFFER_VIEW)std::fprintf(log,",\"rootParameter\":%u",a.ConstantBufferView.RootParameterIndex);
      if(a.Type==D3D12_INDIRECT_ARGUMENT_TYPE_SHADER_RESOURCE_VIEW)std::fprintf(log,",\"rootParameter\":%u",a.ShaderResourceView.RootParameterIndex);
      std::fputc('}',log);
     }std::fprintf(log,"]}\n");std::fflush(log);}
   }
   signature->lpVtbl->Release(signature);
  }
 }
 return result;
}
template<std::size_t N> HRESULT STDMETHODCALLTYPE QueueHook(ID3D12Device* device,const D3D12_COMMAND_QUEUE_DESC* desc,REFIID iid,void** output){
 auto result=queueCreateHooks.originals[N](device,desc,iid,output);
 if(SUCCEEDED(result)&&output&&*output){auto* unknown=static_cast<IUnknown*>(*output);ID3D12CommandQueue* queue=nullptr;
  if(SUCCEEDED(unknown->lpVtbl->QueryInterface(unknown,IID_ID3D12CommandQueue,reinterpret_cast<void**>(&queue)))){
   {std::lock_guard<std::mutex> lock(hookMutex);if(!HookMethod(executeHooks,queue->lpVtbl->ExecuteCommandLists,ExecuteCallbacks(std::make_index_sequence<16>{})))flags.fetch_or(0x8000);}
   if(desc&&queueCount.fetch_add(1)<16){std::lock_guard<std::mutex> lock(logMutex);if(log){std::fprintf(log,"{\"event\":\"queueObserved\",\"type\":%u}\n",unsigned(desc->Type));std::fflush(log);}}
   queue->lpVtbl->Release(queue);
  }
 }
 return result;
}
template<std::size_t N> HRESULT STDMETHODCALLTYPE PSOHook(ID3D12Device* device,const D3D12_GRAPHICS_PIPELINE_STATE_DESC* desc,REFIID iid,void** output){
 auto result=psoCreateHooks.originals[N](device,desc,iid,output);
 if(SUCCEEDED(result)&&desc&&desc->InputLayout.NumElements<=32&&psoCount.fetch_add(1)<64){
  std::lock_guard<std::mutex> lock(logMutex);
  if(log){std::fprintf(log,"{\"event\":\"graphicsInputLayout\",\"elements\":[");
   for(UINT i=0;i<desc->InputLayout.NumElements;i++){const auto& a=desc->InputLayout.pInputElementDescs[i];if(i)std::fputc(',',log);std::fprintf(log,"{\"slot\":%u,\"format\":%u,\"offset\":%u,\"class\":%u}",a.InputSlot,unsigned(a.Format),a.AlignedByteOffset,unsigned(a.InputSlotClass));}
   std::fprintf(log,"]}\n");std::fflush(log);
  }
 }
 return result;
}
template<std::size_t... N> auto ResourceCallbacks(std::index_sequence<N...>){return std::array<CreateResource,sizeof...(N)>{&ResourceHook<N>...};}
template<std::size_t... N> auto ListCallbacks(std::index_sequence<N...>){return std::array<CreateList,sizeof...(N)>{&ListHook<N>...};}
template<std::size_t... N> auto List1Callbacks(std::index_sequence<N...>){return std::array<CreateList1,sizeof...(N)>{&List1Hook<N>...};}
template<std::size_t... N> auto SignatureCallbacks(std::index_sequence<N...>){return std::array<CreateSignature,sizeof...(N)>{&SignatureHook<N>...};}
template<std::size_t... N> auto QueueCallbacks(std::index_sequence<N...>){return std::array<CreateQueue,sizeof...(N)>{&QueueHook<N>...};}
template<std::size_t... N> auto PSOCallbacks(std::index_sequence<N...>){return std::array<CreatePSO,sizeof...(N)>{&PSOHook<N>...};}
void ObserveDevice(HRESULT result,void** output){
 if(SUCCEEDED(result)&&output&&*output){
  ID3D12Device* device=nullptr;auto* unknown=static_cast<IUnknown*>(*output);
  if(SUCCEEDED(unknown->lpVtbl->QueryInterface(unknown,IID_ID3D12Device,reinterpret_cast<void**>(&device)))){
   flags.fetch_or(2);
   {std::lock_guard<std::mutex> logLock(logMutex);if(log){std::fprintf(log,"{\"event\":\"deviceObserved\"}\n");std::fflush(log);}}
   std::lock_guard<std::mutex> lock(hookMutex);
   if(!HookMethod(resourceCreateHooks,device->lpVtbl->CreateCommittedResource,ResourceCallbacks(std::make_index_sequence<16>{})))flags.fetch_or(0x8000);
   if(!HookMethod(listCreateHooks,device->lpVtbl->CreateCommandList,ListCallbacks(std::make_index_sequence<16>{})))flags.fetch_or(0x8000);
   if(!HookMethod(signatureCreateHooks,device->lpVtbl->CreateCommandSignature,SignatureCallbacks(std::make_index_sequence<16>{})))flags.fetch_or(0x8000);
   if(!HookMethod(queueCreateHooks,device->lpVtbl->CreateCommandQueue,QueueCallbacks(std::make_index_sequence<16>{})))flags.fetch_or(0x8000);
   if(!HookMethod(psoCreateHooks,device->lpVtbl->CreateGraphicsPipelineState,PSOCallbacks(std::make_index_sequence<16>{})))flags.fetch_or(0x8000);
   ID3D12Device4* device4=nullptr;
   if(SUCCEEDED(device->lpVtbl->QueryInterface(device,IID_ID3D12Device4,reinterpret_cast<void**>(&device4)))){
    if(!HookMethod(list1CreateHooks,device4->lpVtbl->CreateCommandList1,List1Callbacks(std::make_index_sequence<16>{})))flags.fetch_or(0x8000);
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
void ReleaseGraphicsProbeOwnedResources(){
 std::lock_guard<std::mutex> lock(metadataMutex);
 for(auto* resource:pinnedOwnedResources)resource->lpVtbl->Release(resource);
 pinnedOwnedResources.clear();ownedRanges.clear();bindings.clear();ownedDraws.clear();
}
#ifdef MALEMOD_GRAPHICS_PROBE_TESTING
unsigned TestOwnedDraw(void* list,std::uint32_t indices){
 std::size_t before;{std::lock_guard<std::mutex> lock(metadataMutex);before=ownedDraws.size();}
 ObserveOwnedDraw(static_cast<ID3D12GraphicsCommandList*>(list),indices,0,0);
 std::lock_guard<std::mutex> lock(metadataMutex);return unsigned(ownedDraws.size()-before);
}
#endif
}
