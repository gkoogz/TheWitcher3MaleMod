#define NOMINMAX
#include "float_draw_renderer.hpp"
#include "float_vertex_pipeline.hpp"
#include "live_renderer.hpp"
#include <map>
#include <mutex>
#include <atomic>
#include <limits>
namespace malemod::witcher {
namespace {
using Microsoft::WRL::ComPtr;
std::mutex mutex;
thread_local bool creating=false;
struct Pipeline {ComPtr<ID3D12PipelineState> original,replacement;};
// Process-lifetime tables have no loader-lock COM teardown. Explicit game
// shutdown or the OS owns retirement of the native graphics device.
auto* pipelines=new std::map<void*,Pipeline>;
struct Upload {ComPtr<ID3D12Resource> resource;std::shared_ptr<const RenderDelivery> input;};
struct Mark {ComPtr<ID3D12Fence> fence;UINT64 value;bool Done()const{auto v=fence->GetCompletedValue();if(v==UINT64_MAX)throw std::runtime_error("Float draw device removed");return v>=value;}};
struct Recording {std::vector<std::shared_ptr<Upload>> uploads;std::map<void*,Mark> marks;unsigned epoch=0;std::uint64_t sequence=0;};
struct Queue {ComPtr<ID3D12Fence> fence;UINT64 next=0;};
auto* recordings=new std::map<void*,Recording>;
auto* retired=new std::vector<Recording>;
auto* queues=new std::map<void*,Queue>;
auto* latest=new std::shared_ptr<Upload>;
auto* completedDelivery=new std::shared_ptr<const RenderDelivery>;
std::atomic<unsigned> flags{0},epoch{0},sequence{0};
void HR(HRESULT h){if(FAILED(h))throw std::runtime_error("Float draw HRESULT "+std::to_string(h));}
bool Eligible(const D3D12_INPUT_LAYOUT_DESC& desc){
 try{FloatSkinLayout layout(desc);return layout.Slot()==0;}catch(const std::invalid_argument&){return false;}
}
void Complete(const Recording& r){
 const auto current=LiveRenderLatest();if(!current||current->epoch!=r.epoch)return;
 if(epoch.exchange(r.epoch)!=r.epoch)sequence=0;
 auto old=sequence.load();const auto completed=unsigned(r.sequence);
 while(old<completed&&!sequence.compare_exchange_weak(old,completed)){}
 if(!r.uploads.empty()){
  const auto delivered=r.uploads.back()->input;auto previous=std::atomic_load(completedDelivery);
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
bool FloatDraw(void* pointer,void* original,const D3D12_VERTEX_BUFFER_VIEW& position,const D3D12_VERTEX_BUFFER_VIEW& lighting,const std::function<void()>& draw){
 auto input=LiveRenderLatest();if(!input||input->floatVertices.size()!=36547)return false;
 if(position.StrideInBytes!=24||position.SizeInBytes!=36547*24||(lighting.BufferLocation&&(lighting.BufferLocation!=position.BufferLocation+16||lighting.StrideInBytes!=24)))return false;
 auto* list=static_cast<ID3D12GraphicsCommandList*>(pointer);
 bool bound=false;
 try{
  std::unique_lock<std::mutex> lock(mutex);auto p=pipelines->find(original);if(p==pipelines->end()||flags.load()&128)return false;
  if(list->GetType()!=D3D12_COMMAND_LIST_TYPE_DIRECT&&list->GetType()!=D3D12_COMMAND_LIST_TYPE_BUNDLE)return false;
  Collect();if(retired->size()>64)throw std::runtime_error("Float upload retirement backlog");
  if(!*latest||(*latest)->input!=input){
   auto next=std::make_shared<Upload>();next->input=input;ComPtr<ID3D12Device> device;HR(list->GetDevice(IID_PPV_ARGS(&device)));
   D3D12_HEAP_PROPERTIES heap{};heap.Type=D3D12_HEAP_TYPE_UPLOAD;D3D12_RESOURCE_DESC desc{};desc.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER;desc.Width=input->floatVertices.size()*28;desc.Height=1;desc.DepthOrArraySize=1;desc.MipLevels=1;desc.SampleDesc.Count=1;desc.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
   HR(device->CreateCommittedResource(&heap,D3D12_HEAP_FLAG_NONE,&desc,D3D12_RESOURCE_STATE_GENERIC_READ,nullptr,IID_PPV_ARGS(&next->resource)));
   void* data=nullptr;D3D12_RANGE none{0,0};HR(next->resource->Map(0,&none,&data));std::memcpy(data,input->floatVertices.data(),std::size_t(desc.Width));D3D12_RANGE written{0,std::size_t(desc.Width)};next->resource->Unmap(0,&written);*latest=std::move(next);
  }
  auto& recording=(*recordings)[pointer];if(recording.uploads.size()>128)throw std::runtime_error("Float draw recording backlog");
  if(recording.uploads.empty()||recording.uploads.back()!=*latest)recording.uploads.push_back(*latest);
  recording.epoch=input->epoch;recording.sequence=input->sequence;
  auto replacement=p->second.replacement;auto retained=*latest;lock.unlock();
  const auto address=retained->resource->GetGPUVirtualAddress();D3D12_VERTEX_BUFFER_VIEW vertex{address,36547*28,28},normal{address+20,36547*28-20,28};
  list->SetPipelineState(replacement.Get());list->IASetVertexBuffers(0,1,&vertex);list->IASetVertexBuffers(2,1,&normal);bound=true;
  draw();
  list->IASetVertexBuffers(0,1,&position);list->IASetVertexBuffers(2,1,&lighting);list->SetPipelineState(static_cast<ID3D12PipelineState*>(original));bound=false;
  flags.fetch_or(64|512|4|16);return true;
 }catch(...){
  if(bound){list->IASetVertexBuffers(0,1,&position);list->IASetVertexBuffers(2,1,&lighting);list->SetPipelineState(static_cast<ID3D12PipelineState*>(original));}
  flags.fetch_or(128);return false;
 }
}
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
}catch(...){flags.fetch_or(128);}}
unsigned FloatDrawFlags(){try{std::unique_lock<std::mutex> lock(mutex,std::try_to_lock);if(lock.owns_lock())Collect();}catch(...){flags.fetch_or(128);}return flags.load();}
unsigned FloatDrawSequence(){FloatDrawFlags();return sequence.load();}
bool FloatDrawActive(unsigned character){const auto current=LiveRenderLatest();FloatDrawFlags();return character&&current&&current->epoch==character&&epoch.load()==character&&!(flags.load()&128);}
std::shared_ptr<const RenderDelivery> FloatDrawCompleted(){FloatDrawFlags();return std::atomic_load(completedDelivery);}
}
