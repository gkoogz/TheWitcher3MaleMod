#include "live_renderer.hpp"
#include <atomic>
namespace malemod::witcher {
namespace {auto* latest=new std::shared_ptr<const RenderDelivery>;}
std::shared_ptr<const RenderDelivery> LiveRenderLatest(){return std::atomic_load(latest);}
void LiveRenderFeed(std::shared_ptr<const RenderDelivery> value){std::atomic_store(latest,std::move(value));}
void LiveRenderOwnedStream(std::uint64_t,unsigned,unsigned){}
bool LiveRenderMatchResource(void*,std::uint64_t&){return false;}
void LiveRenderSubmitted(void*,unsigned,void* const*){}
void LiveRenderReset(void*){}
}
