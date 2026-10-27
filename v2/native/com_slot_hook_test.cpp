#define NOMINMAX
#include "engine/com_slot_hook.hpp"
#include <iostream>
#include <stdexcept>
#include <utility>
using Function=int(STDMETHODCALLTYPE*)(void*,int);
template<class F>struct MethodHooks {
 static constexpr std::size_t capacity=16;
 std::array<F,capacity> originals{};std::array<void*,capacity> targets{};std::size_t count=0;
};
MethodHooks<Function> first,second;
int STDMETHODCALLTYPE Original(void*,int x){return x+7;}
int STDMETHODCALLTYPE Other(void*,int x){return x+11;}
int STDMETHODCALLTYPE Foreign(void*,int x){return x+100;}
template<std::size_t N>int STDMETHODCALLTYPE First(void* self,int x){return first.originals[N](self,x)*2;}
template<std::size_t N>int STDMETHODCALLTYPE Second(void* self,int x){return second.originals[N](self,x)*3;}
template<std::size_t...N>auto FirstCallbacks(std::index_sequence<N...>){return std::array<Function,sizeof...(N)>{&First<N>...};}
template<std::size_t...N>auto SecondCallbacks(std::index_sequence<N...>){return std::array<Function,sizeof...(N)>{&Second<N>...};}
void Check(bool value,const char* message){if(!value)throw std::runtime_error(message);}
struct Fake {Function const* table;int Call(std::size_t index,int x){return table[index](this,x);}};
int main(){using namespace malemod::witcher;void* page=nullptr;try{
 page=VirtualAlloc(nullptr,4096,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);Check(page!=nullptr,"Fake table allocation failed");
 auto* table=static_cast<Function*>(page);table[0]=Original;table[1]=Original;table[2]=Other;table[3]=Original;
 DWORD previous=0;Check(VirtualProtect(page,4096,PAGE_READONLY,&previous)!=FALSE,"Fake table read-only protection failed");
 Fake object{table};const auto a=FirstCallbacks(std::make_index_sequence<16>{});const auto b=SecondCallbacks(std::make_index_sequence<16>{});
 Check(HookSlot(first,&object.table[0],a),"First hook failed");Check(object.Call(0,3)==20,"First callback original was not callable");
 Check(first.count==1&&first.originals[0]==Original,"Original family identity changed");
 Check(HookSlot(first,&object.table[0],a)&&first.count==1&&ComSlotHookCount()==1,"Repeated slot registration duplicated hook");
 Check(HookSlot(first,&object.table[1],a),"Second table slot with same implementation was not patched");
 Check(first.count==1&&object.Call(1,3)==20&&ComSlotHookCount()==2,"Duplicate implementation used the wrong callback original");
 Check(HookSlot(first,&object.table[2],a)&&first.count==2&&object.Call(2,3)==28,"Distinct implementation did not retain its own original");
 Check(HookSlot(second,&object.table[3],b)&&second.count==1&&object.Call(3,3)==30,"Different method family alias was suppressed or chained");
 MEMORY_BASIC_INFORMATION info{};Check(VirtualQuery(page,&info,sizeof(info))==sizeof(info)&&info.Protect==PAGE_READONLY,"Read-only table protection was not restored");
 Check(!HookSlot(second,&object.table[0],b),"Different family took an already-owned slot");
 Check(!HookSlot(first,static_cast<Function const*>(nullptr),a),"Null slot accepted");
 Check(VirtualProtect(page,4096,PAGE_READWRITE,&previous)!=FALSE,"Reset fixture protection failed");
 table[2]=Other;DWORD resetIgnored=0;VirtualProtect(page,4096,previous,&resetIgnored);
 Check(HookSlot(first,&object.table[2],a)&&first.count==2&&ComSlotHookCount()==4&&object.Call(2,3)==28,"Known original Reset repatch failed or duplicated ownership");
 // A foreign replacement must survive cleanup; restore retries after its owner
 // retires it. No live COM objects, graphics adapters, game or desktop is used.
 Check(VirtualProtect(page,4096,PAGE_READWRITE,&previous)!=FALSE,"Foreign fixture write protection failed");
 table[1]=Foreign;DWORD ignored=0;VirtualProtect(page,4096,previous,&ignored);
 Check(!HookSlot(first,&object.table[1],a)&&first.count==2,"Unknown Reset replacement was overwritten or added to family");
 Check(!RestoreComSlotHooks(),"Foreign replacement was silently overwritten");Check(object.Call(1,3)==103&&ComSlotHookCount()==1,"Foreign replacement bytes were not preserved");
 Check(object.Call(0,3)==10&&object.Call(2,3)==14&&object.Call(3,3)==10,"Original slots did not restore");
 Check(VirtualProtect(page,4096,PAGE_READWRITE,&previous)!=FALSE,"Fixture callback recovery failed");table[1]=a[0];VirtualProtect(page,4096,previous,&ignored);
 Check(RestoreComSlotHooks()&&ComSlotHookCount()==0&&object.Call(1,3)==10,"Owned restore retry failed");
 Check(RestoreComSlotHooks(),"Empty restore is not repeatable");
 Check(VirtualQuery(page,&info,sizeof(info))==sizeof(info)&&info.Protect==PAGE_READONLY,"Restore changed original memory protection");
 Check(VirtualProtect(page,4096,PAGE_EXECUTE_READ,&previous)!=FALSE,"Executable table fixture failed");
 Check(HookSlot(first,&object.table[0],a)&&first.count==2&&object.Call(0,3)==20,"Rehook after restore did not reuse the original family");
 Check(VirtualQuery(page,&info,sizeof(info))==sizeof(info)&&info.Protect==PAGE_EXECUTE_READ,"Executable page lost its original protection");
 Check(RestoreComSlotHooks()&&object.Call(0,3)==10,"Executable slot did not restore");
 Check(VirtualQuery(page,&info,sizeof(info))==sizeof(info)&&info.Protect==PAGE_EXECUTE_READ,"Executable restore changed original protection");
 VirtualFree(page,0,MEM_RELEASE);page=nullptr;
 std::cout<<"PASS read-only/executable COM slots, duplicate implementation, separate families, callback originals, foreign preservation, rehook and restore\n";return 0;
 }catch(const std::exception& error){if(page){RestoreComSlotHooks();VirtualFree(page,0,MEM_RELEASE);}std::cerr<<error.what()<<'\n';return 1;}
}
