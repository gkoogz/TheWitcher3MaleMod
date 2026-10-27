#pragma once
#include <array>
#include <vector>
#include <cstdint>
#include <cmath>
#include <stdexcept>
#include <memory>
namespace malemod::witcher {
// Engine delivery only. All fitting is generated from the locked canonical
// Mermaid/Meridian source through Base's SDK-free extractor.
struct GarmentDelivery {
 struct Vertex {std::array<float,3> position{},normal{},tangent{};float tangentSign=1;std::array<float,2> uv{};};
 struct Triangle {std::array<unsigned,3> vertices{};unsigned material=0;};
 struct Mesh {std::vector<Vertex> vertices;std::vector<Triangle> triangles;};
 struct Output {Mesh mesh;} output;
 unsigned epoch=0;std::uint64_t serial=0;
};
struct GarmentRenderFeed {
 std::shared_ptr<const GarmentDelivery> input;
 std::array<double,3> origin{};
 double scale=1;
};
inline unsigned PackDirection(std::array<float,3> d,unsigned high){unsigned result=(high&3)<<30;for(unsigned a=0;a<3;a++){const auto value=std::lround((std::max)(0.f,(std::min)(1.f,d[a]*.5f+.5f))*1023);result|=unsigned(value)<<(a*10);}return result;}
}
