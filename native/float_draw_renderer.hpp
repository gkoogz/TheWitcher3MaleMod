#pragma once
#include <d3d12.h>
#include <functional>
#include <memory>
#include <string>
#include <cstdint>
namespace malemod::witcher {
struct RenderDelivery;
struct RenderResource;
// Offset in the exact owned native vertex allocation, including later LODs.
unsigned StaticFloatDrawLOD(const RenderResource&,std::uint64_t positionOffset);
void RegisterFloatDrawPipeline(void* original,const D3D12_GRAPHICS_PIPELINE_STATE_DESC&);
void RegisterFloatDrawStream(void* original,const D3D12_PIPELINE_STATE_STREAM_DESC&,std::size_t layoutValue,std::size_t cacheValue);
bool FloatDraw(void* list,void* original,const D3D12_VERTEX_BUFFER_VIEW& position,const D3D12_VERTEX_BUFFER_VIEW& lighting,const std::function<void()>& draw,unsigned resource=0,unsigned lod=2,void* nativeResource=nullptr,unsigned nativeState=0,const std::function<void()>& restoreCompute={});
void FloatDrawSubmitted(void* queue,unsigned count,void* const* lists);
void FloatDrawReset(void* list);
void FloatDrawBundle(void* parent,void* bundle);
// Called once by the SDK OnTick controller after it publishes the surface.
// All depth/material/body lists consuming that engine frame share one surface.
void FloatDrawFrameBoundary();
unsigned FloatDrawFlags();
std::string FloatDrawError();
unsigned FloatDrawSequence();
unsigned FloatDrawResourceMask();
unsigned FloatDrawPublicationCount();
bool FloatDrawActive(unsigned epoch);
std::shared_ptr<const RenderDelivery> FloatDrawCompleted();
}
