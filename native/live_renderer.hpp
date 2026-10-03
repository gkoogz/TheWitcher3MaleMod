#pragma once
#include "render_service.hpp"
#include <functional>
namespace malemod::witcher {
void LiveRenderFeed(std::shared_ptr<const RenderDelivery>);
std::shared_ptr<const RenderDelivery> LiveRenderLatest();
void LiveRenderOwnedStream(std::uint64_t address,unsigned bytes,unsigned stride);
bool LiveRenderTransition(void* list,void* resource,std::uint64_t offset,const std::function<void()>& restore,unsigned before=8);
bool LiveRenderMatchResource(void* resource,std::uint64_t& offset);
void LiveRenderSubmitted(void* queue,unsigned count,void* const* lists);
void LiveRenderReset(void* list);
unsigned LiveRenderFlags();
unsigned LiveRenderSequence();
bool LiveRenderActive(unsigned epoch);
}
