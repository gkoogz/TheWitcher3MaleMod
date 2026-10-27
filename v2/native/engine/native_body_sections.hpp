#pragma once
#include "live_renderer.hpp"
#include <optional>
#include <limits>
namespace malemod::witcher::native_sections {
inline bool Active(unsigned material,unsigned state){return material==0||(material==1&&state!=0)||(material==2&&state==0);}
// B04 stock skin can remain visible through an outfit without the source
// anatomy. Only its active source material establishes lower-body eligibility.
inline bool SourceVisible(unsigned resource,const RenderResource& r,unsigned section){return resource!=0||r.sections.empty()||(section<r.sections.size()&&(r.sections[section].material==1||r.sections[section].material==2));}
inline bool Contains(const RenderSection& s,unsigned first,unsigned count){return count&&first>=s.indexFirst&&first-s.indexFirst<=s.indexCount&&count<=s.indexCount-(first-s.indexFirst);}
// An exact, independently fingerprinted body index allocation is required by
// the caller. CPU section intervals are loaded from the hash-bound B04 file.
inline std::optional<unsigned> FromIndices(const RenderResource& r,unsigned first,unsigned count,int base){
 if(base)return {};
 std::optional<unsigned> result;
 for(unsigned i=0;i<r.sections.size();i++)if(Contains(r.sections[i],first,count)){
  if(result)return {};
  result=i;
 }
 return result;
}
inline bool StaticView(const RenderSection& s,std::uint64_t offset,std::uint64_t bytes,unsigned stride){return stride==16&&offset==s.positionOffset&&bytes>=std::uint64_t(s.vertexCount)*16;}
inline bool MorphView(const RenderSection& s,std::uint64_t bytes,unsigned stride){return stride==24&&bytes==std::uint64_t(s.vertexCount)*24;}
}
