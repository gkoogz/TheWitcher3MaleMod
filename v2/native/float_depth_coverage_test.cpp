#define NOMINMAX
#include "engine/float_draw_renderer.hpp"
#include "engine/live_renderer.hpp"
#include "engine/garment_renderer.hpp"
#include "engine/fluid_render_feed.hpp"
#include <wrl/client.h>
#include <dxgi1_6.h>
#include <d3dcompiler.h>
#include <cstring>
#include <cmath>
#include <iostream>
#include <stdexcept>
using Microsoft::WRL::ComPtr;
using namespace malemod::witcher;
namespace malemod::witcher {
std::shared_ptr<const GarmentRenderFeed> GarmentRendererLatest(){return {};}
std::shared_ptr<const FluidRenderFeed> FluidRendererLatest(){return {};}
bool GarmentCoverageReady(unsigned,std::uint64_t){return true;}
bool GarmentCoverageReady(unsigned,std::uint64_t,const std::shared_ptr<const GarmentRenderFeed>&){return true;}
}
static void Check(bool value,const char* reason){if(!value)throw std::runtime_error(std::string(reason)+": "+FloatDrawError());}
static void HR(HRESULT result){if(FAILED(result))throw std::runtime_error("D3D12 fixture HRESULT "+std::to_string(result));}
static ComPtr<ID3DBlob> Shader(const char* source,const char* target){ComPtr<ID3DBlob> blob,error;auto h=D3DCompile(source,std::strlen(source),nullptr,nullptr,nullptr,"main",target,D3DCOMPILE_ENABLE_STRICTNESS,0,&blob,&error);if(FAILED(h)&&error)std::cerr<<static_cast<const char*>(error->GetBufferPointer());HR(h);return blob;}
int main(int argc,char** argv){try{
 ComPtr<IDXGIFactory4> factory;HR(CreateDXGIFactory1(IID_PPV_ARGS(&factory)));ComPtr<IDXGIAdapter> adapter;
 if(argc==2&&!std::strcmp(argv[1],"--hardware")){ComPtr<IDXGIFactory6> modern;HR(factory.As(&modern));HR(modern->EnumAdapterByGpuPreference(0,DXGI_GPU_PREFERENCE_HIGH_PERFORMANCE,IID_PPV_ARGS(&adapter)));}else HR(factory->EnumWarpAdapter(IID_PPV_ARGS(&adapter)));
 ComPtr<IDXGIAdapter1> named;HR(adapter.As(&named));DXGI_ADAPTER_DESC1 info{};HR(named->GetDesc1(&info));std::cout<<"Adapter vendor="<<info.VendorId<<" device="<<info.DeviceId<<" software="<<bool(info.Flags&DXGI_ADAPTER_FLAG_SOFTWARE)<<'\n';if(argc==2)Check(!(info.Flags&DXGI_ADAPTER_FLAG_SOFTWARE),"Hardware selected software");
 ComPtr<ID3D12Device> device;HR(D3D12CreateDevice(adapter.Get(),D3D_FEATURE_LEVEL_11_0,IID_PPV_ARGS(&device)));
 auto buffer=[&](UINT64 bytes,D3D12_HEAP_TYPE type,D3D12_RESOURCE_STATES state,const void* data=nullptr){D3D12_HEAP_PROPERTIES heap{};heap.Type=type;D3D12_RESOURCE_DESC desc{};desc.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER;desc.Width=bytes;desc.Height=1;desc.DepthOrArraySize=1;desc.MipLevels=1;desc.SampleDesc.Count=1;desc.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR;ComPtr<ID3D12Resource> out;HR(device->CreateCommittedResource(&heap,D3D12_HEAP_FLAG_NONE,&desc,state,nullptr,IID_PPV_ARGS(&out)));if(data){void* p=nullptr;D3D12_RANGE none{};HR(out->Map(0,&none,&p));std::memcpy(p,data,std::size_t(bytes));out->Unmap(0,nullptr);}return out;};
 D3D12_ROOT_SIGNATURE_DESC rootDesc{};rootDesc.Flags=D3D12_ROOT_SIGNATURE_FLAG_ALLOW_INPUT_ASSEMBLER_INPUT_LAYOUT;ComPtr<ID3DBlob> rootBlob,error;HR(D3D12SerializeRootSignature(&rootDesc,D3D_ROOT_SIGNATURE_VERSION_1,&rootBlob,&error));ComPtr<ID3D12RootSignature> root;HR(device->CreateRootSignature(0,rootBlob->GetBufferPointer(),rootBlob->GetBufferSize(),IID_PPV_ARGS(&root)));
 D3D12_INPUT_ELEMENT_DESC layout[]={
  {"POSITION",0,DXGI_FORMAT_R16G16B16A16_UNORM,0,0,D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA,0},
  {"BLENDINDICES",0,DXGI_FORMAT_R8G8B8A8_UINT,0,8,D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA,0},
  {"BLENDWEIGHT",0,DXGI_FORMAT_R8G8B8A8_UNORM,0,12,D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA,0},
  {"TEXCOORD",7,DXGI_FORMAT_R32G32_FLOAT,2,0,D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA,0}};
 auto vs=Shader("float4 main(float3 p:POSITION,uint4 b:BLENDINDICES,float4 w:BLENDWEIGHT):SV_Position{return float4(p,1);}","vs_5_0");
 D3D12_GRAPHICS_PIPELINE_STATE_DESC desc{};desc.pRootSignature=root.Get();desc.VS={vs->GetBufferPointer(),vs->GetBufferSize()};desc.InputLayout={layout,3};desc.SampleMask=UINT_MAX;desc.SampleDesc.Count=1;desc.PrimitiveTopologyType=D3D12_PRIMITIVE_TOPOLOGY_TYPE_TRIANGLE;desc.DSVFormat=DXGI_FORMAT_D32_FLOAT;
 desc.RasterizerState.FillMode=D3D12_FILL_MODE_SOLID;desc.RasterizerState.CullMode=D3D12_CULL_MODE_NONE;desc.RasterizerState.DepthClipEnable=TRUE;
 desc.DepthStencilState.DepthEnable=TRUE;desc.DepthStencilState.DepthWriteMask=D3D12_DEPTH_WRITE_MASK_ALL;desc.DepthStencilState.DepthFunc=D3D12_COMPARISON_FUNC_LESS;desc.DepthStencilState.FrontFace.StencilFunc=D3D12_COMPARISON_FUNC_ALWAYS;desc.DepthStencilState.FrontFace.StencilFailOp=desc.DepthStencilState.FrontFace.StencilDepthFailOp=desc.DepthStencilState.FrontFace.StencilPassOp=D3D12_STENCIL_OP_KEEP;desc.DepthStencilState.BackFace=desc.DepthStencilState.FrontFace;
 ComPtr<ID3D12PipelineState> depth,slot2;HR(device->CreateGraphicsPipelineState(&desc,IID_PPV_ARGS(&depth)));RegisterFloatDrawPipeline(depth.Get(),desc);auto consumed=desc;consumed.InputLayout.NumElements=4;HR(device->CreateGraphicsPipelineState(&consumed,IID_PPV_ARGS(&slot2)));RegisterFloatDrawPipeline(slot2.Get(),consumed);
 auto delivery=std::make_shared<RenderDelivery>();delivery->epoch=1;delivery->sequence=1;RenderResource resource;resource.vertexCount=3;resource.indexBytes=6;resource.lodVertexCount[0]=3;delivery->resources.push_back(resource);
 for(auto p:std::array<std::array<float,3>,3>{{{-.8f,-.8f,.5f},{.8f,-.8f,.5f},{0,.8f,.5f}}}){RenderDelivery::FloatVertex v;v.position=p;v.weights=255;delivery->floatVertices.push_back(v);}
 auto covered=std::make_shared<const std::vector<std::uint16_t>>(std::initializer_list<std::uint16_t>{0,0,0});
 std::uint16_t sourceIndices[]{0,1,2};auto indices=buffer(sizeof sourceIndices,D3D12_HEAP_TYPE_UPLOAD,D3D12_RESOURCE_STATE_GENERIC_READ,sourceIndices);D3D12_INDEX_BUFFER_VIEW indexView{indices->GetGPUVirtualAddress(),6,DXGI_FORMAT_R16_UINT};
 auto packed=buffer(72,D3D12_HEAP_TYPE_UPLOAD,D3D12_RESOURCE_STATE_GENERIC_READ);auto stale=buffer(256,D3D12_HEAP_TYPE_UPLOAD,D3D12_RESOURCE_STATE_GENERIC_READ);D3D12_VERTEX_BUFFER_VIEW position{packed->GetGPUVirtualAddress(),72,24},lighting{stale->GetGPUVirtualAddress(),256,8};
 D3D12_HEAP_PROPERTIES heapProps{};heapProps.Type=D3D12_HEAP_TYPE_DEFAULT;D3D12_RESOURCE_DESC textureDesc{};textureDesc.Dimension=D3D12_RESOURCE_DIMENSION_TEXTURE2D;textureDesc.Width=32;textureDesc.Height=32;textureDesc.DepthOrArraySize=1;textureDesc.MipLevels=1;textureDesc.Format=DXGI_FORMAT_D32_FLOAT;textureDesc.SampleDesc.Count=1;textureDesc.Flags=D3D12_RESOURCE_FLAG_ALLOW_DEPTH_STENCIL;D3D12_CLEAR_VALUE clearValue{};clearValue.Format=DXGI_FORMAT_D32_FLOAT;clearValue.DepthStencil.Depth=1;
 ComPtr<ID3D12Resource> texture;HR(device->CreateCommittedResource(&heapProps,D3D12_HEAP_FLAG_NONE,&textureDesc,D3D12_RESOURCE_STATE_DEPTH_WRITE,&clearValue,IID_PPV_ARGS(&texture)));
 D3D12_DESCRIPTOR_HEAP_DESC heapDesc{};heapDesc.Type=D3D12_DESCRIPTOR_HEAP_TYPE_DSV;heapDesc.NumDescriptors=1;ComPtr<ID3D12DescriptorHeap> descriptors;HR(device->CreateDescriptorHeap(&heapDesc,IID_PPV_ARGS(&descriptors)));auto dsv=descriptors->GetCPUDescriptorHandleForHeapStart();device->CreateDepthStencilView(texture.Get(),nullptr,dsv);
 D3D12_PLACED_SUBRESOURCE_FOOTPRINT footprint{};UINT rows=0;UINT64 rowBytes=0,bytes=0;device->GetCopyableFootprints(&textureDesc,0,1,0,&footprint,&rows,&rowBytes,&bytes);auto readback=buffer(bytes,D3D12_HEAP_TYPE_READBACK,D3D12_RESOURCE_STATE_COPY_DEST);
 ComPtr<ID3D12CommandAllocator> allocator;HR(device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT,IID_PPV_ARGS(&allocator)));ComPtr<ID3D12GraphicsCommandList> list;HR(device->CreateCommandList(0,D3D12_COMMAND_LIST_TYPE_DIRECT,allocator.Get(),depth.Get(),IID_PPV_ARGS(&list)));HR(list->Close());D3D12_COMMAND_QUEUE_DESC queueDesc{};ComPtr<ID3D12CommandQueue> queue;HR(device->CreateCommandQueue(&queueDesc,IID_PPV_ARGS(&queue)));ComPtr<ID3D12Fence> fence;HR(device->CreateFence(0,D3D12_FENCE_FLAG_NONE,IID_PPV_ARGS(&fence)));UINT64 serial=0;
 for(int test=-2;test<13;test++){
  auto frame=std::make_shared<RenderDelivery>(*delivery);frame->sequence=unsigned(test+3);
  unsigned section=~0u,normalized=0;bool active=true,wantCoverage=test>0,colorPass=test==2;float expected=test?1.f:.5f;
  if(test>=3||test<0){
   const unsigned c=test>=3?test-3:0;frame->epoch=2;frame->materialState=test<0?1:c<6?c/2:(c-6)/2;section=test<0?unsigned(test+2):c<6?1+c%2:frame->materialState==0?2:1;normalized=section*3;wantCoverage=test>=3&&c>=6;colorPass=wantCoverage&&bool(c%2);active=section==0||section==1&&frame->materialState!=0||section==2&&frame->materialState==0;
   auto& r=frame->resources[0];r.vertexCount=18;r.indexBytes=36;r.lodFirstVertex={0,9};r.lodVertexCount={9,9};
   frame->floatVertices.clear();for(unsigned i=0;i<6;i++){RenderSection s;s.lod=i/3;s.material=i%3;s.firstVertex=i*3;s.vertexCount=3;s.indexFirst=i*3;s.indexCount=3;r.sections.push_back(s);for(auto v:delivery->floatVertices){v.position[2]=i==1?.3f:i==2?.7f:.9f;frame->floatVertices.push_back(v);}}
   expected=active&&!wantCoverage?(section==0?.9f:section==1?.3f:.7f):1.f;
  }
  if(wantCoverage)frame->coveredIndices=test<3?covered:std::make_shared<const std::vector<std::uint16_t>>(18u,std::uint16_t(0));
  LiveRenderFeed(frame);FloatDrawFrameBoundary();HR(allocator->Reset());HR(list->Reset(allocator.Get(),depth.Get()));list->SetGraphicsRootSignature(root.Get());D3D12_VIEWPORT viewport{0,0,32,32,0,1};D3D12_RECT rect{0,0,32,32};list->RSSetViewports(1,&viewport);list->RSSetScissorRects(1,&rect);list->OMSetRenderTargets(0,nullptr,FALSE,&dsv);list->ClearDepthStencilView(dsv,D3D12_CLEAR_FLAG_DEPTH,1,0,0,nullptr);list->IASetPrimitiveTopology(D3D_PRIMITIVE_TOPOLOGY_TRIANGLELIST);list->IASetVertexBuffers(0,1,&position);list->IASetVertexBuffers(2,1,&lighting);list->IASetIndexBuffer(&indexView);
  if(test>=0&&test<3)Check(!FloatDraw(list.Get(),slot2.Get(),position,lighting,[&]{throw std::runtime_error("Consumed arbitrary slot2 reached draw");},0,0),"Any consumed slot2 must retain lighting validation");
  unsigned draws=0;FloatDrawReceipt applied;Check(FloatDraw(list.Get(),depth.Get(),position,lighting,[&]{++draws;list->DrawIndexedInstanced(3,1,0,0,0);},0,0,nullptr,0,{},&indexView,0,normalized,colorPass,&applied,section),"No-UV section depth pass with unused stale slot2 was rejected");Check(applied.coverageApplied==(wantCoverage&&active)&&draws==unsigned(active)&&applied.active==active,"Section/state/coverage receipt differs");
  if(test>=3)Check(applied.section==section&&applied.material==section&&applied.state==frame->materialState,"Wrong section rows or source material selected");
  if(test<0)Check(FloatDrawRecentlySeen(0)==(test==-1),"B04 stock skin established source anatomy visibility or active anatomy did not");
  if(test==4){auto newer=std::make_shared<RenderDelivery>(*frame);newer->materialState=1;newer->sequence++;LiveRenderFeed(newer);FloatDrawReceipt same;Check(FloatDraw(list.Get(),depth.Get(),position,lighting,[&]{throw std::runtime_error("Mid-frame state changed the inactive source material");},0,0,nullptr,0,{},&indexView,0,3,false,&same,1)&&!same.active&&same.state==0,"Material state did not follow the selected SDK frame");}
  D3D12_RESOURCE_BARRIER barrier{};barrier.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;barrier.Transition={texture.Get(),D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,D3D12_RESOURCE_STATE_DEPTH_WRITE,D3D12_RESOURCE_STATE_COPY_SOURCE};list->ResourceBarrier(1,&barrier);D3D12_TEXTURE_COPY_LOCATION src{},dst{};src.pResource=texture.Get();src.Type=D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;dst.pResource=readback.Get();dst.Type=D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;dst.PlacedFootprint=footprint;list->CopyTextureRegion(&dst,0,0,0,&src,nullptr);std::swap(barrier.Transition.StateBefore,barrier.Transition.StateAfter);list->ResourceBarrier(1,&barrier);HR(list->Close());ID3D12CommandList* commands[]{list.Get()};queue->ExecuteCommandLists(1,commands);FloatDrawSubmitted(queue.Get(),1,reinterpret_cast<void* const*>(commands));HR(queue->Signal(fence.Get(),++serial));HANDLE event=CreateEventW(nullptr,FALSE,FALSE,nullptr);Check(event!=nullptr,"Fence event failed");HR(fence->SetEventOnCompletion(serial,event));auto wait=WaitForSingleObject(event,10000);CloseHandle(event);Check(wait==WAIT_OBJECT_0,"GPU depth timed out");
  void* data=nullptr;D3D12_RANGE read{0,SIZE_T(bytes)};HR(readback->Map(0,&read,&data));float center=0;std::memcpy(&center,static_cast<unsigned char*>(data)+footprint.Offset+16*footprint.Footprint.RowPitch+16*4,4);D3D12_RANGE none{};readback->Unmap(0,&none);Check(std::abs(center-expected)<1e-6f,"Covered/inactive anatomy left phantom depth or wrong section vertex slice");FloatDrawReset(list.Get());
 }
 const auto counts=FloatDrawCoveragePassCounts();Check(counts[0]==3&&counts[1]==3,"Covered color/depth diagnostic counters differ");Check(!(FloatDrawFlags()&128),"Renderer faulted");std::cout<<"PASS actual FloatDraw: legacy no-UV/stale-unused-slot2 guards; B04 exact section row slices, state0 erect/states1 natural, inactive suppression, geometry/material SDK-frame coherence and coverage in depth/color-flag paths; SDK output only\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
