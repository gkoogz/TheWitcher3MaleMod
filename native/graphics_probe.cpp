// SDK graphics ownership observer plus the guarded native surface draw path.
// Historical observer-only modes do not enable the full runtime feed.
// A device observation alone is not proof of an owned mesh output path.
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
#include <fstream>
#include "graphics_probe.hpp"
#include "graphics_fingerprints.hpp"
#include "live_renderer.hpp"
#include "float_draw_renderer.hpp"

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
using ExecuteBundle=decltype(ID3D12GraphicsCommandListVtbl::ExecuteBundle);
using CreatePSO=decltype(ID3D12DeviceVtbl::CreateGraphicsPipelineState);
using CreateStreamPSO=decltype(ID3D12Device2Vtbl::CreatePipelineState);
using CreatePipelineLibrary=decltype(ID3D12Device1Vtbl::CreatePipelineLibrary);
using LoadGraphicsPipeline=decltype(ID3D12PipelineLibraryVtbl::LoadGraphicsPipeline);
using LoadStreamPipeline=decltype(ID3D12PipelineLibrary1Vtbl::LoadPipeline);
using ResetList=decltype(ID3D12GraphicsCommandListVtbl::Reset);
using SetIndices=decltype(ID3D12GraphicsCommandListVtbl::IASetIndexBuffer);
using SetPipeline=decltype(ID3D12GraphicsCommandListVtbl::SetPipelineState);
using Barriers=decltype(ID3D12GraphicsCommandListVtbl::ResourceBarrier);
using ComputeSignature=decltype(ID3D12GraphicsCommandListVtbl::SetComputeRootSignature);
using ComputeTable=decltype(ID3D12GraphicsCommandListVtbl::SetComputeRootDescriptorTable);
using ComputeConstant=decltype(ID3D12GraphicsCommandListVtbl::SetComputeRoot32BitConstant);
using ComputeConstants=decltype(ID3D12GraphicsCommandListVtbl::SetComputeRoot32BitConstants);
using ComputeCBV=decltype(ID3D12GraphicsCommandListVtbl::SetComputeRootConstantBufferView);
using ComputeSRV=decltype(ID3D12GraphicsCommandListVtbl::SetComputeRootShaderResourceView);
using ComputeUAV=decltype(ID3D12GraphicsCommandListVtbl::SetComputeRootUnorderedAccessView);
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
MethodHooks<CreateStreamPSO> streamPSOHooks;
MethodHooks<CreatePipelineLibrary> libraryCreateHooks;
MethodHooks<LoadGraphicsPipeline> libraryGraphicsHooks;
MethodHooks<LoadStreamPipeline> libraryStreamHooks;
MethodHooks<SetVertices> vertexHooks;
MethodHooks<CopyBuffer> copyHooks;
MethodHooks<DrawIndexed> indexedHooks;
MethodHooks<Draw> drawHooks;
MethodHooks<Indirect> indirectHooks;
MethodHooks<RootSRV> srvHooks;
MethodHooks<ExecuteLists> executeHooks;
MethodHooks<ExecuteBundle> bundleHooks;
MethodHooks<ResetList> resetHooks;
MethodHooks<SetIndices> indexHooks;
MethodHooks<SetPipeline> pipelineHooks;
MethodHooks<Barriers> barrierHooks;
MethodHooks<ComputeSignature> computeSignatureHooks;
MethodHooks<ComputeTable> computeTableHooks;
MethodHooks<ComputeConstant> computeConstantHooks;
MethodHooks<ComputeConstants> computeConstantsHooks;
MethodHooks<ComputeCBV> computeCBVHooks;
MethodHooks<ComputeSRV> computeSRVHooks;
MethodHooks<ComputeUAV> computeUAVHooks;
thread_local bool injectingSurface=false;



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
struct ComputeValue {unsigned kind=0;UINT64 address=0;std::map<UINT,UINT> constants;};
struct ListBindings {std::array<D3D12_VERTEX_BUFFER_VIEW,32> vertices{};D3D12_INDEX_BUFFER_VIEW indices{};std::map<UINT,UINT64> rootSRVs;ID3D12PipelineState* pipeline=nullptr;ID3D12RootSignature* computeSignature=nullptr;std::map<UINT,ComputeValue> computeValues;};
struct PipelineInfo {std::vector<unsigned char> shader;std::vector<std::string> semantics;std::vector<D3D12_INPUT_ELEMENT_DESC> layout;};
std::map<ID3D12PipelineState*,PipelineInfo> pipelines;
std::set<ID3D12PipelineState*> capturedPipelines;
std::filesystem::path logDirectory;
void RememberPipeline(ID3D12PipelineState* pipeline,D3D12_SHADER_BYTECODE vs,D3D12_INPUT_LAYOUT_DESC layout){
 if(!pipeline||!vs.pShaderBytecode||!vs.BytecodeLength||vs.BytecodeLength>1048576||!layout.pInputElementDescs||!layout.NumElements||layout.NumElements>32)return;
 // Retain the actual layout before classifying it. The pre-skin pass may
 // expose a different semantic/index or input slot from the stock SDK path.
 std::lock_guard<std::mutex> lock(metadataMutex);if(pipelines.size()>=16384&&!pipelines.count(pipeline))return;
 auto& p=pipelines[pipeline];p.shader.assign(static_cast<const unsigned char*>(vs.pShaderBytecode),static_cast<const unsigned char*>(vs.pShaderBytecode)+vs.BytecodeLength);p.layout.assign(layout.pInputElementDescs,layout.pInputElementDescs+layout.NumElements);p.semantics.clear();for(const auto& e:p.layout)p.semantics.push_back(e.SemanticName?e.SemanticName:"");
}
template<class T> struct alignas(void*) StreamObject {D3D12_PIPELINE_STATE_SUBOBJECT_TYPE type;T value;};
std::size_t StreamObjectSize(D3D12_PIPELINE_STATE_SUBOBJECT_TYPE type){
 switch(type){
 case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_ROOT_SIGNATURE:return sizeof(StreamObject<ID3D12RootSignature*>);
 case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_VS:case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_PS:case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_DS:case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_HS:case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_GS:case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_CS:case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_AS:case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_MS:return sizeof(StreamObject<D3D12_SHADER_BYTECODE>);
 case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_STREAM_OUTPUT:return sizeof(StreamObject<D3D12_STREAM_OUTPUT_DESC>);
 case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_BLEND:return sizeof(StreamObject<D3D12_BLEND_DESC>);
 case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_SAMPLE_MASK:case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_NODE_MASK:return sizeof(StreamObject<UINT>);
 case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_RASTERIZER:return sizeof(StreamObject<D3D12_RASTERIZER_DESC>);
 case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_DEPTH_STENCIL:return sizeof(StreamObject<D3D12_DEPTH_STENCIL_DESC>);
 case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_DEPTH_STENCIL1:return sizeof(StreamObject<D3D12_DEPTH_STENCIL_DESC1>);
 case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_DEPTH_STENCIL2:return sizeof(StreamObject<D3D12_DEPTH_STENCIL_DESC2>);
 case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_INPUT_LAYOUT:return sizeof(StreamObject<D3D12_INPUT_LAYOUT_DESC>);
 case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_IB_STRIP_CUT_VALUE:return sizeof(StreamObject<D3D12_INDEX_BUFFER_STRIP_CUT_VALUE>);
 case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_PRIMITIVE_TOPOLOGY:return sizeof(StreamObject<D3D12_PRIMITIVE_TOPOLOGY_TYPE>);
 case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_RENDER_TARGET_FORMATS:return sizeof(StreamObject<D3D12_RT_FORMAT_ARRAY>);
 case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_DEPTH_STENCIL_FORMAT:return sizeof(StreamObject<DXGI_FORMAT>);
 case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_SAMPLE_DESC:return sizeof(StreamObject<DXGI_SAMPLE_DESC>);
 case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_CACHED_PSO:return sizeof(StreamObject<D3D12_CACHED_PIPELINE_STATE>);
 case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_FLAGS:return sizeof(StreamObject<D3D12_PIPELINE_STATE_FLAGS>);
 case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_VIEW_INSTANCING:return sizeof(StreamObject<D3D12_VIEW_INSTANCING_DESC>);
 case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_RASTERIZER1:return sizeof(StreamObject<D3D12_RASTERIZER_DESC1>);
 case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_RASTERIZER2:return sizeof(StreamObject<D3D12_RASTERIZER_DESC2>);
 default:return 0;
 }
}
std::map<ID3D12GraphicsCommandList*,ListBindings> bindings;
std::set<std::tuple<UINT64,UINT64,UINT,UINT,INT>> ownedDraws;
std::set<std::tuple<unsigned,unsigned,unsigned,bool>> ownedTransitions;
void ObserveOwnedDraw(ID3D12GraphicsCommandList* list,UINT count,UINT first,INT base)noexcept{
 try{
  std::lock_guard<std::mutex> lock(metadataMutex);auto found=bindings.find(list);if(found==bindings.end())return;
  const auto& state=found->second;
  for(unsigned slot=0;slot<state.vertices.size();slot++){
   const auto& view=state.vertices[slot];if(!view.BufferLocation||!view.SizeInBytes)continue;
   std::vector<std::string> labels;
   for(const auto& range:ownedRanges)if(view.BufferLocation>=range.begin&&view.BufferLocation-range.begin<range.bytes)labels.push_back(range.label);
   if(labels.empty())continue;
   if(state.vertices[2].BufferLocation==state.vertices[0].BufferLocation+16&&state.vertices[2].StrideInBytes==24&&state.indices.Format==DXGI_FORMAT_R16_UINT&&state.indices.SizeInBytes==435936)
    LiveRenderOwnedStream(state.vertices[0].BufferLocation,state.vertices[0].SizeInBytes,state.vertices[0].StrideInBytes);
   // The diagnostic cap must never disable ownership updates. Stream-output
   // rings rotate after these first logged draws, including after loading.
   if(ownedDraws.size()>=128)continue;
   auto pipeline=pipelines.find(state.pipeline);
   if(pipeline!=pipelines.end()&&capturedPipelines.size()<32&&capturedPipelines.emplace(state.pipeline).second){
    const auto stem=std::string("owned-draw-")+std::to_string(GetCurrentProcessId())+"-"+std::to_string(capturedPipelines.size());
    std::ofstream shader(logDirectory/(stem+".vs"),std::ios::binary);shader.write(reinterpret_cast<const char*>(pipeline->second.shader.data()),pipeline->second.shader.size());
    std::lock_guard<std::mutex> logLock(logMutex);
    if(log){std::fprintf(log,"{\"event\":\"ownedDrawPipeline\",\"shader\":\"%s.vs\",\"elements\":[",stem.c_str());
     for(unsigned i=0;i<pipeline->second.layout.size();i++){const auto& e=pipeline->second.layout[i];std::fprintf(log,"%s{\"semantic\":\"%s\",\"semanticIndex\":%u,\"slot\":%u,\"format\":%u,\"offset\":%u,\"class\":%u}",i?",":"",pipeline->second.semantics[i].c_str(),e.SemanticIndex,e.InputSlot,unsigned(e.Format),e.AlignedByteOffset,unsigned(e.InputSlotClass));}
     std::fprintf(log,"]}\n");std::fflush(log);
    }
   }
   if(!ownedDraws.emplace(view.BufferLocation,state.indices.BufferLocation,count,first,base).second)continue;
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
 if(status!=MH_OK){std::lock_guard<std::mutex> lock(logMutex);static std::set<std::pair<void*,int>> failures;if(failures.size()<128&&failures.emplace(address,int(status)).second&&log){std::fprintf(log,"{\"event\":\"hookInstallFailed\",\"target\":\"%p\",\"status\":%d}\n",address,int(status));std::fflush(log);}return false;}
 if(MH_EnableHook(address)==MH_OK)return true;
 MH_RemoveHook(address);return false;
}
void OpenLog(){
 wchar_t path[32768]{};HMODULE module=nullptr;
 if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,reinterpret_cast<LPCWSTR>(&OpenLog),&module))return;
 if(!GetModuleFileNameW(module,path,32768))return;
 const auto ownedPath=std::filesystem::path(path).parent_path()/L"graphics-owned-fingerprints.bin";
 logDirectory=std::filesystem::path(path).parent_path();
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
 if(injectingSurface)return;
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
 if(!injectingSurface){
  ObserveOwnedDraw(list,indices,first,base);
  ListBindings snapshot;bool owned=false;
  {std::lock_guard<std::mutex> lock(metadataMutex);auto found=bindings.find(list);if(found!=bindings.end()){
   snapshot=found->second;
   const auto uv=snapshot.vertices[1].BufferLocation;
   owned=snapshot.indices.Format==DXGI_FORMAT_R16_UINT&&snapshot.indices.SizeInBytes==435936&&
    std::any_of(ownedRanges.begin(),ownedRanges.end(),[&](const auto& r){return uv>=r.begin&&uv-r.begin<r.bytes;});
  }}
  if(owned){
   injectingSurface=true;
   const bool replaced=FloatDraw(list,snapshot.pipeline,snapshot.vertices[0],snapshot.vertices[2],[&]{indexedHooks.originals[N](list,indices,instances,first,base,firstInstance);});
   injectingSurface=false;if(replaced){FirstCall(16,"indexedDrawObserved");return;}
  }
 }
 indexedHooks.originals[N](list,indices,instances,first,base,firstInstance);FirstCall(16,"indexedDrawObserved");
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
 try{std::lock_guard<std::mutex> lock(metadataMutex);if(index<64&&(bindings.size()<512||bindings.count(list))){auto& state=bindings[list];state.rootSRVs[index]=address;if(!injectingSurface&&state.computeSignature)state.computeValues[index]={4,address,{}};}}catch(...){flags.fetch_or(0x8000);}
}
template<std::size_t N> void STDMETHODCALLTYPE IndexHook(ID3D12GraphicsCommandList* list,const D3D12_INDEX_BUFFER_VIEW* view){
 indexHooks.originals[N](list,view);
 try{std::lock_guard<std::mutex> lock(metadataMutex);if(bindings.size()<512||bindings.count(list))bindings[list].indices=view?*view:D3D12_INDEX_BUFFER_VIEW{};}catch(...){flags.fetch_or(0x8000);}
}
template<std::size_t N> void STDMETHODCALLTYPE PipelineHook(ID3D12GraphicsCommandList* list,ID3D12PipelineState* pso){
 pipelineHooks.originals[N](list,pso);
 if(injectingSurface)return;
 try{std::lock_guard<std::mutex> lock(metadataMutex);if(bindings.size()<512||bindings.count(list))bindings[list].pipeline=pso;}catch(...){flags.fetch_or(0x8000);}
}
template<std::size_t... N> auto PipelineCallbacks(std::index_sequence<N...>){return std::array<SetPipeline,sizeof...(N)>{&PipelineHook<N>...};}
template<std::size_t... N> auto IndexCallbacks(std::index_sequence<N...>){return std::array<SetIndices,sizeof...(N)>{&IndexHook<N>...};}
template<std::size_t... N> auto VertexCallbacks(std::index_sequence<N...>){return std::array<SetVertices,sizeof...(N)>{&VerticesHook<N>...};}
template<std::size_t... N> auto CopyCallbacks(std::index_sequence<N...>){return std::array<CopyBuffer,sizeof...(N)>{&CopyHook<N>...};}
template<std::size_t... N> auto IndexedCallbacks(std::index_sequence<N...>){return std::array<DrawIndexed,sizeof...(N)>{&IndexedHook<N>...};}
template<std::size_t... N> auto DrawCallbacks(std::index_sequence<N...>){return std::array<Draw,sizeof...(N)>{&DrawHook<N>...};}
template<std::size_t... N> auto IndirectCallbacks(std::index_sequence<N...>){return std::array<Indirect,sizeof...(N)>{&IndirectHook<N>...};}
template<std::size_t... N> auto SRVCallbacks(std::index_sequence<N...>){return std::array<RootSRV,sizeof...(N)>{&SRVHook<N>...};}

void RestoreCompute(ID3D12GraphicsCommandList* list,const ListBindings& state){
 // REDengine records its skin transitions in dedicated command lists with
 // no previous PSO/root signature. Those are unspecified initial state, not
 // null objects that D3D12 allows us to bind. A later game dispatch must set
 // its own PSO/root; preserve every actual prior binding when one exists.
 if(state.pipeline)list->lpVtbl->SetPipelineState(list,state.pipeline);
 if(state.computeSignature)list->lpVtbl->SetComputeRootSignature(list,state.computeSignature);
 for(const auto& entry:state.computeValues){const auto& value=entry.second;switch(value.kind){
  case 1:list->lpVtbl->SetComputeRootDescriptorTable(list,entry.first,{value.address});break;
  case 2:for(auto item:value.constants)list->lpVtbl->SetComputeRoot32BitConstant(list,entry.first,item.second,item.first);break;
  case 3:list->lpVtbl->SetComputeRootConstantBufferView(list,entry.first,value.address);break;
  case 4:list->lpVtbl->SetComputeRootShaderResourceView(list,entry.first,value.address);break;
  case 5:list->lpVtbl->SetComputeRootUnorderedAccessView(list,entry.first,value.address);break;
 }}
}
template<std::size_t N> void STDMETHODCALLTYPE BarrierHook(ID3D12GraphicsCommandList* list,UINT count,const D3D12_RESOURCE_BARRIER* barriers){
 if(!injectingSurface&&barriers&&count<=512){
  ListBindings snapshot;const auto type=list->lpVtbl->GetType(list);const bool ready=type==D3D12_COMMAND_LIST_TYPE_DIRECT||type==D3D12_COMMAND_LIST_TYPE_COMPUTE;
  {std::lock_guard<std::mutex> lock(metadataMutex);auto found=bindings.find(list);if(found!=bindings.end())snapshot=found->second;}
  for(unsigned i=0;i<count;i++){const auto& barrier=barriers[i];std::uint64_t offset=0;
   if(barrier.Type!=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION)continue;
   if(LiveRenderMatchResource(barrier.Transition.pResource,offset)){
    {std::lock_guard<std::mutex> logLock(logMutex);
     if(ownedTransitions.size()<32&&ownedTransitions.emplace(unsigned(barrier.Transition.StateBefore),unsigned(barrier.Transition.StateAfter),unsigned(barrier.Flags),ready).second&&log){
      std::fprintf(log,"{\"event\":\"ownedOutputTransition\",\"before\":%u,\"after\":%u,\"flags\":%u,\"pipelineReady\":%s}\n",unsigned(barrier.Transition.StateBefore),unsigned(barrier.Transition.StateAfter),unsigned(barrier.Flags),ready?"true":"false");std::fflush(log);
     }}
    if(!ready||barrier.Flags!=D3D12_RESOURCE_BARRIER_FLAG_NONE||barrier.Transition.StateAfter==barrier.Transition.StateBefore)continue;
    const auto producer=barrier.Transition.StateBefore;
    const auto reads=D3D12_RESOURCE_STATE_VERTEX_AND_CONSTANT_BUFFER|D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE|D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE|D3D12_RESOURCE_STATE_COPY_SOURCE;
    if((producer!=D3D12_RESOURCE_STATE_UNORDERED_ACCESS&&producer!=D3D12_RESOURCE_STATE_STREAM_OUT&&producer!=D3D12_RESOURCE_STATE_COPY_DEST)||(barrier.Transition.StateAfter&reads)==0)continue;
    // This exact 24-byte resource is a packed morph output (ushort4 position,
    // byte4 indices/weights, packed normal/tangent), not a float skinned output.
    // Keep it intact. FloatDraw replaces the owned draw's input layout and
    // supplies unbounded float positions through the unchanged game shader.
   }
  }
 }
 barrierHooks.originals[N](list,count,barriers);
}
template<std::size_t... N> auto BarrierCallbacks(std::index_sequence<N...>){return std::array<Barriers,sizeof...(N)>{&BarrierHook<N>...};}
template<std::size_t N> void STDMETHODCALLTYPE ComputeSignatureHook(ID3D12GraphicsCommandList* list,ID3D12RootSignature* root){
 computeSignatureHooks.originals[N](list,root);if(injectingSurface)return;
 try{std::lock_guard<std::mutex> lock(metadataMutex);if(bindings.size()<512||bindings.count(list)){auto& s=bindings[list];if(s.computeSignature!=root)s.computeValues.clear();s.computeSignature=root;}}catch(...){flags.fetch_or(0x8000);}
}
template<std::size_t... N> auto ComputeSignatureCallbacks(std::index_sequence<N...>){return std::array<ComputeSignature,sizeof...(N)>{&ComputeSignatureHook<N>...};}
void RememberComputeAddress(ID3D12GraphicsCommandList* list,UINT index,unsigned kind,UINT64 address){if(injectingSurface||index>=64)return;try{std::lock_guard<std::mutex> lock(metadataMutex);if(bindings.size()<512||bindings.count(list))bindings[list].computeValues[index]={kind,address,{}};}catch(...){flags.fetch_or(0x8000);}}
template<std::size_t N> void STDMETHODCALLTYPE ComputeTableHook(ID3D12GraphicsCommandList* list,UINT index,D3D12_GPU_DESCRIPTOR_HANDLE handle){computeTableHooks.originals[N](list,index,handle);RememberComputeAddress(list,index,1,handle.ptr);}
template<std::size_t N> void STDMETHODCALLTYPE ComputeCBVHook(ID3D12GraphicsCommandList* list,UINT index,D3D12_GPU_VIRTUAL_ADDRESS address){computeCBVHooks.originals[N](list,index,address);RememberComputeAddress(list,index,3,address);}
template<std::size_t N> void STDMETHODCALLTYPE ComputeSRVHook(ID3D12GraphicsCommandList* list,UINT index,D3D12_GPU_VIRTUAL_ADDRESS address){computeSRVHooks.originals[N](list,index,address);RememberComputeAddress(list,index,4,address);}
template<std::size_t N> void STDMETHODCALLTYPE ComputeUAVHook(ID3D12GraphicsCommandList* list,UINT index,D3D12_GPU_VIRTUAL_ADDRESS address){computeUAVHooks.originals[N](list,index,address);RememberComputeAddress(list,index,5,address);}
void RememberComputeConstants(ID3D12GraphicsCommandList* list,UINT index,UINT count,const void* data,UINT offset){if(injectingSurface||index>=64||offset>64||count>64-offset||!data)return;try{std::lock_guard<std::mutex> lock(metadataMutex);if(bindings.size()<512||bindings.count(list)){auto& value=bindings[list].computeValues[index];if(value.kind!=2)value={2,0,{}};for(unsigned i=0;i<count;i++)value.constants[offset+i]=static_cast<const UINT*>(data)[i];}}catch(...){flags.fetch_or(0x8000);}}
template<std::size_t N> void STDMETHODCALLTYPE ComputeConstantHook(ID3D12GraphicsCommandList* list,UINT index,UINT value,UINT offset){computeConstantHooks.originals[N](list,index,value,offset);RememberComputeConstants(list,index,1,&value,offset);}
template<std::size_t N> void STDMETHODCALLTYPE ComputeConstantsHook(ID3D12GraphicsCommandList* list,UINT index,UINT count,const void* data,UINT offset){computeConstantsHooks.originals[N](list,index,count,data,offset);RememberComputeConstants(list,index,count,data,offset);}
template<std::size_t... N> auto ComputeTableCallbacks(std::index_sequence<N...>){return std::array<ComputeTable,sizeof...(N)>{&ComputeTableHook<N>...};}
template<std::size_t... N> auto ComputeCBVCallbacks(std::index_sequence<N...>){return std::array<ComputeCBV,sizeof...(N)>{&ComputeCBVHook<N>...};}
template<std::size_t... N> auto ComputeSRVCallbacks(std::index_sequence<N...>){return std::array<ComputeSRV,sizeof...(N)>{&ComputeSRVHook<N>...};}
template<std::size_t... N> auto ComputeUAVCallbacks(std::index_sequence<N...>){return std::array<ComputeUAV,sizeof...(N)>{&ComputeUAVHook<N>...};}
template<std::size_t... N> auto ComputeConstantCallbacks(std::index_sequence<N...>){return std::array<ComputeConstant,sizeof...(N)>{&ComputeConstantHook<N>...};}
template<std::size_t... N> auto ComputeConstantsCallbacks(std::index_sequence<N...>){return std::array<ComputeConstants,sizeof...(N)>{&ComputeConstantsHook<N>...};}
template<std::size_t N> void STDMETHODCALLTYPE ExecuteHook(ID3D12CommandQueue* queue,UINT count,ID3D12CommandList* const* lists){
 executeHooks.originals[N](queue,count,lists);FirstCall(256,"queueSubmissionObserved");
 LiveRenderSubmitted(queue,count,reinterpret_cast<void* const*>(lists));
 FloatDrawSubmitted(queue,count,reinterpret_cast<void* const*>(lists));
}
template<std::size_t... N> auto ExecuteCallbacks(std::index_sequence<N...>){return std::array<ExecuteLists,sizeof...(N)>{&ExecuteHook<N>...};}
template<std::size_t N> void STDMETHODCALLTYPE BundleHook(ID3D12GraphicsCommandList* list,ID3D12GraphicsCommandList* bundle){
 bundleHooks.originals[N](list,bundle);FloatDrawBundle(list,bundle);
}
template<std::size_t... N> auto BundleCallbacks(std::index_sequence<N...>){return std::array<ExecuteBundle,sizeof...(N)>{&BundleHook<N>...};}
template<class Function> bool HookMethod(MethodHooks<Function>& methods,Function target,const std::array<Function,16>& callbacks){
 auto* address=reinterpret_cast<void*>(target);
 for(std::size_t i=0;i<methods.count;i++)if(methods.targets[i]==address)return true;
 if(methods.count==methods.capacity)return false;
 auto i=methods.count;
 if(!Hook(address,reinterpret_cast<void*>(callbacks[i]),reinterpret_cast<void**>(&methods.originals[i])))return false;
 methods.targets[i]=address;methods.count++;return true;
}
bool HookComputeView(MethodHooks<ComputeCBV>& methods,ComputeCBV target,const std::array<ComputeCBV,16>& callbacks){
 // Drivers may share one root-descriptor setter implementation between CBV,
 // SRV and UAV. Its ABI and GPU root-address operation are identical. Keep
 // the first installed detour and restore through that same SDK entry point.
 for(const auto* group:{&computeCBVHooks,&computeSRVHooks,&computeUAVHooks,&srvHooks})
  for(std::size_t i=0;i<group->count;i++)if(group->targets[i]==reinterpret_cast<void*>(target))return true;
 for(std::size_t i=0;i<computeTableHooks.count;i++)if(computeTableHooks.targets[i]==reinterpret_cast<void*>(target))return true;
 return HookMethod(methods,target,callbacks);
}
void ObserveList(HRESULT result,D3D12_COMMAND_LIST_TYPE type,REFIID iid,void** output);
template<std::size_t N> HRESULT STDMETHODCALLTYPE ResetHook(ID3D12GraphicsCommandList* list,ID3D12CommandAllocator* allocator,ID3D12PipelineState* initial){
 auto result=resetHooks.originals[N](list,allocator,initial);
 if(SUCCEEDED(result))LiveRenderReset(list);
 if(SUCCEEDED(result))FloatDrawReset(list);
 if(SUCCEEDED(result)){flags.fetch_or(2048);{std::lock_guard<std::mutex> lock(metadataMutex);bindings.erase(list);if(initial)bindings[list].pipeline=initial;}void* output=list;ObserveList(result,list->lpVtbl->GetType(list),IID_ID3D12GraphicsCommandList,&output);}
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
   const bool graphics=type==D3D12_COMMAND_LIST_TYPE_DIRECT||type==D3D12_COMMAND_LIST_TYPE_BUNDLE;
   const bool compute=type==D3D12_COMMAND_LIST_TYPE_DIRECT||type==D3D12_COMMAND_LIST_TYPE_COMPUTE;
   const bool copy=compute||type==D3D12_COMMAND_LIST_TYPE_COPY;
   // Unsupported methods on copy/compute lists may share a single no-op
   // driver address. Hook only SDK-valid methods for that list type.
   if(graphics&&(!HookMethod(vertexHooks,list->lpVtbl->IASetVertexBuffers,VertexCallbacks(slots))||
      !HookMethod(indexedHooks,list->lpVtbl->DrawIndexedInstanced,IndexedCallbacks(slots))||
      !HookMethod(drawHooks,list->lpVtbl->DrawInstanced,DrawCallbacks(slots))||
      !HookComputeView(srvHooks,list->lpVtbl->SetGraphicsRootShaderResourceView,SRVCallbacks(slots))||
      !HookMethod(indexHooks,list->lpVtbl->IASetIndexBuffer,IndexCallbacks(slots))))flags.fetch_or(0x8000);
   if(!HookMethod(resetHooks,list->lpVtbl->Reset,ResetCallbacks(slots)))flags.fetch_or(0x8000);
   if(type==D3D12_COMMAND_LIST_TYPE_DIRECT&&!HookMethod(bundleHooks,list->lpVtbl->ExecuteBundle,BundleCallbacks(slots)))flags.fetch_or(0x8000);
   if(copy&&(!HookMethod(copyHooks,list->lpVtbl->CopyBufferRegion,CopyCallbacks(slots))||!HookMethod(barrierHooks,list->lpVtbl->ResourceBarrier,BarrierCallbacks(slots))))flags.fetch_or(0x8000);
   if(compute&&!HookMethod(indirectHooks,list->lpVtbl->ExecuteIndirect,IndirectCallbacks(slots)))flags.fetch_or(0x8000);
   if((graphics||compute)&&!HookMethod(pipelineHooks,list->lpVtbl->SetPipelineState,PipelineCallbacks(slots)))flags.fetch_or(0x8000);
   if((graphics||compute)&&(!HookMethod(computeSignatureHooks,list->lpVtbl->SetComputeRootSignature,ComputeSignatureCallbacks(slots))||
      !HookMethod(computeTableHooks,list->lpVtbl->SetComputeRootDescriptorTable,ComputeTableCallbacks(slots))||
      !HookMethod(computeConstantHooks,list->lpVtbl->SetComputeRoot32BitConstant,ComputeConstantCallbacks(slots))||
      !HookMethod(computeConstantsHooks,list->lpVtbl->SetComputeRoot32BitConstants,ComputeConstantsCallbacks(slots))||
      !HookComputeView(computeCBVHooks,list->lpVtbl->SetComputeRootConstantBufferView,ComputeCBVCallbacks(slots))||
      !HookComputeView(computeSRVHooks,list->lpVtbl->SetComputeRootShaderResourceView,ComputeSRVCallbacks(slots))||
      !HookComputeView(computeUAVHooks,list->lpVtbl->SetComputeRootUnorderedAccessView,ComputeUAVCallbacks(slots))))flags.fetch_or(0x8000);
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
 if(SUCCEEDED(result)&&desc&&output&&*output&&IsEqualGUID(iid,IID_ID3D12PipelineState))try{RememberPipeline(static_cast<ID3D12PipelineState*>(*output),desc->VS,desc->InputLayout);RegisterFloatDrawPipeline(*output,*desc);}catch(...){flags.fetch_or(0x8000);}
 if(SUCCEEDED(result)&&desc&&desc->InputLayout.NumElements<=32&&psoCount.fetch_add(1)<64){
  std::lock_guard<std::mutex> lock(logMutex);
  if(log){std::fprintf(log,"{\"event\":\"graphicsInputLayout\",\"elements\":[");
   for(UINT i=0;i<desc->InputLayout.NumElements;i++){const auto& a=desc->InputLayout.pInputElementDescs[i];if(i)std::fputc(',',log);std::fprintf(log,"{\"slot\":%u,\"format\":%u,\"offset\":%u,\"class\":%u}",a.InputSlot,unsigned(a.Format),a.AlignedByteOffset,unsigned(a.InputSlotClass));}
   std::fprintf(log,"]}\n");std::fflush(log);
  }
 }
 return result;
}
void RememberStream(HRESULT result,const D3D12_PIPELINE_STATE_STREAM_DESC* desc,REFIID iid,void** output){
 if(SUCCEEDED(result)&&desc&&output&&*output&&IsEqualGUID(iid,IID_ID3D12PipelineState)&&desc->pPipelineStateSubobjectStream&&desc->SizeInBytes<=16384){
  try{D3D12_SHADER_BYTECODE vs{};D3D12_INPUT_LAYOUT_DESC layout{};const auto* bytes=static_cast<const unsigned char*>(desc->pPipelineStateSubobjectStream);std::size_t at=0,layoutValue=SIZE_MAX,cacheValue=SIZE_MAX;
   while(at<desc->SizeInBytes){if(desc->SizeInBytes-at<sizeof(D3D12_PIPELINE_STATE_SUBOBJECT_TYPE))return;auto type=*reinterpret_cast<const D3D12_PIPELINE_STATE_SUBOBJECT_TYPE*>(bytes+at);auto size=StreamObjectSize(type);if(!size||size>desc->SizeInBytes-at)return;
    if(type==D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_VS)vs=reinterpret_cast<const StreamObject<D3D12_SHADER_BYTECODE>*>(bytes+at)->value;
    if(type==D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_INPUT_LAYOUT){layout=reinterpret_cast<const StreamObject<D3D12_INPUT_LAYOUT_DESC>*>(bytes+at)->value;layoutValue=at+offsetof(StreamObject<D3D12_INPUT_LAYOUT_DESC>,value);}
    if(type==D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_CACHED_PSO)cacheValue=at+offsetof(StreamObject<D3D12_CACHED_PIPELINE_STATE>,value);at+=size;
   }RememberPipeline(static_cast<ID3D12PipelineState*>(*output),vs,layout);RegisterFloatDrawStream(*output,*desc,layoutValue,cacheValue);
  }catch(...){flags.fetch_or(0x8000);}
 }
}
template<std::size_t N> HRESULT STDMETHODCALLTYPE StreamPSOHook(ID3D12Device2* device,const D3D12_PIPELINE_STATE_STREAM_DESC* desc,REFIID iid,void** output){
 auto result=streamPSOHooks.originals[N](device,desc,iid,output);RememberStream(result,desc,iid,output);return result;
}
template<std::size_t... N> auto StreamPSOCallbacks(std::index_sequence<N...>){return std::array<CreateStreamPSO,sizeof...(N)>{&StreamPSOHook<N>...};}
template<std::size_t N> HRESULT STDMETHODCALLTYPE LibraryGraphicsHook(ID3D12PipelineLibrary* library,LPCWSTR name,const D3D12_GRAPHICS_PIPELINE_STATE_DESC* desc,REFIID iid,void** output){auto result=libraryGraphicsHooks.originals[N](library,name,desc,iid,output);if(SUCCEEDED(result)&&desc&&output&&*output&&IsEqualGUID(iid,IID_ID3D12PipelineState))try{RememberPipeline(static_cast<ID3D12PipelineState*>(*output),desc->VS,desc->InputLayout);RegisterFloatDrawPipeline(*output,*desc);}catch(...){flags.fetch_or(0x8000);}return result;}
template<std::size_t N> HRESULT STDMETHODCALLTYPE LibraryStreamHook(ID3D12PipelineLibrary1* library,LPCWSTR name,const D3D12_PIPELINE_STATE_STREAM_DESC* desc,REFIID iid,void** output){auto result=libraryStreamHooks.originals[N](library,name,desc,iid,output);RememberStream(result,desc,iid,output);return result;}
template<std::size_t... N> auto LibraryGraphicsCallbacks(std::index_sequence<N...>){return std::array<LoadGraphicsPipeline,sizeof...(N)>{&LibraryGraphicsHook<N>...};}
template<std::size_t... N> auto LibraryStreamCallbacks(std::index_sequence<N...>){return std::array<LoadStreamPipeline,sizeof...(N)>{&LibraryStreamHook<N>...};}
template<std::size_t N> HRESULT STDMETHODCALLTYPE LibraryCreateHook(ID3D12Device1* device,const void* blob,SIZE_T bytes,REFIID iid,void** output){
 auto result=libraryCreateHooks.originals[N](device,blob,bytes,iid,output);if(SUCCEEDED(result)&&output&&*output){auto* unknown=static_cast<IUnknown*>(*output);ID3D12PipelineLibrary* library=nullptr;ID3D12PipelineLibrary1* derived=nullptr;
  std::lock_guard<std::mutex> lock(hookMutex);
  if(SUCCEEDED(unknown->lpVtbl->QueryInterface(unknown,IID_ID3D12PipelineLibrary,reinterpret_cast<void**>(&library)))){if(!HookMethod(libraryGraphicsHooks,library->lpVtbl->LoadGraphicsPipeline,LibraryGraphicsCallbacks(std::make_index_sequence<16>{})))flags.fetch_or(0x8000);library->lpVtbl->Release(library);}
  if(SUCCEEDED(unknown->lpVtbl->QueryInterface(unknown,IID_ID3D12PipelineLibrary1,reinterpret_cast<void**>(&derived)))){if(!HookMethod(libraryStreamHooks,derived->lpVtbl->LoadPipeline,LibraryStreamCallbacks(std::make_index_sequence<16>{})))flags.fetch_or(0x8000);derived->lpVtbl->Release(derived);}
 }return result;
}
template<std::size_t... N> auto LibraryCreateCallbacks(std::index_sequence<N...>){return std::array<CreatePipelineLibrary,sizeof...(N)>{&LibraryCreateHook<N>...};}
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
   ID3D12Device1* device1=nullptr;if(SUCCEEDED(device->lpVtbl->QueryInterface(device,IID_ID3D12Device1,reinterpret_cast<void**>(&device1)))){if(!HookMethod(libraryCreateHooks,device1->lpVtbl->CreatePipelineLibrary,LibraryCreateCallbacks(std::make_index_sequence<16>{})))flags.fetch_or(0x8000);device1->lpVtbl->Release(device1);}
   ID3D12Device2* device2=nullptr;if(SUCCEEDED(device->lpVtbl->QueryInterface(device,IID_ID3D12Device2,reinterpret_cast<void**>(&device2)))){if(!HookMethod(streamPSOHooks,device2->lpVtbl->CreatePipelineState,StreamPSOCallbacks(std::make_index_sequence<16>{})))flags.fetch_or(0x8000);device2->lpVtbl->Release(device2);}
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
