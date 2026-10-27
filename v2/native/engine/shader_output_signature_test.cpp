#include "shader_output_signature.hpp"
#include <cstring>
#include <fstream>
#include <iterator>
#include <iostream>
using namespace malemod::witcher::shader_signature;
using Bytes=std::vector<std::uint8_t>;
void Check(bool v){if(!v)throw std::runtime_error("Signature test assertion failed");}
void Put(Bytes& v,std::size_t at,std::uint32_t x){for(unsigned i=0;i<4;i++)v.at(at+i)=std::uint8_t(x>>(i*8));}
Bytes Fixture(const char* chunk,const char* name,unsigned system){
 const bool old=std::strcmp(chunk,"OSGN")==0,v1=std::strcmp(chunk,"OSG1")==0;const unsigned stride=old?24:v1?32:28;
 Bytes s(8+stride);Put(s,0,1);Put(s,4,8);const unsigned p=8,shift=old?0:4;Put(s,p+shift,unsigned(s.size()));Put(s,p+shift+8,system);Put(s,p+shift+12,3);s[p+shift+20]=15;
 s.insert(s.end(),name,name+std::strlen(name)+1);
 // Unreferenced text must never be mistaken for a declared depth output.
 const char unused[]="SV_Depth";s.insert(s.end(),unused,unused+sizeof(unused));
 Bytes v(40);std::memcpy(v.data(),"DXBC",4);Put(v,20,1);Put(v,28,2);Put(v,32,40);
 v.insert(v.end(),chunk,chunk+4);auto off=v.size();v.resize(v.size()+4);Put(v,off,unsigned(s.size()));v.insert(v.end(),s.begin(),s.end());Put(v,36,unsigned(v.size()));
 const char code[]="SHDR";v.insert(v.end(),code,code+4);off=v.size();v.resize(v.size()+12);Put(v,off,8);Put(v,off+4,0x50);Put(v,off+8,2);Put(v,24,unsigned(v.size()));return v;
}
void Bad(Bytes v){bool threw=false;try{ParsePixelOutputs(v.data(),v.size());}catch(const std::runtime_error&){threw=true;}Check(threw);}
int main(int argc,char** argv){try{
 for(const auto* kind:{"OSGN","OSG5","OSG1"}){
  auto v=Fixture(kind,"SV_Target",64);auto p=ParsePixelOutputs(v.data(),v.size());Check(p.parameters.size()==1&&!p.WritesDepth()&&p.parameters[0].semantic=="SV_Target");
  for(unsigned sys:{65u,67u,68u}){v=Fixture(kind,"depth_name",sys);Check(ParsePixelOutputs(v.data(),v.size()).WritesDepth());}
  v=Fixture(kind,"sV_DePtH",0);Check(ParsePixelOutputs(v.data(),v.size()).WritesDepth());
 }
 auto v=Fixture("OSG1","SV_Target",64);auto original=v;v.pop_back();Bad(v);v=original;Put(v,28,100);Bad(v);
 v=original;Put(v,32,4);Bad(v);v=original;Put(v,36,40);Bad(v);
 v=original;Put(v,48,129);Bad(v);v=original;Put(v,60,8);Bad(v);
 v=original;const auto codeOffset=std::size_t(v[36])|(std::size_t(v[37])<<8)|(std::size_t(v[38])<<16)|(std::size_t(v[39])<<24);Put(v,codeOffset+8,0x10050);Bad(v);
 unsigned actual=0;for(int i=1;i<argc;i++){std::ifstream in(argv[i],std::ios::binary);Bytes b((std::istreambuf_iterator<char>(in)),{});auto p=ParsePixelOutputs(b.data(),b.size());Check(!p.WritesDepth()&&(p.parameters.size()==4||p.parameters.size()==5));for(const auto& o:p.parameters)Check(o.semantic=="SV_Target"&&o.systemValue==64);++actual;}
 std::cout<<"Signature wire formats/depth variants/malformed bounds passed; actual captured pixel shaders="<<actual<<'\n';return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
