#pragma once
#include <windows.h>
#include <cstdio>
#include <cstdint>
#include <cwchar>

namespace malemod::witcher {
// Sealed-test metadata only. No device, hooks, clock or file-identity policy.
class StartupDiagnostics {
 HANDLE file_=INVALID_HANDLE_VALUE;unsigned records_=0;std::uint64_t creation_=0;
 static void Escape(char* out,std::size_t size,const char* text)noexcept{
  std::size_t at=0;if(!text)text="";
  for(unsigned i=0;text[i]&&i<384&&at+7<size;i++){
   const auto c=static_cast<unsigned char>(text[i]);
   if(c=='"'||c=='\\'){out[at++]='\\';out[at++]=char(c);}
   else if(c<32||c>=127){const auto n=std::snprintf(out+at,size-at,"\\u%04x",unsigned(c));if(n>0)at+=std::size_t(n);}
   else out[at++]=char(c);
  }out[at]=0;
 }
 public:
 StartupDiagnostics(bool sealed,const void* address)noexcept{
  if(!sealed)return;const DWORD error=GetLastError();
  HMODULE module=nullptr;wchar_t path[32768]{};
  if(GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,reinterpret_cast<LPCWSTR>(address),&module)){
   const auto size=GetModuleFileNameW(module,path,32768);auto* slash=std::wcsrchr(path,L'\\');
   if(size&&size<32768&&slash){
    FILETIME created{},exited{},kernel{},user{};GetProcessTimes(GetCurrentProcess(),&created,&exited,&kernel,&user);
    const auto identity=(std::uint64_t(created.dwHighDateTime)<<32)|created.dwLowDateTime;creation_=identity;
    const auto remaining=32768-std::size_t(slash+1-path);
    const int n=_snwprintf_s(slash+1,remaining,_TRUNCATE,L"startup-initialize-%lu-%llu.jsonl",GetCurrentProcessId(),static_cast<unsigned long long>(identity));
    if(n>0)file_=CreateFileW(path,GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
   }
  }SetLastError(error);
 }
 ~StartupDiagnostics()noexcept{if(file_!=INVALID_HANDLE_VALUE){const DWORD error=GetLastError();CloseHandle(file_);SetLastError(error);}}
 void Step(const char* step,int result=0,const char* message="")noexcept{
  if(file_==INVALID_HANDLE_VALUE||records_++>=64)return;const DWORD error=GetLastError();
  char escaped[2400]{},label[256]{},line[3072]{};Escape(escaped,sizeof(escaped),message);Escape(label,sizeof(label),step);
  const int n=std::snprintf(line,sizeof(line),"{\"pid\":%lu,\"processCreationTime\":\"%llu\",\"record\":%u,\"step\":\"%s\",\"result\":%d,\"win32Error\":%lu,\"message\":\"%s\"}\n",GetCurrentProcessId(),static_cast<unsigned long long>(creation_),records_,label,result,error,escaped);
  if(n>0&&n<int(sizeof(line))){DWORD written=0;WriteFile(file_,line,DWORD(n),&written,nullptr);FlushFileBuffers(file_);}
  SetLastError(error);
 }
 DWORD Return(DWORD code,const char* step)noexcept{Step(step,int(code));return code;}
};
}
