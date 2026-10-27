#pragma once
#include <d3d12.h>
#include <array>
#include <cstdint>
#include <filesystem>
#include <functional>
#include <memory>
#include <vector>
#include <string>
namespace malemod::witcher {
struct RenderDelivery;struct GarmentDelivery;
// A diagnostic receipt describes the selected immutable upload at this draw,
// never a later LiveRenderLatest publication.
struct PositionDrawReceipt {
 bool cloth=false,morph=false,wholeMorph=false;unsigned resource=0,lod=0,section=0,material=0,kind=0,epoch=0;
 std::uint64_t sequence=0,presentationSerial=0,nativePresentSerial=0,drawSerial=0;
 std::uint64_t latestSequence=0,frameSequence=0,recordingSequence=0;
 unsigned indexCount=0,indexFirst=0,normalizedFirst=0,instances=0,firstInstance=0;int baseVertex=0;
 std::array<double,3> origin{};std::array<float,3> scale{},bias{};
 std::shared_ptr<const RenderDelivery> body;std::shared_ptr<const GarmentDelivery> garment;
 std::array<D3D12_VERTEX_BUFFER_VIEW,4> uploadViews{};D3D12_INDEX_BUFFER_VIEW uploadIndices{};
 void* ownedVertexUpload=nullptr;void* ownedIndexUpload=nullptr;
};
void InitializePositionCapture(const std::filesystem::path&) noexcept;
bool PositionCaptureEnabled() noexcept;
bool PositionCapturePending() noexcept;
void PositionCaptureCheckpoint(unsigned,unsigned,std::uint64_t) noexcept;
void PositionCapturePresent(std::uint64_t) noexcept;
void PositionCapturePose(std::shared_ptr<const RenderDelivery>,std::shared_ptr<const GarmentDelivery>,unsigned,const float*,const float*) noexcept;
void PositionCaptureBundle(void*,void*) noexcept;
void PositionCaptureRoot(void*,void*) noexcept;
void PositionCaptureTargets(void*,unsigned,const D3D12_CPU_DESCRIPTOR_HANDLE*,bool,const D3D12_CPU_DESCRIPTOR_HANDLE*) noexcept;
void PositionCapturePipeline(void*,const D3D12_GRAPHICS_PIPELINE_STATE_DESC&) noexcept;
void PositionCaptureStream(void*,const D3D12_PIPELINE_STATE_STREAM_DESC&) noexcept;
// Called after the real draw, while its replacement pipeline/index/IA inputs
// are still bound. The callback repeats exactly that original indexed draw.
void PositionCaptureInsideDraw(void*,void*,void*,PositionDrawReceipt,const std::function<void()>&) noexcept;
void PositionCaptureSubmitted(void*,unsigned,void* const*) noexcept;
void PositionCaptureReset(void*) noexcept;
void ShutdownPositionCapture() noexcept;
#ifdef MALEMOD_POSITION_CAPTURE_TESTING
void PositionCaptureTestAllowShader(const std::string&,unsigned);
unsigned PositionCaptureWritten();std::uint64_t PositionCaptureBytes();
#endif
}
