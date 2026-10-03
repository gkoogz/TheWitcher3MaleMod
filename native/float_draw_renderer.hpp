#pragma once
#include <d3d12.h>
#include <functional>
#include <memory>
namespace malemod::witcher {
struct RenderDelivery;
void RegisterFloatDrawPipeline(void* original,const D3D12_GRAPHICS_PIPELINE_STATE_DESC&);
void RegisterFloatDrawStream(void* original,const D3D12_PIPELINE_STATE_STREAM_DESC&,std::size_t layoutValue,std::size_t cacheValue);
bool FloatDraw(void* list,void* original,const D3D12_VERTEX_BUFFER_VIEW& position,const D3D12_VERTEX_BUFFER_VIEW& lighting,const std::function<void()>& draw,unsigned resource=0,unsigned lod=2);
void FloatDrawSubmitted(void* queue,unsigned count,void* const* lists);
void FloatDrawReset(void* list);
void FloatDrawBundle(void* parent,void* bundle);
unsigned FloatDrawFlags();
unsigned FloatDrawSequence();
unsigned FloatDrawResourceMask();
unsigned FloatDrawPublicationCount();
bool FloatDrawActive(unsigned epoch);
std::shared_ptr<const RenderDelivery> FloatDrawCompleted();
}
