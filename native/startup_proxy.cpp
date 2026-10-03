#define NOMINMAX
#include <windows.h>
#include <dinput.h>
#include "startup_gate.hpp"
#include "game_profile.hpp"

namespace {
malemod::witcher::StartupGate gate;
wchar_t modulePath[32768]{};
HMODULE systemInput=nullptr;
FARPROC SystemFunction(const char* name){
 if(!systemInput){wchar_t path[MAX_PATH]{};const auto n=GetSystemDirectoryW(path,MAX_PATH);if(!n||n+13>=MAX_PATH)return nullptr;
  wcscat_s(path,L"\\dinput8.dll");auto loaded=LoadLibraryExW(path,nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);
  if(!loaded)return nullptr;auto previous=InterlockedCompareExchangePointer(reinterpret_cast<void* volatile*>(&systemInput),loaded,nullptr);if(previous)FreeLibrary(loaded);
 }
 return GetProcAddress(systemInput,name);
}
void Status(const char* text){
 wchar_t path[32768]{};wcscpy_s(path,modulePath);auto slash=wcsrchr(path,L'\\');if(!slash)return;
 wcscpy_s(slash+1,32768-std::size_t(slash+1-path),L"malemod-native\\startup.log");
 HANDLE file=CreateFileW(path,GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
 if(file==INVALID_HANDLE_VALUE)return;DWORD written=0;WriteFile(file,text,DWORD(std::strlen(text)),&written,nullptr);CloseHandle(file);
}
int WINAPI GameEntry(){
 auto original=reinterpret_cast<int(WINAPI*)()>(gate.Restore());if(!original)TerminateProcess(GetCurrentProcess(),0x4d4d0001);
 // This runs on the ordinary executable startup thread after loader return.
 wchar_t path[32768]{};wcscpy_s(path,modulePath);auto slash=wcsrchr(path,L'\\');if(!slash)TerminateProcess(GetCurrentProcess(),0x4d4d0002);
 wcscpy_s(slash+1,32768-std::size_t(slash+1-path),L"malemod-native\\malemod_witcher.dll");
 auto library=LoadLibraryExW(path,nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
 auto initialize=library?reinterpret_cast<DWORD(WINAPI*)(void*)>(GetProcAddress(library,"MaleModInitialize")):nullptr;
 auto runtime=library?reinterpret_cast<DWORD(WINAPI*)(void*)>(GetProcAddress(library,"MaleModRuntimeStatus")):nullptr;
 const auto result=initialize?initialize(nullptr):DWORD(-1);
 if(result||!runtime||!(runtime(nullptr)&1)){Status("Native initialization failed before script compilation. Restore the managed native installation.\r\n");TerminateProcess(GetCurrentProcess(),0x4d4d0003);return 0;}
 Status("Native runtime initialized before game entry; normal startup enabled.\r\n");return original();
}
}
extern "C" HRESULT WINAPI DirectInput8Create(HINSTANCE instance,DWORD version,REFIID iid,LPVOID* out,LPUNKNOWN outer){
 auto fn=reinterpret_cast<HRESULT(WINAPI*)(HINSTANCE,DWORD,REFIID,LPVOID*,LPUNKNOWN)>(SystemFunction("DirectInput8Create"));return fn?fn(instance,version,iid,out,outer):E_FAIL;
}
extern "C" HRESULT WINAPI DllCanUnloadNow(){auto fn=reinterpret_cast<HRESULT(WINAPI*)()>(SystemFunction("DllCanUnloadNow"));return fn?fn():S_FALSE;}
extern "C" HRESULT WINAPI DllGetClassObject(REFCLSID cls,REFIID iid,LPVOID* out){auto fn=reinterpret_cast<HRESULT(WINAPI*)(REFCLSID,REFIID,LPVOID*)>(SystemFunction("DllGetClassObject"));return fn?fn(cls,iid,out):E_FAIL;}
extern "C" HRESULT WINAPI DllRegisterServer(){auto fn=reinterpret_cast<HRESULT(WINAPI*)()>(SystemFunction("DllRegisterServer"));return fn?fn():E_FAIL;}
extern "C" HRESULT WINAPI DllUnregisterServer(){auto fn=reinterpret_cast<HRESULT(WINAPI*)()>(SystemFunction("DllUnregisterServer"));return fn?fn():E_FAIL;}
extern "C" LPCDIDATAFORMAT WINAPI GetdfDIJoystick(){auto fn=reinterpret_cast<LPCDIDATAFORMAT(WINAPI*)()>(SystemFunction("GetdfDIJoystick"));return fn?fn():nullptr;}
BOOL WINAPI DllMain(HINSTANCE self,DWORD reason,LPVOID){
 if(reason!=DLL_PROCESS_ATTACH)return TRUE;
 if(!GetModuleFileNameW(self,modulePath,32768))return FALSE;
 wchar_t executable[32768]{};if(!GetModuleFileNameW(nullptr,executable,32768))return FALSE;
 const auto filename=wcsrchr(executable,L'\\');if(!filename||_wcsicmp(filename+1,L"witcher3.exe"))return TRUE;
 auto base=reinterpret_cast<unsigned char*>(GetModuleHandleW(nullptr));auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(base);
 if(dos->e_magic!=IMAGE_DOS_SIGNATURE||dos->e_lfanew<0||dos->e_lfanew>4096)return FALSE;
 auto nt=reinterpret_cast<IMAGE_NT_HEADERS64*>(base+dos->e_lfanew);
 if(nt->Signature!=IMAGE_NT_SIGNATURE||nt->OptionalHeader.SizeOfImage!=malemod::witcher::profile::imageSize||nt->OptionalHeader.AddressOfEntryPoint!=0x1a6a598)return FALSE;
 constexpr std::array<unsigned char,14> expected{0x48,0x83,0xec,0x28,0xe8,0xbf,0x0c,0,0,0x48,0x83,0xc4,0x28,0xe9};
 return gate.Arm(base+nt->OptionalHeader.AddressOfEntryPoint,expected,reinterpret_cast<void*>(&GameEntry));
}
