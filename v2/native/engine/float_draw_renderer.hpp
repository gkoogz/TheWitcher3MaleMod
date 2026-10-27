#pragma once
#include <d3d12.h>
#include <functional>
#include <memory>
#include <string>
#include <cstdint>
#include <array>
#include <vector>
namespace malemod::witcher {
struct RenderDelivery;
struct RenderResource;
struct PositionDrawReceipt;
struct FloatDrawReceipt {unsigned section=~0u,material=0,state=2,epoch=0;std::uint64_t sequence=0,presentationSerial=0;bool active=true,coverageApplied=false;std::shared_ptr<const std::vector<std::uint16_t>> coverageSource;};
// Offset in the exact owned native vertex allocation, including later LODs.
unsigned StaticFloatDrawLOD(const RenderResource&,std::uint64_t positionOffset);
void RegisterFloatDrawPipeline(void* original,const D3D12_GRAPHICS_PIPELINE_STATE_DESC&);
void RegisterFloatDrawStream(void* original,const D3D12_PIPELINE_STATE_STREAM_DESC&,std::size_t layoutValue,std::size_t cacheValue);
bool FloatDraw(void* list,void* original,const D3D12_VERTEX_BUFFER_VIEW& position,const D3D12_VERTEX_BUFFER_VIEW& lighting,const std::function<void()>& draw,unsigned resource=0,unsigned lod=2,void* nativeResource=nullptr,unsigned nativeState=0,const std::function<void()>& restoreCompute={},const D3D12_INDEX_BUFFER_VIEW* indexView=nullptr,unsigned firstIndex=0,unsigned normalizedFirst=0,bool colorPass=false,FloatDrawReceipt* receipt=nullptr,unsigned sectionIndex=~0u,PositionDrawReceipt* diagnostic=nullptr);
bool ModularDraw(void* list,void* original,const std::array<D3D12_VERTEX_BUFFER_VIEW,32>& views,const D3D12_INDEX_BUFFER_VIEW& indices,unsigned resource,unsigned lod,unsigned first,unsigned count,const std::function<void(unsigned)>& draw);
void FloatDrawSubmitted(void* queue,unsigned count,void* const* lists);
void FloatDrawReset(void* list);
void FloatDrawBundle(void* parent,void* bundle);
// Called by the render thread after a real DXGI Present (not a test Present).
// All depth/material/body lists consuming that engine frame share one surface.
void FloatDrawFrameBoundary();
unsigned FloatDrawFlags();
std::string FloatDrawError();
unsigned FloatDrawSequence();
unsigned FloatDrawResourceMask();
unsigned ModularDrawCompletedLODMask();
unsigned FloatDrawPublicationCount();
unsigned FloatDrawCoverageCount();
std::array<std::uint64_t,2> FloatDrawCoveragePassCounts();
bool FloatDrawActive(unsigned epoch);
bool FloatDrawRecentlySeen(unsigned resource);
std::array<std::uint64_t,3> FloatDrawVisibility(unsigned resource);
std::shared_ptr<const RenderDelivery> FloatDrawCompleted();
}
