#pragma once
#define NOMINMAX
#include <windows.h>
#include <array>
#include <cstring>

namespace malemod::witcher {
// Redirect only the hash-locked executable entry, before it runs. The complete
// original bytes are restored before calling it, so no instruction relocation
// or partially decoded instruction is executed. Initialization occurs outside
// DllMain and the Windows loader lock.
class StartupGate {
 void* entry_=nullptr;std::array<unsigned char,14> original_{};
 public:
 bool Arm(void* entry,const std::array<unsigned char,14>& expected,void* gate){
  if(entry_||!entry||!gate||std::memcmp(entry,expected.data(),expected.size()))return false;
  DWORD old=0;if(!VirtualProtect(entry,14,PAGE_EXECUTE_READWRITE,&old))return false;
  original_=expected;entry_=entry;
  std::array<unsigned char,14> jump{0xff,0x25,0,0,0,0};std::memcpy(jump.data()+6,&gate,8);
  std::memcpy(entry,jump.data(),14);FlushInstructionCache(GetCurrentProcess(),entry,14);
  DWORD unused=0;return VirtualProtect(entry,14,old,&unused)!=0;
 }
 void* Restore(){
  if(!entry_)return nullptr;DWORD old=0;if(!VirtualProtect(entry_,14,PAGE_EXECUTE_READWRITE,&old))return nullptr;
  void* result=entry_;std::memcpy(result,original_.data(),14);FlushInstructionCache(GetCurrentProcess(),result,14);
  DWORD unused=0;if(!VirtualProtect(result,14,old,&unused))return nullptr;entry_=nullptr;return result;
 }
};
}
