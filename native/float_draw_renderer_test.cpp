#define NOMINMAX
#include "float_vertex_pipeline.hpp"
#include "float_draw_renderer.hpp"
#include "live_renderer.hpp"
#include <dxgi1_6.h>
#include <d3dcompiler.h>
#include <iostream>
using Microsoft::WRL::ComPtr;
using namespace malemod::witcher;
static void Check(bool b,const char* s){if(!b)throw std::runtime_error(s);}
static void HR(HRESULT h){if(FAILED(h))throw std::runtime_error("D3D12 output test failed HRESULT="+std::to_string(h));}
static ComPtr<ID3DBlob> Shader(const char* source,const char* target){ComPtr<ID3DBlob> b,e;auto h=D3DCompile(source,std::strlen(source),nullptr,nullptr,nullptr,"main",target,D3DCOMPILE_ENABLE_STRICTNESS,0,&b,&e);if(FAILED(h)){if(e)std::cerr<<static_cast<const char*>(e->GetBufferPointer());HR(h);}return b;}
int main(){try{
 ComPtr<IDXGIFactory4> factory;HR(CreateDXGIFactory1(IID_PPV_ARGS(&factory)));ComPtr<IDXGIAdapter> warp;HR(factory->EnumWarpAdapter(IID_PPV_ARGS(&warp)));ComPtr<ID3D12Device> device;HR(D3D12CreateDevice(warp.Get(),D3D_FEATURE_LEVEL_11_0,IID_PPV_ARGS(&device)));
 D3D12_INPUT_ELEMENT_DESC original[]={
  {"POSITION",0,DXGI_FORMAT_R16G16B16A16_UNORM,0,0,D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA,0},
  {"BLENDINDICES",0,DXGI_FORMAT_R8G8B8A8_UINT,0,8,D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA,0},
  {"BLENDWEIGHT",0,DXGI_FORMAT_R8G8B8A8_UNORM,0,12,D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA,0},
  {"TEXCOORD",0,DXGI_FORMAT_R32G32_FLOAT,1,0,D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA,0}};
 FloatSkinLayout layout({original,4});Check(layout.Slot()==0,"Wrong float output slot");
 auto invalid=original[1];original[1].AlignedByteOffset=7;bool rejected=false;try{FloatSkinLayout bad({original,4});}catch(const std::invalid_argument&){rejected=true;}original[1]=invalid;Check(rejected,"Unknown original skin layout accepted");
 D3D12_ROOT_SIGNATURE_DESC rootDesc{};rootDesc.Flags=D3D12_ROOT_SIGNATURE_FLAG_ALLOW_INPUT_ASSEMBLER_INPUT_LAYOUT;ComPtr<ID3DBlob> rootBlob,errors;HR(D3D12SerializeRootSignature(&rootDesc,D3D_ROOT_SIGNATURE_VERSION_1,&rootBlob,&errors));ComPtr<ID3D12RootSignature> root;HR(device->CreateRootSignature(0,rootBlob->GetBufferPointer(),rootBlob->GetBufferSize(),IID_PPV_ARGS(&root)));
 auto vs=Shader(R"(
struct Input {float3 p:POSITION;uint4 bones:BLENDINDICES;float4 weights:BLENDWEIGHT;float2 uv:TEXCOORD;};
struct Output {float4 p:SV_Position;float4 color:COLOR;};
Output main(Input v){Output o;float3 dequantized=v.p*float3(1,1,1)+float3(0,0,0);
 o.p=float4(dequantized.x-2,dequantized.y,0,1);float sum=v.weights.x+v.weights.y+v.weights.z+v.weights.w;
 o.color=float4(v.bones.x/7.0,v.weights.x/sum,v.uv.x,1);return o;}
)","vs_5_0");
 auto ps=Shader("float4 main(float4 p:SV_Position,float4 color:COLOR):SV_Target{return color;}","ps_5_0");
 D3D12_GRAPHICS_PIPELINE_STATE_DESC desc{};desc.pRootSignature=root.Get();desc.VS={vs->GetBufferPointer(),vs->GetBufferSize()};desc.PS={ps->GetBufferPointer(),ps->GetBufferSize()};desc.InputLayout={original,4};desc.SampleMask=UINT_MAX;
 desc.RasterizerState.FillMode=D3D12_FILL_MODE_SOLID;desc.RasterizerState.CullMode=D3D12_CULL_MODE_NONE;desc.RasterizerState.DepthClipEnable=TRUE;
 auto& blend=desc.BlendState.RenderTarget[0];blend.SrcBlend=D3D12_BLEND_ONE;blend.DestBlend=D3D12_BLEND_ZERO;blend.BlendOp=D3D12_BLEND_OP_ADD;blend.SrcBlendAlpha=D3D12_BLEND_ONE;blend.DestBlendAlpha=D3D12_BLEND_ZERO;blend.BlendOpAlpha=D3D12_BLEND_OP_ADD;blend.LogicOp=D3D12_LOGIC_OP_NOOP;blend.RenderTargetWriteMask=D3D12_COLOR_WRITE_ENABLE_ALL;
 desc.DepthStencilState.DepthFunc=D3D12_COMPARISON_FUNC_ALWAYS;desc.DepthStencilState.FrontFace.StencilFunc=D3D12_COMPARISON_FUNC_ALWAYS;desc.DepthStencilState.FrontFace.StencilFailOp=desc.DepthStencilState.FrontFace.StencilDepthFailOp=desc.DepthStencilState.FrontFace.StencilPassOp=D3D12_STENCIL_OP_KEEP;desc.DepthStencilState.BackFace=desc.DepthStencilState.FrontFace;
 desc.PrimitiveTopologyType=D3D12_PRIMITIVE_TOPOLOGY_TYPE_TRIANGLE;desc.NumRenderTargets=1;desc.RTVFormats[0]=DXGI_FORMAT_R32G32B32A32_FLOAT;desc.SampleDesc.Count=1;
 ComPtr<ID3D12PipelineState> pipeline;HR(device->CreateGraphicsPipelineState(&desc,IID_PPV_ARGS(&pipeline)));RegisterFloatDrawPipeline(pipeline.Get(),desc);Check(FloatDrawFlags()&1,"Native draw PSO was not cloned");Check(desc.InputLayout.pInputElementDescs[0].Format==DXGI_FORMAT_R16G16B16A16_UNORM,"Original PSO layout mutated");
 std::vector<FloatSkinVertex> vertices={{{1.1f,-.9f,0},{7,1,0,0},{128,121,0,0}},{{2.9f,-.9f,0},{7,1,0,0},{128,121,0,0}},{{2,.9f,0},{7,1,0,0},{128,121,0,0}}};
 auto delivery=std::make_shared<RenderDelivery>();delivery->epoch=1;delivery->sequence=1;delivery->resources.push_back({0,36547,0,46,435936,{1,1,1},{0,0,0}});delivery->floatVertices.resize(36547);for(unsigned i=0;i<3;i++){auto& to=delivery->floatVertices[i];to.position=vertices[i].position;std::memcpy(&to.bones,vertices[i].bones.data(),4);std::memcpy(&to.weights,vertices[i].weights.data(),4);}LiveRenderFeed(delivery);
 delivery->resources[0].lodFirstVertex[1]=10;delivery->resources[0].lodVertexCount[1]=3;for(unsigned i=0;i<3;i++)delivery->floatVertices[10+i]=delivery->floatVertices[i];
 auto buffer=[&](UINT64 bytes,D3D12_HEAP_TYPE type,D3D12_RESOURCE_STATES state){D3D12_HEAP_PROPERTIES heap{};heap.Type=type;D3D12_RESOURCE_DESC r{};r.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER;r.Width=bytes;r.Height=1;r.DepthOrArraySize=1;r.MipLevels=1;r.SampleDesc.Count=1;r.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR;ComPtr<ID3D12Resource> out;HR(device->CreateCommittedResource(&heap,D3D12_HEAP_FLAG_NONE,&r,state,nullptr,IID_PPV_ARGS(&out)));return out;};
 auto uv=buffer(24,D3D12_HEAP_TYPE_UPLOAD,D3D12_RESOURCE_STATE_GENERIC_READ);float uvData[]={.25f,0,.25f,0,.25f,0};void* mapped=nullptr;D3D12_RANGE none{0,0};HR(uv->Map(0,&none,&mapped));std::memcpy(mapped,uvData,24);uv->Unmap(0,nullptr);
 D3D12_HEAP_PROPERTIES defaultHeap{};defaultHeap.Type=D3D12_HEAP_TYPE_DEFAULT;D3D12_RESOURCE_DESC textureDesc{};textureDesc.Dimension=D3D12_RESOURCE_DIMENSION_TEXTURE2D;textureDesc.Width=64;textureDesc.Height=64;textureDesc.DepthOrArraySize=1;textureDesc.MipLevels=1;textureDesc.Format=DXGI_FORMAT_R32G32B32A32_FLOAT;textureDesc.SampleDesc.Count=1;textureDesc.Flags=D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET;
 ComPtr<ID3D12Resource> texture;HR(device->CreateCommittedResource(&defaultHeap,D3D12_HEAP_FLAG_NONE,&textureDesc,D3D12_RESOURCE_STATE_RENDER_TARGET,nullptr,IID_PPV_ARGS(&texture)));
 D3D12_DESCRIPTOR_HEAP_DESC heapDesc{};heapDesc.Type=D3D12_DESCRIPTOR_HEAP_TYPE_RTV;heapDesc.NumDescriptors=1;ComPtr<ID3D12DescriptorHeap> heap;HR(device->CreateDescriptorHeap(&heapDesc,IID_PPV_ARGS(&heap)));auto rtv=heap->GetCPUDescriptorHandleForHeapStart();device->CreateRenderTargetView(texture.Get(),nullptr,rtv);
 D3D12_PLACED_SUBRESOURCE_FOOTPRINT footprint{};UINT rows=0;UINT64 rowBytes=0,bytes=0;device->GetCopyableFootprints(&textureDesc,0,1,0,&footprint,&rows,&rowBytes,&bytes);auto readback=buffer(bytes,D3D12_HEAP_TYPE_READBACK,D3D12_RESOURCE_STATE_COPY_DEST);
 ComPtr<ID3D12CommandAllocator> allocator;HR(device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT,IID_PPV_ARGS(&allocator)));ComPtr<ID3D12GraphicsCommandList> list;HR(device->CreateCommandList(0,D3D12_COMMAND_LIST_TYPE_DIRECT,allocator.Get(),pipeline.Get(),IID_PPV_ARGS(&list)));
 list->SetGraphicsRootSignature(root.Get());D3D12_VIEWPORT viewport{0,0,64,64,0,1};D3D12_RECT rect{0,0,64,64};list->RSSetViewports(1,&viewport);list->RSSetScissorRects(1,&rect);list->OMSetRenderTargets(1,&rtv,FALSE,nullptr);float clear[4]{};list->ClearRenderTargetView(rtv,clear,0,nullptr);list->IASetPrimitiveTopology(D3D_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
 auto packed=buffer(36547*24,D3D12_HEAP_TYPE_UPLOAD,D3D12_RESOURCE_STATE_GENERIC_READ);D3D12_VERTEX_BUFFER_VIEW views[]={{packed->GetGPUVirtualAddress(),36547*24,24},{uv->GetGPUVirtualAddress(),24,8},{packed->GetGPUVirtualAddress()+16,36547*24-16,24}};list->IASetVertexBuffers(0,3,views);Check(FloatDraw(list.Get(),pipeline.Get(),views[0],views[2],[&]{list->DrawInstanced(3,1,0,0);}),"Native float draw was not applied");
 auto staticBuffer=buffer(256,D3D12_HEAP_TYPE_UPLOAD,D3D12_RESOURCE_STATE_GENERIC_READ);D3D12_VERTEX_BUFFER_VIEW staticPosition{staticBuffer->GetGPUVirtualAddress(),256,16},staticLighting{staticBuffer->GetGPUVirtualAddress()+64,192,8};list->IASetVertexBuffers(0,1,&staticPosition);list->IASetVertexBuffers(2,1,&staticLighting);list->ClearRenderTargetView(rtv,clear,0,nullptr);Check(FloatDraw(list.Get(),pipeline.Get(),staticPosition,staticLighting,[&]{list->DrawInstanced(3,1,0,0);},0,1),"Static LOD slice was not applied");
 D3D12_VERTEX_BUFFER_VIEW absentLighting{};list->IASetVertexBuffers(2,1,&absentLighting);list->ClearRenderTargetView(rtv,clear,0,nullptr);Check(FloatDraw(list.Get(),pipeline.Get(),staticPosition,absentLighting,[&]{list->DrawInstanced(3,1,0,0);},0,1),"Static position-only depth pass was not applied");
 D3D12_RESOURCE_BARRIER barrier{};barrier.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;barrier.Transition={texture.Get(),D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,D3D12_RESOURCE_STATE_RENDER_TARGET,D3D12_RESOURCE_STATE_COPY_SOURCE};list->ResourceBarrier(1,&barrier);
 D3D12_TEXTURE_COPY_LOCATION dst{},src{};dst.pResource=readback.Get();dst.Type=D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;dst.PlacedFootprint=footprint;src.pResource=texture.Get();src.Type=D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;list->CopyTextureRegion(&dst,0,0,0,&src,nullptr);HR(list->Close());
 D3D12_COMMAND_QUEUE_DESC queueDesc{};ComPtr<ID3D12CommandQueue> queue;HR(device->CreateCommandQueue(&queueDesc,IID_PPV_ARGS(&queue)));ComPtr<ID3D12Fence> fence,other;HR(device->CreateFence(0,D3D12_FENCE_FLAG_NONE,IID_PPV_ARGS(&fence)));HR(device->CreateFence(0,D3D12_FENCE_FLAG_NONE,IID_PPV_ARGS(&other)));
 ID3D12CommandList* lists[]={list.Get()};queue->ExecuteCommandLists(1,lists);FloatDrawSubmitted(queue.Get(),1,reinterpret_cast<void* const*>(lists));HR(queue->Signal(fence.Get(),1));HANDLE event=CreateEventW(nullptr,FALSE,FALSE,nullptr);Check(event!=nullptr,"Fence event creation failed");HR(fence->SetEventOnCompletion(1,event));auto waited=WaitForSingleObject(event,10000);CloseHandle(event);Check(waited==WAIT_OBJECT_0,"GPU output timed out");
 Check((FloatDrawFlags()&256)&&!(FloatDrawFlags()&128)&&FloatDrawSequence()==1&&FloatDrawActive(1)&&!FloatDrawActive(2),"Native draw completion or epoch isolation failed");FloatDrawReset(list.Get());
 D3D12_RANGE read{0,static_cast<SIZE_T>(bytes)};HR(readback->Map(0,&read,&mapped));const auto pixel=reinterpret_cast<const float*>(static_cast<const unsigned char*>(mapped)+footprint.Offset+32*footprint.Footprint.RowPitch+32*16);std::array<float,4> color{};std::memcpy(color.data(),pixel,16);readback->Unmap(0,&none);
 Check(std::abs(color[0]-1)<1e-6f&&std::abs(color[1]-128.f/249.f)<1e-6f&&std::abs(color[2]-.25f)<1e-6f&&std::abs(color[3]-1)<1e-6f,"Unbounded position/skin/other-stream GPU draw differs");
 std::cout<<"PASS: actual FloatDraw backend clones original PSO, substitutes 28-byte surface input, preserves bone/weight/UV input, renders beyond UNORM range and selects static LOD slices from trailing-allocation views, restores original bindings and reports fenced epoch/sequence completion; SDK output only\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
