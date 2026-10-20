#define NOMINMAX
#include "overlay_panel.hpp"
#include "overlay_parent.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <mutex>
#include <sstream>
#include <stdexcept>
using namespace malemod::witcher;
namespace {
void Check(bool value,const char* text){if(!value)throw std::runtime_error(text);}
std::wstring Env(const wchar_t* name){wchar_t value[32768]{};auto n=GetEnvironmentVariableW(name,value,32768);return n&&n<32768?value:L"";}
template<class Predicate>void Wait(Predicate ready){auto end=GetTickCount64()+10000;while(!ready()){MSG msg{};while(PeekMessageW(&msg,nullptr,0,0,PM_REMOVE)){TranslateMessage(&msg);DispatchMessageW(&msg);}Check(GetTickCount64()<end,"Owned panel acknowledgement timed out");Sleep(5);}}
}
int wmain(int argc,wchar_t** argv){try{
 Check(argc==3,"Usage: overlay_panel_probe_test width height (sealed session/env required)");
 USEROBJECTFLAGS flags{};DWORD bytes=0;Check(GetUserObjectInformationW(GetProcessWindowStation(),UOI_FLAGS,&flags,sizeof(flags),&bytes)&&!(flags.dwFlags&WSF_VISIBLE),"Fixture refuses the interactive station before creating a window");
 const int width=std::stoi(argv[1]),height=std::stoi(argv[2]);Check(width>=640&&width<=3840&&height>=480&&height<=2160,"Unsupported fixture viewport");
 const auto directory=std::filesystem::path(Env(L"MALEMOD_PANEL_PROBE_DIR"));const auto token=Env(L"MALEMOD_PANEL_PROBE_TOKEN");Check(!directory.empty()&&token.size()==32,"Missing owned probe identity");
 std::string asciiToken;for(auto c:token){Check((c>=L'0'&&c<=L'9')||(c>=L'a'&&c<=L'f'),"Nonhex fixture token");asciiToken+=static_cast<char>(c);}
 WNDCLASSW wc{};wc.lpfnWndProc=DefWindowProcW;wc.hInstance=GetModuleHandleW(nullptr);wc.lpszClassName=L"W2ViewportClass";RegisterClassW(&wc);
 auto parent=CreateWindowExW(WS_EX_NOACTIVATE|WS_EX_TOOLWINDOW,wc.lpszClassName,L"Owned SDK fixture",WS_POPUP,0,0,width,height,nullptr,nullptr,wc.hInstance,nullptr);Check(parent!=nullptr,"Fixture parent creation failed");
 Check(!PanelProbe::FromEnvironment(parent,false).Enabled(),"Unauthorised parent accepted");Check(!PanelProbe::FromEnvironment(nullptr,true).Enabled(),"Missing parent accepted");
 Check(!EligibleOverlayParent(parent,false),"Hidden parent accepted without authorization");
 SetEnvironmentVariableW(L"MALEMOD_PANEL_PROBE_TOKEN",L"bad");Check(!PanelProbe::FromEnvironment(parent,true).Enabled(),"Malformed token accepted");SetEnvironmentVariableW(L"MALEMOD_PANEL_PROBE_TOKEN",token.c_str());
 const auto station=Env(L"MALEMOD_SEALED_SESSION");SetEnvironmentVariableW(L"MALEMOD_SEALED_SESSION",L"wrong-station");Check(!PanelProbe::FromEnvironment(parent,true).Enabled(),"Wrong station accepted");SetEnvironmentVariableW(L"MALEMOD_SEALED_SESSION",station.c_str());
 Check(PanelProbe::FromEnvironment(parent,true).Enabled(),"Verified scoped probe was rejected");
 Check(!IsWindowVisible(parent)&&EligibleOverlayParent(parent,true),"Verified hidden engine-parent fixture was rejected");
 std::mutex lock;malemod::surface::Controls controls;std::array<float,3> clinical{};
 auto read=[&]{std::lock_guard<std::mutex> guard(lock);return controls;};
 auto write=[&](unsigned i,float value){std::lock_guard<std::mutex> guard(lock);controls.values.at(i)=value;return true;};
 auto readClinical=[&]{std::lock_guard<std::mutex> guard(lock);return clinical;};
 auto action=[&](unsigned row,float value){std::lock_guard<std::mutex> guard(lock);clinical.at(row-18)=value;};
 {
 OverlayPanel panel(parent,read,write,readClinical,action,true);Wait([&]{return std::filesystem::exists(directory/L"panel-ready.json");});
 FILETIME created{},exit{},kernel{},user{};Check(GetProcessTimes(GetCurrentProcess(),&created,&exit,&kernel,&user)!=0,"Process creation identity unavailable");const auto creation=(std::uint64_t(created.dwHighDateTime)<<32)|created.dwLowDateTime;unsigned revision=0;
 auto send=[&](const char* key,const char* command="Press",const char* suppliedToken=nullptr){
  ++revision;std::ostringstream s;s<<"Revision="<<revision<<"\nToken="<<(suppliedToken?suppliedToken:asciiToken)<<"\nProcessID="<<GetCurrentProcessId()<<"\nCreationTime="<<creation<<"\nKey="<<key<<"\nAction="<<command<<"\n";
  auto pending=directory/L"test-command.pending",destination=directory/L"panel-command.ini";{std::ofstream f(pending,std::ios::binary);f<<s.str();Check(bool(f),"Command write failed");}Check(MoveFileExW(pending.c_str(),destination.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)!=0,"Command publish failed");
  return revision;
 };
 auto command=[&](const char* key,const char* value="Press"){auto id=send(key,value);auto receipt=directory/(L"panel-receipt-"+std::to_wstring(id)+L".json");Wait([&]{return std::filesystem::exists(receipt);});return id;};
 auto capture=[&]{auto id=command("Capture");Check(std::filesystem::exists(directory/(L"panel-"+std::to_wstring(id)+L".bmp")),"Owned client paint did not produce a capture");};
 auto invalid=send("F6","Press","00000000000000000000000000000000");Sleep(150);Check(!std::filesystem::exists(directory/(L"panel-receipt-"+std::to_wstring(invalid)+L".json"))&&!panel.Open(),"Wrong session token changed the panel");
 command("F6");Check(panel.Open(),"Panel did not expand");command("Down");command("Right");Check(read().values[1]==51,"One-step arrow adjustment failed");
 command("Shift","Hold");command("Right");command("Shift","Release");Check(read().values[1]==56,"Shift five-step adjustment failed");capture();
 command("Up");command("Left");Check(read().values[0]==1,"State navigation differs from Base");
 // Reset is now a real selectable row between clothing and the state row.
 command("Up");command("Up");command("Right");Check(readClinical()[2]==1,"Wardrobe row was not reached through wrapped selection");capture();
 command("Up");command("Right");Check(readClinical()[1]==1,"Clinical action did not use existing row path");command("Up");command("Right");Check(readClinical()[0]==1,"Mode row did not use existing row path");
 command("Down");command("Down");command("Down");capture();
 const auto defaults=malemod::surface::Controls{};
 for(const char* key:{"Enter","Space","Right"}){write(1,75);command(key);Check(read().values==defaults.values&&readClinical()==std::array<float,3>{},"Keyboard Reset defaults failed");}
 capture();
 command("F6");Check(!panel.Open(),"Panel did not collapse");command("Right");Check(read().values==defaults.values,"Collapsed panel edited controls");capture();
 }
 DestroyWindow(parent);
 std::cout<<"PASS owned GDI panel "<<width<<'x'<<height<<": token/station/authorization guards, navigation, Shift, wrap, clinical rows, reset, collapse and client captures; Witcher-game integration and attachment gate UNTESTED\n";return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
