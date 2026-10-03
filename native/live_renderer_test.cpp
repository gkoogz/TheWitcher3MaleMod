#define NOMINMAX
#include "live_renderer.hpp"
#include "graphics_probe.hpp"
#include <d3d12.h>
#include <d3dcompiler.h>
#include <dxgi1_4.h>
#include <wrl/client.h>
#include <MinHook.h>
#include <iostream>
#include <cmath>
using Microsoft::WRL::ComPtr;
using namespace malemod::witcher;
static void Check(bool b,const char* text){if(!b)throw std::runtime_error(text);}
static void HR(HRESULT h){if(FAILED(h))throw std::runtime_error("SDK test HRESULT "+std::to_string(h));}
static ComPtr<ID3D12Resource> Buffer(ID3D12Device* d,unsigned bytes,D3D12_HEAP_TYPE heap,D3D12_RESOURCE_STATES state,const void* data=nullptr,bool uav=true){
 D3D12_HEAP_PROPERTIES hp{};hp.Type=heap;D3D12_RESOURCE_DESC desc{};desc.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER;desc.Width=bytes;desc.Height=1;desc.DepthOrArraySize=1;desc.MipLevels=1;desc.SampleDesc.Count=1;desc.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR;if(heap==D3D12_HEAP_TYPE_DEFAULT&&uav)desc.Flags=D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS;ComPtr<ID3D12Resource> b;HR(d->CreateCommittedResource(&hp,D3D12_HEAP_FLAG_NONE,&desc,state,nullptr,IID_PPV_ARGS(&b)));if(data){void* p;D3D12_RANGE none{0,0};HR(b->Map(0,&none,&p));std::memcpy(p,data,bytes);b->Unmap(0,nullptr);}return b;
}
static void Barrier(ID3D12GraphicsCommandList* l,ID3D12Resource* r,D3D12_RESOURCE_STATES a,D3D12_RESOURCE_STATES b){D3D12_RESOURCE_BARRIER t{};t.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;t.Transition={r,D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,a,b};l->ResourceBarrier(1,&t);}
int main(){try{
 HR(MH_Initialize()==MH_OK?S_OK:E_FAIL);Check(InitializeGraphicsProbe(),"Hook initialization failed");
 ComPtr<IDXGIFactory4> factory;ComPtr<IDXGIAdapter> warp;ComPtr<ID3D12Device> device;HR(CreateDXGIFactory1(IID_PPV_ARGS(&factory)));HR(factory->EnumWarpAdapter(IID_PPV_ARGS(&warp)));HR(D3D12CreateDevice(warp.Get(),D3D_FEATURE_LEVEL_11_0,IID_PPV_ARGS(&device)));
 ComPtr<ID3D12InfoQueue> unused;
 D3D12_DESCRIPTOR_RANGE range{D3D12_DESCRIPTOR_RANGE_TYPE_SRV,1,1,0,0};D3D12_ROOT_PARAMETER p[5]{};p[0].ParameterType=D3D12_ROOT_PARAMETER_TYPE_32BIT_CONSTANTS;p[0].Constants={0,0,4};p[1].ParameterType=D3D12_ROOT_PARAMETER_TYPE_UAV;p[1].Descriptor={0,0};p[2].ParameterType=D3D12_ROOT_PARAMETER_TYPE_SRV;p[2].Descriptor={0,0};p[3].ParameterType=D3D12_ROOT_PARAMETER_TYPE_CBV;p[3].Descriptor={1,0};p[4].ParameterType=D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;p[4].DescriptorTable={1,&range};D3D12_ROOT_SIGNATURE_DESC rd{5,p,0,nullptr,D3D12_ROOT_SIGNATURE_FLAG_NONE};ComPtr<ID3DBlob> blob,error;HR(D3D12SerializeRootSignature(&rd,D3D_ROOT_SIGNATURE_VERSION_1,&blob,&error));ComPtr<ID3D12RootSignature> root;HR(device->CreateRootSignature(0,blob->GetBufferPointer(),blob->GetBufferSize(),IID_PPV_ARGS(&root)));
 const char* shader="cbuffer A:register(b0){uint4 v;};cbuffer B:register(b1){uint4 b;};RWByteAddressBuffer o:register(u0);ByteAddressBuffer i:register(t0);ByteAddressBuffer t:register(t1);[numthreads(1,1,1)]void main(){o.Store4(0,v+uint4(i.Load(0),b.x,t.Load(0),0));}";
 HR(D3DCompile(shader,strlen(shader),"restore-sentinel",nullptr,nullptr,"main","cs_5_1",0,0,&blob,&error));D3D12_COMPUTE_PIPELINE_STATE_DESC pd{};pd.pRootSignature=root.Get();pd.CS={blob->GetBufferPointer(),blob->GetBufferSize()};ComPtr<ID3D12PipelineState> pipeline;HR(device->CreateComputePipelineState(&pd,IID_PPV_ARGS(&pipeline)));
 const unsigned n=36547;std::vector<PreSkinnedVertex> original(n);auto source=std::make_shared<std::vector<SourceRenderVertex>>(n);PoseMatrix identity{1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1};
 RenderPose pose{1,1,identity,std::vector<PoseMatrix>(46,identity)};pose.actorWorld[3]=100;pose.actorWorld[7]=-20;pose.actorWorld[11]=30;
 for(unsigned i=0;i<n;i++){auto& v=(*source)[i];v.reference={float(i)*1e-5f,.1f,.95f};v.position={v.reference[0]+1.5f,.2f,1.f};v.normal={0,0,1};v.tangent={1,0,0};v.sign=1;v.weights=255;v.calibration=i<16;original[i]={{v.reference[0],v.reference[1],v.reference[2],.375f},0x80000000|PackDirection({0,0,1},0),PackDirection({1,0,0},3)};}
 auto delivery=std::make_shared<RenderDelivery>();delivery->epoch=1;delivery->sequence=1;delivery->vertices=source;delivery->pose=pose;LiveRenderFeed(delivery);
 auto upload=Buffer(device.Get(),n*24,D3D12_HEAP_TYPE_UPLOAD,D3D12_RESOURCE_STATE_GENERIC_READ,original.data());auto target=Buffer(device.Get(),n*24,D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_COPY_DEST,nullptr,false);auto readback=Buffer(device.Get(),n*24,D3D12_HEAP_TYPE_READBACK,D3D12_RESOURCE_STATE_COPY_DEST);
 std::array<unsigned,64> inputs{};inputs[0]=33;inputs[4]=17;inputs[8]=11;auto input=Buffer(device.Get(),256,D3D12_HEAP_TYPE_UPLOAD,D3D12_RESOURCE_STATE_GENERIC_READ,inputs.data());auto sentinel=Buffer(device.Get(),16,D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_UNORDERED_ACCESS);auto sentinelRead=Buffer(device.Get(),16,D3D12_HEAP_TYPE_READBACK,D3D12_RESOURCE_STATE_COPY_DEST);
 D3D12_DESCRIPTOR_HEAP_DESC hd{};hd.Type=D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV;hd.NumDescriptors=1;hd.Flags=D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;ComPtr<ID3D12DescriptorHeap> heap;HR(device->CreateDescriptorHeap(&hd,IID_PPV_ARGS(&heap)));D3D12_SHADER_RESOURCE_VIEW_DESC srv{};srv.Format=DXGI_FORMAT_R32_TYPELESS;srv.ViewDimension=D3D12_SRV_DIMENSION_BUFFER;srv.Shader4ComponentMapping=D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;srv.Buffer.FirstElement=8;srv.Buffer.NumElements=4;srv.Buffer.Flags=D3D12_BUFFER_SRV_FLAG_RAW;device->CreateShaderResourceView(input.Get(),&srv,heap->GetCPUDescriptorHandleForHeapStart());
 ComPtr<ID3D12CommandAllocator> allocator;ComPtr<ID3D12GraphicsCommandList> list;HR(device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT,IID_PPV_ARGS(&allocator)));HR(device->CreateCommandList(0,D3D12_COMMAND_LIST_TYPE_DIRECT,allocator.Get(),pipeline.Get(),IID_PPV_ARGS(&list)));D3D12_COMMAND_QUEUE_DESC qd{};qd.Type=D3D12_COMMAND_LIST_TYPE_DIRECT;ComPtr<ID3D12CommandQueue> queue;HR(device->CreateCommandQueue(&qd,IID_PPV_ARGS(&queue)));ComPtr<ID3D12Fence> fence;HR(device->CreateFence(0,D3D12_FENCE_FLAG_NONE,IID_PPV_ARGS(&fence)));
 auto submit=[&](unsigned value){HR(list->Close());ID3D12CommandList* lists[]={list.Get()};queue->ExecuteCommandLists(1,lists);HR(queue->Signal(fence.Get(),value));auto event=CreateEventW(nullptr,FALSE,FALSE,nullptr);HR(fence->SetEventOnCompletion(value,event));Check(WaitForSingleObject(event,10000)==WAIT_OBJECT_0,"GPU timeout");CloseHandle(event);};
 auto bind=[&]{list->SetPipelineState(pipeline.Get());list->SetComputeRootSignature(root.Get());ID3D12DescriptorHeap* heaps[]={heap.Get()};list->SetDescriptorHeaps(1,heaps);list->SetComputeRoot32BitConstant(0,7,0);unsigned two[]={8,9};list->SetComputeRoot32BitConstants(0,2,two,1);list->SetComputeRoot32BitConstant(0,10,3);list->SetComputeRootUnorderedAccessView(1,sentinel->GetGPUVirtualAddress());list->SetComputeRootShaderResourceView(2,input->GetGPUVirtualAddress());list->SetComputeRootConstantBufferView(3,input->GetGPUVirtualAddress()+0);list->SetComputeRootDescriptorTable(4,heap->GetGPUDescriptorHandleForHeapStart());};
 // CBV uses inputs[0]=33, distinct from table's value 11.
 list->CopyBufferRegion(target.Get(),0,upload.Get(),0,n*24);Barrier(list.Get(),target.Get(),D3D12_RESOURCE_STATE_COPY_DEST,D3D12_RESOURCE_STATE_STREAM_OUT);bind();LiveRenderOwnedStream(target->GetGPUVirtualAddress(),n*24,24);
 Barrier(list.Get(),target.Get(),D3D12_RESOURCE_STATE_STREAM_OUT,D3D12_RESOURCE_STATE_COPY_SOURCE);list->Dispatch(1,1,1);Barrier(list.Get(),sentinel.Get(),D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_STATE_COPY_SOURCE);list->CopyBufferRegion(sentinelRead.Get(),0,sentinel.Get(),0,16);submit(1);
 void* data=nullptr;D3D12_RANGE bytes{0,16};HR(sentinelRead->Map(0,&bytes,&data));auto values=static_cast<unsigned*>(data);Check(values[0]==40&&values[1]==41&&values[2]==20&&values[3]==10,"Compute root state was not restored");D3D12_RANGE none{0,0};sentinelRead->Unmap(0,&none);
 HR(allocator->Reset());HR(list->Reset(allocator.Get(),pipeline.Get()));bind();Barrier(list.Get(),target.Get(),D3D12_RESOURCE_STATE_COPY_SOURCE,D3D12_RESOURCE_STATE_STREAM_OUT);Barrier(list.Get(),target.Get(),D3D12_RESOURCE_STATE_STREAM_OUT,D3D12_RESOURCE_STATE_COPY_SOURCE);list->CopyBufferRegion(readback.Get(),0,target.Get(),0,n*24);submit(2);
 D3D12_RANGE all{0,n*24};HR(readback->Map(0,&all,&data));auto rows=static_cast<PreSkinnedVertex*>(data);for(unsigned i=0;i<n;i++){Check(std::abs(rows[i].position[0]-(*source)[i].position[0])<2e-6f,"Complete float surface was not written");Check(rows[i].position[3]==.375f,"Engine position metadata changed");Check((rows[i].normal>>30)==2,"Engine normal metadata changed");Check((rows[i].tangent>>30)==3,"Tangent handedness lost");}readback->Unmap(0,&none);
 Check((LiveRenderFlags()&91)==91&&!(LiveRenderFlags()&128),"Renderer did not validate actor-local space and write surface");
 // The game submits dedicated skin-transition command lists without an
 // initial PSO. Exercise that actual scheduling shape, not just a bound
 // compute dispatch, and require the next complete surface to reach the GPU.
 auto changed=std::make_shared<std::vector<SourceRenderVertex>>(*source);
 for(auto& vertex:*changed)vertex.position[0]+=2;
 auto next=std::make_shared<RenderDelivery>(*delivery);next->sequence=2;next->vertices=changed;LiveRenderFeed(next);
 HR(allocator->Reset());HR(list->Reset(allocator.Get(),nullptr));
 Barrier(list.Get(),target.Get(),D3D12_RESOURCE_STATE_COPY_SOURCE,D3D12_RESOURCE_STATE_STREAM_OUT);
 Barrier(list.Get(),target.Get(),D3D12_RESOURCE_STATE_STREAM_OUT,D3D12_RESOURCE_STATE_COPY_SOURCE);
 list->CopyBufferRegion(readback.Get(),0,target.Get(),0,n*24);submit(3);
 HR(readback->Map(0,&all,&data));rows=static_cast<PreSkinnedVertex*>(data);
 for(unsigned i=0;i<n;i++)Check(std::abs(rows[i].position[0]-(*changed)[i].position[0])<2e-6f,"Transition-only list did not write the next surface");
 readback->Unmap(0,&none);
 Check(LiveRenderSequence()==2,"GPU completion did not identify the updated source sequence");
 // Retirement after Reset must keep uploads until submitted queue fences finish.
 HR(allocator->Reset());HR(list->Reset(allocator.Get(),pipeline.Get()));HR(list->Close());Check(LiveRenderActive(1)&&!LiveRenderActive(2),"Wrong character epoch became active");
 MH_DisableHook(MH_ALL_HOOKS);MH_Uninitialize();ReleaseGraphicsProbeOwnedResources();
 std::cout<<"PASS: actual D3D12 WARP skin-output replacement of 36547 vertices, protected-point space validation, unbounded positions, metadata preservation, compute root/PSO/descriptor restoration, fence retirement and epoch gating\n";return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';MH_DisableHook(MH_ALL_HOOKS);MH_Uninitialize();return 1;}}
