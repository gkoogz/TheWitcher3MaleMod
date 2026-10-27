#pragma once
#include <cstdint>
#include <string>
#include <sstream>
namespace malemod::witcher::position_capture {
constexpr std::uint64_t Budget=512ull*1024*1024;
enum class WorldLayout {Unknown,XYZ4,Packed034};
inline WorldLayout Layout(const std::string& sha){
 if(sha=="3b97e5149772e7364a87d70297e223df9187ea25992cafe1da881d1f8fa515d5"||sha=="e5f5a94bbc7a4d7afece0bf12c1ad1fb907d82e4419a7efbadf369518585caa9")return WorldLayout::XYZ4;
 if(sha=="10b6bfbf76bcc58e39955bf77c0e9afdf7a71ab611bf1d7ba64d645a25b702ad")return WorldLayout::Packed034;
 return WorldLayout::Unknown;
}
struct Request {std::string station,id;unsigned stage=0,width=0,height=0,left=0,top=0,roiWidth=0,roiHeight=0;};
inline bool Parse(const std::string& text,const std::string& station,Request& r){
 if(text.size()>512)return false;std::istringstream f(text);std::string magic;Request value;
 if(!(f>>magic>>value.station>>value.id>>value.stage>>value.width>>value.height>>value.left>>value.top>>value.roiWidth>>value.roiHeight))return false;f>>std::ws;
 if(!f.eof()||magic!="MMGP1"||station.empty()||value.station!=station||value.id.empty()||value.id.size()>64||value.id.find_first_not_of("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")!=std::string::npos)return false;
 if(value.stage>=1000||value.width<256||value.height<256||value.width>4096||value.height>2160||!value.roiWidth||!value.roiHeight||value.left>=value.width||value.top>=value.height||value.roiWidth>value.width-value.left||value.roiHeight>value.height-value.top)return false;
 r=value;return true;
}
inline unsigned Component(bool cloth,unsigned resource,unsigned material,unsigned kind){return cloth?(kind<4?3+kind:7):resource==1?0:resource==0?(material==0?1:material<=2?2:7):7;}
inline bool Reserve(std::uint64_t& used,std::uint64_t bytes){if(bytes>Budget||used>Budget-bytes)return false;used+=bytes;return true;}
}
