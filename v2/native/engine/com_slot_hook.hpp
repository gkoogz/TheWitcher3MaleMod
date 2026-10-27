#pragma once
// SDK COM calls dispatch through data slots. Patching those slots avoids an
// executable trampoline/near-allocation search inside a packed driver image.
// The caller serializes each MethodHooks family and keeps its vtables alive.
#include <windows.h>
#include <array>
#include <cstddef>
#include <cstdint>
#include <mutex>
#include <type_traits>

namespace malemod::witcher {
namespace com_slot_detail {
struct Patch {void* volatile* slot=nullptr;void* original=nullptr;void* callback=nullptr;};
struct Registry {std::mutex mutex;std::array<Patch,4096> rows{};std::size_t count=0;};
inline Registry& Patches(){static Registry value;return value;}

inline bool Accessible(void* volatile* slot,MEMORY_BASIC_INFORMATION& info){
 if(!slot||(reinterpret_cast<std::uintptr_t>(slot)%alignof(void*))!=0)return false;
 if(VirtualQuery(const_cast<void**>(slot),&info,sizeof(info))!=sizeof(info)||info.State!=MEM_COMMIT
    ||(info.Protect&(PAGE_NOACCESS|PAGE_GUARD))!=0)return false;
 const auto begin=reinterpret_cast<std::uintptr_t>(slot);
 return begin+sizeof(void*)<=reinterpret_cast<std::uintptr_t>(info.BaseAddress)+info.RegionSize;
}

inline bool Exchange(void* volatile* slot,void* expected,void* replacement){
 MEMORY_BASIC_INFORMATION info{};if(!Accessible(slot,info))return false;
 const DWORD executable=PAGE_EXECUTE|PAGE_EXECUTE_READ|PAGE_EXECUTE_READWRITE|PAGE_EXECUTE_WRITECOPY;
 const DWORD writable=((info.Protect&executable)?PAGE_EXECUTE_READWRITE:PAGE_READWRITE)
   |(info.Protect&(PAGE_NOCACHE|PAGE_WRITECOMBINE));
 DWORD previous=0;if(!VirtualProtect(const_cast<void**>(slot),sizeof(void*),writable,&previous))return false;
 const bool changed=InterlockedCompareExchangePointer(slot,replacement,expected)==expected;
 DWORD ignored=0;const bool protectedAgain=VirtualProtect(const_cast<void**>(slot),sizeof(void*),previous,&ignored)!=FALSE;
 // A protection restoration failure must not leave an untracked publication.
 if(changed&&!protectedAgain){
  InterlockedCompareExchangePointer(slot,expected,replacement);
  VirtualProtect(const_cast<void**>(slot),sizeof(void*),previous,&ignored);
 }
 return changed&&protectedAgain;
}
}

// Methods is the existing MethodHooks<F> shape: capacity, originals, targets,
// count. callbacks[N] invokes originals[N]; one family may share an original
// implementation across many vtables, but each distinct slot is still patched.
template<class Methods,class Function,std::size_t N>
bool HookSlot(Methods& methods,Function const* slot,const std::array<Function,N>& callbacks){
 static_assert(std::is_pointer_v<Function>&&std::is_function_v<std::remove_pointer_t<Function>>,"Expected a typed COM function pointer");
 static_assert(sizeof(Function)==sizeof(void*),"Windows COM pointer size differs");
 static_assert(N>=Methods::capacity,"Missing callback family slots");
 auto* address=reinterpret_cast<void* volatile*>(const_cast<Function*>(slot));
 auto& registry=com_slot_detail::Patches();std::lock_guard<std::mutex> lock(registry.mutex);
 MEMORY_BASIC_INFORMATION info{};
 if(methods.count>Methods::capacity||!com_slot_detail::Accessible(address,info))return false;
 auto current=*slot;if(!current)return false;
 com_slot_detail::Patch* owned=nullptr;
 for(std::size_t i=0;i<registry.count;i++)if(registry.rows[i].slot==address){owned=&registry.rows[i];break;}
 for(std::size_t i=0;i<methods.count;i++)if(current==callbacks[i]){
  return !owned||owned->callback==reinterpret_cast<void*>(current);
 }
 std::size_t index=methods.count;
 for(std::size_t i=0;i<methods.count;i++){
  if(methods.originals[i]==current||methods.targets[i]==reinterpret_cast<void*>(current)){index=i;break;}
 }
 if(index>=Methods::capacity||!callbacks[index])return false;
 if(owned){
  // Reset/interposer code may rewrite its table to the exact known original.
  // Reapply only that same family's callback without allocating another row.
  if(index==methods.count||owned->original!=reinterpret_cast<void*>(current)
     ||owned->callback!=reinterpret_cast<void*>(callbacks[index]))return false;
  return com_slot_detail::Exchange(address,owned->original,owned->callback);
 }
 if(registry.count==registry.rows.size())return false;
 const bool newImplementation=index==methods.count;
 if(newImplementation){
  methods.originals[index]=current;methods.targets[index]=reinterpret_cast<void*>(current);++methods.count;
 }
 if(!com_slot_detail::Exchange(address,reinterpret_cast<void*>(current),reinterpret_cast<void*>(callbacks[index]))){
  if(newImplementation){--methods.count;methods.originals[index]=nullptr;methods.targets[index]=nullptr;}
  return false;
 }
 registry.rows[registry.count++]={address,reinterpret_cast<void*>(current),reinterpret_cast<void*>(callbacks[index])};
 return true;
}

// Controlled teardown only: first stop callback dispatch and keep all driver
// vtables resident. A foreign replacement is preserved and remains reported.
inline bool RestoreComSlotHooks(){
 auto& registry=com_slot_detail::Patches();std::lock_guard<std::mutex> lock(registry.mutex);bool complete=true;
 for(std::size_t i=registry.count;i>0;--i){
  auto& row=registry.rows[i-1];MEMORY_BASIC_INFORMATION info{};
  if(!com_slot_detail::Accessible(row.slot,info)){complete=false;continue;}
  auto current=*row.slot;
  if(current==row.original){row={};continue;}
  if(current!=row.callback||!com_slot_detail::Exchange(row.slot,row.callback,row.original)){complete=false;continue;}
  row={};
 }
 std::size_t retained=0;
 for(std::size_t i=0;i<registry.count;i++)if(registry.rows[i].slot)registry.rows[retained++]=registry.rows[i];
 registry.count=retained;return complete;
}

inline std::size_t ComSlotHookCount(){
 auto& registry=com_slot_detail::Patches();std::lock_guard<std::mutex> lock(registry.mutex);return registry.count;
}
}
