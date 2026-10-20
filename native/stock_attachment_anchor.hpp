#pragma once
#include <malemod/surface/runtime.hpp>
#include <array>

namespace malemod::witcher {
// Preview-only measured authoring binding. Original licensed lower FBX SHA256:
// 486dcf786c56068a54625eaa4a7d1527e9dd3cf721b52a52a838f141cd5ad51d.
// LOD0 triangle 75, donors 71/70/65 and barycentric weights
// .00972417245878604 / .6419497766830006 / .3483260508582134.
// Native meters (0,.07096233882514812,.975), calibrated by the existing
// 431e626 Geralt binding. Use one root for worker mechanics and both LODs.
inline constexpr std::array<double,3> geraltStockAttachmentAnchor={
 6.562195452391908,.1267323493957523,83.42259979248047};
inline surface::Point StockAttachmentAnchor(){
 return {float(geraltStockAttachmentAnchor[0]),float(geraltStockAttachmentAnchor[1]),float(geraltStockAttachmentAnchor[2])};
}
}
