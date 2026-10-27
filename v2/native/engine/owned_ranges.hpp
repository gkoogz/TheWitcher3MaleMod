#pragma once
#include <algorithm>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
namespace malemod::witcher::ownership {
struct Range {
 std::uint64_t begin=0,bytes=0;std::string label;
 bool operator==(const Range& other)const{return begin==other.begin&&bytes==other.bytes&&label==other.label;}
};
// Input is the state BEFORE the GPU copy. Only complete, already-owned byte
// ranges contained in the source interval retain their exact identity. Every
// intersected destination claim is revoked, even for an unknown/partial copy.
// Snapshot evaluation also handles overlapping and self copies without reading
// identities that this same copy has just revoked or created.
inline std::vector<Range> PropagateCopy(const std::vector<Range>& snapshot,std::uint64_t sourceBegin,std::uint64_t destinationBegin,std::uint64_t bytes){
 const auto end=[](std::uint64_t start,std::uint64_t count){if(count>std::numeric_limits<std::uint64_t>::max()-start)throw std::invalid_argument("GPU ownership range overflow");return start+count;};
 const auto sourceEnd=end(sourceBegin,bytes),destinationEnd=end(destinationBegin,bytes);
 for(const auto& range:snapshot)end(range.begin,range.bytes);
 if(!bytes)return snapshot;
 std::vector<Range> result,translated;result.reserve(snapshot.size());translated.reserve(snapshot.size());
 for(const auto& range:snapshot){
  const auto rangeEnd=range.begin+range.bytes;
  if(range.bytes&&range.begin>=sourceBegin&&rangeEnd<=sourceEnd)translated.push_back({destinationBegin+(range.begin-sourceBegin),range.bytes,range.label});
  if(!range.bytes||range.begin>=destinationEnd||destinationBegin>=rangeEnd)result.push_back(range);
 }
 for(auto& range:translated)if(std::find(result.begin(),result.end(),range)==result.end())result.push_back(std::move(range));
 return result;
}
}
