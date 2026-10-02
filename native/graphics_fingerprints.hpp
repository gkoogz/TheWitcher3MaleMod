#pragma once
#include <windows.h>
#include <bcrypt.h>
#include <array>
#include <vector>
#include <string>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <algorithm>
#include <cstring>
#include <cstdint>

namespace malemod::witcher {
// Immutable hashes of our cooked resources. Never stores captured game data.
class GraphicsFingerprints {
 struct Entry {std::uint32_t bytes;std::array<unsigned char,32> prefix,hash;std::string label;};
 std::vector<Entry> entries_;BCRYPT_ALG_HANDLE algorithm_=nullptr;
 public:
 GraphicsFingerprints()=default;
 ~GraphicsFingerprints(){if(algorithm_)BCryptCloseAlgorithmProvider(algorithm_,0);}
 GraphicsFingerprints(const GraphicsFingerprints&)=delete;
 void Load(const std::filesystem::path& path){
  if(!entries_.empty()||algorithm_)throw std::logic_error("Fingerprint lifetime already initialized");
  std::ifstream file(path,std::ios::binary|std::ios::ate);
  if(!file)throw std::runtime_error("Fingerprint file unavailable");
  auto size=file.tellg();if(size<12||size>1024*1024)throw std::runtime_error("Invalid fingerprint file size");
  std::vector<unsigned char> data(static_cast<std::size_t>(size));file.seekg(0);file.read(reinterpret_cast<char*>(data.data()),size);
  if(!file||std::memcmp(data.data(),"MMGPH01\0",8))throw std::runtime_error("Invalid fingerprint header");
  std::size_t at=8;
  auto take=[&](void* target,std::size_t count){if(count>data.size()-at)throw std::runtime_error("Truncated fingerprint");std::memcpy(target,data.data()+at,count);at+=count;};
  std::uint32_t count;take(&count,4);if(!count||count>1024)throw std::runtime_error("Invalid fingerprint count");
  std::vector<Entry> result;result.reserve(count);
  for(std::uint32_t i=0;i<count;i++){Entry e{};std::uint16_t length;take(&e.bytes,4);take(&length,2);
   if(e.bytes<32||e.bytes>64*1024*1024||!length||length>128)throw std::runtime_error("Invalid fingerprint record");
   take(e.prefix.data(),32);take(e.hash.data(),32);e.label.resize(length);take(e.label.data(),length);
   for(auto c:e.label)if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-'||c=='.'))throw std::runtime_error("Invalid fingerprint label");
   result.push_back(std::move(e));
  }
  if(at!=data.size())throw std::runtime_error("Unexpected fingerprint trailer");
  if(BCryptOpenAlgorithmProvider(&algorithm_,BCRYPT_SHA256_ALGORITHM,nullptr,0)<0)throw std::runtime_error("SHA256 provider unavailable");
  entries_=std::move(result);
 }
 bool HasSize(std::uint64_t bytes)const{return std::any_of(entries_.begin(),entries_.end(),[&](const Entry& e){return e.bytes==bytes;});}
 std::size_t Count()const{return entries_.size();}
 std::vector<std::string> Match(const void* bytes,std::uint32_t count)const{
  std::vector<std::string> hits;std::array<unsigned char,32> hash{};bool hashed=false;
  if(!bytes||count<32)return hits;
  for(const auto& e:entries_)if(e.bytes==count&&!std::memcmp(bytes,e.prefix.data(),32)){
   if(!hashed){if(!algorithm_||BCryptHash(algorithm_,nullptr,0,static_cast<unsigned char*>(const_cast<void*>(bytes)),count,hash.data(),32)<0)throw std::runtime_error("Fingerprint hash failed");hashed=true;}
   if(hash==e.hash)hits.push_back(e.label);
  }
  return hits;
 }
};
}
