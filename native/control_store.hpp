#pragma once
#include <windows.h>
#include <malemod/surface/wire.hpp>
#include <filesystem>
#include <fstream>
#include <optional>
#include <string>

namespace malemod::witcher {
// Adapter storage only. Values/order/defaults/ranges remain the pinned Base
// Controls contract. This file is user data and is never an installer asset.
class ControlStore {
 std::filesystem::path path_;
 public:
 explicit ControlStore(std::filesystem::path path):path_(std::move(path)){}
 std::optional<surface::Controls> Load()const{
  if(!std::filesystem::exists(path_))return {};
  if(std::filesystem::file_size(path_)!=80)throw std::runtime_error("Invalid saved control size");
  std::ifstream f(path_,std::ios::binary);char magic[8];surface::Controls c;
  if(!f.read(magic,8)||std::memcmp(magic,"MMCNT001",8)||!f.read(reinterpret_cast<char*>(c.values.data()),72))throw std::runtime_error("Unknown saved control contract");
  surface::wire::Validate(c);return c;
 }
 void Save(const surface::Controls& c)const{
  surface::wire::Validate(c);auto temporary=path_;temporary+=L".tmp-"+std::to_wstring(GetCurrentProcessId());
  unsigned char bytes[80];std::memcpy(bytes,"MMCNT001",8);std::memcpy(bytes+8,c.values.data(),72);
  auto handle=CreateFileW(temporary.c_str(),GENERIC_WRITE,0,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
  if(handle==INVALID_HANDLE_VALUE)throw std::runtime_error("Cannot open saved controls");DWORD written=0;
  const bool ok=WriteFile(handle,bytes,80,&written,nullptr)&&written==80&&FlushFileBuffers(handle);CloseHandle(handle);
  if(!ok||!MoveFileExW(temporary.c_str(),path_.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)){DeleteFileW(temporary.c_str());throw std::runtime_error("Cannot atomically save controls");}
 }
};
}
