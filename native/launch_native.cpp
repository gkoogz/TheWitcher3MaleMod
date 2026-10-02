#define NOMINMAX
#include <windows.h>
#include <tlhelp32.h>
#include <psapi.h>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {
struct Handle {HANDLE h=nullptr;explicit Handle(HANDLE p=nullptr):h(p){}~Handle(){if(h&&h!=INVALID_HANDLE_VALUE)CloseHandle(h);}};
void Check(bool value,const char* text){if(!value)throw std::runtime_error(std::string(text)+" (Win32 "+std::to_string(GetLastError())+")");}
bool GameRunning(){
 Handle snapshot(CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS,0));Check(snapshot.h!=INVALID_HANDLE_VALUE,"Read game process state");
 PROCESSENTRY32W entry{};entry.dwSize=sizeof(entry);if(!Process32FirstW(snapshot.h,&entry))return false;
 do{if(_wcsicmp(entry.szExeFile,L"witcher3.exe")==0)return true;}while(Process32NextW(snapshot.h,&entry));return false;
}
std::uintptr_t RemoteModule(DWORD pid,HANDLE process,const wchar_t* name){
 HANDLE raw=INVALID_HANDLE_VALUE;
 for(unsigned attempt=0;attempt<4;attempt++){raw=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE,pid);if(raw!=INVALID_HANDLE_VALUE||GetLastError()!=ERROR_BAD_LENGTH)break;}
 Handle snapshot(raw);
 if(snapshot.h==INVALID_HANDLE_VALUE){
  // Toolhelp cannot enumerate an uninitialized suspended process (299). Its
  // mapped images still have file identities; query only our child's VADs.
  Check(GetLastError()==ERROR_PARTIAL_COPY||GetLastError()==ERROR_BAD_LENGTH,"Read owned process modules");
  std::uintptr_t cursor=0;
  for(;;){
   MEMORY_BASIC_INFORMATION region{};if(!VirtualQueryEx(process,reinterpret_cast<const void*>(cursor),&region,sizeof(region)))break;
   const auto next=reinterpret_cast<std::uintptr_t>(region.BaseAddress)+region.RegionSize;if(next<=cursor)break;
   if(region.Type==MEM_IMAGE&&region.BaseAddress==region.AllocationBase){
    wchar_t path[32768]{};if(GetMappedFileNameW(process,region.AllocationBase,path,32768)&&_wcsicmp(std::filesystem::path(path).filename().c_str(),name)==0)return reinterpret_cast<std::uintptr_t>(region.AllocationBase);
   }
   cursor=next;
  }
  return 0;
 }
 MODULEENTRY32W entry{};entry.dwSize=sizeof(entry);if(!Module32FirstW(snapshot.h,&entry))return 0;
 do{if(_wcsicmp(entry.szModule,name)==0)return reinterpret_cast<std::uintptr_t>(entry.modBaseAddr);}while(Module32NextW(snapshot.h,&entry));return 0;
}
DWORD Invoke(HANDLE process,std::uintptr_t function,void* argument){
 Handle thread(CreateRemoteThread(process,nullptr,0,reinterpret_cast<LPTHREAD_START_ROUTINE>(function),argument,0,nullptr));Check(thread.h!=nullptr,"Initialize owned native module");
 Check(WaitForSingleObject(thread.h,30000)==WAIT_OBJECT_0,"Wait for native initialization");DWORD result=0;Check(GetExitCodeThread(thread.h,&result)!=0,"Read native initialization result");return result;
}
}
int wmain(int argc,wchar_t** argv){
 if(argc!=3){std::wcerr<<L"Usage: launch_native <exact witcher3.exe> <owned malemod_witcher.dll>\n";return 2;}
 PROCESS_INFORMATION process{};bool resumed=false;
 try{
  const auto game=std::filesystem::canonical(argv[1]),library=std::filesystem::canonical(argv[2]);
  Check(_wcsicmp(game.filename().c_str(),L"witcher3.exe")==0,"Require the actual game executable");
  Check(_wcsicmp(library.filename().c_str(),L"malemod_witcher.dll")==0,"Require the owned module");
  Check(!GameRunning(),"Game is already running; preserve its session");
  // Steam identity is local to this launcher and its child; no game file or
  // user's persistent environment is written.
  SetEnvironmentVariableW(L"SteamAppId",L"292030");SetEnvironmentVariableW(L"SteamGameId",L"292030");
  std::wstring command=L"\""+game.wstring()+L"\"";
  STARTUPINFOW startup{};startup.cb=sizeof(startup);
  Check(CreateProcessW(game.c_str(),command.data(),nullptr,nullptr,FALSE,CREATE_SUSPENDED,nullptr,game.parent_path().c_str(),&startup,&process)!=0,"Launch owned game process suspended");
  FILETIME created{},exited{},kernel{},user{};
  Check(GetProcessTimes(process.hProcess,&created,&exited,&kernel,&user)!=0,"Identify owned process lifetime");
  const auto creationTime=(std::uint64_t(created.dwHighDateTime)<<32)|created.dwLowDateTime;
  // Locate LoadLibraryW relative to its containing system module. Its local
  // absolute address is not assumed to be valid in another process.
  auto localLoad=GetProcAddress(GetModuleHandleW(L"kernel32.dll"),"LoadLibraryW");HMODULE localContainer=nullptr;
  Check(GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,reinterpret_cast<LPCWSTR>(localLoad),&localContainer)!=0,"Locate library-loader module");
  wchar_t loaderPath[32768]{};Check(GetModuleFileNameW(localContainer,loaderPath,32768)!=0,"Identify library-loader module");
  auto remoteContainer=RemoteModule(process.dwProcessId,process.hProcess,std::filesystem::path(loaderPath).filename().c_str());
  if(!remoteContainer){
   // A newly suspended process can initially expose only ntdll. A short owned
   // thread initializes its loader without executing the suspended game entry.
   HMODULE localNT=GetModuleHandleW(L"ntdll.dll");auto exitThread=GetProcAddress(localNT,"RtlExitUserThread");
   const auto remoteNT=RemoteModule(process.dwProcessId,process.hProcess,L"ntdll.dll");Check(remoteNT&&exitThread,"Find child loader bootstrap");
   Invoke(process.hProcess,remoteNT+(reinterpret_cast<std::uintptr_t>(exitThread)-reinterpret_cast<std::uintptr_t>(localNT)),nullptr);
   remoteContainer=RemoteModule(process.dwProcessId,process.hProcess,std::filesystem::path(loaderPath).filename().c_str());
  }
  Check(remoteContainer!=0,"Find child library-loader module");
  const auto remoteLoad=remoteContainer+(reinterpret_cast<std::uintptr_t>(localLoad)-reinterpret_cast<std::uintptr_t>(localContainer));
  std::wstring path=library.wstring();const auto bytes=(path.size()+1)*sizeof(wchar_t);
  void* remote=VirtualAllocEx(process.hProcess,nullptr,bytes,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);Check(remote!=nullptr,"Allocate owned module path");
  SIZE_T copied=0;bool written=WriteProcessMemory(process.hProcess,remote,path.c_str(),bytes,&copied)!=0&&copied==bytes;
  if(!written){VirtualFreeEx(process.hProcess,remote,0,MEM_RELEASE);Check(false,"Copy owned module path");}
  Invoke(process.hProcess,remoteLoad,remote);VirtualFreeEx(process.hProcess,remote,0,MEM_RELEASE);
  const auto remoteLibrary=RemoteModule(process.dwProcessId,process.hProcess,library.filename().c_str());Check(remoteLibrary!=0,"Native module did not load");
  HMODULE localLibrary=LoadLibraryExW(library.c_str(),nullptr,DONT_RESOLVE_DLL_REFERENCES);Check(localLibrary!=nullptr,"Read owned export address");
  const auto entry=GetProcAddress(localLibrary,"MaleModInitialize"),probe=GetProcAddress(localLibrary,"MaleModProbeStatus");
  const auto rva=reinterpret_cast<std::uintptr_t>(entry)-reinterpret_cast<std::uintptr_t>(localLibrary),probeRVA=reinterpret_cast<std::uintptr_t>(probe)-reinterpret_cast<std::uintptr_t>(localLibrary);
  FreeLibrary(localLibrary);Check(entry&&probe,"Missing native initialization/status export");
  const auto status=Invoke(process.hProcess,remoteLibrary+rva,nullptr);Check(status==0,"Native executable/profile/hook verification failed");
  Check(ResumeThread(process.hThread)!=DWORD(-1),"Resume owned game process");resumed=true;
  std::cout<<"Native probe initialized in owned process "<<process.dwProcessId<<"; registration and script invocation still require live verification.\n";
  DWORD flags=0;
  std::cout<<"{\"processID\":"<<process.dwProcessId<<",\"processCreationTime\":\""<<creationTime<<"\"}\n"<<std::flush;
  for(unsigned i=0;i<180;i++){
   if(WaitForSingleObject(process.hProcess,1000)==WAIT_OBJECT_0)break;
   flags=Invoke(process.hProcess,remoteLibrary+probeRVA,nullptr);if(flags&98)break;
   if(i&&i%30==0)std::cout<<"Waiting for the owned startup test; status flags "<<flags<<".\n"<<std::flush;
  }
  std::cout<<"{\"processID\":"<<process.dwProcessId<<",\"initialized\":"<<((flags&4)?"true":"false")<<",\"registrationObserved\":"<<((flags&1)?"true":"false")<<",\"registrationFailed\":"<<((flags&2)?"true":"false")<<",\"scriptInvocationObserved\":"<<((flags&8)?"true":"false")<<",\"typedArgumentsObserved\":"<<((flags&16)?"true":"false")<<",\"typedRoundtripObserved\":"<<((flags&64)?"true":"false")<<",\"typedProbeFailed\":"<<((flags&32)?"true":"false")<<"}\n";
  CloseHandle(process.hThread);CloseHandle(process.hProcess);return 0;
 }catch(const std::exception& e){
  // Terminate only the suspended process created by this failed launcher. Never
  // touch a pre-existing user session or terminate a resumed game.
  if(process.hProcess){if(!resumed)TerminateProcess(process.hProcess,1);CloseHandle(process.hProcess);}
  if(process.hThread)CloseHandle(process.hThread);std::cerr<<e.what()<<"\n";return 1;
 }
}
