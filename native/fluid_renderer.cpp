#define NOMINMAX
#include "fluid_renderer.hpp"
#include "clinical_service.hpp"
#include <wrl/client.h>
#include <fstream>
#include <map>
#include <mutex>
#include <atomic>
namespace malemod::witcher { namespace {
using Microsoft::WRL::ComPtr;
std::mutex mutex;std::atomic<unsigned> flags{0},publications{0};thread_local bool creating=false;
struct Layout {
 std::vector<std::string> names;std::vector<D3D12_INPUT_ELEMENT_DESC> elements;
 explicit Layout(const D3D12_INPUT_LAYOUT_DESC& d){
  if(!d.pInputElementDescs||!d.NumElements||d.NumElements>32)throw std::invalid_argument("Invalid fluid input layout");
  for(unsigned i=0;i<d.NumElements;i++){auto e=d.pInputElementDescs[i];if(!e.SemanticName)throw std::invalid_argument("Missing fluid semantic");names.push_back(e.SemanticName);elements.push_back(e);}
  bool position=false;
  for(auto& e:elements){if(e.InputSlotClass==D3D12_INPUT_CLASSIFICATION_PER_INSTANCE_DATA)continue;
   if(!_stricmp(e.SemanticName,"BLENDINDICES")||!_stricmp(e.SemanticName,"BLENDWEIGHT"))throw std::invalid_argument("Fluid carrier must be rigid");
   if(!_stricmp(e.SemanticName,"POSITION")){if(e.SemanticIndex||e.InputSlot||e.AlignedByteOffset||e.Format!=DXGI_FORMAT_R16G16B16A16_UNORM)throw std::invalid_argument("Unobserved fluid position");e.Format=DXGI_FORMAT_R32G32B32_FLOAT;position=true;}
   else if(!_stricmp(e.SemanticName,"NORMAL")||!_stricmp(e.SemanticName,"TANGENT")){if(e.InputSlot!=2||e.Format!=DXGI_FORMAT_R10G10B10A2_UNORM||e.AlignedByteOffset!=(!_stricmp(e.SemanticName,"NORMAL")?0:4))throw std::invalid_argument("Unobserved fluid lighting");}
   else if(!_stricmp(e.SemanticName,"TEXCOORD")){if(e.Format!=DXGI_FORMAT_R16G16_FLOAT||!(e.SemanticIndex==0&&e.InputSlot==1&&e.AlignedByteOffset==0||e.SemanticIndex==1&&e.InputSlot==3&&e.AlignedByteOffset==4))throw std::invalid_argument("Unobserved fluid UV");}
   else if(!_stricmp(e.SemanticName,"COLOR")){if(e.InputSlot!=3||e.AlignedByteOffset||e.Format!=DXGI_FORMAT_R8G8B8A8_UNORM)throw std::invalid_argument("Unobserved fluid color");}
   else throw std::invalid_argument("Unobserved fluid attribute");
  }
  if(!position)throw std::invalid_argument("No fluid POSITION");for(unsigned i=0;i<elements.size();i++)elements[i].SemanticName=names[i].c_str();
 }
 D3D12_INPUT_LAYOUT_DESC View()const{return {elements.data(),UINT(elements.size())};}
};
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

struct Pipeline {
 ComPtr<ID3D12PipelineState> original,replacement;ComPtr<ID3D12RootSignature> root;
 D3D12_GRAPHICS_PIPELINE_STATE_DESC desc{};std::vector<unsigned char> stream;
 std::array<std::vector<unsigned char>,5> shaders;
 std::vector<std::string> names;std::vector<D3D12_INPUT_ELEMENT_DESC> elements;
 std::size_t layout=SIZE_MAX,cache=SIZE_MAX;
};
auto* pipelines=new std::map<void*,std::shared_ptr<Pipeline>>;
struct Resource {std::array<float,3> scale,bias;unsigned indexBytes=0;};
std::array<Resource,2> resources{};bool configured=false,valid=false;std::array<double,3> origin{};
struct Feed {std::shared_ptr<const ClinicalDelivery> input;std::array<double,3> origin;double scale;};
auto* feed=new std::shared_ptr<const Feed>;
auto* frameFeed=new std::shared_ptr<const Feed>;
struct Vertex {std::array<float,3> p;unsigned normal,tangent,uv=0x38003800,color=0xffffffff,uv2=0;};
static_assert(sizeof(Vertex)==32);
struct Upload {ComPtr<ID3D12Resource> vertices,indices;std::shared_ptr<const Feed> packet;unsigned opaque=0,count=0;std::array<D3D12_VERTEX_BUFFER_VIEW,4> views;D3D12_INDEX_BUFFER_VIEW index;};
struct Mark {ComPtr<ID3D12Fence> fence;UINT64 value;bool Done(){auto v=fence->GetCompletedValue();if(v==UINT64_MAX)throw std::runtime_error("Fluid device removed");return v>=value;}};
struct Recording {std::array<std::shared_ptr<Upload>,2> uploads{};std::vector<std::shared_ptr<Upload>> retained;std::map<void*,Mark> marks;};
struct Queue {ComPtr<ID3D12Fence> fence;UINT64 next=0;};
auto* recordings=new std::map<void*,Recording>;auto* retired=new std::vector<Recording>;auto* queues=new std::map<void*,Queue>;
std::atomic<std::uint64_t> counted{0};
void HR(HRESULT r){if(FAILED(r))throw std::runtime_error("Fluid HRESULT "+std::to_string(r));}
void Collect(){for(auto i=retired->begin();i!=retired->end();){bool done=!i->marks.empty();for(auto& m:i->marks)done&=m.second.Done();if(done)i=retired->erase(i);else ++i;}}
ComPtr<ID3D12Resource> Buffer(ID3D12Device* device,const void* bytes,std::size_t size,std::size_t padding=0){
 D3D12_HEAP_PROPERTIES heap{};heap.Type=D3D12_HEAP_TYPE_UPLOAD;D3D12_RESOURCE_DESC d{};d.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER;d.Width=size+padding;d.Height=1;d.DepthOrArraySize=1;d.MipLevels=1;d.SampleDesc.Count=1;d.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
 ComPtr<ID3D12Resource> out;HR(device->CreateCommittedResource(&heap,D3D12_HEAP_FLAG_NONE,&d,D3D12_RESOURCE_STATE_GENERIC_READ,nullptr,IID_PPV_ARGS(&out)));void* p;D3D12_RANGE none{0,0};HR(out->Map(0,&none,&p));std::memcpy(p,bytes,size);if(padding)std::memset(static_cast<unsigned char*>(p)+size,0,padding);D3D12_RANGE written{0,size+padding};out->Unmap(0,&written);return out;
}
void SaveLayout(Pipeline& p,const D3D12_INPUT_LAYOUT_DESC& d){for(unsigned i=0;i<d.NumElements;i++){p.names.push_back(d.pInputElementDescs[i].SemanticName);p.elements.push_back(d.pInputElementDescs[i]);}for(unsigned i=0;i<p.elements.size();i++)p.elements[i].SemanticName=p.names[i].c_str();}
void Clone(Pipeline& p){if(p.replacement)return;ComPtr<ID3D12Device> device;HR(p.original->GetDevice(IID_PPV_ARGS(&device)));Layout layout({p.elements.data(),UINT(p.elements.size())});creating=true;
 try{if(p.stream.empty()){auto d=p.desc;d.InputLayout=layout.View();d.CachedPSO={};HR(device->CreateGraphicsPipelineState(&d,IID_PPV_ARGS(&p.replacement)));}
 else{auto copy=p.stream;*reinterpret_cast<D3D12_INPUT_LAYOUT_DESC*>(copy.data()+p.layout)=layout.View();if(p.cache!=SIZE_MAX)*reinterpret_cast<D3D12_CACHED_PIPELINE_STATE*>(copy.data()+p.cache)={};ComPtr<ID3D12Device2> d;HR(device.As(&d));D3D12_PIPELINE_STATE_STREAM_DESC s{copy.size(),copy.data()};HR(d->CreatePipelineState(&s,IID_PPV_ARGS(&p.replacement)));}creating=false;}catch(...){creating=false;throw;}
}
} // internal
void FluidRendererConfigure(const std::filesystem::path& path){std::ifstream f(path,std::ios::binary);char magic[8]{};f.read(magic,8);if(std::memcmp(magic,"MMFLD001",8))throw std::invalid_argument("Fluid resource contract differs");for(auto& r:resources){f.read(reinterpret_cast<char*>(r.scale.data()),12);f.read(reinterpret_cast<char*>(r.bias.data()),12);f.read(reinterpret_cast<char*>(&r.indexBytes),4);for(float x:r.scale)if(!std::isfinite(x)||x<=0)throw std::invalid_argument("Invalid fluid quantization");if(!r.indexBytes)throw std::invalid_argument("Missing fluid native indices");}if(!f||f.peek()!=EOF)throw std::invalid_argument("Fluid contract size differs");configured=true;flags.fetch_or(1);}
void FluidRendererOrigin(std::array<double,3> p,bool active){std::lock_guard<std::mutex> lock(mutex);origin=p;valid=active;if(!active)std::atomic_store(feed,std::shared_ptr<const Feed>{});}
void FluidRendererFeed(std::shared_ptr<const ClinicalDelivery> input,double scale){std::lock_guard<std::mutex> lock(mutex);if(!valid||!configured)return;std::atomic_store(feed,std::shared_ptr<const Feed>(std::make_shared<Feed>(Feed{std::move(input),origin,scale})));}
void FluidRendererFrameBoundary(){std::lock_guard<std::mutex> lock(mutex);std::atomic_store(frameFeed,std::atomic_load(feed));}
void RegisterFluidPipeline(void* original,const D3D12_GRAPHICS_PIPELINE_STATE_DESC& desc){if(creating||!original)return;try{Layout l(desc.InputLayout);auto p=std::make_shared<Pipeline>();p->original=static_cast<ID3D12PipelineState*>(original);p->desc=desc;p->root=desc.pRootSignature;SaveLayout(*p,desc.InputLayout);p->desc.InputLayout={p->elements.data(),UINT(p->elements.size())};D3D12_SHADER_BYTECODE* stages[]={&p->desc.VS,&p->desc.PS,&p->desc.DS,&p->desc.HS,&p->desc.GS};for(unsigned i=0;i<5;i++){auto& s=*stages[i];auto* bytes=static_cast<const unsigned char*>(s.pShaderBytecode);if(s.BytecodeLength){p->shaders[i].assign(bytes,bytes+s.BytecodeLength);s={p->shaders[i].data(),p->shaders[i].size()};}}p->desc.CachedPSO={};std::lock_guard<std::mutex> lock(mutex);if(pipelines->size()<16384)(*pipelines)[original]=p;}catch(const std::invalid_argument&){}catch(...){flags.fetch_or(128);}}
void RegisterFluidStream(void* original,const D3D12_PIPELINE_STATE_STREAM_DESC& desc,std::size_t layout,std::size_t cache){if(creating||!original||layout==SIZE_MAX)return;try{auto* bytes=static_cast<const unsigned char*>(desc.pPipelineStateSubobjectStream);Layout l(*reinterpret_cast<const D3D12_INPUT_LAYOUT_DESC*>(bytes+layout));auto p=std::make_shared<Pipeline>();p->original=static_cast<ID3D12PipelineState*>(original);p->stream.assign(bytes,bytes+desc.SizeInBytes);p->layout=layout;p->cache=cache;SaveLayout(*p,*reinterpret_cast<const D3D12_INPUT_LAYOUT_DESC*>(bytes+layout));
 // Stream bytecode is retained by the observer at creation; copy shader payloads
 // while traversing the same SDK stream subobjects below.
 std::size_t at=0;unsigned shader=0;
 while(at<p->stream.size()){
  if(p->stream.size()-at<sizeof(D3D12_PIPELINE_STATE_SUBOBJECT_TYPE))throw std::invalid_argument("Truncated fluid stream");
  auto type=*reinterpret_cast<D3D12_PIPELINE_STATE_SUBOBJECT_TYPE*>(p->stream.data()+at);
  auto size=StreamObjectSize(type);if(!size||size>p->stream.size()-at)throw std::invalid_argument("Unknown fluid stream subobject");
  if(type==D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_ROOT_SIGNATURE)p->root=reinterpret_cast<StreamObject<ID3D12RootSignature*>*>(p->stream.data()+at)->value;
  if(type==D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_VS||type==D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_PS||type==D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_DS||type==D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_HS||type==D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_GS){
   auto& code=reinterpret_cast<StreamObject<D3D12_SHADER_BYTECODE>*>(p->stream.data()+at)->value;
   if(shader>=5)throw std::invalid_argument("Too many fluid stages");
   if(code.BytecodeLength){auto* bytes=static_cast<const unsigned char*>(code.pShaderBytecode);p->shaders[shader].assign(bytes,bytes+code.BytecodeLength);code={p->shaders[shader].data(),p->shaders[shader].size()};}++shader;
  }
  // Engine material streams do not use stream output or view instancing.
  // Their pointer-bearing descriptors cannot be retained without deep copies.
  if(type==D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_STREAM_OUTPUT||type==D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_VIEW_INSTANCING)throw std::invalid_argument("Unsupported carrier stream pointers");
  at+=size;
 }
 std::lock_guard<std::mutex> lock(mutex);if(pipelines->size()<16384)(*pipelines)[original]=p;
 }catch(const std::invalid_argument&){}catch(...){flags.fetch_or(128);}}
bool FluidDraw(void* pointer,void* original,const std::array<D3D12_VERTEX_BUFFER_VIEW,32>& saved,const D3D12_INDEX_BUFFER_VIEW& indices,unsigned kind,const std::function<void(unsigned,unsigned)>& draw){
 if(kind>1)return false;auto packet=std::atomic_load(feed);if(!packet||!packet->input)return true;
 // Depth, opaque and transparent command lists share the SDK frame's exact
 // mesh and carrier transform. A later worker publication waits for the next
 // frame boundary. Empty feeds and character changes suppress stale frames.
 auto frame=std::atomic_load(frameFeed);if(frame&&frame->input&&frame->input->epoch==packet->input->epoch)packet=frame;
 auto input=packet->input;
 auto* list=static_cast<ID3D12GraphicsCommandList*>(pointer);bool bound=false;
 try{std::unique_lock<std::mutex> lock(mutex);Collect();auto found=pipelines->find(original);if(found==pipelines->end()){flags.fetch_or(2);return true;}if(retired->size()>128)throw std::runtime_error("Fluid retirement backlog");auto pipeline=found->second;Clone(*pipeline);auto& record=(*recordings)[pointer];auto upload=record.uploads[kind];if(record.uploads[1-kind])packet=record.uploads[1-kind]->packet;
  if(!upload){upload=std::make_shared<Upload>();upload->packet=packet;const auto& mesh=packet->input->mesh;std::vector<Vertex> vertices;vertices.reserve(mesh.vertices.size()+packet->input->deposits.vertices.size());const auto& r=resources[kind];
   auto append=[&](malemod::V3 p,malemod::V3 n,float alpha){Vertex v{};for(unsigned a=0;a<3;a++){float value=a==0?p.x:a==1?p.y:p.z;v.p[a]=float((double(value)*packet->scale-packet->origin[a]-r.bias[a])/r.scale[a]);if(!std::isfinite(v.p[a]))throw std::runtime_error("Nonfinite clinical vertex");}skin::Point normal{n.x,n.y,n.z};auto tangent=Unit(Cross(n,std::abs(n.z)<.8f?malemod::V3{0,0,1}:malemod::V3{0,1,0}));v.normal=PackDirection(normal,1);v.tangent=PackDirection({tangent.x,tangent.y,tangent.z},3);v.color=0x00ffffffu|(unsigned(std::clamp(alpha,0.f,1.f)*255+.5f)<<24);vertices.push_back(v);};
   for(const auto& v:mesh.vertices)append(v.p,v.n,1);unsigned first=unsigned(vertices.size());for(const auto& v:packet->input->deposits.vertices)append(v.p,v.n,v.alpha);
   auto topology=mesh.indices;upload->opaque=mesh.opaqueIndices;for(unsigned id:packet->input->deposits.indices)topology.push_back(first+id);upload->count=unsigned(topology.size());
   for(auto id:topology)if(id>=vertices.size())throw std::runtime_error("Invalid clinical index");if(vertices.size()>250000||topology.size()>1500000)throw std::runtime_error("Clinical output capacity exceeded");
   if(vertices.empty()||topology.empty())return true;ComPtr<ID3D12Device> device;HR(list->GetDevice(IID_PPV_ARGS(&device)));
   // Each shifted stream needs a complete final stride. AMD zeroes the last
   // vertex's attributes when SizeInBytes ends partway through that record,
   // even if the individual fields fit. Pad the allocation, not the source
   // mesh, and expose exactly the same vertex count in every stream.
   const UINT vertexBytes=UINT(vertices.size()*sizeof(Vertex));
   upload->vertices=Buffer(device.Get(),vertices.data(),vertexBytes,24);upload->indices=Buffer(device.Get(),topology.data(),topology.size()*4);auto address=upload->vertices->GetGPUVirtualAddress();const unsigned offsets[4]={0,20,12,24};for(unsigned i=0;i<4;i++)upload->views[i]={address+offsets[i],vertexBytes,sizeof(Vertex)};upload->index={upload->indices->GetGPUVirtualAddress(),UINT(topology.size()*4),DXGI_FORMAT_R32_UINT};record.uploads[kind]=upload;
  }
  const unsigned first=kind?upload->opaque:0,count=kind?upload->count-upload->opaque:upload->opaque;if(!count)return true;lock.unlock();list->SetPipelineState(pipeline->replacement.Get());list->IASetVertexBuffers(0,4,upload->views.data());list->IASetIndexBuffer(&upload->index);bound=true;draw(count,first);list->IASetIndexBuffer(&indices);list->IASetVertexBuffers(0,4,saved.data());list->SetPipelineState(static_cast<ID3D12PipelineState*>(original));bound=false;flags.fetch_or(4|(kind?16:8));auto serial=upload->packet->input->serial,previous=counted.load();while(serial>previous){if(counted.compare_exchange_weak(previous,serial)){publications.fetch_add(1);break;}}return true;
 }catch(...){if(bound){list->IASetIndexBuffer(&indices);list->IASetVertexBuffers(0,4,saved.data());list->SetPipelineState(static_cast<ID3D12PipelineState*>(original));}flags.fetch_or(128);return true;}
}
void FluidDrawSubmitted(void* pointer,unsigned count,void* const* lists){try{std::lock_guard<std::mutex> lock(mutex);Collect();bool used=false;for(unsigned i=0;i<count;i++)used|=recordings->count(lists[i])!=0;if(!used)return;auto* queue=static_cast<ID3D12CommandQueue*>(pointer);auto& q=(*queues)[pointer];if(!q.fence){ComPtr<ID3D12Device> device;HR(queue->GetDevice(IID_PPV_ARGS(&device)));HR(device->CreateFence(0,D3D12_FENCE_FLAG_NONE,IID_PPV_ARGS(&q.fence)));}auto value=++q.next;HR(queue->Signal(q.fence.Get(),value));for(unsigned i=0;i<count;i++){auto r=recordings->find(lists[i]);if(r!=recordings->end())r->second.marks[pointer]={q.fence,value};}}catch(...){flags.fetch_or(128);}}
void FluidDrawReset(void* pointer){try{std::lock_guard<std::mutex> lock(mutex);auto i=recordings->find(pointer);if(i!=recordings->end()){if(!i->second.marks.empty())retired->push_back(std::move(i->second));recordings->erase(i);}Collect();}catch(...){flags.fetch_or(128);}}
void FluidDrawBundle(void* parent,void* bundle){std::lock_guard<std::mutex> lock(mutex);auto i=recordings->find(bundle);if(i!=recordings->end()){auto& r=(*recordings)[parent];for(auto& u:i->second.uploads)if(u)r.retained.push_back(u);r.retained.insert(r.retained.end(),i->second.retained.begin(),i->second.retained.end());}}
unsigned FluidDrawFlags(){return flags.load();}unsigned FluidDrawPublications(){return publications.load();}
} // namespace
