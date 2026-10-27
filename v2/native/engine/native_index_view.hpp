#pragma once
#include <cstdint>
#include <optional>
#include <limits>

namespace malemod::witcher {
// Normalize a 16-bit index view into its fingerprinted allocation. REDengine
// rebases the second LOD's index view and then submits firstIndex=0.
inline std::optional<std::uint32_t> NativeIndexFirst(
 std::uint64_t ownedBegin,std::uint64_t ownedBytes,
 std::uint64_t viewBegin,std::uint64_t viewBytes,
 std::uint32_t first,std::uint32_t count) {
 if(viewBegin<ownedBegin||!viewBytes||!count)return {};
 const auto offset=viewBegin-ownedBegin;
 if(offset>ownedBytes||viewBytes>ownedBytes-offset||(offset&1)||(viewBytes&1))return {};
 const auto entries=viewBytes/2;
 if(first>entries||count>entries-first)return {};
 const auto normalized=offset/2+first;
 if(normalized>std::numeric_limits<std::uint32_t>::max())return {};
 return static_cast<std::uint32_t>(normalized);
}
}
