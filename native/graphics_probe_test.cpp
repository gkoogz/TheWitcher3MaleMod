// SDK smoke test in an owned process. No game, native assets or GPU submission.
#define NOMINMAX
#include <windows.h>
#include <d3d12.h>
#include <dxgi1_4.h>
#include <wrl/client.h>
#include <MinHook.h>
#include <cstdio>
#include <initializer_list>
#include "graphics_probe.hpp"
using Microsoft::WRL::ComPtr;
int main(){
 if(MH_Initialize()!=MH_OK||!malemod::witcher::InitializeGraphicsProbe())return 1;
 ComPtr<IDXGIFactory4> factory;ComPtr<IDXGIAdapter> warp;ComPtr<ID3D12Device> device;
 if(FAILED(CreateDXGIFactory1(IID_PPV_ARGS(&factory)))||FAILED(factory->EnumWarpAdapter(IID_PPV_ARGS(&warp)))||FAILED(D3D12CreateDevice(warp.Get(),D3D_FEATURE_LEVEL_11_0,IID_PPV_ARGS(&device))))return 2;
 D3D12_RESOURCE_DESC desc{};desc.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER;desc.Width=4096;desc.Height=1;desc.DepthOrArraySize=1;desc.MipLevels=1;desc.SampleDesc.Count=1;desc.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
 D3D12_HEAP_PROPERTIES heap{};heap.Type=D3D12_HEAP_TYPE_UPLOAD;
 ComPtr<ID3D12Resource> source,destination;
 if(FAILED(device->CreateCommittedResource(&heap,D3D12_HEAP_FLAG_NONE,&desc,D3D12_RESOURCE_STATE_GENERIC_READ,nullptr,IID_PPV_ARGS(&source))))return 3;
 heap.Type=D3D12_HEAP_TYPE_DEFAULT;
 if(FAILED(device->CreateCommittedResource(&heap,D3D12_HEAP_FLAG_NONE,&desc,D3D12_RESOURCE_STATE_COPY_DEST,nullptr,IID_PPV_ARGS(&destination))))return 4;
 for(auto type:{D3D12_COMMAND_LIST_TYPE_COPY,D3D12_COMMAND_LIST_TYPE_DIRECT}){
  ComPtr<ID3D12CommandAllocator> allocator;ComPtr<ID3D12GraphicsCommandList> list;
  if(FAILED(device->CreateCommandAllocator(type,IID_PPV_ARGS(&allocator)))||FAILED(device->CreateCommandList(0,type,allocator.Get(),nullptr,IID_PPV_ARGS(&list))))return 5;
  list->CopyBufferRegion(destination.Get(),0,source.Get(),0,256);
  if(type==D3D12_COMMAND_LIST_TYPE_DIRECT){D3D12_VERTEX_BUFFER_VIEW view{source->GetGPUVirtualAddress(),4096,16};list->IASetVertexBuffers(0,1,&view);}
  if(FAILED(list->Close()))return 6;
 }
 const auto flags=malemod::witcher::GraphicsProbeFlags();
 std::printf("SDK copy/direct observer flags: %u\n",flags);
 // Restore patched SDK entry points before releasing their last owners.
 MH_DisableHook(MH_ALL_HOOKS);MH_Uninitialize();
 return (flags&15)==15&&!(flags&0x8000)?0:7;
}
