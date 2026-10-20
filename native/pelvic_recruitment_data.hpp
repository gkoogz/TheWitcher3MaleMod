#pragma once
#include <malemod/surface/pelvic_recruitment.hpp>
#include <filesystem>
#include <fstream>
#include <cstring>
namespace malemod::witcher {
struct PelvicRecruitmentData {
 std::vector<std::vector<double>> participation;
 std::vector<std::vector<double>> angles,stations;
 std::vector<std::vector<double>> lobeRoles;
 static std::uint64_t FNV(const unsigned char* p,std::size_t n){std::uint64_t h=14695981039346656037ull;for(std::size_t i=0;i<n;i++){h^=p[i];h*=1099511628211ull;}return h;}
 static std::vector<unsigned char> File(const std::filesystem::path& p){const auto n=std::filesystem::file_size(p);if(n>16*1024*1024)throw std::invalid_argument("Oversize pelvic material artifact");std::vector<unsigned char>b(std::size_t(n),0);std::ifstream f(p,std::ios::binary);if(!f.read(reinterpret_cast<char*>(b.data()),b.size()))throw std::invalid_argument("Unreadable pelvic material artifact");return b;}
 static PelvicRecruitmentData Load(const std::filesystem::path& path,const std::filesystem::path& bindings,const std::string& revision){
  auto bytes=File(path);if(bytes.size()<68)throw std::invalid_argument("Short pelvic material artifact");std::uint64_t checksum;std::memcpy(&checksum,bytes.data()+bytes.size()-8,8);if(FNV(bytes.data(),bytes.size()-8)!=checksum)throw std::invalid_argument("Pelvic material checksum differs");
  std::size_t at=0;auto read=[&](void* p,std::size_t n){if(n>bytes.size()-8-at)throw std::invalid_argument("Truncated pelvic material artifact");std::memcpy(p,bytes.data()+at,n);at+=n;};
  char magic[8],base[40];std::uint64_t bindingHash;std::uint32_t lodCount;read(magic,8);read(base,40);read(&bindingHash,8);read(&lodCount,4);const auto original=File(bindings);
  const bool roles=!std::memcmp(magic,"MMPREC03",8);
  if((!roles&&std::memcmp(magic,"MMPREC02",8))||revision.size()!=40||std::string(base,40)!=revision||bindingHash!=FNV(original.data(),original.size())||lodCount!=2)throw std::invalid_argument("Pelvic material binding differs");
  PelvicRecruitmentData out;for(unsigned l=0;l<lodCount;l++){std::uint32_t count;read(&count,4);if(count>1000000)throw std::invalid_argument("Oversize pelvic material count");std::vector<double> weights(count),angles(count),stations(count);read(weights.data(),weights.size()*sizeof(double));read(angles.data(),angles.size()*sizeof(double));read(stations.data(),stations.size()*sizeof(double));for(unsigned i=0;i<count;i++)if(!std::isfinite(weights[i]+angles[i]+stations[i])||weights[i]<0||weights[i]>1||stations[i]<-.01||stations[i]>1.5)throw std::invalid_argument("Invalid pelvic material chart");out.participation.push_back(std::move(weights));out.angles.push_back(std::move(angles));out.stations.push_back(std::move(stations));if(roles){std::vector<double> ownership(count);read(ownership.data(),ownership.size()*sizeof(double));for(double x:ownership)if(!std::isfinite(x)||x<0||x>1.000001)throw std::invalid_argument("Invalid source material ownership");out.lobeRoles.push_back(std::move(ownership));}}
  if(at!=bytes.size()-8)throw std::invalid_argument("Trailing pelvic material bytes");return out;
 }
};
}
