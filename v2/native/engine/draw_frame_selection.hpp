#pragma once
#include "first_draw_latch.hpp"
#include "frame_publication.hpp"
#include "live_renderer.hpp"
#include "garment_delivery.hpp"
#include "fluid_render_feed.hpp"
namespace malemod::witcher {
std::shared_ptr<const GarmentRenderFeed> GarmentRendererLatest();
std::shared_ptr<const FluidRenderFeed> FluidRendererLatest();
using DrawFrameLatch=FirstDrawLatch<RenderDelivery,GarmentRenderFeed,FluidRenderFeed>;
inline DrawFrameLatch& SharedDrawFrameLatch(){static auto* value=new DrawFrameLatch;return *value;}
inline DrawFrameLatch::Selection SelectDrawFrame(){
 FramePublicationLock lock(FramePublicationMutex());
 auto body=LiveRenderLatest();auto garment=GarmentRendererLatest();auto fluid=FluidRendererLatest();
 if(garment&&garment->input&&(!body||garment->input->epoch!=body->epoch||garment->input->serial!=body->sequence))garment.reset();
 if(fluid&&(!body||fluid->epoch!=body->epoch||fluid->sequence!=body->sequence))fluid.reset();
 return SharedDrawFrameLatch().Select({std::move(body),std::move(garment),std::move(fluid)});
}
// Present already holds FramePublicationMutex. No renderer lock is acquired.
inline void InvalidateDrawFrame(){SharedDrawFrameLatch().Invalidate();}
}
