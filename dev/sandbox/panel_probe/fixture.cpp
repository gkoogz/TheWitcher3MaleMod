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
 std::mutex lock;malemod::surface::Controls controls;OverlayPanel::FeatureState features;std::atomic<unsigned> lightingToggles{0},resets{0};
 auto read=[&]{std::lock_guard<std::mutex> guard(lock);return controls;};
 auto write=[&](unsigned i,float value){std::lock_guard<std::mutex> guard(lock);controls.values.at(i)=value;return true;};
 auto readFeatures=[&]{std::lock_guard<std::mutex> guard(lock);return features;};
 auto action=[&](OverlayPanel::FeatureAction action,float value){std::lock_guard<std::mutex> guard(lock);using Action=OverlayPanel::FeatureAction;switch(action){
  case Action::SetThrob:features.throbMode=unsigned(value);break;
  case Action::SetIdleChatter:features.idleChatter=value!=0;break;
  case Action::SetGarment:features.garment=unsigned(value);break;
  case Action::ToggleTeaching:features.teachingActive=!features.teachingActive;break;
  case Action::CancelTeaching:features.teachingActive=false;break;
  case Action::ResetDefaults:controls=malemod::surface::Controls{};features=OverlayPanel::FeatureState{};++resets;break;
  case Action::ToggleLighting:++lightingToggles;break;
 }}; {
 OverlayPanel panel(parent,read,write,readFeatures,action,true);Wait([&]{return std::filesystem::exists(directory/L"panel-ready.json");});
 FILETIME created{},exit{},kernel{},user{};Check(GetProcessTimes(GetCurrentProcess(),&created,&exit,&kernel,&user)!=0,"Process creation identity unavailable");const auto creation=(std::uint64_t(created.dwHighDateTime)<<32)|created.dwLowDateTime;unsigned revision=0;
 auto send=[&](const char* key,const char* command="Press",const char* suppliedToken=nullptr){
  ++revision;std::ostringstream s;s<<"Revision="<<revision<<"\nToken="<<(suppliedToken?suppliedToken:asciiToken)<<"\nProcessID="<<GetCurrentProcessId()<<"\nCreationTime="<<creation<<"\nKey="<<key<<"\nAction="<<command<<"\n";
  auto pending=directory/L"test-command.pending",destination=directory/L"panel-command.ini";{std::ofstream f(pending,std::ios::binary);f<<s.str();Check(bool(f),"Command write failed");}Wait([&]{if(MoveFileExW(pending.c_str(),destination.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))return true;const auto error=GetLastError();Check(error==ERROR_SHARING_VIOLATION||error==ERROR_ACCESS_DENIED,"Command publish failed");return false;});
  return revision;
 };
 auto command=[&](const char* key,const char* value="Press"){auto id=send(key,value);auto receipt=directory/(L"panel-receipt-"+std::to_wstring(id)+L".json");Wait([&]{return std::filesystem::exists(receipt);});return id;};
 auto receiptText=[&](unsigned id){std::ifstream file(directory/(L"panel-receipt-"+std::to_wstring(id)+L".json"));return std::string((std::istreambuf_iterator<char>(file)),{});};
 auto capture=[&]{auto id=command("Capture");Check(std::filesystem::exists(directory/(L"panel-"+std::to_wstring(id)+L".bmp")),"Owned client paint did not produce a capture");};
 Check(panel.Open(),"Canonical menu must start open");
 auto invalid=send("F6","Press","00000000000000000000000000000000");Sleep(150);Check(!std::filesystem::exists(directory/(L"panel-receipt-"+std::to_wstring(invalid)+L".json"))&&panel.Open(),"Wrong session token changed the panel");
 command("Down");command("Right");Check(readFeatures().throbMode==1,"Throb row is missing");
 command("Left");command("Left");Check(readFeatures().throbMode==3,"Throb modes do not wrap");
 command("Down");command("Right");Check(readFeatures().idleChatter,"Idle chatter row is missing");
 command("Down");command("Right");Check(read().values[1]==51,"One-step arrow adjustment failed");
 command("Shift","Hold");command("Right");command("Shift","Release");Check(read().values[1]==56,"Shift five-step adjustment failed");capture();
 {std::lock_guard<std::mutex> guard(lock);features.displayControls=controls.values;features.displayControls[1]=88;features.displayAnimated=true;}
 capture();command("Right");Check(read().values[1]==57,"Animated readout changed the stored adjustment baseline");
 {std::lock_guard<std::mutex> guard(lock);features.displayAnimated=false;}
 command("J");Check(readFeatures().teachingActive,"Sequence shortcut failed");command("Right");Check(!readFeatures().teachingActive,"Shape adjustment did not cancel sequence");
 command("Up");command("Up");command("Up");command("Left");Check(read().values[0]==1,"State navigation differs from Base");
 command("Up");command("Right");Check(readFeatures().garment==1,"Wardrobe row was not reached through wrapped selection");capture();
 command("J");command("Left");Check(readFeatures().teachingActive&&readFeatures().garment==0,"Wardrobe adjustment incorrectly cancelled sequence");
 command("J");Check(!readFeatures().teachingActive,"Sequence shortcut did not cancel active sequence");
 command("F8");Check(resets==1&&read().values==malemod::surface::Controls{}.values&&readFeatures().throbMode==0&&!readFeatures().idleChatter&&readFeatures().garment==0,"F8 atomic reset failed");capture();
 command("F6");Check(!panel.Open(),"Panel did not collapse");command("Right");Check(read().values==malemod::surface::Controls{}.values,"Collapsed panel edited controls");
 command("J");Check(readFeatures().teachingActive,"Sequence shortcut must work with menu collapsed");command("F9");Check(lightingToggles==1,"Lighting shortcut must work with menu collapsed");command("F8");Check(resets==1,"Collapsed menu must ignore F8");capture();
 command("F6");command("F8");Check(resets==2&&!readFeatures().teachingActive,"F8 did not cancel sequence and reset atomically");capture();
 auto posted=command("WindowJ");{std::ifstream f(directory/(L"panel-receipt-"+std::to_wstring(posted)+L".json"));std::string text((std::istreambuf_iterator<char>(f)),{});Check(text.find("\"windowMessagePosted\":true")!=std::string::npos,"Private parent message receipt missing");}Check(!readFeatures().teachingActive,"Parent-window message injected a panel shortcut");
 auto logical=command("Capture");const auto logicalText=receiptText(logical);Check(logicalText.find("\"logicalEligible\":true")!=std::string::npos&&logicalText.find("\"anatomyVisible\":true")!=std::string::npos&&logicalText.find("\"parentVisible\":false")!=std::string::npos,"Hidden-owner logical eligibility metadata is incorrect");
 {std::lock_guard<std::mutex> guard(lock);features.anatomyVisible=false;controls.values[1]=65;}
 auto absent=command("Capture");Check(receiptText(absent).find("\"logicalEligible\":false")!=std::string::npos,"Anatomy absence was not reflected in the logical gate");
 command("F8");command("Right");Check(read().values[1]==65&&resets==2&&readFeatures().garment==0,"Hidden anatomy accepted a menu mutation");
 command("F6");Check(!panel.Open(),"F6 stopped working when anatomy was absent");
 {std::lock_guard<std::mutex> guard(lock);features.anatomyVisible=true;}
 command("F6");command("F8");Check(panel.Open()&&resets==3&&read().values==malemod::surface::Controls{}.values,"Restored anatomy did not restore menu eligibility");capture();
 }
 DestroyWindow(parent);
 std::cout<<"PASS owned GDI panel "<<width<<'x'<<height<<": token/station/authorization guards, canonical 21-row navigation, throb/idle, Shift, wardrobe, J/F8/F9 and collapse and client captures; Witcher-game integration and attachment gate UNTESTED\n";return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
