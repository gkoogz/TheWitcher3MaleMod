// Explicitly unavailable until the v2 garment/clinical adapters are connected.
// Never report readiness from these draw hooks.
#include "garment_renderer.hpp"
#include "fluid_renderer.hpp"
namespace malemod::witcher {
void FluidRendererFrameBoundary(){}
void RegisterFluidPipeline(void*,const D3D12_GRAPHICS_PIPELINE_STATE_DESC&){}
void RegisterFluidStream(void*,const D3D12_PIPELINE_STATE_STREAM_DESC&,std::size_t,std::size_t){}
bool FluidDraw(void*,void*,const std::array<D3D12_VERTEX_BUFFER_VIEW,32>&,const D3D12_INDEX_BUFFER_VIEW&,unsigned,const std::function<void(unsigned,unsigned)>&){return false;}
void FluidDrawSubmitted(void*,unsigned,void* const*){}
void FluidDrawReset(void*){}
void FluidDrawBundle(void*,void*){}
}
