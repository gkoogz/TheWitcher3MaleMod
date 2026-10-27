#pragma once
#include "live_renderer.hpp"
#include <optional>
#include <cstdint>
namespace malemod::witcher::native_draw {
struct Contract {std::uint32_t vertices,indexBytes;std::array<unsigned,2> firstVertex,vertexCount,firstIndex,indexCount;};
inline bool Matches(const Contract& c,const RenderResource& r){return c.vertices==r.vertexCount&&c.indexBytes==r.indexBytes&&c.firstVertex==r.lodFirstVertex&&c.vertexCount==r.lodVertexCount;}
// Ownership of the exact native index allocation is supplied by the caller.
// This converts its measured per-LOD intervals to a bounded morph view, without
// consulting UVs or any vertex slot the current depth shader does not consume.
inline std::optional<unsigned> MorphLOD(const Contract& c,const RenderResource& r,std::uint64_t positionBytes,unsigned stride,unsigned first,unsigned count,int base){
 if(!Matches(c,r)||stride!=24||base!=0||!count)return {};
 for(unsigned lod=0;lod<2;lod++){
  if(first<c.firstIndex[lod]||first-c.firstIndex[lod]>c.indexCount[lod]||count>c.indexCount[lod]-(first-c.firstIndex[lod]))continue;
  const bool subset=positionBytes==std::uint64_t(c.vertexCount[lod])*24;
  const bool whole=lod==0&&positionBytes==std::uint64_t(c.vertices)*24;
  if(subset||whole)return lod;
 }
 return {};
}
inline bool MorphView(const RenderResource& r,unsigned lod,std::uint64_t bytes,unsigned stride,std::uint64_t position,std::uint64_t lighting,unsigned lightStride,bool usesSlot2){
 const bool shape=stride==24&&(bytes==std::uint64_t(r.vertexCount)*24||(lod<2&&bytes==std::uint64_t(r.lodVertexCount[lod])*24));
 return shape&&(!usesSlot2||!lighting||(position<=UINT64_MAX-16&&lighting==position+16&&lightStride==24));
}
}
