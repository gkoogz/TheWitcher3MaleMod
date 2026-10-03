#pragma once
#include <d3d12.h>
#include <memory>
#include <array>
#include <functional>
#include <filesystem>
namespace malemod::witcher {
struct ClinicalDelivery;
void FluidRendererConfigure(const std::filesystem::path&);
void FluidRendererOrigin(std::array<double,3>,bool);
void FluidRendererFeed(std::shared_ptr<const ClinicalDelivery>,double);
void FluidRendererFrameBoundary();
void RegisterFluidPipeline(void*,const D3D12_GRAPHICS_PIPELINE_STATE_DESC&);
void RegisterFluidStream(void*,const D3D12_PIPELINE_STATE_STREAM_DESC&,std::size_t,std::size_t);
bool FluidDraw(void*,void*,const std::array<D3D12_VERTEX_BUFFER_VIEW,32>&,const D3D12_INDEX_BUFFER_VIEW&,unsigned kind,const std::function<void(unsigned,unsigned)>&);
void FluidDrawSubmitted(void*,unsigned,void* const*);
void FluidDrawReset(void*);
void FluidDrawBundle(void*,void*);
unsigned FluidDrawFlags();
unsigned FluidDrawPublications();
}
