#include "pelvic_recruitment_data.hpp"
#include <chrono>
#include <iostream>
#include <limits>
#include <string>
using namespace malemod::witcher;
using Bytes=std::vector<unsigned char>;
template<class T>void Put(Bytes& bytes,T value){const auto* p=reinterpret_cast<const unsigned char*>(&value);bytes.insert(bytes.end(),p,p+sizeof(value));}
void Save(const std::filesystem::path& path,const Bytes& bytes){std::ofstream out(path,std::ios::binary);out.write(reinterpret_cast<const char*>(bytes.data()),bytes.size());}
void Check(bool value){if(!value)throw std::runtime_error("Pelvic ownership artifact regression");}
int main(){
 const auto dir=std::filesystem::temp_directory_path()/("malemod-material-test-"+std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));std::filesystem::create_directory(dir);
 const auto binding=dir/"binding",file=dir/"material";const Bytes bound={'t','e','s','t'};Save(binding,bound);const std::string revision(40,'a');
 auto make=[&](bool roles,double role=.5){Bytes b={'M','M','P','R','E','C','0',static_cast<unsigned char>(roles?'3':'2')};b.insert(b.end(),revision.begin(),revision.end());Put(b,PelvicRecruitmentData::FNV(bound.data(),bound.size()));Put(b,std::uint32_t(2));for(unsigned lod=0;lod<2;lod++){Put(b,std::uint32_t(3));for(double x:{0.,.5,1.,0.,1.,2.,0.,.1,.8})Put(b,x);if(roles)for(double x:{1.,role,0.})Put(b,x);}Put(b,PelvicRecruitmentData::FNV(b.data(),b.size()));return b;};
 try{
  for(bool roles:{false,true}){Save(file,make(roles));auto data=PelvicRecruitmentData::Load(file,binding,revision);Check(data.participation.size()==2&&data.stations[1][2]==.8);Check(data.lobeRoles.size()==(roles?2:0));if(roles)Check(data.lobeRoles[0][1]==.5);}
  auto reject=[&](Bytes b){Save(file,b);try{PelvicRecruitmentData::Load(file,binding,revision);return false;}catch(const std::exception&){return true;}};
  Check(reject(make(true,-.1)));Check(reject(make(true,1.01)));Check(reject(make(true,std::numeric_limits<double>::quiet_NaN())));
  auto corrupt=make(true);corrupt[70]^=1;Check(reject(corrupt));auto shortFile=make(true);shortFile.resize(67);Check(reject(shortFile));
  Save(binding,Bytes{'x'});Check(reject(make(true)));std::filesystem::remove(file);std::filesystem::remove(binding);std::filesystem::remove(dir);
  std::cout<<"MMPREC02/03, ownership, checksum, truncation and binding validation passed\n";return 0;
 }catch(const std::exception& e){std::filesystem::remove(file);std::filesystem::remove(binding);std::filesystem::remove(dir);std::cerr<<e.what()<<'\n';return 1;}
}
