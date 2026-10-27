#pragma once
#include <memory>
#include <array>
#include <cstdint>
namespace malemod::witcher {
struct ClinicalDelivery;
// Delivery ownership and carrier origin are published together. Copying this
// small owner does not copy or advance the canonical liquid/deposit meshes.
struct FluidRenderFeed {
 std::shared_ptr<const ClinicalDelivery> input;
 std::array<double,3> origin{};
 double scale=1;
 unsigned epoch=0;
 std::uint64_t sequence=0;
};
}
