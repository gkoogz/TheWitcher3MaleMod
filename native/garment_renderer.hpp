#pragma once
#include <d3d12.h>
#include <memory>
#include <array>
#include <functional>
#include <filesystem>
namespace malemod::witcher {
struct GarmentDelivery;
void GarmentRendererConfigure(const std::filesystem::path&);
void GarmentRendererOrigin(std::array<double,3>,bool);
void GarmentRendererFeed(std::shared_ptr<const GarmentDelivery>,double=1);
void GarmentRendererFrameBoundary();
void RegisterGarmentPipeline(void*,const D3D12_GRAPHICS_PIPELINE_STATE_DESC&);
void RegisterGarmentStream(void*,const D3D12_PIPELINE_STATE_STREAM_DESC&,std::size_t,std::size_t);
bool GarmentDraw(void*,void*,const std::array<D3D12_VERTEX_BUFFER_VIEW,32>&,const D3D12_INDEX_BUFFER_VIEW&,unsigned,const std::function<void(unsigned,unsigned)>&);
void GarmentDrawSubmitted(void*,unsigned,void* const*);
void GarmentDrawReset(void*);
void GarmentDrawBundle(void*,void*);
unsigned GarmentDrawFlags();unsigned GarmentDrawPublications();
}
