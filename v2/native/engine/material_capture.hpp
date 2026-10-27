#pragma once
#include <cstdint>
#include <filesystem>
#include <cstddef>
#include <d3d12.h>
namespace malemod::witcher {
// Diagnostic only. No request file, or a visible/nonmatching station, leaves
// this disabled. The request must exist before graphics initialization.
void InitializeMaterialCapture(const std::filesystem::path& ownedDirectory) noexcept;
bool MaterialCaptureEnabled() noexcept;
bool MaterialCapturePendingDraw() noexcept;
// MMGBD1 only: typed debug configuration before the first actual device, then
// bounded native validation/DRED observation. MMGB1 does not enable this.
void MaterialCaptureBeforeDevice(void* factory=nullptr) noexcept;
void MaterialCaptureDevice(void* device) noexcept;
void GraphicsMaterialCaptureCheckpoint(unsigned stage,unsigned epoch,std::uint64_t sequence) noexcept;
void MaterialCaptureRTV(void* device,void* resource,const D3D12_RENDER_TARGET_VIEW_DESC*,D3D12_CPU_DESCRIPTOR_HANDLE) noexcept;
void MaterialCaptureTargets(void* list,unsigned count,const D3D12_CPU_DESCRIPTOR_HANDLE*,bool contiguous) noexcept;
void MaterialCaptureCopyDescriptors(void* device,unsigned destinationRanges,const D3D12_CPU_DESCRIPTOR_HANDLE* destinations,const unsigned* destinationSizes,unsigned sourceRanges,const D3D12_CPU_DESCRIPTOR_HANDLE* sources,const unsigned* sourceSizes,D3D12_DESCRIPTOR_HEAP_TYPE) noexcept;
void MaterialCaptureCopyDescriptorsSimple(void* device,unsigned count,D3D12_CPU_DESCRIPTOR_HANDLE destination,D3D12_CPU_DESCRIPTOR_HANDLE source,D3D12_DESCRIPTOR_HEAP_TYPE) noexcept;
// Uses actual GetBuffer objects, never a name/format classification. No chain
// or backbuffer reference survives this call unless an own GPU copy is unsafe
// to release (reported explicitly and kept alive through its existing fence).
void MaterialCaptureSwapChain(void* chain) noexcept;
void MaterialCaptureResizeResult(void* chain,const char* method,unsigned buffers,unsigned width,unsigned height,unsigned format,long result) noexcept;
struct MaterialCaptureDraw {
 unsigned resource=0,lod=0,section=0,material=0,epoch=0;
 std::uint64_t sequence=0,presentationSerial=0,nativePresentSerial=0,drawSerial=0;
 unsigned indexFirst=0,indexCount=0,depthFunc=0,depthWrite=0,cullMode=0,frontCounterClockwise=0;
};
void MaterialCaptureAfterDraw(void* list,const MaterialCaptureDraw&,const void* pixelShader,std::size_t pixelShaderBytes) noexcept;
void MaterialCaptureSubmitted(void* queue,unsigned count,void* const* lists) noexcept;
void MaterialCaptureReset(void* list) noexcept;
// Called after graphics hooks are disabled, outside loader locks.
void ShutdownMaterialCapture() noexcept;
#ifdef MALEMOD_MATERIAL_CAPTURE_TESTING
// The fixture must itself use an invisible station; this bypasses only the
// module-directory discovery, never the sealed station/request parser.
unsigned MaterialCaptureWritten();
std::uint64_t MaterialCapturePinnedBytes();
#endif
}
