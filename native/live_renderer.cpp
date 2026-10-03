#define NOMINMAX
#include "live_renderer.hpp"
#include <d3d12.h>
#include <d3dcompiler.h>
#include <wrl/client.h>
#include <map>
#include <mutex>
#include <set>

namespace malemod::witcher {
namespace {
using Microsoft::WRL::ComPtr;
void HR(HRESULT h){if(FAILED(h))throw std::runtime_error("Native surface GPU operation failed: "+std::to_string(h));}
struct Buffer {
 ComPtr<ID3D12Resource> resource;
 Buffer(ID3D12Device* device,std::size_t size,D3D12_HEAP_TYPE heap,D3D12_RESOURCE_STATES state,const void* bytes=nullptr){
  D3D12_HEAP_PROPERTIES hp{};hp.Type=heap;D3D12_RESOURCE_DESC d{};d.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER;d.Width=size;d.Height=1;d.DepthOrArraySize=1;d.MipLevels=1;d.SampleDesc.Count=1;d.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
  if(heap==D3D12_HEAP_TYPE_DEFAULT)d.Flags=D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS;
  HR(device->CreateCommittedResource(&hp,D3D12_HEAP_FLAG_NONE,&d,state,nullptr,IID_PPV_ARGS(&resource)));
  if(bytes){void* p=nullptr;D3D12_RANGE none{0,0};HR(resource->Map(0,&none,&p));std::memcpy(p,bytes,size);D3D12_RANGE written{0,size};resource->Unmap(0,&written);}
 }
};
struct Mark {ComPtr<ID3D12Fence> fence;UINT64 value=0;bool Done()const{auto v=fence->GetCompletedValue();if(v==UINT64_MAX)throw std::runtime_error("GPU removed");return v>=value;}};
struct Recording {std::vector<std::shared_ptr<Buffer>> buffers;std::map<void*,Mark> marks;bool diagnostic=false,wrote=false;unsigned epoch=0;std::uint64_t sequence=0;};
struct Retired {Recording recording;};
struct QueueState {ComPtr<ID3D12Fence> fence;UINT64 next=0;};
struct State {
 ComPtr<ID3D12Device> device;ComPtr<ID3D12RootSignature> root;ComPtr<ID3D12PipelineState> pipeline;
 std::shared_ptr<Buffer> diagnostic,readback,geometry;std::shared_ptr<const std::vector<SourceRenderVertex>> source;
 std::map<void*,Recording> recordings;std::map<void*,QueueState> queues;std::vector<Retired> retired;
 std::optional<Mark> diagnosticMark;bool diagnosticRecorded=false;unsigned mode=0;
 std::uint64_t sequence=0;unsigned epoch=0;
 State(ID3D12Device* d):device(d){
  D3D12_ROOT_PARAMETER p[5]{};
  p[0].ParameterType=D3D12_ROOT_PARAMETER_TYPE_SRV;p[0].Descriptor.ShaderRegister=0;
  p[1].ParameterType=D3D12_ROOT_PARAMETER_TYPE_SRV;p[1].Descriptor.ShaderRegister=1;
  p[2].ParameterType=D3D12_ROOT_PARAMETER_TYPE_UAV;p[2].Descriptor.ShaderRegister=0;
  p[3].ParameterType=D3D12_ROOT_PARAMETER_TYPE_UAV;p[3].Descriptor.ShaderRegister=1;
  p[4].ParameterType=D3D12_ROOT_PARAMETER_TYPE_32BIT_CONSTANTS;p[4].Constants={0,0,3};
  D3D12_ROOT_SIGNATURE_DESC desc{5,p,0,nullptr,D3D12_ROOT_SIGNATURE_FLAG_NONE};ComPtr<ID3DBlob> blob,error;
  HR(D3D12SerializeRootSignature(&desc,D3D_ROOT_SIGNATURE_VERSION_1,&blob,&error));HR(device->CreateRootSignature(0,blob->GetBufferPointer(),blob->GetBufferSize(),IID_PPV_ARGS(&root)));
  const char* shader=R"(
ByteAddressBuffer vertices:register(t0); ByteAddressBuffer palette:register(t1);
RWByteAddressBuffer output:register(u0); RWByteAddressBuffer check:register(u1);
cbuffer Constants:register(b0){uint count;uint base;uint mode;};
float4 row(uint bone,uint r){return asfloat(palette.Load4(bone*64+r*16));}
float3 transform(uint bone,float3 p,float w){float4 q=float4(p,w);return float3(dot(row(bone,0),q),dot(row(bone,1),q),dot(row(bone,2),q));}
uint pack(float3 v){return uint(round(saturate(normalize(v)*.5+.5).x*1023))|(uint(round(saturate(normalize(v)*.5+.5).y*1023))<<10)|(uint(round(saturate(normalize(v)*.5+.5).z*1023))<<20);}
[numthreads(64,1,1)] void main(uint3 thread:SV_DispatchThreadID){
 uint i=thread.x;if(i>=count)return;uint at=i*64,indices=vertices.Load(at+12),weights=vertices.Load(at+16);
 uint4 bi=(indices>>uint4(0,8,16,24))&255;float4 bw=float4((weights>>uint4(0,8,16,24))&255)/255.;bw/=dot(bw,1.0.xxxx);
 float3 position=asfloat(vertices.Load3(at+(mode==0?48:0))),normal=asfloat(vertices.Load3(at+20)),tangent=asfloat(vertices.Load3(at+32));
 float3 p=0,n=0,t=0;
 [unroll]for(uint k=0;k<4;k++){p+=transform(bi[k],position,1)*bw[k];n+=transform(bi[k],normal,0)*bw[k];t+=transform(bi[k],tangent,0)*bw[k];}
 uint dest=base+i*24;
 if(mode==0){if(vertices.Load(at+60)==0)return;
  float3 actual=asfloat(output.Load3(dest));float3 world=transform(46,p,1);
  float localError=max(abs(actual.x-p.x),max(abs(actual.y-p.y),abs(actual.z-p.z)));
  float worldError=max(abs(actual.x-world.x),max(abs(actual.y-world.y),abs(actual.z-world.z)));
  if(!all(isfinite(actual))||!isfinite(localError)||!isfinite(worldError)){check.InterlockedAdd(12,1);return;}
  check.InterlockedMax(0,asuint(localError));check.InterlockedMax(4,asuint(worldError));check.InterlockedAdd(8,1);return;
 }
 if(mode==2){p=transform(46,p,1);n=transform(46,n,0);t=transform(46,t,0);}
 // Preserve the engine's fourth position component and normal metadata.
 output.Store3(dest,asuint(p));output.Store(dest+16,pack(n)|(output.Load(dest+16)&0xc0000000));
 output.Store(dest+20,pack(t)|(asfloat(vertices.Load(at+44))<0?0:0xc0000000));
})";
  HR(D3DCompile(shader,std::strlen(shader),"MaleMod-owned-skin-output",nullptr,nullptr,"main","cs_5_1",D3DCOMPILE_ENABLE_STRICTNESS,0,&blob,&error));
  D3D12_COMPUTE_PIPELINE_STATE_DESC pd{};pd.pRootSignature=root.Get();pd.CS={blob->GetBufferPointer(),blob->GetBufferSize()};HR(device->CreateComputePipelineState(&pd,IID_PPV_ARGS(&pipeline)));
  std::array<unsigned,4> zero{};diagnostic=std::make_shared<Buffer>(d,16,D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
  readback=std::make_shared<Buffer>(d,16,D3D12_HEAP_TYPE_READBACK,D3D12_RESOURCE_STATE_COPY_DEST);
 }
};
std::mutex mutex;std::unique_ptr<State> state;
std::set<std::uint64_t> ownedStreams;
std::shared_ptr<const RenderDelivery> feed;
std::atomic<unsigned> flags{0},activeEpoch{0};
std::atomic<unsigned> completedSequence{0};
void Barrier(ID3D12GraphicsCommandList* list,ID3D12Resource* resource,D3D12_RESOURCE_STATES a,D3D12_RESOURCE_STATES b){D3D12_RESOURCE_BARRIER t{};t.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;t.Transition={resource,D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,a,b};list->ResourceBarrier(1,&t);}
void PublishGPUCompletion(const Recording& recording){
 auto current=std::atomic_load(&feed);
 if(!recording.wrote||!current||current->epoch!=recording.epoch)return;
 if(activeEpoch.exchange(recording.epoch)!=recording.epoch)completedSequence.store(0);
 auto old=completedSequence.load();const auto sequence=unsigned(recording.sequence);
 while(old<sequence&&!completedSequence.compare_exchange_weak(old,sequence)){}
 flags.fetch_or(256);
}
void Collect(){
 if(!state)return;
 for(auto i=state->retired.begin();i!=state->retired.end();){bool done=!i->recording.marks.empty();for(const auto& mark:i->recording.marks)done&=mark.second.Done();if(done){PublishGPUCompletion(i->recording);i=state->retired.erase(i);}else ++i;}
 for(auto& entry:state->recordings)if(entry.second.wrote&&!entry.second.marks.empty()){bool done=true;for(const auto& m:entry.second.marks)done&=m.second.Done();if(done)PublishGPUCompletion(entry.second);}
 if(state->diagnosticMark&&state->diagnosticMark->Done()&&state->mode==0){
  std::array<unsigned,4> result{};void* data=nullptr;D3D12_RANGE range{0,16};HR(state->readback->resource->Map(0,&range,&data));std::memcpy(result.data(),data,16);D3D12_RANGE none{0,0};state->readback->resource->Unmap(0,&none);
  float local=0,world=0;std::memcpy(&local,&result[0],4);std::memcpy(&world,&result[1],4);
  flags.fetch_or(8);
  if(result[2]>=8&&!result[3]&&std::isfinite(local)&&std::isfinite(world)){
   if(local<.02f&&world>(std::max)(.2f,local*10)){state->mode=1;flags.fetch_or(16);}
   else if(world<.02f&&local>(std::max)(.2f,world*10)){state->mode=2;flags.fetch_or(32);}
  }
  if(!state->mode){flags.fetch_or(128);OutputDebugStringW(L"MaleMod: skin-output space validation failed; no geometry written\n");}
 }
}
}
void LiveRenderFeed(std::shared_ptr<const RenderDelivery> delivery){if(delivery)flags.fetch_or(512);std::atomic_store(&feed,std::move(delivery));}
std::shared_ptr<const RenderDelivery> LiveRenderLatest(){return std::atomic_load(&feed);}
void LiveRenderOwnedStream(std::uint64_t address,unsigned bytes,unsigned stride){if(stride!=24||bytes!=36547*24)return;std::lock_guard<std::mutex> lock(mutex);if(ownedStreams.size()<32||ownedStreams.count(address)){ownedStreams.insert(address);flags.fetch_or(4);}}
bool LiveRenderMatchResource(void* pointer,std::uint64_t& offset){
 if(!pointer)return false;auto* resource=static_cast<ID3D12Resource*>(pointer);auto desc=resource->GetDesc();if(desc.Dimension!=D3D12_RESOURCE_DIMENSION_BUFFER)return false;
 auto address=resource->GetGPUVirtualAddress();std::lock_guard<std::mutex> lock(mutex);
 for(auto owned:ownedStreams)if(owned>=address&&owned-address<=desc.Width&&36547*24<=desc.Width-(owned-address)){offset=owned-address;return true;}return false;
}
bool LiveRenderTransition(void* pointer,void* resourcePointer,std::uint64_t offset,const std::function<void()>& restore,unsigned before){
 try{
  auto delivery=std::atomic_load(&feed);if(!delivery||!delivery->vertices||delivery->vertices->size()!=36547||delivery->pose.skinDeltas.size()!=46)return false;
  auto* list=static_cast<ID3D12GraphicsCommandList*>(pointer);auto* resource=static_cast<ID3D12Resource*>(resourcePointer);
  if(list->GetType()!=D3D12_COMMAND_LIST_TYPE_DIRECT&&list->GetType()!=D3D12_COMMAND_LIST_TYPE_COMPUTE)return false;
  std::lock_guard<std::mutex> lock(mutex);ComPtr<ID3D12Device> device;HR(list->GetDevice(IID_PPV_ARGS(&device)));
  if(!state)state=std::make_unique<State>(device.Get());if(state->device.Get()!=device.Get())return false;
  Collect();if(flags.load()&128)return false;if(state->retired.size()>=64)throw std::runtime_error("Native output retirement backlog");
  if(!state->mode&&state->diagnosticRecorded)return false;
  if(!state->geometry||state->source!=delivery->vertices){state->geometry=std::make_shared<Buffer>(device.Get(),delivery->vertices->size()*sizeof(SourceRenderVertex),D3D12_HEAP_TYPE_UPLOAD,D3D12_RESOURCE_STATE_GENERIC_READ,delivery->vertices->data());state->source=delivery->vertices;}
  std::array<std::array<float,16>,47> matrices{};for(unsigned b=0;b<46;b++)for(unsigned a=0;a<16;a++)matrices[b][a]=float(delivery->pose.skinDeltas[b][a]);for(unsigned a=0;a<16;a++)matrices[46][a]=float(delivery->pose.actorWorld[a]);
  auto pose=std::make_shared<Buffer>(device.Get(),sizeof(matrices),D3D12_HEAP_TYPE_UPLOAD,D3D12_RESOURCE_STATE_GENERIC_READ,matrices.data());
  auto& recording=state->recordings[list];if(recording.buffers.size()>128)throw std::runtime_error("Native command recording backlog");recording.buffers.push_back(state->geometry);recording.buffers.push_back(pose);recording.epoch=delivery->epoch;recording.sequence=delivery->sequence;
  // REDengine also skins through stream output. That buffer need not support
  // UAVs. Copy the exact 24-byte rows to our private UAV, preserve all metadata,
  // evaluate there, then copy the completed rows back before the engine's read
  // transition. The native vertex shader, materials and buffer binding remain.
  auto output=std::make_shared<Buffer>(device.Get(),36547*24,D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_COPY_DEST);recording.buffers.push_back(output);
  const auto originalState=static_cast<D3D12_RESOURCE_STATES>(before);
  Barrier(list,resource,originalState,D3D12_RESOURCE_STATE_COPY_SOURCE);
  list->CopyBufferRegion(output->resource.Get(),0,resource,offset,36547*24);
  Barrier(list,resource,D3D12_RESOURCE_STATE_COPY_SOURCE,originalState);
  Barrier(list,output->resource.Get(),D3D12_RESOURCE_STATE_COPY_DEST,D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
  if(!state->mode){
   std::array<unsigned,4> zero{};auto clear=std::make_shared<Buffer>(device.Get(),16,D3D12_HEAP_TYPE_UPLOAD,D3D12_RESOURCE_STATE_GENERIC_READ,zero.data());recording.buffers.push_back(clear);
   Barrier(list,state->diagnostic->resource.Get(),D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_STATE_COPY_DEST);list->CopyBufferRegion(state->diagnostic->resource.Get(),0,clear->resource.Get(),0,16);Barrier(list,state->diagnostic->resource.Get(),D3D12_RESOURCE_STATE_COPY_DEST,D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
  }
  list->SetPipelineState(state->pipeline.Get());list->SetComputeRootSignature(state->root.Get());
  list->SetComputeRootShaderResourceView(0,state->geometry->resource->GetGPUVirtualAddress());list->SetComputeRootShaderResourceView(1,pose->resource->GetGPUVirtualAddress());
  list->SetComputeRootUnorderedAccessView(2,output->resource->GetGPUVirtualAddress());list->SetComputeRootUnorderedAccessView(3,state->diagnostic->resource->GetGPUVirtualAddress());
  std::array<unsigned,3> constants{36547,0,state->mode};list->SetComputeRoot32BitConstants(4,3,constants.data(),0);list->Dispatch((36547+63)/64,1,1);
  D3D12_RESOURCE_BARRIER uav{};uav.Type=D3D12_RESOURCE_BARRIER_TYPE_UAV;uav.UAV.pResource=output->resource.Get();list->ResourceBarrier(1,&uav);
  if(!state->mode){
   Barrier(list,state->diagnostic->resource.Get(),D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_STATE_COPY_SOURCE);list->CopyBufferRegion(state->readback->resource.Get(),0,state->diagnostic->resource.Get(),0,16);Barrier(list,state->diagnostic->resource.Get(),D3D12_RESOURCE_STATE_COPY_SOURCE,D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
   recording.diagnostic=true;state->diagnosticRecorded=true;
  }else{
   Barrier(list,output->resource.Get(),D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_STATE_COPY_SOURCE);
   Barrier(list,resource,originalState,D3D12_RESOURCE_STATE_COPY_DEST);
   list->CopyBufferRegion(resource,offset,output->resource.Get(),0,36547*24);
   Barrier(list,resource,D3D12_RESOURCE_STATE_COPY_DEST,originalState);
   recording.wrote=true;flags.fetch_or(64);
  }
  restore();flags.fetch_or(3);return true;
 }catch(const std::exception&){restore();flags.fetch_or(128);return false;}
}
void LiveRenderSubmitted(void* pointer,unsigned count,void* const* lists){
 try{std::lock_guard<std::mutex> lock(mutex);if(!state)return;Collect();bool used=false;for(unsigned i=0;i<count;i++)used|=state->recordings.count(lists[i])!=0;if(!used)return;
  auto* queue=static_cast<ID3D12CommandQueue*>(pointer);auto& q=state->queues[queue];if(!q.fence)HR(state->device->CreateFence(0,D3D12_FENCE_FLAG_NONE,IID_PPV_ARGS(&q.fence)));const auto value=++q.next;HR(queue->Signal(q.fence.Get(),value));
  for(unsigned i=0;i<count;i++){auto record=state->recordings.find(lists[i]);if(record==state->recordings.end())continue;record->second.marks[queue]={q.fence,value};if(record->second.diagnostic&&!state->diagnosticMark)state->diagnosticMark=Mark{q.fence,value};}
 }catch(const std::exception&){flags.fetch_or(128);}
}
void LiveRenderReset(void* pointer){try{std::lock_guard<std::mutex> lock(mutex);if(!state)return;auto found=state->recordings.find(pointer);if(found!=state->recordings.end()){if(!found->second.marks.empty())state->retired.push_back({std::move(found->second)});state->recordings.erase(found);}Collect();}catch(const std::exception&){flags.fetch_or(128);}}
unsigned LiveRenderFlags(){try{std::unique_lock<std::mutex> lock(mutex,std::try_to_lock);if(lock.owns_lock())Collect();}catch(...){flags.fetch_or(128);}return flags.load();}
unsigned LiveRenderSequence(){LiveRenderFlags();return completedSequence.load();}
bool LiveRenderActive(unsigned epoch){auto current=std::atomic_load(&feed);return epoch&&current&&current->epoch==epoch&&epoch==activeEpoch.load()&&!(flags.load()&128);}
}
