#pragma once
#define NOMINMAX
#include <windows.h>
#include <malemod/surface/wire.hpp>
#include <array>
#include <atomic>
#include <mutex>
#include <string>
#include <stdexcept>
#include <cstddef>

namespace malemod::witcher {
namespace wire=malemod::surface::wire;
struct SharedPacket {
 std::uint32_t magic=0,version=0,sequence=0,operation=0,status=0,length=0;
 float stepMs=0,readMs=0,encodeMs=0;
 float geometryMs[16]{};
 std::uint8_t payload[wire::maximumBytes];
};
static_assert(offsetof(SharedPacket,payload)==100&&sizeof(SharedPacket)==wire::maximumBytes+100,"Cross-architecture packet layout changed");
constexpr std::uint32_t packetMagic=0x4d4d5357;
struct Handle {
 HANDLE value=nullptr;
 Handle()=default;explicit Handle(HANDLE v):value(v){}
 ~Handle(){if(value&&value!=INVALID_HANDLE_VALUE)CloseHandle(value);}
 Handle(const Handle&)=delete;Handle& operator=(const Handle&)=delete;
};
inline void Require(bool ok,const char* message){if(!ok)throw std::runtime_error(std::string(message)+" (Win32 "+std::to_string(GetLastError())+")");}
inline std::wstring EventName(const std::wstring& prefix,const wchar_t* suffix){return prefix+suffix;}
struct Channel {
 Handle mapping,request,reply;SharedPacket* packet=nullptr;
 explicit Channel(const std::wstring& prefix,bool create){
  Require(prefix.rfind(L"Local\\MaleModSurface-",0)==0&&prefix.size()<150,"Invalid owned transport name");
  if(create){
   mapping.value=CreateFileMappingW(INVALID_HANDLE_VALUE,nullptr,PAGE_READWRITE,0,sizeof(SharedPacket),EventName(prefix,L"-data").c_str());
   auto error=GetLastError();Require(mapping.value&&error!=ERROR_ALREADY_EXISTS,"Create private surface mapping");
   request.value=CreateEventW(nullptr,FALSE,FALSE,EventName(prefix,L"-request").c_str());
   reply.value=CreateEventW(nullptr,FALSE,FALSE,EventName(prefix,L"-reply").c_str());
  }else{
   mapping.value=OpenFileMappingW(FILE_MAP_ALL_ACCESS,FALSE,EventName(prefix,L"-data").c_str());
   request.value=OpenEventW(SYNCHRONIZE|EVENT_MODIFY_STATE,FALSE,EventName(prefix,L"-request").c_str());
   reply.value=OpenEventW(SYNCHRONIZE|EVENT_MODIFY_STATE,FALSE,EventName(prefix,L"-reply").c_str());
  }
  Require(mapping.value&&request.value&&reply.value,"Open surface transport");
  packet=static_cast<SharedPacket*>(MapViewOfFile(mapping.value,FILE_MAP_ALL_ACCESS,0,0,sizeof(SharedPacket)));
  Require(packet!=nullptr,"Map surface transport");
  if(create){packet->magic=packetMagic;packet->version=wire::version;packet->sequence=0;packet->length=0;packet->status=0;packet->operation=0;}
 }
 ~Channel(){if(packet)UnmapViewOfFile(packet);}
};
inline std::wstring NewChannelName(){
 std::array<unsigned char,16> random{};
 // System RNG, not a predictable/reused name shared with a previous session.
 using Random=BOOLEAN(WINAPI*)(void*,ULONG);
 auto lib=LoadLibraryW(L"advapi32.dll");Require(lib!=nullptr,"Load random generator");
 auto fn=reinterpret_cast<Random>(GetProcAddress(lib,"SystemFunction036"));
 bool ok=fn&&fn(random.data(),ULONG(random.size()));FreeLibrary(lib);Require(ok,"Generate transport token");
 static const wchar_t hex[]=L"0123456789abcdef";std::wstring name=L"Local\\MaleModSurface-"+std::to_wstring(GetCurrentProcessId())+L"-";
 for(auto x:random){name+=hex[x>>4];name+=hex[x&15];}return name;
}
class SurfaceClient {
 std::wstring name_;Channel channel_;Handle job_,process_;std::mutex mutex_;std::uint32_t sequence_=0;bool healthy_=true;
 wire::Bytes Exchange(const wire::Bytes& payload,std::uint32_t operation,DWORD timeout){
  if(!healthy_)throw std::runtime_error("Surface worker requires explicit restart");
  Require(payload.size()<=wire::maximumBytes,"Request too large");
  auto& p=*channel_.packet;p.sequence=++sequence_;p.operation=operation;p.status=0;p.length=std::uint32_t(payload.size());
  std::memcpy(p.payload,payload.data(),payload.size());std::atomic_thread_fence(std::memory_order_release);
  Require(SetEvent(channel_.request.value)!=0,"Submit surface request");
  HANDLE waits[2]={channel_.reply.value,process_.value};auto result=WaitForMultipleObjects(2,waits,FALSE,timeout);
  if(result!=WAIT_OBJECT_0){healthy_=false;throw std::runtime_error(result==WAIT_OBJECT_0+1?"Surface worker exited":"Surface request timed out");}
  std::atomic_thread_fence(std::memory_order_acquire);
  if(p.magic!=packetMagic||p.version!=wire::version||p.sequence!=sequence_||p.length>wire::maximumBytes){healthy_=false;throw std::runtime_error("Invalid surface response identity");}
  if(p.status!=1)throw std::runtime_error(std::string(reinterpret_cast<char*>(p.payload),p.length));
  return wire::Bytes(p.payload,p.payload+p.length);
 }
 public:
 std::array<float,3> LastWorkerTimings()const{return {channel_.packet->stepMs,channel_.packet->readMs,channel_.packet->encodeMs};}
 std::array<float,16> LastGeometryTimings()const{std::array<float,16> result{};std::copy(std::begin(channel_.packet->geometryMs),std::end(channel_.packet->geometryMs),result.begin());return result;}
 explicit SurfaceClient(const std::wstring& worker):name_(NewChannelName()),channel_(name_,true){
  Require(worker.find(L'"')==std::wstring::npos,"Unsafe worker path");
  job_.value=CreateJobObjectW(nullptr,nullptr);Require(job_.value!=nullptr,"Create worker job");
  JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
  Require(SetInformationJobObject(job_.value,JobObjectExtendedLimitInformation,&limits,sizeof(limits))!=0,"Configure worker lifetime");
  std::wstring command=L"\""+worker+L"\" --worker "+name_+L" "+std::to_wstring(GetCurrentProcessId());
  STARTUPINFOW start{};start.cb=sizeof(start);start.dwFlags=STARTF_USESHOWWINDOW;start.wShowWindow=SW_HIDE;PROCESS_INFORMATION info{};
  Require(CreateProcessW(worker.c_str(),command.data(),nullptr,nullptr,FALSE,CREATE_NO_WINDOW|CREATE_SUSPENDED,nullptr,nullptr,&start,&info)!=0,"Launch owned surface worker");
  process_.value=info.hProcess;Handle thread(info.hThread);
  if(!AssignProcessToJobObject(job_.value,process_.value)){TerminateProcess(process_.value,1);throw std::runtime_error("Cannot own surface worker lifetime");}
  Require(ResumeThread(thread.value)!=DWORD(-1),"Start surface worker");
 }
 ~SurfaceClient(){
  if(healthy_&&process_.value&&WaitForSingleObject(process_.value,0)==WAIT_TIMEOUT){try{Exchange({},2,2000);}catch(...){}}
  // Closing our job terminates only its owned worker if graceful shutdown failed.
 }
 malemod::surface::Output Evaluate(const wire::Request& request,DWORD timeout=1000){
  std::lock_guard<std::mutex> lock(mutex_);return wire::DecodeOutput(Exchange(wire::Encode(request),1,timeout));
 }
 malemod::surface::Output Initialize(const malemod::surface::Controls& controls,DWORD timeout=10000){
  std::lock_guard<std::mutex> lock(mutex_);wire::Request request;request.controls=controls;
  return wire::DecodeOutput(Exchange(wire::Encode(request),3,timeout));
 }
};
}
