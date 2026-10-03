#define CINTERFACE
#define NOMINMAX
#include <windows.h>
#include <d3d12.h>
#include <dxgi1_4.h>
#include <cstdio>
#include <initializer_list>
int main(){IDXGIFactory1* factory=nullptr;IDXGIAdapter1* adapter=nullptr;CreateDXGIFactory1(IID_IDXGIFactory1,reinterpret_cast<void**>(&factory));
 for(unsigned i=0;factory&&SUCCEEDED(factory->lpVtbl->EnumAdapters1(factory,i,&adapter));i++){DXGI_ADAPTER_DESC1 desc{};adapter->lpVtbl->GetDesc1(adapter,&desc);std::printf("adapter vendor %x\n",desc.VendorId);if(desc.VendorId==0x1002)break;adapter->lpVtbl->Release(adapter);adapter=nullptr;}
 ID3D12Device* device=nullptr;if(FAILED(D3D12CreateDevice(reinterpret_cast<IUnknown*>(adapter),D3D_FEATURE_LEVEL_11_0,IID_ID3D12Device,reinterpret_cast<void**>(&device))))return 1;
 for(auto type:{D3D12_COMMAND_LIST_TYPE_DIRECT,D3D12_COMMAND_LIST_TYPE_COMPUTE,D3D12_COMMAND_LIST_TYPE_COPY}){
  ID3D12CommandAllocator* allocator=nullptr;ID3D12GraphicsCommandList* list=nullptr;
  if(FAILED(device->lpVtbl->CreateCommandAllocator(device,type,IID_ID3D12CommandAllocator,reinterpret_cast<void**>(&allocator))))return 2;
  if(FAILED(device->lpVtbl->CreateCommandList(device,0,type,allocator,nullptr,IID_ID3D12GraphicsCommandList,reinterpret_cast<void**>(&list))))return 3;
  std::printf("type %u\n",unsigned(type));
#define MM_METHOD(name) {auto address=reinterpret_cast<void*>(list->lpVtbl->name);HMODULE container=nullptr;GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,reinterpret_cast<LPCWSTR>(address),&container);std::printf("%s %p RVA %llx\n",#name,address,reinterpret_cast<unsigned long long>(address)-reinterpret_cast<unsigned long long>(container));}
  MM_METHOD(SetPipelineState) MM_METHOD(ResourceBarrier) MM_METHOD(SetComputeRootSignature) MM_METHOD(SetComputeRootDescriptorTable)
  MM_METHOD(SetComputeRoot32BitConstant) MM_METHOD(SetComputeRoot32BitConstants) MM_METHOD(SetComputeRootConstantBufferView)
  MM_METHOD(SetComputeRootShaderResourceView) MM_METHOD(SetComputeRootUnorderedAccessView) MM_METHOD(SetGraphicsRootShaderResourceView)
  MM_METHOD(IASetVertexBuffers) MM_METHOD(DrawIndexedInstanced) MM_METHOD(Reset) MM_METHOD(CopyBufferRegion)
  list->lpVtbl->Close(list);list->lpVtbl->Release(list);allocator->lpVtbl->Release(allocator);
 }
 device->lpVtbl->Release(device);
}
