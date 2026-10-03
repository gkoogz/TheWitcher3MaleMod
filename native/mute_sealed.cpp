#include "session_audio.hpp"
#include <iostream>
int wmain(int argc,wchar_t** argv) {
 if(argc!=2&&argc!=3)return 2;
 const bool unmute=argc==3&&!_wcsicmp(argv[2],L"--unmute");
 if(argc==3&&!unmute)return 2;
 const DWORD pid=wcstoul(argv[1],nullptr,10);
 HANDLE process=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION|SYNCHRONIZE,FALSE,pid);
 if(!process)return 3;
 wchar_t path[32768]{};DWORD length=32768;
 if(!QueryFullProcessImageNameW(process,0,path,&length)||
    _wcsicmp(path,L"E:\\SteamLibrary\\steamapps\\common\\The Witcher 3\\bin\\x64_dx12\\witcher3.exe"))return 4;
 if(FAILED(CoInitializeEx(nullptr,COINIT_MULTITHREADED)))return 5;
 const auto muted=SetProcessAudioMute(pid,unmute?FALSE:TRUE);
 std::cout<<"{\"processID\":"<<pid<<",\"verifiedSessions\":"<<muted<<"}\n";
 CoUninitialize();CloseHandle(process);return muted?0:6;
}
