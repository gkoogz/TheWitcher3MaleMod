#define NOMINMAX
#include "float_vertex_pipeline.hpp"
#include "fluid_renderer.hpp"
#include "clinical_service.hpp"
#include <fstream>
#include "live_renderer.hpp"
#include <dxgi1_6.h>
#include <d3dcompiler.h>
#include <iostream>
using Microsoft::WRL::ComPtr;
using namespace malemod::witcher;
static void Check(bool b,const char* s){if(!b)throw std::runtime_error(s);}
static void HR(HRESULT h){if(FAILED(h))throw std::runtime_error("D3D12 output test failed HRESULT="+std::to_string(h));}
static ComPtr<ID3DBlob> Shader(const char* source,const char* target){ComPtr<ID3DBlob> b,e;auto h=D3DCompile(source,std::strlen(source),nullptr,nullptr,nullptr,"main",target,D3DCOMPILE_ENABLE_STRICTNESS,0,&b,&e);if(FAILED(h)){if(e)std::cerr<<static_cast<const char*>(e->GetBufferPointer());HR(h);}return b;}
int main(int argc,char** argv){try{
 ComPtr<IDXGIFactory4> factory;HR(CreateDXGIFactory1(IID_PPV_ARGS(&factory)));ComPtr<IDXGIAdapter> warp;if(argc==2&&!std::strcmp(argv[1],"--hardware")){ComPtr<IDXGIFactory6> latestFactory;HR(factory.As(&latestFactory));HR(latestFactory->EnumAdapterByGpuPreference(0,DXGI_GPU_PREFERENCE_HIGH_PERFORMANCE,IID_PPV_ARGS(&warp)));}else HR(factory->EnumWarpAdapter(IID_PPV_ARGS(&warp)));ComPtr<ID3D12Device> device;HR(D3D12CreateDevice(warp.Get(),D3D_FEATURE_LEVEL_11_0,IID_PPV_ARGS(&device)));
 ComPtr<IDXGIAdapter1> adapter;HR(warp.As(&adapter));DXGI_ADAPTER_DESC1 adapterInfo{};HR(adapter->GetDesc1(&adapterInfo));if(argc==2&&!std::strcmp(argv[1],"--hardware"))Check(!(adapterInfo.Flags&DXGI_ADAPTER_FLAG_SOFTWARE),"Hardware fixture selected a software adapter");std::cout<<"Adapter vendor="<<adapterInfo.VendorId<<" device="<<adapterInfo.DeviceId<<" software="<<bool(adapterInfo.Flags&DXGI_ADAPTER_FLAG_SOFTWARE)<<'\n';
 D3D12_INPUT_ELEMENT_DESC original[]={
  {"POSITION",0,DXGI_FORMAT_R16G16B16A16_UNORM,0,0,D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA,0},
  {"NORMAL",0,DXGI_FORMAT_R10G10B10A2_UNORM,2,0,D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA,0},
  {"TANGENT",0,DXGI_FORMAT_R10G10B10A2_UNORM,2,4,D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA,0},
  {"TEXCOORD",0,DXGI_FORMAT_R16G16_FLOAT,1,0,D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA,0},
  {"COLOR",0,DXGI_FORMAT_R8G8B8A8_UNORM,3,0,D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA,0},
  {"TEXCOORD",1,DXGI_FORMAT_R16G16_FLOAT,3,4,D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA,0}};
 auto contract=std::filesystem::temp_directory_path()/("malemod-fluid-sdk-"+std::to_string(GetCurrentProcessId())+".bin");
 {std::ofstream f(contract,std::ios::binary);f.write("MMFLD001",8);for(int i=0;i<2;i++){float scale[3]={2,2,2},bias[3]={.5f,.5f,.5f};unsigned bytes=384;f.write(reinterpret_cast<char*>(scale),12);f.write(reinterpret_cast<char*>(bias),12);f.write(reinterpret_cast<char*>(&bytes),4);}}
 FluidRendererConfigure(contract);std::filesystem::remove(contract);FluidRendererOrigin({0,0,0},true);
 D3D12_ROOT_SIGNATURE_DESC rootDesc{};rootDesc.Flags=D3D12_ROOT_SIGNATURE_FLAG_ALLOW_INPUT_ASSEMBLER_INPUT_LAYOUT;ComPtr<ID3DBlob> rootBlob,errors;HR(D3D12SerializeRootSignature(&rootDesc,D3D_ROOT_SIGNATURE_VERSION_1,&rootBlob,&errors));ComPtr<ID3D12RootSignature> root;HR(device->CreateRootSignature(0,rootBlob->GetBufferPointer(),rootBlob->GetBufferSize(),IID_PPV_ARGS(&root)));
 auto vs=Shader(R"(
struct Input {float3 p:POSITION;float4 n:NORMAL;float4 t:TANGENT;float2 uv:TEXCOORD;float4 color:COLOR;float2 uv2:TEXCOORD1;};
struct Output {float4 p:SV_Position;float4 color:COLOR;};
Output main(Input v){Output o;float3 dequantized=v.p*float3(2,2,2)+float3(.5,.5,.5);
 o.p=float4(dequantized.x-2,dequantized.y,0,1);o.color=float4(v.n.z,v.uv.x,v.color.a,1);return o;}
)","vs_5_0");
 auto ps=Shader("float4 main(float4 p:SV_Position,float4 color:COLOR):SV_Target{return color;}","ps_5_0");
 D3D12_GRAPHICS_PIPELINE_STATE_DESC desc{};desc.pRootSignature=root.Get();desc.VS={vs->GetBufferPointer(),vs->GetBufferSize()};desc.PS={ps->GetBufferPointer(),ps->GetBufferSize()};desc.InputLayout={original,6};desc.SampleMask=UINT_MAX;
 desc.RasterizerState.FillMode=D3D12_FILL_MODE_SOLID;desc.RasterizerState.CullMode=D3D12_CULL_MODE_NONE;desc.RasterizerState.DepthClipEnable=TRUE;
 auto& blend=desc.BlendState.RenderTarget[0];blend.SrcBlend=D3D12_BLEND_ONE;blend.DestBlend=D3D12_BLEND_ZERO;blend.BlendOp=D3D12_BLEND_OP_ADD;blend.SrcBlendAlpha=D3D12_BLEND_ONE;blend.DestBlendAlpha=D3D12_BLEND_ZERO;blend.BlendOpAlpha=D3D12_BLEND_OP_ADD;blend.LogicOp=D3D12_LOGIC_OP_NOOP;blend.RenderTargetWriteMask=D3D12_COLOR_WRITE_ENABLE_ALL;
 desc.DepthStencilState.DepthFunc=D3D12_COMPARISON_FUNC_ALWAYS;desc.DepthStencilState.FrontFace.StencilFunc=D3D12_COMPARISON_FUNC_ALWAYS;desc.DepthStencilState.FrontFace.StencilFailOp=desc.DepthStencilState.FrontFace.StencilDepthFailOp=desc.DepthStencilState.FrontFace.StencilPassOp=D3D12_STENCIL_OP_KEEP;desc.DepthStencilState.BackFace=desc.DepthStencilState.FrontFace;
 desc.PrimitiveTopologyType=D3D12_PRIMITIVE_TOPOLOGY_TYPE_TRIANGLE;desc.NumRenderTargets=1;desc.RTVFormats[0]=DXGI_FORMAT_R32G32B32A32_FLOAT;desc.SampleDesc.Count=1;
 ComPtr<ID3D12PipelineState> pipeline;HR(device->CreateGraphicsPipelineState(&desc,IID_PPV_ARGS(&pipeline)));RegisterFluidPipeline(pipeline.Get(),desc);Check(desc.InputLayout.pInputElementDescs[0].Format==DXGI_FORMAT_R16G16B16A16_UNORM,"Original fluid layout mutated");
 auto delivery=std::make_shared<ClinicalDelivery>();delivery->epoch=1;delivery->serial=1;
 for(auto p:std::vector<malemod::V3>{{1.1f,-.9f,0},{2.9f,-.9f,0},{2,.9f,0}}){malemod::clinical::teaching::LiquidVertex v{};v.p=p;v.n={0,0,1};delivery->mesh.vertices.push_back(v);delivery->deposits.vertices.push_back({p,{0,0,1},.75f});}
 delivery->mesh.indices={0,1,2,0,1,2};delivery->mesh.opaqueIndices=3;delivery->deposits.indices={0,1,2};FluidRendererFeed(delivery,1);FluidRendererFrameBoundary();
 auto buffer=[&](UINT64 bytes,D3D12_HEAP_TYPE type,D3D12_RESOURCE_STATES state){D3D12_HEAP_PROPERTIES heap{};heap.Type=type;D3D12_RESOURCE_DESC r{};r.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER;r.Width=bytes;r.Height=1;r.DepthOrArraySize=1;r.MipLevels=1;r.SampleDesc.Count=1;r.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR;ComPtr<ID3D12Resource> out;HR(device->CreateCommittedResource(&heap,D3D12_HEAP_FLAG_NONE,&r,state,nullptr,IID_PPV_ARGS(&out)));return out;};
 auto uv=buffer(24,D3D12_HEAP_TYPE_UPLOAD,D3D12_RESOURCE_STATE_GENERIC_READ);float uvData[]={.25f,0,.25f,0,.25f,0};void* mapped=nullptr;D3D12_RANGE none{0,0};HR(uv->Map(0,&none,&mapped));std::memcpy(mapped,uvData,24);uv->Unmap(0,nullptr);
 D3D12_HEAP_PROPERTIES defaultHeap{};defaultHeap.Type=D3D12_HEAP_TYPE_DEFAULT;D3D12_RESOURCE_DESC textureDesc{};textureDesc.Dimension=D3D12_RESOURCE_DIMENSION_TEXTURE2D;textureDesc.Width=64;textureDesc.Height=64;textureDesc.DepthOrArraySize=1;textureDesc.MipLevels=1;textureDesc.Format=DXGI_FORMAT_R32G32B32A32_FLOAT;textureDesc.SampleDesc.Count=1;textureDesc.Flags=D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET;
 ComPtr<ID3D12Resource> texture;HR(device->CreateCommittedResource(&defaultHeap,D3D12_HEAP_FLAG_NONE,&textureDesc,D3D12_RESOURCE_STATE_RENDER_TARGET,nullptr,IID_PPV_ARGS(&texture)));
 D3D12_DESCRIPTOR_HEAP_DESC heapDesc{};heapDesc.Type=D3D12_DESCRIPTOR_HEAP_TYPE_RTV;heapDesc.NumDescriptors=1;ComPtr<ID3D12DescriptorHeap> heap;HR(device->CreateDescriptorHeap(&heapDesc,IID_PPV_ARGS(&heap)));auto rtv=heap->GetCPUDescriptorHandleForHeapStart();device->CreateRenderTargetView(texture.Get(),nullptr,rtv);
 D3D12_PLACED_SUBRESOURCE_FOOTPRINT footprint{};UINT rows=0;UINT64 rowBytes=0,bytes=0;device->GetCopyableFootprints(&textureDesc,0,1,0,&footprint,&rows,&rowBytes,&bytes);auto readback=buffer(bytes,D3D12_HEAP_TYPE_READBACK,D3D12_RESOURCE_STATE_COPY_DEST);
 ComPtr<ID3D12CommandAllocator> allocator;HR(device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT,IID_PPV_ARGS(&allocator)));ComPtr<ID3D12GraphicsCommandList> list;HR(device->CreateCommandList(0,D3D12_COMMAND_LIST_TYPE_DIRECT,allocator.Get(),pipeline.Get(),IID_PPV_ARGS(&list)));
 list->SetGraphicsRootSignature(root.Get());D3D12_VIEWPORT viewport{0,0,64,64,0,1};D3D12_RECT rect{0,0,64,64};list->RSSetViewports(1,&viewport);list->RSSetScissorRects(1,&rect);list->OMSetRenderTargets(1,&rtv,FALSE,nullptr);float clear[4]{};list->ClearRenderTargetView(rtv,clear,0,nullptr);list->IASetPrimitiveTopology(D3D_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
 auto packed=buffer(256,D3D12_HEAP_TYPE_UPLOAD,D3D12_RESOURCE_STATE_GENERIC_READ);
 std::array<D3D12_VERTEX_BUFFER_VIEW,32> views{};for(unsigned i=0;i<4;i++)views[i]={packed->GetGPUVirtualAddress(),256,8};D3D12_INDEX_BUFFER_VIEW savedIndex{packed->GetGPUVirtualAddress(),256,DXGI_FORMAT_R16_UINT};list->IASetVertexBuffers(0,4,views.data());list->IASetIndexBuffer(&savedIndex);
 unsigned draws=0;for(unsigned kind=0;kind<2;kind++){list->ClearRenderTargetView(rtv,clear,0,nullptr);Check(FluidDraw(list.Get(),pipeline.Get(),views,savedIndex,kind,[&](unsigned count,unsigned first){++draws;Check(count==(kind?6:3)&&first==(kind?3:0),"Fluid material index slice differs");list->DrawIndexedInstanced(count,1,first,0,0);}),"Fluid draw not consumed");}
 Check(draws==2,"Both native material carriers were not drawn");
 D3D12_RESOURCE_BARRIER barrier{};barrier.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;barrier.Transition={texture.Get(),D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,D3D12_RESOURCE_STATE_RENDER_TARGET,D3D12_RESOURCE_STATE_COPY_SOURCE};list->ResourceBarrier(1,&barrier);
 D3D12_TEXTURE_COPY_LOCATION dst{},src{};dst.pResource=readback.Get();dst.Type=D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;dst.PlacedFootprint=footprint;src.pResource=texture.Get();src.Type=D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;list->CopyTextureRegion(&dst,0,0,0,&src,nullptr);HR(list->Close());
 D3D12_COMMAND_QUEUE_DESC queueDesc{};ComPtr<ID3D12CommandQueue> queue;HR(device->CreateCommandQueue(&queueDesc,IID_PPV_ARGS(&queue)));ComPtr<ID3D12Fence> fence,other;HR(device->CreateFence(0,D3D12_FENCE_FLAG_NONE,IID_PPV_ARGS(&fence)));HR(device->CreateFence(0,D3D12_FENCE_FLAG_NONE,IID_PPV_ARGS(&other)));
 ID3D12CommandList* lists[]={list.Get()};queue->ExecuteCommandLists(1,lists);FluidDrawSubmitted(queue.Get(),1,reinterpret_cast<void* const*>(lists));HR(queue->Signal(fence.Get(),1));HANDLE event=CreateEventW(nullptr,FALSE,FALSE,nullptr);Check(event!=nullptr,"Fence event creation failed");HR(fence->SetEventOnCompletion(1,event));auto waited=WaitForSingleObject(event,10000);CloseHandle(event);Check(waited==WAIT_OBJECT_0,"GPU output timed out");
 Check((FluidDrawFlags()&29)==29&&!(FluidDrawFlags()&128)&&FluidDrawPublications()==1,"Fluid output or publication isolation failed");FluidDrawReset(list.Get());
 D3D12_RANGE read{0,static_cast<SIZE_T>(bytes)};HR(readback->Map(0,&read,&mapped));const auto pixel=reinterpret_cast<const float*>(static_cast<const unsigned char*>(mapped)+footprint.Offset+32*footprint.Footprint.RowPitch+32*16);std::array<float,4> color{};std::memcpy(color.data(),pixel,16);readback->Unmap(0,&none);
 Check(std::abs(color[0]-1)<1e-6f&&std::abs(color[1]-.5f)<1e-6f&&std::abs(color[2]-191.f/255.f)<1e-6f&&std::abs(color[3]-1)<1e-6f,"Fluid quantization, UV, normal, floor alpha or native material slice differs");
 // A later clinical publication must not make a second scene pass disagree
 // with the first one. Its translated mesh becomes visible next SDK frame.
 auto shifted=std::make_shared<ClinicalDelivery>(*delivery);shifted->serial=2;for(auto& v:shifted->mesh.vertices)v.p.x+=4;for(auto& v:shifted->deposits.vertices)v.p.x+=4;FluidRendererOrigin({1,0,0},true);FluidRendererFeed(shifted,1);
 UINT64 fenceValue=1;
 auto renderCenter=[&](){
  HR(allocator->Reset());HR(list->Reset(allocator.Get(),pipeline.Get()));
  list->SetGraphicsRootSignature(root.Get());list->RSSetViewports(1,&viewport);list->RSSetScissorRects(1,&rect);list->OMSetRenderTargets(1,&rtv,FALSE,nullptr);list->IASetPrimitiveTopology(D3D_PRIMITIVE_TOPOLOGY_TRIANGLELIST);list->IASetVertexBuffers(0,4,views.data());list->IASetIndexBuffer(&savedIndex);
  std::swap(barrier.Transition.StateBefore,barrier.Transition.StateAfter);list->ResourceBarrier(1,&barrier);list->ClearRenderTargetView(rtv,clear,0,nullptr);
  Check(FluidDraw(list.Get(),pipeline.Get(),views,savedIndex,1,[&](unsigned count,unsigned first){list->DrawIndexedInstanced(count,1,first,0,0);}),"Additional native fluid pass not consumed");
  std::swap(barrier.Transition.StateBefore,barrier.Transition.StateAfter);list->ResourceBarrier(1,&barrier);list->CopyTextureRegion(&dst,0,0,0,&src,nullptr);HR(list->Close());queue->ExecuteCommandLists(1,lists);FluidDrawSubmitted(queue.Get(),1,reinterpret_cast<void* const*>(lists));HR(queue->Signal(fence.Get(),++fenceValue));
  HANDLE done=CreateEventW(nullptr,FALSE,FALSE,nullptr);Check(done!=nullptr,"Additional fluid fence event unavailable");HR(fence->SetEventOnCompletion(fenceValue,done));auto status=WaitForSingleObject(done,10000);CloseHandle(done);Check(status==WAIT_OBJECT_0,"Additional fluid pass timed out");FluidDrawReset(list.Get());
  HR(readback->Map(0,&read,&mapped));std::array<float,4> result{};std::memcpy(result.data(),static_cast<const unsigned char*>(mapped)+footprint.Offset+32*footprint.Footprint.RowPitch+32*16,16);readback->Unmap(0,&none);return result;
 };
 auto sameFrame=renderCenter();Check(sameFrame==color&&FluidDrawPublications()==1,"Worker update changed a later pass within the SDK frame");
 FluidRendererFrameBoundary();auto nextFrame=renderCenter();Check(nextFrame==std::array<float,4>{}&&FluidDrawPublications()==2,"Next SDK frame failed to adopt translated clinical mesh");
 auto character=std::make_shared<ClinicalDelivery>(*delivery);character->epoch=2;character->serial=3;FluidRendererOrigin({0,0,0},true);FluidRendererFeed(character,1);auto newCharacter=renderCenter();Check(newCharacter==color&&FluidDrawPublications()==3,"New character reused previous epoch's latched liquid or carrier origin");
 // Read eight input components from the actual LAST upload vertex. Triangle
 // interpolation hides a missing final record; WARP also accepts the old
 // partial-stride views that AMD treats as out of bounds. This point exercises
 // normal/tangent, UV and color streams through the production FluidDraw.
 auto pointVS=Shader(R"(
struct Input {float3 p:POSITION;float4 n:NORMAL;float4 t:TANGENT;float2 uv:TEXCOORD;float4 color:COLOR;float2 uv2:TEXCOORD1;};
struct Output {float4 p:SV_Position;float4 a:COLOR0;float4 b:COLOR1;};
Output main(Input v){Output o;o.p=float4(0,0,0,1);o.a=v.n;o.b=float4(v.t.w,v.uv.x,v.color.a,v.uv2.x);return o;}
)","vs_5_0");
 auto pointPS=Shader("void main(float4 p:SV_Position,float4 a:COLOR0,float4 b:COLOR1,out float4 x:SV_Target0,out float4 y:SV_Target1){x=a;y=b;}","ps_5_0");
 auto pointDesc=desc;pointDesc.VS={pointVS->GetBufferPointer(),pointVS->GetBufferSize()};pointDesc.PS={pointPS->GetBufferPointer(),pointPS->GetBufferSize()};pointDesc.PrimitiveTopologyType=D3D12_PRIMITIVE_TOPOLOGY_TYPE_POINT;pointDesc.NumRenderTargets=2;pointDesc.RTVFormats[1]=DXGI_FORMAT_R32G32B32A32_FLOAT;pointDesc.BlendState.IndependentBlendEnable=TRUE;pointDesc.BlendState.RenderTarget[1]=pointDesc.BlendState.RenderTarget[0];ComPtr<ID3D12PipelineState> pointPipeline;HR(device->CreateGraphicsPipelineState(&pointDesc,IID_PPV_ARGS(&pointPipeline)));RegisterFluidPipeline(pointPipeline.Get(),pointDesc);
 auto pointTextureDesc=textureDesc;pointTextureDesc.Width=pointTextureDesc.Height=1;std::array<ComPtr<ID3D12Resource>,2> pointTextures,pointReadbacks;std::array<D3D12_PLACED_SUBRESOURCE_FOOTPRINT,2> pointFootprints;std::array<UINT64,2> pointBytes{};D3D12_DESCRIPTOR_HEAP_DESC pointHeapDesc=heapDesc;pointHeapDesc.NumDescriptors=2;ComPtr<ID3D12DescriptorHeap> pointHeap;HR(device->CreateDescriptorHeap(&pointHeapDesc,IID_PPV_ARGS(&pointHeap)));std::array<D3D12_CPU_DESCRIPTOR_HANDLE,2> pointTargets{};const auto pointIncrement=device->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_RTV);
 for(unsigned i=0;i<2;i++){HR(device->CreateCommittedResource(&defaultHeap,D3D12_HEAP_FLAG_NONE,&pointTextureDesc,D3D12_RESOURCE_STATE_RENDER_TARGET,nullptr,IID_PPV_ARGS(&pointTextures[i])));pointTargets[i]={pointHeap->GetCPUDescriptorHandleForHeapStart().ptr+i*pointIncrement};device->CreateRenderTargetView(pointTextures[i].Get(),nullptr,pointTargets[i]);device->GetCopyableFootprints(&pointTextureDesc,0,1,0,&pointFootprints[i],&rows,&rowBytes,&pointBytes[i]);pointReadbacks[i]=buffer(pointBytes[i],D3D12_HEAP_TYPE_READBACK,D3D12_RESOURCE_STATE_COPY_DEST);}
 HR(allocator->Reset());HR(list->Reset(allocator.Get(),pointPipeline.Get()));list->SetGraphicsRootSignature(root.Get());D3D12_VIEWPORT pointViewport{0,0,1,1,0,1};D3D12_RECT pointRect{0,0,1,1};list->RSSetViewports(1,&pointViewport);list->RSSetScissorRects(1,&pointRect);list->OMSetRenderTargets(2,pointTargets.data(),FALSE,nullptr);for(auto target:pointTargets)list->ClearRenderTargetView(target,clear,0,nullptr);list->IASetPrimitiveTopology(D3D_PRIMITIVE_TOPOLOGY_POINTLIST);list->IASetVertexBuffers(0,4,views.data());list->IASetIndexBuffer(&savedIndex);
 unsigned pointDraws=0;Check(FluidDraw(list.Get(),pointPipeline.Get(),views,savedIndex,1,[&](unsigned,unsigned){++pointDraws;list->DrawInstanced(1,1,UINT(character->mesh.vertices.size()+character->deposits.vertices.size()-1),0);}),"Last clinical vertex point not consumed");Check(pointDraws==1,"Last clinical vertex point was suppressed");
 for(unsigned i=0;i<2;i++){D3D12_RESOURCE_BARRIER pointBarrier{};pointBarrier.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;pointBarrier.Transition={pointTextures[i].Get(),D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,D3D12_RESOURCE_STATE_RENDER_TARGET,D3D12_RESOURCE_STATE_COPY_SOURCE};list->ResourceBarrier(1,&pointBarrier);D3D12_TEXTURE_COPY_LOCATION pointDst{},pointSrc{};pointDst.pResource=pointReadbacks[i].Get();pointDst.Type=D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;pointDst.PlacedFootprint=pointFootprints[i];pointSrc.pResource=pointTextures[i].Get();pointSrc.Type=D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;list->CopyTextureRegion(&pointDst,0,0,0,&pointSrc,nullptr);}
 HR(list->Close());queue->ExecuteCommandLists(1,lists);FluidDrawSubmitted(queue.Get(),1,reinterpret_cast<void* const*>(lists));HR(queue->Signal(fence.Get(),++fenceValue));HANDLE pointDone=CreateEventW(nullptr,FALSE,FALSE,nullptr);Check(pointDone!=nullptr,"Last vertex fence event unavailable");HR(fence->SetEventOnCompletion(fenceValue,pointDone));auto pointStatus=WaitForSingleObject(pointDone,10000);CloseHandle(pointDone);Check(pointStatus==WAIT_OBJECT_0,"Last clinical vertex point timed out");FluidDrawReset(list.Get());
 const std::array<float,8> expectedLast{512.f/1023,512.f/1023,1,1.f/3,1,.5f,191.f/255,0};std::array<float,8> actualLast{};for(unsigned i=0;i<2;i++){D3D12_RANGE pointRead{0,SIZE_T(pointBytes[i])};HR(pointReadbacks[i]->Map(0,&pointRead,&mapped));std::memcpy(actualLast.data()+i*4,static_cast<const unsigned char*>(mapped)+pointFootprints[i].Offset,16);pointReadbacks[i]->Unmap(0,&none);}for(unsigned i=0;i<8;i++)if(!std::isfinite(actualLast[i])||std::abs(actualLast[i]-expectedLast[i])>=1e-6f)throw std::runtime_error("LAST clinical vertex normal/tangent/UV/color component "+std::to_string(i)+" differs: got "+std::to_string(actualLast[i])+" expected "+std::to_string(expectedLast[i]));
 FluidRendererFeed({},1);unsigned emptyDraws=0;Check(FluidDraw(list.Get(),pipeline.Get(),views,savedIndex,1,[&](unsigned,unsigned){++emptyDraws;}),"Empty fluid feed not suppressed");Check(emptyDraws==0,"Empty feed rendered a retained frame");
 std::cout<<"PASS native rigid fluid draw: unclamped source-world positions, native dequantization, packed lighting/UV/color, opaque and clear/floor slices, fenced uploads and restored bindings; SDK frame coherence, next-frame adoption and empty suppression; LAST vertex eight-component hardware input bounds; SDK output only\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
