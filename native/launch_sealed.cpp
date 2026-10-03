#define NOMINMAX
#include <windows.h>
#include <string>
#include <iostream>
#include <stdexcept>
#include <filesystem>
#include "session_audio.hpp"
namespace {void Check(bool b,const char* s){if(!b)throw std::runtime_error(std::string(s)+" Win32="+std::to_string(GetLastError()));}}
int wmain(int argc,wchar_t** argv){
 if(argc!=2)return 2;HWINSTA station=nullptr;HDESK desktop=nullptr;PROCESS_INFORMATION child{};
 auto original=GetProcessWindowStation();
 try{
  // A standard user cannot name a window station. Let Windows allocate this
  // user's noninteractive station, and verify its actual name/visibility.
  station=CreateWindowStationW(nullptr,0,WINSTA_CREATEDESKTOP|WINSTA_ENUMDESKTOPS|WINSTA_READATTRIBUTES|WINSTA_ACCESSGLOBALATOMS,nullptr);Check(station!=nullptr,"Open user noninteractive window station");
  USEROBJECTFLAGS flags{};DWORD bytes=0;Check(GetUserObjectInformationW(station,UOI_FLAGS,&flags,sizeof(flags),&bytes)!=0&&!(flags.dwFlags&WSF_VISIBLE),"Require noninteractive isolation");
  wchar_t actualName[256]{};Check(GetUserObjectInformationW(station,UOI_NAME,actualName,sizeof(actualName),&bytes)!=0&&_wcsicmp(actualName,L"WinSta0")!=0,"Require a private station identity");const std::wstring name=actualName;
  Check(SetProcessWindowStation(station)!=0,"Select private station in this launcher only");
  const auto desktopName=L"MaleModGame."+std::to_wstring(GetCurrentProcessId())+L"."+std::to_wstring(GetTickCount64());
  desktop=CreateDesktopW(desktopName.c_str(),nullptr,nullptr,0,DESKTOP_CREATEWINDOW|DESKTOP_READOBJECTS|DESKTOP_WRITEOBJECTS,nullptr);Check(desktop!=nullptr,"Create private game desktop");
  Check(SetProcessWindowStation(original)!=0,"Restore launcher station");
  std::wstring privateDesktop=name+L"\\"+desktopName,command=L"\""+std::wstring(argv[1])+L"\"";
  SetEnvironmentVariableW(L"SteamAppId",L"292030");SetEnvironmentVariableW(L"SteamGameId",L"292030");SetEnvironmentVariableW(L"MALEMOD_SEALED_SESSION",name.c_str());
  STARTUPINFOW startup{};startup.cb=sizeof(startup);startup.lpDesktop=privateDesktop.data();startup.dwFlags=STARTF_USESHOWWINDOW;startup.wShowWindow=SW_SHOWNORMAL;
  const auto directory=std::filesystem::path(argv[1]).parent_path();
  Check(CreateProcessW(argv[1],command.data(),nullptr,nullptr,FALSE,0,nullptr,directory.c_str(),&startup,&child)!=0,"Launch game in private desktop");
  FILETIME created{},exit{},kernel{},user{};Check(GetProcessTimes(child.hProcess,&created,&exit,&kernel,&user)!=0,"Identify private game lifetime");
  std::cout<<"{\"processID\":"<<child.dwProcessId<<",\"processCreationTime\":\""<<((std::uint64_t(created.dwHighDateTime)<<32)|created.dwLowDateTime)<<"\",\"noninteractiveWindowStation\":true,\"physicalInputUsed\":false}\n"<<std::flush;
  // Retain the private station while its child initializes. No SwitchDesktop,
  // SetForegroundWindow, SendInput, mouse or keyboard APIs are used.
  Check(SUCCEEDED(CoInitializeEx(nullptr,COINIT_MULTITHREADED)),"Initialize isolated audio control");
  unsigned muted=0;
  while(WaitForSingleObject(child.hProcess,250)==WAIT_TIMEOUT){
   const auto now=MuteProcessAudio(child.dwProcessId);
   if(now&&now!=muted){muted=now;std::cout<<"{\"verifiedMutedSessions\":"<<muted<<"}\n"<<std::flush;}
  }
  CoUninitialize();
  DWORD code=0;GetExitCodeProcess(child.hProcess,&code);std::cout<<"{\"exitCode\":"<<code<<"}\n";
  CloseHandle(child.hThread);CloseHandle(child.hProcess);CloseDesktop(desktop);CloseWindowStation(station);return 0;
 }catch(const std::exception& e){SetProcessWindowStation(original);if(child.hThread)CloseHandle(child.hThread);if(child.hProcess)CloseHandle(child.hProcess);if(desktop)CloseDesktop(desktop);if(station)CloseWindowStation(station);std::cerr<<e.what()<<'\n';return 1;}
}
