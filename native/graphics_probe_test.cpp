// SDK smoke test in an owned process. No game, native assets or GPU submission.
#define NOMINMAX
#include <windows.h>
#include <d3d12.h>
#include <dxgi1_4.h>
#include <wrl/client.h>
#include <MinHook.h>
#include <cstdio>
#include <cstring>
#include <cwchar>
#include <initializer_list>
#include <fstream>
#include <vector>
#include <filesystem>
#include "graphics_probe.hpp"
using Microsoft::WRL::ComPtr;
int wmain(int argc,wchar_t** argv){
 std::vector<unsigned char> replay;
 // --late-garment accepts an actual cooked carrier buffer whose immutable
 // fingerprint is already in the selected executable's manifest. No game data
 // or test-only production ownership bypass is introduced.
 const wchar_t* replayPath=argc==2?argv[1]:argc==3&&!std::wcscmp(argv[1],L"--late-garment")?argv[2]:nullptr;
 if(argc>1&&!replayPath)return 19;
 if(replayPath){std::ifstream file(std::filesystem::path(replayPath),std::ios::binary|std::ios::ate);if(!file||file.tellg()<=0||file.tellg()>64*1024*1024)return 10;replay.resize(static_cast<std::size_t>(file.tellg()));file.seekg(0);file.read(reinterpret_cast<char*>(replay.data()),replay.size());if(!file)return 11;}
 if(MH_Initialize()!=MH_OK||!malemod::witcher::InitializeGraphicsProbe())return 1;
 ComPtr<IDXGIFactory4> factory;ComPtr<IDXGIAdapter> warp;ComPtr<ID3D12Device> device;
 if(FAILED(CreateDXGIFactory1(IID_PPV_ARGS(&factory)))||FAILED(factory->EnumWarpAdapter(IID_PPV_ARGS(&warp)))||FAILED(D3D12CreateDevice(warp.Get(),D3D_FEATURE_LEVEL_11_0,IID_PPV_ARGS(&device))))return 2;
 D3D12_RESOURCE_DESC desc{};desc.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER;desc.Width=replay.empty()?4096:replay.size();desc.Height=1;desc.DepthOrArraySize=1;desc.MipLevels=1;desc.SampleDesc.Count=1;desc.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
 D3D12_HEAP_PROPERTIES heap{};heap.Type=D3D12_HEAP_TYPE_UPLOAD;
 ComPtr<ID3D12Resource> source,destination;
 if(FAILED(device->CreateCommittedResource(&heap,D3D12_HEAP_FLAG_NONE,&desc,D3D12_RESOURCE_STATE_GENERIC_READ,nullptr,IID_PPV_ARGS(&source))))return 3;
 if(!replay.empty()){void* mapped=nullptr;D3D12_RANGE read{0,0};if(FAILED(source->Map(0,&read,&mapped)))return 12;std::memcpy(mapped,replay.data(),replay.size());D3D12_RANGE written{0,replay.size()};source->Unmap(0,&written);}
 if(!replay.empty())desc.Width=replay.size()*2; // Separate pool region for nonoverlap regression.
 heap.Type=D3D12_HEAP_TYPE_DEFAULT;
 if(FAILED(device->CreateCommittedResource(&heap,D3D12_HEAP_FLAG_NONE,&desc,D3D12_RESOURCE_STATE_COPY_DEST,nullptr,IID_PPV_ARGS(&destination))))return 4;
 D3D12_INDIRECT_ARGUMENT_DESC argument{};argument.Type=D3D12_INDIRECT_ARGUMENT_TYPE_DRAW_INDEXED;
 D3D12_COMMAND_SIGNATURE_DESC signatureDesc{};signatureDesc.ByteStride=sizeof(D3D12_DRAW_INDEXED_ARGUMENTS);signatureDesc.NumArgumentDescs=1;signatureDesc.pArgumentDescs=&argument;
 ComPtr<ID3D12CommandSignature> signature;
 if(FAILED(device->CreateCommandSignature(&signatureDesc,nullptr,IID_PPV_ARGS(&signature))))return 13;
 if(!replay.empty()){
  ComPtr<ID3D12CommandAllocator> allocator;ComPtr<ID3D12GraphicsCommandList> list;
  if(FAILED(device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT,IID_PPV_ARGS(&allocator)))||FAILED(device->CreateCommandList(0,D3D12_COMMAND_LIST_TYPE_DIRECT,allocator.Get(),nullptr,IID_PPV_ARGS(&list))))return 20;
  void* mapped=nullptr;D3D12_RANGE read{0,0};if(FAILED(source->Map(0,&read,&mapped)))return 21;
  // Correct matching size, foreign prefix: these consume the former lifetime
  // sample budget, while the production prefix gate must reject their ownership.
  std::memset(mapped,0xa5,replay.size());D3D12_RANGE written{0,replay.size()};source->Unmap(0,&written);
  for(unsigned upload=0;upload<700;upload++)list->CopyBufferRegion(destination.Get(),0,source.Get(),0,replay.size());
  D3D12_VERTEX_BUFFER_VIEW vertices{destination->GetGPUVirtualAddress(),static_cast<UINT>(replay.size()),16};list->IASetVertexBuffers(0,1,&vertices);
  D3D12_INDEX_BUFFER_VIEW index{destination->GetGPUVirtualAddress(),6,DXGI_FORMAT_R16_UINT};list->IASetIndexBuffer(&index);
  if(malemod::witcher::TestOwnedDraw(list.Get(),110230)!=0)return 22;
  if(FAILED(source->Map(0,&read,&mapped)))return 23;std::memcpy(mapped,replay.data(),replay.size());source->Unmap(0,&written);
  list->CopyBufferRegion(destination.Get(),0,source.Get(),0,replay.size());
  if(malemod::witcher::TestOwnedDraw(list.Get(),110231)!=1)return 24;
  if(FAILED(source->Map(0,&read,&mapped)))return 26;std::memset(mapped,0xa5,replay.size());source->Unmap(0,&written);
  // A disjoint copy into the same pooled resource preserves the exact claim.
  // A short intersecting copy is deliberately not a manifest-sized upload.
  list->CopyBufferRegion(destination.Get(),replay.size(),source.Get(),0,16);
  if(malemod::witcher::TestOwnedDraw(list.Get(),110235)!=1)return 27;
  list->CopyBufferRegion(destination.Get(),16,source.Get(),0,16);
  if(malemod::witcher::TestOwnedDraw(list.Get(),110236)!=0)return 28;
  if(FAILED(source->Map(0,&read,&mapped)))return 29;std::memcpy(mapped,replay.data(),replay.size());source->Unmap(0,&written);
  list->CopyBufferRegion(destination.Get(),0,source.Get(),0,replay.size());
  if(malemod::witcher::TestOwnedDraw(list.Get(),110237)!=1)return 30;
  if(FAILED(source->Map(0,&read,&mapped)))return 31;std::memset(mapped,0xa5,replay.size());source->Unmap(0,&written);
  list->CopyBufferRegion(destination.Get(),0,source.Get(),0,replay.size());
  if(malemod::witcher::TestOwnedDraw(list.Get(),110238)!=0)return 32;
  if(FAILED(source->Map(0,&read,&mapped)))return 33;std::memcpy(mapped,replay.data(),replay.size());source->Unmap(0,&written);
  list->CopyBufferRegion(destination.Get(),0,source.Get(),0,replay.size());
  if(malemod::witcher::TestOwnedDraw(list.Get(),110239)!=1)return 34;
  if(FAILED(list->Close()))return 25;
  std::puts("PASS 700 foreign uploads rejected, late exact upload classified; disjoint pool copy preserved, short/full foreign overwrite revoked, exact reload recovered");
 }
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
