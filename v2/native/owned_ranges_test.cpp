#include "engine/owned_ranges.hpp"
#include <cassert>
#include <iostream>
using namespace malemod::witcher::ownership;
static bool Has(const std::vector<Range>& ranges,Range row){return std::find(ranges.begin(),ranges.end(),row)!=ranges.end();}
int main(){
 std::vector<Range> a{{100,100,"fluid_opaque_vertices"},{110,20,"fluid_opaque_lod0_stream0"},{140,30,"fluid_opaque_lod0_stream1"},{400,100,"unrelated"}};
 auto b=PropagateCopy(a,100,1000,100);assert(b.size()==7&&Has(b,{1000,100,"fluid_opaque_vertices"})&&Has(b,{1010,20,"fluid_opaque_lod0_stream0"})&&Has(b,{1040,30,"fluid_opaque_lod0_stream1"}));
 auto c=PropagateCopy(b,1000,2000,100);assert(c.size()==10&&Has(c,{2000,100,"fluid_opaque_vertices"})&&Has(c,{2010,20,"fluid_opaque_lod0_stream0"})&&Has(c,{2040,30,"fluid_opaque_lod0_stream1"}));
 // A foreign partial overwrite revokes whole identities, including overlapping
 // substreams; a disjoint stream and unrelated allocation remain owned.
 auto overwritten=PropagateCopy(a,9000,115,10);assert(overwritten.size()==2&&Has(overwritten,{140,30,"fluid_opaque_lod0_stream1"})&&Has(overwritten,{400,100,"unrelated"}));
 auto partial=PropagateCopy(a,105,1000,30);assert(!Has(partial,{1000,100,"fluid_opaque_vertices"})&&Has(partial,{1005,20,"fluid_opaque_lod0_stream0"}));
 auto overlap=PropagateCopy(a,100,150,100);assert(Has(overlap,{150,100,"fluid_opaque_vertices"})&&Has(overlap,{160,20,"fluid_opaque_lod0_stream0"})&&Has(overlap,{190,30,"fluid_opaque_lod0_stream1"}));assert(!Has(overlap,{100,100,"fluid_opaque_vertices"}));
 auto self=PropagateCopy(a,100,100,100);assert(self.size()==a.size());for(auto row:a)assert(Has(self,row));
 // Shared index bytes do not transfer a vertex identity or invent a kind.
 std::vector<Range> aliases{{100,384,"fluid_opaque_indices"},{100,384,"fluid_clear_indices"},{100,384,"garment_ribbed_indices"},{1000,6912,"fluid_clear_vertices"}};
 auto index=PropagateCopy(aliases,100,10000,384);assert(Has(index,{10000,384,"fluid_opaque_indices"})&&Has(index,{10000,384,"fluid_clear_indices"})&&Has(index,{10000,384,"garment_ribbed_indices"}));assert(!Has(index,{10000,6912,"fluid_clear_vertices"}));
 auto unknown=PropagateCopy(aliases,99000,1000,6912);assert(!Has(unknown,{1000,6912,"fluid_clear_vertices"})&&unknown.size()==3);
 assert(PropagateCopy(a,0,0,0)==a);const auto max=std::numeric_limits<std::uint64_t>::max();
 for(bool source:{false,true}){bool threw=false;try{PropagateCopy(a,source?max-3:0,source?0:max-3,4);}catch(const std::invalid_argument&){threw=true;}assert(threw);}
 bool badRange=false;try{PropagateCopy({{max-1,2,"bad"}},0,0,1);}catch(const std::invalid_argument&){badRange=true;}assert(badRange);
 assert(a.size()==4&&a[0].begin==100);std::cout<<"PASS exact GPU copy ownership: A-B-C, multi-range translation, partial foreign revocation, snapshot overlap/self-copy, shared-index aliases and overflow rejection\n";
}
