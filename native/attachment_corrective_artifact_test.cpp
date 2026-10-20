#include "collar_corrective.hpp"
#include <chrono>
#include <iostream>
#include <string>
using namespace malemod::witcher;
using Bytes=std::vector<unsigned char>;
template<class T>void Put(Bytes& b,const T& v){auto p=reinterpret_cast<const unsigned char*>(&v);b.insert(b.end(),p,p+sizeof(v));}
template<class T>void List(Bytes& b,std::initializer_list<T> values){Put(b,std::uint32_t(values.size()));for(auto v:values)Put(b,v);}
void Save(const std::filesystem::path& path,const Bytes& b){std::ofstream f(path,std::ios::binary);f.write(reinterpret_cast<const char*>(b.data()),b.size());}
void Check(bool value){if(!value)throw std::runtime_error("Artifact regression failed");}
int main(){
 auto folder=std::filesystem::temp_directory_path()/("malemod-corrective-test-"+std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
 std::filesystem::create_directory(folder);auto binding=folder/"binding",artifact=folder/"corrective";
 try{
  const Bytes bound={'t','e','s','t'};Save(binding,bound);const std::string revision(40,'a');
  Bytes original={'M','M','C','O','R','R','0','3'};Put(original,std::uint32_t(3));Put(original,collar_detail::FNV(bound.data(),bound.size()));original.insert(original.end(),revision.begin(),revision.end());
  for(double v:{1.,1.,1.,0.,0.,1.,1.,0.,0.,0.,1.,0.,0.,0.,1.})Put(original,v);Put(original,std::uint32_t(2));
  for(unsigned lod=0;lod<2;lod++){
   Put(original,std::uint32_t(4));Put(original,1.);List<std::uint32_t>(original,{0});List<std::uint32_t>(original,{1,2,3});List<std::uint32_t>(original,{1});List<std::uint32_t>(original,{0});
   List<double>(original,{0,0,1});
   Put(original,std::uint32_t(1));Put(original,1.);List<malemod::surface::corrective::Point>(original,{{0,0,.2},{0,0,.2},{0,0,.2}});
  }
  auto seal=[](Bytes b){Put(b,collar_detail::FNV(b.data(),b.size()));return b;};Save(artifact,seal(original));
  auto valid=CollarCorrectiveArtifact::Load(artifact,binding,revision);Check(valid.lods.size()==2&&valid.lods[1].ids.size()==3);
  auto rejected=[&](Bytes data,const std::string& rev){Save(artifact,data);try{CollarCorrectiveArtifact::Load(artifact,binding,rev);return false;}catch(const std::exception&){return true;}};
  auto corrupt=seal(original);corrupt[24]^=1;Check(rejected(corrupt,revision));
  Check(rejected(Bytes{1,2,3},revision));Check(rejected(seal(original),std::string(40,'b')));
  auto unsupported=original;unsupported[8]=4;Check(rejected(seal(unsupported),revision));
  auto trailing=original;trailing.push_back(0);Check(rejected(seal(trailing),revision));
  Save(binding,Bytes{'x'});Check(rejected(seal(original),revision));
  std::filesystem::remove(artifact);std::filesystem::remove(binding);std::filesystem::remove(folder);
  std::cout<<"Corrective artifact: both LODs, checksum, truncation, revision, version and binding tests passed\n";return 0;
 }catch(const std::exception& e){std::filesystem::remove(artifact);std::filesystem::remove(binding);std::filesystem::remove(folder);std::cerr<<e.what()<<'\n';return 1;}
}
