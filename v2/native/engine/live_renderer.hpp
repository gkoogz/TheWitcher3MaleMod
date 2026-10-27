#pragma once
#include <array>
#include <vector>
#include <memory>
#include <cstdint>

namespace malemod::witcher {
struct RenderSection {
 unsigned lod=0,material=0,firstVertex=0,vertexCount=0;
 unsigned positionOffset=0,uvOffset=0,lightingOffset=0,extraOffset=0;
 unsigned indexFirst=0,indexCount=0;
};
static_assert(sizeof(RenderSection)==40);
struct RenderResource {
 unsigned firstVertex=0,vertexCount=0,firstPalette=0,paletteCount=0,indexBytes=0,vertexBufferBytes=0;
 std::array<float,3> scale{},bias{};
 std::array<unsigned,2> lodFirstVertex{},lodVertexCount{},lodUVOffset{},lodExtraOffset{};
 std::vector<RenderSection> sections;
};
struct RenderDelivery {
 struct FloatVertex {std::array<float,3> position{};std::uint32_t bones=0,weights=0,normal=0,tangent=0;};
 struct MorphReference {std::array<float,3> position{};std::uint32_t normal=0,tangent=0,boundary=0;};
 unsigned epoch=0,materialState=2;std::uint64_t sequence=0,presentationSerial=0;
 std::vector<RenderResource> resources;
 std::vector<FloatVertex> floatVertices;
 std::shared_ptr<const std::vector<MorphReference>> morphReference;
 std::shared_ptr<const std::vector<std::uint16_t>> coveredIndices;
 bool modular=false;
};
static_assert(sizeof(RenderDelivery::FloatVertex)==28);
static_assert(sizeof(RenderDelivery::MorphReference)==24);
std::shared_ptr<const RenderDelivery> LiveRenderLatest();
void LiveRenderFeed(std::shared_ptr<const RenderDelivery>);
// These observer callbacks do not mutate native resources. The float draw
// backend owns replacement input streams and their GPU fence lifetimes.
void LiveRenderOwnedStream(std::uint64_t,unsigned,unsigned);
bool LiveRenderMatchResource(void*,std::uint64_t&);
void LiveRenderSubmitted(void*,unsigned,void* const*);
void LiveRenderReset(void*);
}
