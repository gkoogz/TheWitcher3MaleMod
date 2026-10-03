#define NOMINMAX
#include "float_draw_renderer.hpp"
#include "float_vertex_pipeline.hpp"
#include "live_renderer.hpp"
#include <map>
#include <mutex>
#include <atomic>
#include <limits>
#include <algorithm>
#include <d3dcompiler.h>
namespace malemod::witcher {
namespace {
using Microsoft::WRL::ComPtr;
std::mutex mutex;
std::mutex errorMutex;std::string lastError;
thread_local bool creating=false;
struct Pipeline {ComPtr<ID3D12PipelineState> original,replacement;};
// Process-lifetime tables have no loader-lock COM teardown. Explicit game
// shutdown or the OS owns retirement of the native graphics device.
auto* pipelines=new std::map<void*,Pipeline>;
struct Upload {ComPtr<ID3D12Resource> resource,reference;std::shared_ptr<const RenderDelivery> input;};
struct MorphOutput {ComPtr<ID3D12Resource> resource,native;std::shared_ptr<Upload> input;};
struct MorphPipeline {ComPtr<ID3D12RootSignature> root;ComPtr<ID3D12PipelineState> pipeline;ComPtr<ID3D12Resource> unorm,reference;std::shared_ptr<const std::vector<RenderDelivery::MorphReference>> referenceSource;};
auto* morphPipelines=new std::map<void*,MorphPipeline>;
struct Mark {ComPtr<ID3D12Fence> fence;UINT64 value;bool Done()const{auto v=fence->GetCompletedValue();if(v==UINT64_MAX)throw std::runtime_error("Float draw device removed");return v>=value;}};
struct Recording {std::vector<std::shared_ptr<Upload>> uploads;std::map<std::pair<UINT64,unsigned>,std::shared_ptr<MorphOutput>> morph;std::map<void*,Mark> marks;unsigned epoch=0,resourceMask=0;std::uint64_t sequence=0;};
struct Queue {ComPtr<ID3D12Fence> fence;UINT64 next=0;};
auto* recordings=new std::map<void*,Recording>;
auto* retired=new std::vector<Recording>;
auto* queues=new std::map<void*,Queue>;
auto* latest=new std::shared_ptr<Upload>;
auto* completedDelivery=new std::shared_ptr<const RenderDelivery>;
auto* frameDelivery=new std::shared_ptr<const RenderDelivery>;
std::atomic<unsigned> flags{0},epoch{0},sequence{0};
std::atomic<unsigned> resourceMask{0},publicationCount{0};
std::uint64_t countedSerial=0;
void HR(HRESULT h){if(FAILED(h))throw std::runtime_error("Float draw HRESULT "+std::to_string(h));}
ComPtr<ID3D12Resource> MorphBuffer(ID3D12Device* device,UINT64 bytes,D3D12_HEAP_TYPE type,D3D12_RESOURCE_STATES state,const void* data=nullptr){
 D3D12_HEAP_PROPERTIES heap{};heap.Type=type;D3D12_RESOURCE_DESC desc{};desc.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER;desc.Width=bytes;desc.Height=1;desc.DepthOrArraySize=1;desc.MipLevels=1;desc.SampleDesc.Count=1;desc.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR;if(type==D3D12_HEAP_TYPE_DEFAULT)desc.Flags=D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS;
 ComPtr<ID3D12Resource> result;HR(device->CreateCommittedResource(&heap,D3D12_HEAP_FLAG_NONE,&desc,state,nullptr,IID_PPV_ARGS(&result)));if(data){void* p=nullptr;D3D12_RANGE none{0,0};HR(result->Map(0,&none,&p));std::memcpy(p,data,std::size_t(bytes));D3D12_RANGE written{0,std::size_t(bytes)};result->Unmap(0,&written);}return result;
}
void MorphBarrier(ID3D12GraphicsCommandList* list,ID3D12Resource* resource,D3D12_RESOURCE_STATES before,D3D12_RESOURCE_STATES after){D3D12_RESOURCE_BARRIER b{};b.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;b.Transition={resource,D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,before,after};list->ResourceBarrier(1,&b);}
MorphPipeline& NativeMorphPipeline(ID3D12Device* device){
 auto found=morphPipelines->find(device);if(found!=morphPipelines->end())return found->second;
 MorphPipeline value;D3D12_ROOT_PARAMETER p[6]{};for(unsigned i=0;i<4;i++){p[i].ParameterType=D3D12_ROOT_PARAMETER_TYPE_SRV;p[i].Descriptor.ShaderRegister=i;}p[4].ParameterType=D3D12_ROOT_PARAMETER_TYPE_UAV;p[5].ParameterType=D3D12_ROOT_PARAMETER_TYPE_32BIT_CONSTANTS;p[5].Constants={0,0,2};D3D12_ROOT_SIGNATURE_DESC desc{6,p,0,nullptr,D3D12_ROOT_SIGNATURE_FLAG_NONE};ComPtr<ID3DBlob> blob,error;HR(D3D12SerializeRootSignature(&desc,D3D_ROOT_SIGNATURE_VERSION_1,&blob,&error));HR(device->CreateRootSignature(0,blob->GetBufferPointer(),blob->GetBufferSize(),IID_PPV_ARGS(&value.root)));
 const char* shader=R"(
ByteAddressBuffer authored:register(t0),reference:register(t1),native:register(t2),unormTable:register(t3);
RWByteAddressBuffer output:register(u0);
cbuffer Constants:register(b0){uint count;uint base;};
[numthreads(64,1,1)]void main(uint3 tid:SV_DispatchThreadID){uint i=tid.x;if(i>=count)return;uint a=(base+i)*28,r=(base+i)*24,n=i*24,d=i*28;uint2 words=native.Load2(n);uint3 cell=uint3(words.x&65535,words.x>>16,words.y&65535);
 float3 original=float3(asfloat(unormTable.Load(cell.x*4)),asfloat(unormTable.Load(cell.y*4)),asfloat(unormTable.Load(cell.z*4)));
 precise float3 delta=asfloat(authored.Load3(a))-asfloat(reference.Load3(r));
 uint boundary=reference.Load(r+20);output.Store3(d,asuint(boundary?asfloat(authored.Load3(a)):original+delta));output.Store2(d+12,authored.Load2(a+12));
 uint normal=authored.Load(a+20),tangent=authored.Load(a+24),rn=reference.Load(r+12),rt=reference.Load(r+16);
 uint light=count*28+i*8;
 output.Store(light,boundary?normal:(normal==rn?native.Load(n+16):(normal&0x3fffffff)|(native.Load(n+16)&0xc0000000)));
 output.Store(light+4,boundary?tangent:(tangent==rt?native.Load(n+20):tangent));
})";
 auto compiled=D3DCompile(shader,std::strlen(shader),"MaleMod-native-morph-baseline",nullptr,nullptr,"main","cs_5_1",D3DCOMPILE_ENABLE_STRICTNESS,0,&blob,&error);if(FAILED(compiled)&&error)throw std::runtime_error(std::string("Native morph shader: ")+static_cast<const char*>(error->GetBufferPointer()));HR(compiled);D3D12_COMPUTE_PIPELINE_STATE_DESC ps{};ps.pRootSignature=value.root.Get();ps.CS={blob->GetBufferPointer(),blob->GetBufferSize()};HR(device->CreateComputePipelineState(&ps,IID_PPV_ARGS(&value.pipeline)));
 // Exact IA UNORM values, independently checked for all 65,536 cells on
 // WARP and the installed AMD GPU. A shader reciprocal is not the IA oracle.
 std::vector<float> table(65536);for(unsigned i=0;i<table.size();i++)table[i]=float(i)/65535.f;value.unorm=MorphBuffer(device,table.size()*4,D3D12_HEAP_TYPE_UPLOAD,D3D12_RESOURCE_STATE_GENERIC_READ,table.data());return morphPipelines->emplace(device,std::move(value)).first->second;
}
bool Eligible(const D3D12_INPUT_LAYOUT_DESC& desc){
 try{FloatSkinLayout layout(desc);return layout.Slot()==0;}catch(const std::invalid_argument&){return false;}
}
void Complete(const Recording& r){
 const auto current=LiveRenderLatest();if(!current||current->epoch!=r.epoch)return;
 if(epoch.exchange(r.epoch)!=r.epoch){sequence=0;resourceMask=0;}
 resourceMask.fetch_or(r.resourceMask);
 auto old=sequence.load();const auto completed=unsigned(r.sequence);
 while(old<completed&&!sequence.compare_exchange_weak(old,completed)){}
 if(!r.uploads.empty()){
  const auto delivered=r.uploads.back()->input;auto previous=std::atomic_load(completedDelivery);
  if(delivered->presentationSerial>countedSerial){countedSerial=delivered->presentationSerial;publicationCount.fetch_add(1);}
  if(!previous||previous->epoch!=r.epoch||previous->sequence<=delivered->sequence)std::atomic_store(completedDelivery,delivered);
 }
 flags.fetch_or(256);
}
void Collect(){
 for(auto i=retired->begin();i!=retired->end();){bool done=!i->marks.empty();for(const auto& mark:i->marks)done&=mark.second.Done();if(done){Complete(*i);i=retired->erase(i);}else ++i;}
 for(const auto& entry:*recordings){bool done=!entry.second.marks.empty();for(const auto& mark:entry.second.marks)done&=mark.second.Done();if(done)Complete(entry.second);}
}
}
void RegisterFloatDrawPipeline(void* original,const D3D12_GRAPHICS_PIPELINE_STATE_DESC& desc){
 if(creating||!original||!Eligible(desc.InputLayout))return;
 try{
  auto* native=static_cast<ID3D12PipelineState*>(original);ComPtr<ID3D12Device> device;HR(native->GetDevice(IID_PPV_ARGS(&device)));
  FloatSkinLayout layout(desc.InputLayout);creating=true;auto replacement=layout.Create(device.Get(),desc);creating=false;
  std::lock_guard<std::mutex> lock(mutex);if(pipelines->size()<16384)(*pipelines)[original]={native,std::move(replacement)};
  flags.fetch_or(1);
 }catch(...){creating=false;flags.fetch_or(2);}
}
void RegisterFloatDrawStream(void* original,const D3D12_PIPELINE_STATE_STREAM_DESC& desc,std::size_t layoutValue,std::size_t cacheValue){
 if(creating||!original||layoutValue==SIZE_MAX||layoutValue+sizeof(D3D12_INPUT_LAYOUT_DESC)>desc.SizeInBytes)return;
 const auto* bytes=static_cast<const unsigned char*>(desc.pPipelineStateSubobjectStream);
 const auto& originalLayout=*reinterpret_cast<const D3D12_INPUT_LAYOUT_DESC*>(bytes+layoutValue);
 if(!Eligible(originalLayout))return;
 try{
  auto* native=static_cast<ID3D12PipelineState*>(original);ComPtr<ID3D12Device2> device;HR(native->GetDevice(IID_PPV_ARGS(&device)));
  FloatSkinLayout layout(originalLayout);std::vector<unsigned char> copy(bytes,bytes+desc.SizeInBytes);
  *reinterpret_cast<D3D12_INPUT_LAYOUT_DESC*>(copy.data()+layoutValue)=layout.View();
  if(cacheValue!=SIZE_MAX){if(cacheValue+sizeof(D3D12_CACHED_PIPELINE_STATE)>copy.size())throw std::invalid_argument("Invalid pipeline cache offset");*reinterpret_cast<D3D12_CACHED_PIPELINE_STATE*>(copy.data()+cacheValue)={};}
  D3D12_PIPELINE_STATE_STREAM_DESC modified{copy.size(),copy.data()};ComPtr<ID3D12PipelineState> replacement;
  creating=true;const auto result=device->CreatePipelineState(&modified,IID_PPV_ARGS(&replacement));creating=false;HR(result);
  std::lock_guard<std::mutex> lock(mutex);if(pipelines->size()<16384)(*pipelines)[original]={native,std::move(replacement)};
  flags.fetch_or(1);
 }catch(...){creating=false;flags.fetch_or(2);}
}
unsigned StaticFloatDrawLOD(const RenderResource& r,std::uint64_t offset){
 for(unsigned lod=0;lod<2;lod++){const std::uint64_t bytes=std::uint64_t(r.lodVertexCount[lod])*16;if(bytes&&r.lodUVOffset[lod]>=bytes&&offset==r.lodUVOffset[lod]-bytes)return lod;}return 2;
}
bool FloatDraw(void* pointer,void* original,const D3D12_VERTEX_BUFFER_VIEW& position,const D3D12_VERTEX_BUFFER_VIEW& lighting,const std::function<void()>& draw,unsigned resource,unsigned lod,void* nativeResource,unsigned nativeState,const std::function<void()>& restoreCompute){
 auto input=LiveRenderLatest();if(!input||resource>=input->resources.size())return false;const auto& r=input->resources[resource];
 if(r.firstVertex+r.vertexCount>input->floatVertices.size())return false;
 const bool morph=position.StrideInBytes==24&&position.SizeInBytes==r.vertexCount*24&&(!lighting.BufferLocation||(lighting.BufferLocation==position.BufferLocation+16&&lighting.StrideInBytes==24));
 const unsigned firstVertex=lod<2?r.lodFirstVertex[lod]:0;
 const unsigned vertexCount=lod<2?r.lodVertexCount[lod]:r.vertexCount;
 // Static skin streams point into the original combined native allocation;
 // their views include the remaining streams, not just the position rows.
 const bool stock=lod<2&&vertexCount&&position.StrideInBytes==16&&position.SizeInBytes>=vertexCount*16&&(!lighting.BufferLocation||(lighting.StrideInBytes==8&&lighting.SizeInBytes>=vertexCount*8));
 if(!morph&&!stock)return false;
 auto* list=static_cast<ID3D12GraphicsCommandList*>(pointer);
 bool bound=false,computeTouched=false;
 try{
  std::unique_lock<std::mutex> lock(mutex);auto p=pipelines->find(original);if(p==pipelines->end()||flags.load()&128)return false;
  if(list->GetType()!=D3D12_COMMAND_LIST_TYPE_DIRECT&&list->GetType()!=D3D12_COMMAND_LIST_TYPE_BUNDLE)return false;
  Collect();if(retired->size()>64)throw std::runtime_error("Float upload retirement backlog");
  // The SDK component tick selects one published surface for command lists.
  // Each list retains that immutable selection while it is recorded; the next
  // SDK tick can select new output without freezing the character surface.
  if(*frameDelivery&&(*frameDelivery)->epoch==input->epoch)input=*frameDelivery;
  // A command list uses one immutable whole-body snapshot for all its draws.
  auto previousRecording=recordings->find(pointer);
  if(previousRecording!=recordings->end()&&!previousRecording->second.uploads.empty()&&previousRecording->second.epoch==input->epoch)input=previousRecording->second.uploads.back()->input;
  if(!*latest||(*latest)->input!=input){
   auto next=std::make_shared<Upload>();next->input=input;ComPtr<ID3D12Device> device;HR(list->GetDevice(IID_PPV_ARGS(&device)));
   D3D12_HEAP_PROPERTIES heap{};heap.Type=D3D12_HEAP_TYPE_UPLOAD;D3D12_RESOURCE_DESC desc{};desc.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER;desc.Width=input->floatVertices.size()*36;desc.Height=1;desc.DepthOrArraySize=1;desc.MipLevels=1;desc.SampleDesc.Count=1;desc.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
   HR(device->CreateCommittedResource(&heap,D3D12_HEAP_FLAG_NONE,&desc,D3D12_RESOURCE_STATE_GENERIC_READ,nullptr,IID_PPV_ARGS(&next->resource)));
   void* data=nullptr;D3D12_RANGE none{0,0};HR(next->resource->Map(0,&none,&data));const auto packedBytes=input->floatVertices.size()*28;std::memcpy(data,input->floatVertices.data(),packedBytes);auto* light=static_cast<unsigned char*>(data)+packedBytes;for(const auto& row:input->floatVertices){std::memcpy(light,&row.normal,8);light+=8;}D3D12_RANGE written{0,std::size_t(desc.Width)};next->resource->Unmap(0,&written);if(input->morphReference){if(input->morphReference->size()!=input->floatVertices.size())throw std::runtime_error("Native morph reference count differs");auto& composer=NativeMorphPipeline(device.Get());if(composer.referenceSource!=input->morphReference){composer.reference=MorphBuffer(device.Get(),input->morphReference->size()*24,D3D12_HEAP_TYPE_UPLOAD,D3D12_RESOURCE_STATE_GENERIC_READ,input->morphReference->data());composer.referenceSource=input->morphReference;}next->reference=composer.reference;}*latest=std::move(next);
  }
  auto& recording=(*recordings)[pointer];if(recording.uploads.size()>128)throw std::runtime_error("Float draw recording backlog");
  if(recording.uploads.empty()||recording.uploads.back()!=*latest)recording.uploads.push_back(*latest);
  recording.epoch=input->epoch;recording.sequence=input->sequence;recording.resourceMask|=1u<<resource;
  auto replacement=p->second.replacement;auto retained=*latest;const auto vertexOffset=std::uint64_t(r.firstVertex+(morph?0:firstVertex));UINT64 address=retained->resource->GetGPUVirtualAddress()+vertexOffset*28,lightingAddress=retained->resource->GetGPUVirtualAddress()+input->floatVertices.size()*28+vertexOffset*8;const unsigned count=morph?r.vertexCount:vertexCount;
  if(morph&&input->morphReference){
   if(!nativeResource||!restoreCompute)throw std::runtime_error("Native morph source state is unavailable");auto* source=static_cast<ID3D12Resource*>(nativeResource);const auto sourceAddress=source->GetGPUVirtualAddress();const auto sourceDesc=source->GetDesc();if(sourceDesc.Dimension!=D3D12_RESOURCE_DIMENSION_BUFFER||position.BufferLocation<sourceAddress||position.BufferLocation-sourceAddress>sourceDesc.Width||position.SizeInBytes>sourceDesc.Width-(position.BufferLocation-sourceAddress))throw std::runtime_error("Native morph source leaves observed resource");
   auto key=std::make_pair(position.BufferLocation,resource);auto previous=recording.morph.find(key);if(previous==recording.morph.end()){
    auto composed=std::make_shared<MorphOutput>();composed->native=source;composed->input=retained;ComPtr<ID3D12Device> device;HR(list->GetDevice(IID_PPV_ARGS(&device)));auto& composer=NativeMorphPipeline(device.Get());composed->resource=MorphBuffer(device.Get(),UINT64(count)*36,D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
    const auto before=D3D12_RESOURCE_STATES(nativeState);const bool transition=before!=D3D12_RESOURCE_STATE_COMMON&&!(before&D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);if(transition)MorphBarrier(list,source,before,D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);
    computeTouched=true;list->SetPipelineState(composer.pipeline.Get());list->SetComputeRootSignature(composer.root.Get());list->SetComputeRootShaderResourceView(0,retained->resource->GetGPUVirtualAddress());list->SetComputeRootShaderResourceView(1,retained->reference->GetGPUVirtualAddress());list->SetComputeRootShaderResourceView(2,position.BufferLocation);list->SetComputeRootShaderResourceView(3,composer.unorm->GetGPUVirtualAddress());list->SetComputeRootUnorderedAccessView(4,composed->resource->GetGPUVirtualAddress());const unsigned constants[2]{count,r.firstVertex};list->SetComputeRoot32BitConstants(5,2,constants,0);list->Dispatch((count+63)/64,1,1);MorphBarrier(list,composed->resource.Get(),D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_STATE_VERTEX_AND_CONSTANT_BUFFER);if(transition)MorphBarrier(list,source,D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE,before);restoreCompute();computeTouched=false;previous=recording.morph.emplace(key,std::move(composed)).first;
   }address=previous->second->resource->GetGPUVirtualAddress();lightingAddress=address+UINT64(count)*28;
  }
  // Match the engine's complete 8-byte lighting records. An interleaved view
  // beginning 20 bytes into a 28-byte row had only count-1 full IA records;
  // the final torso UV alias belongs to the two rear faces reported black.
  lock.unlock();D3D12_VERTEX_BUFFER_VIEW vertex{address,count*28,28},normal{lightingAddress,count*8,8};
  list->SetPipelineState(replacement.Get());list->IASetVertexBuffers(0,1,&vertex);list->IASetVertexBuffers(2,1,&normal);bound=true;
  draw();
  list->IASetVertexBuffers(0,1,&position);list->IASetVertexBuffers(2,1,&lighting);list->SetPipelineState(static_cast<ID3D12PipelineState*>(original));bound=false;
  flags.fetch_or(64|512|4|16);return true;
 }catch(...){
  try{throw;}catch(const std::exception& e){std::lock_guard<std::mutex> lock(errorMutex);lastError=e.what();}catch(...){std::lock_guard<std::mutex> lock(errorMutex);lastError="Unknown native morph draw failure";}
  if(computeTouched){try{if(restoreCompute)restoreCompute();}catch(...){}list->SetPipelineState(static_cast<ID3D12PipelineState*>(original));}
  if(bound){list->IASetVertexBuffers(0,1,&position);list->IASetVertexBuffers(2,1,&lighting);list->SetPipelineState(static_cast<ID3D12PipelineState*>(original));}
  flags.fetch_or(128);return false;
 }
}
void FloatDrawFrameBoundary(){try{
 auto input=LiveRenderLatest();std::lock_guard<std::mutex> lock(mutex);*frameDelivery=std::move(input);
 }catch(...){flags.fetch_or(128);}}
void FloatDrawSubmitted(void* pointer,unsigned count,void* const* lists){
 try{
  std::lock_guard<std::mutex> lock(mutex);Collect();bool used=false;for(unsigned i=0;i<count;i++)used|=recordings->count(lists[i])!=0;if(!used)return;
  auto* queue=static_cast<ID3D12CommandQueue*>(pointer);auto& q=(*queues)[pointer];
  if(!q.fence){ComPtr<ID3D12Device> device;HR(queue->GetDevice(IID_PPV_ARGS(&device)));HR(device->CreateFence(0,D3D12_FENCE_FLAG_NONE,IID_PPV_ARGS(&q.fence)));}
  const auto value=++q.next;HR(queue->Signal(q.fence.Get(),value));
  for(unsigned i=0;i<count;i++){auto r=recordings->find(lists[i]);if(r!=recordings->end())r->second.marks[pointer]={q.fence,value};}
 }catch(...){flags.fetch_or(128);}
}
void FloatDrawReset(void* pointer){try{
 std::lock_guard<std::mutex> lock(mutex);auto r=recordings->find(pointer);if(r!=recordings->end()){if(!r->second.marks.empty())retired->push_back(std::move(r->second));recordings->erase(r);}Collect();
}catch(...){flags.fetch_or(128);}}
void FloatDrawBundle(void* parent,void* bundle){try{
 std::lock_guard<std::mutex> lock(mutex);auto found=recordings->find(bundle);if(found==recordings->end())return;
 auto& destination=(*recordings)[parent];destination.uploads.insert(destination.uploads.end(),found->second.uploads.begin(),found->second.uploads.end());
 destination.epoch=found->second.epoch;destination.sequence=found->second.sequence;
 destination.resourceMask|=found->second.resourceMask;
}catch(...){flags.fetch_or(128);}}
unsigned FloatDrawFlags(){try{std::unique_lock<std::mutex> lock(mutex,std::try_to_lock);if(lock.owns_lock())Collect();}catch(...){flags.fetch_or(128);}return flags.load();}
std::string FloatDrawError(){std::lock_guard<std::mutex> lock(errorMutex);return lastError;}
unsigned FloatDrawSequence(){FloatDrawFlags();return sequence.load();}
unsigned FloatDrawResourceMask(){FloatDrawFlags();return resourceMask.load();}
unsigned FloatDrawPublicationCount(){FloatDrawFlags();return publicationCount.load();}
bool FloatDrawActive(unsigned character){const auto current=LiveRenderLatest();FloatDrawFlags();return character&&current&&current->epoch==character&&epoch.load()==character&&!(flags.load()&128);}
std::shared_ptr<const RenderDelivery> FloatDrawCompleted(){FloatDrawFlags();return std::atomic_load(completedDelivery);}
}
