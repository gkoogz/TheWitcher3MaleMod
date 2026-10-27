#define NOMINMAX
#define DIRECTINPUT_VERSION 0x0800
#include "overlay_input.hpp"
#include <dinput.h>
#include <atomic>
#include <array>
#include <mutex>
#include <vector>
#include <cstring>
namespace malemod::witcher {namespace {
std::atomic<HWND> parent{};std::atomic<bool> expanded{},visible{},privateSession{};
std::atomic<unsigned> importCount{},asyncCount{},rawCount{},messageCount{},directCount{},keyboardCount{};
using Async=SHORT(WINAPI*)(int);using Raw=UINT(WINAPI*)(HRAWINPUT,UINT,LPVOID,PUINT,UINT);using Peek=BOOL(WINAPI*)(LPMSG,HWND,UINT,UINT,UINT);
Async asyncOriginal=&GetAsyncKeyState;Raw rawOriginal=nullptr;Peek peekOriginal=nullptr;
using Create=HRESULT(WINAPI*)(HINSTANCE,DWORD,REFIID,LPVOID*,LPUNKNOWN);Create createOriginal=nullptr;
struct Patch {void** slot;void* before;void* after;};std::vector<Patch> patches;std::mutex gate;
struct Methods {void** table;void* create=nullptr;void* release=nullptr;void* state=nullptr;void* data=nullptr;void* cooperative=nullptr;};
struct Device {void* pointer;HWND owner;};std::vector<Methods> factories,devices;std::vector<Device> identities;
bool PatchSlot(void** slot,void* hook){if(*slot==hook)return true;DWORD protection=0;if(!VirtualProtect(slot,sizeof(*slot),PAGE_READWRITE,&protection))return false;patches.push_back({slot,*slot,hook});InterlockedExchangePointer(slot,hook);DWORD ignored;VirtualProtect(slot,sizeof(*slot),protection,&ignored);return true;}
using Focus=HWND(WINAPI*)();Focus foreground=&GetForegroundWindow;
bool Scope(){auto p=parent.load();return p&&(privateSession.load()||foreground()==p);}
bool Block(unsigned key){return Scope()&&OverlayInputBlocks(key,expanded.load(),visible.load());}
SHORT WINAPI AsyncHook(int key){if(Block(unsigned(key))){++asyncCount;return 0;}return asyncOriginal(key);}
UINT WINAPI RawHook(HRAWINPUT input,UINT command,LPVOID data,PUINT bytes,UINT header){auto result=rawOriginal(input,command,data,bytes,header);if(result!=UINT(-1)&&command==RID_INPUT&&data&&result>=sizeof(RAWINPUTHEADER)+sizeof(RAWKEYBOARD)){
 auto* raw=static_cast<RAWINPUT*>(data);if(raw->header.dwType==RIM_TYPEKEYBOARD&&!(raw->data.keyboard.Flags&RI_KEY_BREAK)&&Block(raw->data.keyboard.VKey)){raw->data.keyboard.VKey=255;raw->data.keyboard.MakeCode=0;raw->data.keyboard.Message=WM_NULL;raw->data.keyboard.Flags=RI_KEY_BREAK;++rawCount;}}
 return result;}
BOOL WINAPI PeekHook(LPMSG msg,HWND window,UINT first,UINT last,UINT remove){auto result=peekOriginal(msg,window,first,last,remove);if(result&&msg&&msg->hwnd==parent.load()&&(msg->message==WM_KEYDOWN||msg->message==WM_SYSKEYDOWN)&&Block(unsigned(msg->wParam))){msg->message=WM_NULL;msg->wParam=0;msg->lParam=0;++messageCount;}return result;}
Methods Method(void* self,bool factory=false){std::lock_guard<std::mutex> lock(gate);auto** table=*static_cast<void***>(self);for(auto& m:factory?factories:devices)if(m.table==table)return m;return {};}
bool Owned(void* self){if(!Scope())return false;std::lock_guard<std::mutex> lock(gate);for(auto& d:identities)if(d.pointer==self)return d.owner==parent.load();return false;}
struct Key {unsigned vk,scan;};constexpr Key keys[]={{VK_F6,DIK_F6},{VK_F8,DIK_F8},{VK_UP,DIK_UP},{VK_DOWN,DIK_DOWN},{VK_LEFT,DIK_LEFT},{VK_RIGHT,DIK_RIGHT},{VK_LSHIFT,DIK_LSHIFT},{VK_RSHIFT,DIK_RSHIFT},{'J',DIK_J}};
HRESULT STDMETHODCALLTYPE StateHook(void* self,DWORD bytes,LPVOID data){auto m=Method(self);using Fn=HRESULT(STDMETHODCALLTYPE*)(void*,DWORD,LPVOID);if(!m.state)return E_FAIL;auto result=reinterpret_cast<Fn>(m.state)(self,bytes,data);if(SUCCEEDED(result)&&bytes==256&&data&&Owned(self))for(auto k:keys)if(Block(k.vk)){static_cast<unsigned char*>(data)[k.scan]=0;++directCount;}return result;}
HRESULT STDMETHODCALLTYPE DataHook(void* self,DWORD size,LPDIDEVICEOBJECTDATA data,LPDWORD count,DWORD options){auto m=Method(self);using Fn=HRESULT(STDMETHODCALLTYPE*)(void*,DWORD,LPDIDEVICEOBJECTDATA,LPDWORD,DWORD);if(!m.data)return E_FAIL;auto result=reinterpret_cast<Fn>(m.data)(self,size,data,count,options);if(SUCCEEDED(result)&&data&&count&&size>=sizeof(DIDEVICEOBJECTDATA)&&Owned(self)){DWORD kept=0;for(DWORD i=0;i<*count;i++){auto* entry=reinterpret_cast<DIDEVICEOBJECTDATA*>(reinterpret_cast<unsigned char*>(data)+i*size);bool blocked=false;for(auto k:keys)if((entry->dwData&0x80)&&entry->dwOfs==k.scan&&Block(k.vk)){blocked=true;break;}if(blocked){++directCount;continue;}if(i!=kept)std::memmove(reinterpret_cast<unsigned char*>(data)+kept*size,entry,size);++kept;}*count=kept;}return result;}
HRESULT STDMETHODCALLTYPE CooperativeHook(void* self,HWND window,DWORD flags){auto m=Method(self);using Fn=HRESULT(STDMETHODCALLTYPE*)(void*,HWND,DWORD);if(!m.cooperative)return E_FAIL;auto result=reinterpret_cast<Fn>(m.cooperative)(self,window,flags);if(SUCCEEDED(result)){DWORD pid=0;GetWindowThreadProcessId(window,&pid);std::lock_guard<std::mutex> lock(gate);for(auto& d:identities)if(d.pointer==self)d.owner=pid==GetCurrentProcessId()?window:nullptr;}return result;}
ULONG STDMETHODCALLTYPE ReleaseHook(void* self){auto m=Method(self);using Fn=ULONG(STDMETHODCALLTYPE*)(void*);if(!m.release)return 0;auto result=reinterpret_cast<Fn>(m.release)(self);if(!result){std::lock_guard<std::mutex> lock(gate);for(auto it=identities.begin();it!=identities.end();++it)if(it->pointer==self){identities.erase(it);break;}}return result;}
HRESULT STDMETHODCALLTYPE DeviceHook(void* self,REFGUID guid,void** output,LPUNKNOWN outer){auto m=Method(self,true);using Fn=HRESULT(STDMETHODCALLTYPE*)(void*,REFGUID,void**,LPUNKNOWN);if(!m.create)return E_FAIL;auto result=reinterpret_cast<Fn>(m.create)(self,guid,output,outer);if(FAILED(result)||!output||!*output)return result;
 auto* device=*output;auto** table=*static_cast<void***>(device);DIDEVCAPS caps{};caps.dwSize=sizeof(caps);using Caps=HRESULT(STDMETHODCALLTYPE*)(void*,LPDIDEVCAPS);if(FAILED(reinterpret_cast<Caps>(table[3])(device,&caps))||GET_DIDEVICE_TYPE(caps.dwDevType)!=DI8DEVTYPE_KEYBOARD)return result;
 std::lock_guard<std::mutex> lock(gate);bool known=false;for(auto& d:devices)known|=d.table==table;if(!known){devices.push_back({table,nullptr,table[2],table[9],table[10],table[13]});PatchSlot(table+2,reinterpret_cast<void*>(ReleaseHook));PatchSlot(table+9,reinterpret_cast<void*>(StateHook));PatchSlot(table+10,reinterpret_cast<void*>(DataHook));PatchSlot(table+13,reinterpret_cast<void*>(CooperativeHook));}PatchSlot(table+2,reinterpret_cast<void*>(ReleaseHook));PatchSlot(table+9,reinterpret_cast<void*>(StateHook));PatchSlot(table+10,reinterpret_cast<void*>(DataHook));PatchSlot(table+13,reinterpret_cast<void*>(CooperativeHook));bool tracked=false;for(auto& d:identities)if(d.pointer==device){d.owner=nullptr;tracked=true;}if(!tracked)identities.push_back({device,nullptr});++keyboardCount;return result;}
HRESULT WINAPI CreateHook(HINSTANCE instance,DWORD version,REFIID iid,LPVOID* output,LPUNKNOWN outer){auto result=createOriginal(instance,version,iid,output,outer);if(SUCCEEDED(result)&&output&&*output){auto** table=*static_cast<void***>(*output);std::lock_guard<std::mutex> lock(gate);bool known=false;for(auto& f:factories)known|=f.table==table;if(!known){factories.push_back({table,table[3]});PatchSlot(table+3,reinterpret_cast<void*>(DeviceHook));}else PatchSlot(table+3,reinterpret_cast<void*>(DeviceHook));}return result;}
}
bool OverlayInputBlocks(unsigned key,bool open,bool anatomy){if(key==VK_F6)return true;if(anatomy&&key=='J')return true;return anatomy&&open&&(key==VK_F8||key==VK_UP||key==VK_DOWN||key==VK_LEFT||key==VK_RIGHT||key==VK_SHIFT||key==VK_LSHIFT||key==VK_RSHIFT);}
void OverlayInputPublish(HWND window,bool open,bool anatomy,bool probe){DWORD pid=0;GetWindowThreadProcessId(window,&pid);parent=pid==GetCurrentProcessId()?window:nullptr;expanded=open;visible=anatomy;privateSession=probe;}
SHORT OverlayInputPoll(int key){return asyncOriginal(key);}
OverlayInputMetrics OverlayInputStatus(){return {importCount.load(),asyncCount.load(),rawCount.load(),messageCount.load(),directCount.load(),keyboardCount.load()};}
bool OverlayInputInstall(HMODULE executable){
 if(executable!=GetModuleHandleW(nullptr))return false;auto* base=reinterpret_cast<unsigned char*>(executable);auto* dos=reinterpret_cast<IMAGE_DOS_HEADER*>(base);if(dos->e_magic!=IMAGE_DOS_SIGNATURE)return false;auto* nt=reinterpret_cast<IMAGE_NT_HEADERS64*>(base+dos->e_lfanew);if(nt->Signature!=IMAGE_NT_SIGNATURE||nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR64_MAGIC)return false;
 auto directory=nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];if(!directory.VirtualAddress)return false;std::lock_guard<std::mutex> lock(gate);if(importCount)return true;
 for(auto* entry=reinterpret_cast<IMAGE_IMPORT_DESCRIPTOR*>(base+directory.VirtualAddress);entry->Name;++entry){const auto* lib=reinterpret_cast<char*>(base+entry->Name);bool user=!_stricmp(lib,"USER32.dll"),input=!_stricmp(lib,"DINPUT8.dll");if((!user&&!input)||!entry->OriginalFirstThunk)continue;
  auto* names=reinterpret_cast<IMAGE_THUNK_DATA64*>(base+entry->OriginalFirstThunk);auto* slots=reinterpret_cast<IMAGE_THUNK_DATA64*>(base+entry->FirstThunk);for(;names->u1.AddressOfData;++names,++slots){if(IMAGE_SNAP_BY_ORDINAL64(names->u1.Ordinal))continue;const auto* name=reinterpret_cast<IMAGE_IMPORT_BY_NAME*>(base+names->u1.AddressOfData);auto** slot=reinterpret_cast<void**>(&slots->u1.Function);void* hook=nullptr;
   if(user&&!std::strcmp(reinterpret_cast<const char*>(name->Name),"GetAsyncKeyState")){asyncOriginal=reinterpret_cast<Async>(*slot);hook=reinterpret_cast<void*>(AsyncHook);}
   else if(user&&!std::strcmp(reinterpret_cast<const char*>(name->Name),"GetRawInputData")){rawOriginal=reinterpret_cast<Raw>(*slot);hook=reinterpret_cast<void*>(RawHook);}
   else if(user&&!std::strcmp(reinterpret_cast<const char*>(name->Name),"PeekMessageA")){peekOriginal=reinterpret_cast<Peek>(*slot);hook=reinterpret_cast<void*>(PeekHook);}
   else if(input&&!std::strcmp(reinterpret_cast<const char*>(name->Name),"DirectInput8Create")){createOriginal=reinterpret_cast<Create>(*slot);hook=reinterpret_cast<void*>(CreateHook);}
   if(hook&&PatchSlot(slot,hook))++importCount;
  }
 }return importCount>=3;
}
void OverlayInputShutdown(){OverlayInputPublish(nullptr,false,false);std::lock_guard<std::mutex> lock(gate);for(auto i=patches.rbegin();i!=patches.rend();++i){MEMORY_BASIC_INFORMATION region{};if(!VirtualQuery(i->slot,&region,sizeof(region))||region.State!=MEM_COMMIT||(region.Protect&(PAGE_NOACCESS|PAGE_GUARD))||*i->slot!=i->after)continue;DWORD protection=0;if(VirtualProtect(i->slot,sizeof(void*),PAGE_READWRITE,&protection)){InterlockedExchangePointer(i->slot,i->before);DWORD ignored;VirtualProtect(i->slot,sizeof(void*),protection,&ignored);}}patches.clear();importCount=0;}
}




