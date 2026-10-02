#pragma once
#include "runtime_controller.hpp"
#include <fstream>

namespace malemod::witcher {
struct RuntimeProfile {
 std::string revision,workerSHA256,bindingsSHA256;
 surface::CoordinateCalibration calibration;
 PoseMatrix inverseBind{};
 std::optional<surface::CollisionCalibration> contacts;
 bool diagnosticSourceContacts=false;
 static RuntimeProfile Load(const std::filesystem::path& path,const std::string& expectedRevision){
  std::ifstream f(path,std::ios::binary);if(!f||std::filesystem::file_size(path)>1024)throw std::runtime_error("Invalid runtime profile size");
  auto bytes=[&](void* p,std::size_t n){if(!f.read(static_cast<char*>(p),n))throw std::runtime_error("Truncated runtime profile");};
  auto text=[&](std::size_t n){std::string s(n,'\0');bytes(s.data(),n);return s;};
  if(text(8)!="MMRUN001")throw std::runtime_error("Unknown runtime profile version");
  RuntimeProfile p;p.revision=text(40);p.workerSHA256=text(64);p.bindingsSHA256=text(64);
  for(const auto& s:{p.revision,p.workerSHA256,p.bindingsSHA256})for(char x:s)if(!((x>='0'&&x<='9')||(x>='a'&&x<='f')))throw std::runtime_error("Invalid runtime revision/hash");
  if(p.revision!=expectedRevision)throw std::runtime_error("Runtime profile differs from compiled Base pin");
  bytes(&p.calibration.basis,sizeof(p.calibration.basis));bytes(&p.calibration.sourceRoot,sizeof(p.calibration.sourceRoot));bytes(&p.calibration.targetRoot,sizeof(p.calibration.targetRoot));bytes(&p.calibration.targetUnitsPerSourceUnit,8);bytes(&p.inverseBind,sizeof(p.inverseBind));
  unsigned flags=0;bytes(&flags,4);if(flags&~3u)throw std::runtime_error("Unknown runtime profile flags");p.diagnosticSourceContacts=bool(flags&2);
  if(flags&1){surface::CollisionCalibration c;bytes(&c.thighRadii,sizeof(c.thighRadii));bytes(&c.pelvisEndpoints,sizeof(c.pelvisEndpoints));bytes(&c.pelvisRadius,sizeof(c.pelvisRadius));p.contacts=c;}
  if(!p.contacts&&!p.diagnosticSourceContacts)throw std::runtime_error("Runtime profile has no calibrated character contacts");
  p.calibration.Validate();InversePose(p.inverseBind);PoseInput validate(p.calibration,p.inverseBind,p.contacts);
  char extra=0;if(f.read(&extra,1))throw std::runtime_error("Trailing runtime profile bytes");return p;
 }
};
}
