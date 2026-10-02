#pragma once
#include <d3d12.h>
#include <wrl/client.h>
#include <array>
#include <cstdint>
#include <cstring>
#include <vector>
#include <string>
#include <memory>
#include <cstddef>
#include <stdexcept>
#include "skin_output.hpp"

namespace malemod::witcher {
struct FloatSkinVertex {skin::Point position;std::array<std::uint8_t,4> bones,weights;};
static_assert(sizeof(FloatSkinVertex)==20&&offsetof(FloatSkinVertex,bones)==12&&offsetof(FloatSkinVertex,weights)==16);
// Uses the unchanged vertex shader's quantization equation, with unbounded float
// input. Does not alter UV/lighting/instance attributes, shaders or root layouts.
class FloatSkinLayout {
 std::vector<std::string> names_;
 std::vector<D3D12_INPUT_ELEMENT_DESC> elements_;
 UINT slot_=0;
 public:
 explicit FloatSkinLayout(const D3D12_INPUT_LAYOUT_DESC& original){
  if(!original.pInputElementDescs||!original.NumElements||original.NumElements>32)throw std::invalid_argument("Invalid original skin layout");
  names_.reserve(original.NumElements);elements_.reserve(original.NumElements);
  for(UINT i=0;i<original.NumElements;i++){auto e=original.pInputElementDescs[i];if(!e.SemanticName||std::strlen(e.SemanticName)>64)throw std::invalid_argument("Invalid input semantic");names_.push_back(e.SemanticName);elements_.push_back(e);}
  unsigned position=0,indices=0,weights=0;
  for(auto& e:elements_)if(!_stricmp(e.SemanticName,"POSITION")&&e.SemanticIndex==0){
   if(e.Format!=DXGI_FORMAT_R16G16B16A16_UNORM||e.AlignedByteOffset!=0||e.InputSlotClass!=D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA)throw std::invalid_argument("Unsupported native position layout");slot_=e.InputSlot;e.Format=DXGI_FORMAT_R32G32B32_FLOAT;++position;
  }
  if(position!=1)throw std::invalid_argument("Expected exactly one native POSITION");
  for(auto& e:elements_){
   if(e.InputSlot!=slot_)continue;
   if(e.InputSlotClass!=D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA||e.InstanceDataStepRate)throw std::invalid_argument("Position stream contains instance data");
   if(!_stricmp(e.SemanticName,"BLENDINDICES")&&e.SemanticIndex==0){if(e.Format!=DXGI_FORMAT_R8G8B8A8_UINT||e.AlignedByteOffset!=8)throw std::invalid_argument("Unsupported skin index layout");e.AlignedByteOffset=12;++indices;}
   else if(!_stricmp(e.SemanticName,"BLENDWEIGHT")&&e.SemanticIndex==0){if(e.Format!=DXGI_FORMAT_R8G8B8A8_UNORM||e.AlignedByteOffset!=12)throw std::invalid_argument("Unsupported skin weight layout");e.AlignedByteOffset=16;++weights;}
   else if(_stricmp(e.SemanticName,"POSITION")||e.SemanticIndex!=0)throw std::invalid_argument("Unknown attribute in native position/skin stream");
  }
  if(indices!=1||weights!=1)throw std::invalid_argument("Native four-influence skin attributes missing");
  for(unsigned i=0;i<elements_.size();i++)elements_[i].SemanticName=names_[i].c_str();
 }
 FloatSkinLayout(const FloatSkinLayout&)=delete;FloatSkinLayout& operator=(const FloatSkinLayout&)=delete;
 D3D12_INPUT_LAYOUT_DESC View()const{return {elements_.data(),UINT(elements_.size())};}
 UINT Slot()const{return slot_;}
 Microsoft::WRL::ComPtr<ID3D12PipelineState> Create(ID3D12Device* device,const D3D12_GRAPHICS_PIPELINE_STATE_DESC& original)const{
  if(!device)throw std::invalid_argument("Missing original pipeline device");auto desc=original;desc.InputLayout=View();
  // Shader cache data belongs to the original layout and must not be reused.
  desc.CachedPSO={};Microsoft::WRL::ComPtr<ID3D12PipelineState> result;
  if(FAILED(device->CreateGraphicsPipelineState(&desc,IID_PPV_ARGS(&result))))throw std::runtime_error("Float skin pipeline creation failed");return result;
 }
};
struct VertexUpload {
 Microsoft::WRL::ComPtr<ID3D12Resource> resource;
 D3D12_VERTEX_BUFFER_VIEW view{};
 VertexUpload(ID3D12Device* device,const std::vector<FloatSkinVertex>& vertices){
  if(!device||vertices.empty()||vertices.size()>2000000)throw std::invalid_argument("Invalid immutable vertex upload");
  for(const auto& v:vertices)for(float x:v.position)if(!std::isfinite(x))throw std::invalid_argument("Nonfinite float output vertex");
  D3D12_HEAP_PROPERTIES heap{};heap.Type=D3D12_HEAP_TYPE_UPLOAD;
  D3D12_RESOURCE_DESC desc{};desc.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER;desc.Width=vertices.size()*sizeof(FloatSkinVertex);desc.Height=1;desc.DepthOrArraySize=1;desc.MipLevels=1;desc.SampleDesc.Count=1;desc.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
  if(FAILED(device->CreateCommittedResource(&heap,D3D12_HEAP_FLAG_NONE,&desc,D3D12_RESOURCE_STATE_GENERIC_READ,nullptr,IID_PPV_ARGS(&resource))))throw std::runtime_error("Immutable vertex allocation failed");
  void* data=nullptr;D3D12_RANGE none{0,0};if(FAILED(resource->Map(0,&none,&data))||!data)throw std::runtime_error("Immutable vertex upload map failed");
  std::memcpy(data,vertices.data(),static_cast<std::size_t>(desc.Width));D3D12_RANGE written{0,static_cast<std::size_t>(desc.Width)};resource->Unmap(0,&written);
  view={resource->GetGPUVirtualAddress(),static_cast<UINT>(desc.Width),sizeof(FloatSkinVertex)};
 }
};
// A retired resource is retained until ALL queues that consumed it complete.
// Submitters supply fence marks after the relevant command lists are submitted.
struct QueueCompletion {Microsoft::WRL::ComPtr<ID3D12Fence> fence;UINT64 value=0;};
class UploadRetirement {
 struct Retired {std::shared_ptr<const VertexUpload> upload;std::vector<QueueCompletion> completions;};
 std::vector<Retired> retired_;
 public:
 void Retire(std::shared_ptr<const VertexUpload> upload,std::vector<QueueCompletion> completions){
  if(!upload||completions.empty()||completions.size()>16)throw std::invalid_argument("Missing output consumption fences");
  for(const auto& c:completions)if(!c.fence||!c.value)throw std::invalid_argument("Invalid queue completion");
  if(retired_.size()>=64)throw std::runtime_error("GPU output retirement backlog");retired_.push_back({std::move(upload),std::move(completions)});
 }
 void Collect(){
  for(auto i=retired_.begin();i!=retired_.end();){bool done=true;for(const auto& c:i->completions){auto value=c.fence->GetCompletedValue();if(value==UINT64_MAX)throw std::runtime_error("GPU removed during output retirement");done&=value>=c.value;}if(done)i=retired_.erase(i);else ++i;}
 }
 std::size_t Pending()const{return retired_.size();}
};
}
