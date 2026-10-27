#include "engine/native_body_sections.hpp"
#include <iostream>
#include <stdexcept>
using namespace malemod::witcher;
static void Check(bool b,const char* why){if(!b)throw std::runtime_error(why);}
int main(){try{
 RenderResource r;
 for(unsigned lod=0;lod<2;lod++)for(unsigned material=0;material<3;material++){
  RenderSection s;s.lod=lod;s.material=material;s.firstVertex=unsigned(r.sections.size())*8;s.vertexCount=8;
  s.positionOffset=s.firstVertex*16;s.indexFirst=unsigned(r.sections.size())*12;s.indexCount=12;r.sections.push_back(s);
 }
 for(unsigned i=0;i<r.sections.size();i++){
  auto s=r.sections[i];Check(native_sections::FromIndices(r,s.indexFirst,12,0)==i,"Exact section interval rejected");
  Check(native_sections::FromIndices(r,s.indexFirst+3,6,0)==i,"Section subset rejected");
  Check(!native_sections::FromIndices(r,s.indexFirst,15,0),"Cross-section draw accepted");
  Check(!native_sections::FromIndices(r,s.indexFirst,12,1),"Unmeasured base accepted");
  Check(native_sections::StaticView(s,s.positionOffset,128,16),"Exact static section rejected");
  Check(native_sections::StaticView(s,s.positionOffset,4096,16),"Trailing native allocation view rejected");
  Check(!native_sections::StaticView(s,s.positionOffset+16,128,16),"Misaligned section position origin accepted");
  Check(!native_sections::StaticView(s,s.positionOffset,127,16),"Short static section accepted");
  Check(native_sections::MorphView(s,192,24)&&!native_sections::MorphView(s,191,24),"Morph section extent guard failed");
  Check(native_sections::SourceVisible(0,r,i)==(s.material==1||s.material==2),"B04 stock skin altered source anatomy visibility");
  Check(native_sections::SourceVisible(1,r,i),"Upper resource visibility changed");
 }
 Check(!native_sections::FromIndices(r,UINT32_MAX,12,0)&&!native_sections::FromIndices(r,0,UINT32_MAX,0),"Index overflow accepted");
 Check(native_sections::SourceVisible(0,RenderResource{},~0u),"Legacy B03 visibility changed");
 Check(!native_sections::SourceVisible(0,r,~0u),"Unknown B04 section established source visibility");
 r.sections.push_back(r.sections.front());Check(!native_sections::FromIndices(r,0,12,0),"Ambiguous section ownership accepted");
 for(unsigned state=0;state<3;state++){
  Check(native_sections::Active(0,state),"Stock body hidden by source state");
  Check(native_sections::Active(1,state)==(state!=0),"Natural source map selection differs");
  Check(native_sections::Active(2,state)==(state==0),"Erect source map selection differs");
  Check(!native_sections::Active(3,state),"Unknown material selected");
 }
 std::cout<<"PASS bounded B04 section/index/static/morph selection, native trailing views, alias/overflow rejection, exact canonical state0 erect and states1/2 natural\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
