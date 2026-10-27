#pragma once
#include <windows.h>
#include <malemod/surface/canonical_packet.hpp>
#include <filesystem>
#include <string>
#include <stdexcept>
#include <new>

namespace malemod::witcher::v2 {
class SourceHost {
 HANDLE mapping_=nullptr,input_=nullptr,output_=nullptr;
 PROCESS_INFORMATION process_{};
 surface::canonical::Packet* packet_=nullptr;
 std::uint64_t sequence_=0;
 public:
 explicit SourceHost(const std::filesystem::path& executable){
  const auto name=L"Local\\MaleModV2."+std::to_wstring(GetCurrentProcessId());
  mapping_=CreateFileMappingW(INVALID_HANDLE_VALUE,nullptr,PAGE_READWRITE,0,sizeof(surface::canonical::Packet),(name+L".map").c_str());
  input_=CreateEventW(nullptr,FALSE,FALSE,(name+L".input").c_str());
  output_=CreateEventW(nullptr,FALSE,FALSE,(name+L".output").c_str());
  if(!mapping_||!input_||!output_)throw std::runtime_error("Cannot create canonical source channel");
  auto* memory=MapViewOfFile(mapping_,FILE_MAP_ALL_ACCESS,0,0,sizeof(surface::canonical::Packet));
  if(!memory)throw std::runtime_error("Cannot map canonical source channel");
  packet_=new(memory)surface::canonical::Packet{};
  std::wstring command=L"\""+executable.wstring()+L"\" \""+name+L"\" "+std::to_wstring(GetCurrentProcessId());
  STARTUPINFOW startup{};startup.cb=sizeof(startup);startup.dwFlags=STARTF_USESHOWWINDOW;startup.wShowWindow=SW_HIDE;
  if(!CreateProcessW(executable.c_str(),command.data(),nullptr,nullptr,FALSE,CREATE_NO_WINDOW,nullptr,executable.parent_path().c_str(),&startup,&process_))throw std::runtime_error("Cannot start canonical source process");
 }
 ~SourceHost(){
  if(packet_){packet_->stop=1;SetEvent(input_);}
  if(process_.hProcess){if(WaitForSingleObject(process_.hProcess,3000)==WAIT_TIMEOUT)TerminateProcess(process_.hProcess,1);CloseHandle(process_.hProcess);}
  if(process_.hThread)CloseHandle(process_.hThread);
  if(packet_)UnmapViewOfFile(packet_);if(mapping_)CloseHandle(mapping_);if(input_)CloseHandle(input_);if(output_)CloseHandle(output_);
 }
 SourceHost(const SourceHost&)=delete;
 surface::canonical::Packet& Input(){return *packet_;}
 const surface::canonical::Packet& Step(){
  packet_->request=++sequence_;packet_->status=0;MemoryBarrier();SetEvent(input_);
  HANDLE handles[]={output_,process_.hProcess};
  if(WaitForMultipleObjects(2,handles,FALSE,5000)!=WAIT_OBJECT_0||packet_->completed!=sequence_||packet_->status!=1)
   throw std::runtime_error("Canonical source failed or returned stale output");
  return *packet_;
 }
 unsigned ProcessID()const{return process_.dwProcessId;}
};
}
