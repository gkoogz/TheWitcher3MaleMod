#pragma once
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>
#include <utility>
namespace malemod::witcher::shader_signature {
struct Output {
 std::string semantic;
 std::uint32_t index=0,systemValue=0,componentType=0,registerIndex=0,stream=0,minimumPrecision=0;
 std::uint8_t mask=0,readWriteMask=0;
};
struct PixelOutputs {
 std::vector<Output> parameters;
 bool WritesDepth()const {
  for(const auto& p:parameters){
   if(p.systemValue==65||p.systemValue==67||p.systemValue==68)return true;
   auto s=p.semantic;for(auto& c:s)if(c>='A'&&c<='Z')c=char(c-'A'+'a');
   if(s=="sv_depth"||s=="sv_depthgreaterequal"||s=="sv_depthlessequal")return true;
  }return false;
 }
};
// DXBC signature chunks are serialized records, not searchable shader text.
// OSG1 adds stream/minimum-precision to OSGN; OSG5 adds stream only.
inline PixelOutputs ParsePixelOutputs(const void* data,std::size_t size){
 const auto* b=static_cast<const std::uint8_t*>(data);
 auto need=[&](std::size_t at,std::size_t n){if(!b||at>size||n>size-at)throw std::runtime_error("Truncated DXBC output signature");};
 auto u32=[&](std::size_t at){need(at,4);return std::uint32_t(b[at])|(std::uint32_t(b[at+1])<<8)|(std::uint32_t(b[at+2])<<16)|(std::uint32_t(b[at+3])<<24);};
 auto tag=[&](std::size_t at,const char* s){need(at,4);return b[at]==s[0]&&b[at+1]==s[1]&&b[at+2]==s[2]&&b[at+3]==s[3];};
 need(0,32);if(!tag(0,"DXBC")||u32(24)!=size)throw std::runtime_error("Invalid DXBC container bounds");
 const auto count=u32(28);if(!count||count>64)throw std::runtime_error("Invalid DXBC chunk count");need(32,std::size_t(count)*4);
 std::vector<std::pair<std::size_t,std::size_t>> ranges;bool code=false,signature=false;PixelOutputs result;
 for(unsigned c=0;c<count;c++){
  const std::size_t at=u32(32+c*4);if(at<32+std::size_t(count)*4)throw std::runtime_error("DXBC chunk overlaps header");need(at,8);
  const std::size_t bytes=u32(at+4);need(at+8,bytes);const auto end=at+8+bytes;
  for(auto r:ranges)if(at<r.second&&r.first<end)throw std::runtime_error("Overlapping DXBC chunks");ranges.emplace_back(at,end);
  if(tag(at,"DXIL")||tag(at,"SHDR")||tag(at,"SHEX")){
   if(code||bytes<4||(u32(at+8)>>16)!=0)throw std::runtime_error("Expected one pixel shader program");code=true;
  }
  const bool v1=tag(at,"OSG1"),v5=tag(at,"OSG5"),old=tag(at,"OSGN");if(!v1&&!v5&&!old)continue;
  if(signature||bytes<8)throw std::runtime_error("Invalid or duplicate pixel output signature");signature=true;
  const std::size_t base=at+8,n=u32(base),first=u32(base+4),stride=v1?32:v5?28:24;
  if(n>128||first<8||first>bytes||n>(bytes-first)/stride)throw std::runtime_error("Pixel output records leave signature chunk");
  for(std::size_t i=0;i<n;i++){
   const std::size_t p=base+first+i*stride,shift=old?0:4;Output out;
   if(!old)out.stream=u32(p);const std::size_t name=u32(p+shift);
   if(name<first+n*stride||name>=bytes)throw std::runtime_error("Pixel semantic string leaves signature names");
   std::size_t pos=base+name;while(pos<end&&b[pos]){if(out.semantic.size()>=255||b[pos]<32||b[pos]>126)throw std::runtime_error("Invalid pixel semantic string");out.semantic+=char(b[pos++]);}
   if(pos==end||out.semantic.empty())throw std::runtime_error("Unterminated pixel semantic string");
   out.index=u32(p+shift+4);out.systemValue=u32(p+shift+8);out.componentType=u32(p+shift+12);out.registerIndex=u32(p+shift+16);
   out.mask=b[p+shift+20];out.readWriteMask=b[p+shift+21];if((out.mask|out.readWriteMask)&0xf0)throw std::runtime_error("Invalid pixel component mask");
   if(v1)out.minimumPrecision=u32(p+28);result.parameters.push_back(std::move(out));
  }
 }
 if(!code||!signature)throw std::runtime_error("Pixel shader program/output signature missing");return result;
}
}
