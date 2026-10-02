#include "target_surface.hpp"
#include <malemod/surface/wire.hpp>
#include <fstream>
#include <iostream>
#include <chrono>
int main(int argc,char** argv){
 if(argc!=5)return 2;
 try{
  std::ifstream input(argv[3],std::ios::binary);malemod::surface::wire::Bytes bytes((std::istreambuf_iterator<char>(input)),{});
  auto source=malemod::surface::wire::DecodeOutput(bytes);
  malemod::witcher::TargetSurface target(argv[1],argv[2]);
  for(unsigned lod=0;lod<target.LODCount();lod++){
   auto start=std::chrono::steady_clock::now();auto result=target.Evaluate(lod,source);auto prepared=std::chrono::steady_clock::now();
   for(unsigned i=0;i<8;i++)if(target.Evaluate(lod,source)!=result)throw std::runtime_error("Repeated full target evaluation changed");
   auto end=std::chrono::steady_clock::now();std::ofstream out(std::string(argv[4])+"-lod"+std::to_string(lod)+".bin",std::ios::binary);
   out.write(reinterpret_cast<const char*>(result.data()),result.size()*sizeof(malemod::surface::PrecisePoint));if(!out)throw std::runtime_error("Cannot write full target output");
   std::cout<<"{\"lod\":"<<lod<<",\"vertices\":"<<result.size()<<",\"firstMs\":"<<std::chrono::duration<double,std::milli>(prepared-start).count()<<",\"cachedMs\":"<<std::chrono::duration<double,std::milli>(end-prepared).count()/8<<"}\n";
  }
 }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
