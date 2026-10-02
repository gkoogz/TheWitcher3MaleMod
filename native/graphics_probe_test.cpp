// SDK smoke test in an owned process. No game, native assets or GPU submission.
#define NOMINMAX
#include <windows.h>
#include <d3d12.h>
#include <dxgi1_4.h>
#include <wrl/client.h>
#include <MinHook.h>
#include <cstdio>
#include <initializer_list>
#include <fstream>
#include <vector>
#include <filesystem>
#include "graphics_probe.hpp"
using Microsoft::WRL::ComPtr;
int wmain(int argc,wchar_t** argv){
 std::vector<unsigned char> replay;
 if(argc==2){std::ifstream file(std::filesystem::path(argv[1]),std::ios::binary|std::ios::ate);if(!file||file.tellg()<=0||file.tellg()>64*1024*1024)return 10;replay.resize(static_cast<std::size_t>(file.tellg()));file.seekg(0);file.read(reinterpret_cast<char*>(replay.data()),replay.size());if(!file)return 11;}
 if(MH_Initialize()!=MH_OK||!malemod::witcher::InitializeGraphicsProbe())return 1;
 ComPtr<IDXGIFactory4> factory;ComPtr<IDXGIAdapter> warp;ComPtr<ID3D12Device> device;
 if(FAILED(CreateDXGIFactory1(IID_PPV_ARGS(&factory)))||FAILED(factory->EnumWarpAdapter(IID_PPV_ARGS(&warp)))||FAILED(D3D12CreateDevice(warp.Get(),D3D_FEATURE_LEVEL_11_0,IID_PPV_ARGS(&device))))return 2;
 D3D12_RESOURCE_DESC desc{};desc.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER;desc.Width=replay.empty()?4096:replay.size();desc.Height=1;desc.DepthOrArraySize=1;desc.MipLevels=1;desc.SampleDesc.Count=1;desc.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
 D3D12_HEAP_PROPERTIES heap{};heap.Type=D3D12_HEAP_TYPE_UPLOAD;
 ComPtr<ID3D12Resource> source,destination;
 if(FAILED(device->CreateCommittedResource(&heap,D3D12_HEAP_FLAG_NONE,&desc,D3D12_RESOURCE_STATE_GENERIC_READ,nullptr,IID_PPV_ARGS(&source))))return 3;
 if(!replay.empty()){void* mapped=nullptr;D3D12_RANGE read{0,0};if(FAILED(source->Map(0,&read,&mapped)))return 12;std::memcpy(mapped,replay.data(),replay.size());D3D12_RANGE written{0,replay.size()};source->Unmap(0,&written);}
 heap.Type=D3D12_HEAP_TYPE_DEFAULT;
 if(FAILED(device->CreateCommittedResource(&heap,D3D12_HEAP_FLAG_NONE,&desc,D3D12_RESOURCE_STATE_COPY_DEST,nullptr,IID_PPV_ARGS(&destination))))return 4;
 D3D12_INDIRECT_ARGUMENT_DESC argument{};argument.Type=D3D12_INDIRECT_ARGUMENT_TYPE_DRAW_INDEXED;
 D3D12_COMMAND_SIGNATURE_DESC signatureDesc{};signatureDesc.ByteStride=sizeof(D3D12_DRAW_INDEXED_ARGUMENTS);signatureDesc.NumArgumentDescs=1;signatureDesc.pArgumentDescs=&argument;
 ComPtr<ID3D12CommandSignature> signature;
 if(FAILED(device->CreateCommandSignature(&signatureDesc,nullptr,IID_PPV_ARGS(&signature))))return 13;
 for(auto type:{D3D12_COMMAND_LIST_TYPE_COPY,D3D12_COMMAND_LIST_TYPE_DIRECT,D3D12_COMMAND_LIST_TYPE_BUNDLE}){
  ComPtr<ID3D12CommandAllocator> allocator;ComPtr<ID3D12GraphicsCommandList> list;
  if(FAILED(device->CreateCommandAllocator(type,IID_PPV_ARGS(&allocator)))||FAILED(device->CreateCommandList(0,type,allocator.Get(),nullptr,IID_PPV_ARGS(&list))))return 5;
  if(type!=D3D12_COMMAND_LIST_TYPE_BUNDLE)list->CopyBufferRegion(destination.Get(),0,source.Get(),0,replay.empty()?256:replay.size());
  if(type!=D3D12_COMMAND_LIST_TYPE_COPY){D3D12_VERTEX_BUFFER_VIEW view{replay.empty()?source->GetGPUVirtualAddress():destination->GetGPUVirtualAddress(),4096,type==D3D12_COMMAND_LIST_TYPE_BUNDLE?32u:16u};list->IASetVertexBuffers(0,1,&view);}
  if(type==D3D12_COMMAND_LIST_TYPE_DIRECT&&!replay.empty()){
   D3D12_INDEX_BUFFER_VIEW view{destination->GetGPUVirtualAddress()+1315840,435936,DXGI_FORMAT_R16_UINT};list->IASetIndexBuffer(&view);
   // Test only the metadata observer, not an invalid GPU draw without a PSO.
   if(malemod::witcher::TestOwnedDraw(list.Get(),110232)!=1)return 16;
  }
  if(FAILED(list->Close()))return 6;
  // Engine command lists are pooled and reused. Verify hooks after Close/Reset
  // rather than observing only the initial creation-time implementation.
  if(FAILED(allocator->Reset())||FAILED(list->Reset(allocator.Get(),nullptr)))return 14;
  if(malemod::witcher::TestOwnedDraw(list.Get(),110234)!=0)return 17;
  if(type!=D3D12_COMMAND_LIST_TYPE_COPY){D3D12_VERTEX_BUFFER_VIEW view{replay.empty()?source->GetGPUVirtualAddress():destination->GetGPUVirtualAddress(),4096,24};list->IASetVertexBuffers(0,1,&view);}
  if(type==D3D12_COMMAND_LIST_TYPE_DIRECT&&!replay.empty()&&malemod::witcher::TestOwnedDraw(list.Get(),110234)!=1)return 18;
  if(FAILED(list->Close()))return 15;
 }
 const auto flags=malemod::witcher::GraphicsProbeFlags();
 std::printf("SDK copy/direct/bundle observer flags: %u\n",flags);
 // Restore patched SDK entry points before releasing their last owners.
 MH_DisableHook(MH_ALL_HOOKS);MH_Uninitialize();
 malemod::witcher::ReleaseGraphicsProbeOwnedResources();
 return (flags&3087)==3087&&!(flags&0x8000)&&(replay.empty()||(flags&4608)==4608)?0:7;
}
