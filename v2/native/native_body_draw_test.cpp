#include "engine/native_body_draw.hpp"
#include "native_draw_contract.inc"
#include <iostream>
#include <stdexcept>
using namespace malemod::witcher;
static void Check(bool value,const char* reason){if(!value)throw std::runtime_error(reason);}
int main(){try{
 for(const auto& c:native_draw::resources){
  RenderResource r;r.vertexCount=c.vertices;r.indexBytes=c.indexBytes;r.lodFirstVertex=c.firstVertex;r.lodVertexCount=c.vertexCount;
  Check(native_draw::Matches(c,r),"Generated native contract mismatch");
  for(unsigned lod=0;lod<2;lod++){
   const auto bytes=std::uint64_t(c.vertexCount[lod])*24;
   const auto first=c.firstIndex[lod],count=c.indexCount[lod];
   Check(native_draw::MorphLOD(c,r,bytes,24,first,count,0)==lod,"Exact native LOD not identified without UV");
   Check(native_draw::MorphLOD(c,r,bytes,24,first+3,count-3,0)==lod,"Bounded native subsection rejected");
   Check(!native_draw::MorphLOD(c,r,bytes,24,first,count+1,0),"Draw crossed native LOD interval");
   Check(!native_draw::MorphLOD(c,r,bytes+1,24,first,count,0),"Partial morph view accepted");
   Check(!native_draw::MorphLOD(c,r,bytes,16,first,count,0),"Static view accepted as morph");
   Check(!native_draw::MorphLOD(c,r,bytes,24,first,count,1),"Unmeasured baseVertex accepted");
   Check(!native_draw::MorphLOD(c,r,bytes,24,UINT32_MAX,3,0),"Overflowed first index accepted");
   Check(!native_draw::MorphLOD(c,r,bytes,24,first,UINT32_MAX,0),"Overflowed index count accepted");
   Check(native_draw::MorphView(r,lod,bytes,24,1000,5000,8,false),"Unused stale slot 2 blocked depth morph");
   Check(!native_draw::MorphView(r,lod,bytes,24,1000,5000,8,true),"Consumed stale slot 2 accepted");
   Check(native_draw::MorphView(r,lod,bytes,24,1000,1016,24,true),"Actual interleaved morph lighting rejected");
   Check(native_draw::MorphView(r,lod,bytes,24,1000,0,0,true),"Absent lighting changed previous supported path");
   Check(!native_draw::MorphView(r,lod,bytes,24,UINT64_MAX-8,7,24,true),"Lighting address overflow accepted");
  }
  Check(native_draw::MorphLOD(c,r,std::uint64_t(c.vertices)*24,24,0,c.indexCount[0],0)==0,"Whole native LOD0 morph rejected");
  Check(!native_draw::MorphLOD(c,r,std::uint64_t(c.vertices)*24,24,c.firstIndex[1],c.indexCount[1],0),"Ambiguous whole resource LOD1 accepted");
  r.indexBytes+=2;Check(!native_draw::MorphLOD(c,r,std::uint64_t(c.vertexCount[0])*24,24,0,3,0),"Unbound index topology accepted");
  r.indexBytes=c.indexBytes;r.lodFirstVertex[1]++;Check(!native_draw::Matches(c,r),"Unbound vertex topology accepted");
 }
 std::cout<<"PASS generated body LOD ownership, bounded subsets, exact metadata, stale unconsumed slot2, consumed lighting rejection, overflow and whole/subset view guards\n";
 return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
