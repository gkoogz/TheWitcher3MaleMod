#pragma once
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <stdexcept>
namespace malemod::witcher {
// Development-only panel transport. It never posts engine input or changes
// focus; all command state lives in this exact overlay instance.
class PanelProbe {
 std::filesystem::path directory_;std::string token_;std::wstring station_;
 std::array<bool,256> held_{},transient_{};std::uint32_t revision_=0;
 std::uint64_t creation_=0;bool enabled_=false,private_=false;
 static std::wstring Env(const wchar_t* name){wchar_t value[32768]{};auto n=GetEnvironmentVariableW(name,value,32768);return n&&n<32768?value:L"";}
 static std::string UTF8(const std::wstring& text){int n=WideCharToMultiByte(CP_UTF8,0,text.data(),int(text.size()),nullptr,0,nullptr,nullptr);std::string s(n,'\0');if(n)WideCharToMultiByte(CP_UTF8,0,text.data(),int(text.size()),s.data(),n,nullptr,nullptr);return s;}
 static std::string JSON(const std::string& text){std::string s="\"";for(unsigned char c:text){if(c=='\\'||c=='\"')s+='\\';if(c>=32)s+=char(c);}return s+'\"';}
 void Write(const char* name,const std::string& text){auto path=directory_/name,temp=path;temp+=L".pending";{std::ofstream f(temp,std::ios::binary);f<<text;f.close();if(!f)throw std::runtime_error("Cannot write owned panel receipt");}if(!MoveFileExW(temp.c_str(),path.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))throw std::runtime_error("Cannot acknowledge owned panel command");}
public:
 static PanelProbe FromEnvironment(HWND parent,bool authorized){
  PanelProbe p;if(!authorized||Env(L"MALEMOD_PANEL_PROBE")!=L"1")return p;
  DWORD process=0;GetWindowThreadProcessId(parent,&process);if(!parent||process!=GetCurrentProcessId())return p;
  USEROBJECTFLAGS flags{};DWORD bytes=0;wchar_t name[256]{};auto station=GetProcessWindowStation();
  if(!GetUserObjectInformationW(station,UOI_FLAGS,&flags,sizeof(flags),&bytes)||(flags.dwFlags&WSF_VISIBLE)||!GetUserObjectInformationW(station,UOI_NAME,name,sizeof(name),&bytes)||_wcsicmp(name,L"WinSta0")==0||Env(L"MALEMOD_SEALED_SESSION")!=name)return p;
  auto token=Env(L"MALEMOD_PANEL_PROBE_TOKEN"),path=Env(L"MALEMOD_PANEL_PROBE_DIR");if(token.size()!=32||path.empty())return p;
  for(auto c:token)if(!((c>=L'0'&&c<=L'9')||(c>=L'a'&&c<=L'f')))return p;
  std::error_code error;auto directory=std::filesystem::canonical(path,error);if(error||!directory.is_absolute()||directory.filename()!=L"panel-probe-"+token)return p;
  // Reject junction-backed output; evidence belongs to the owned local probe.
  for(auto ancestor=directory;!ancestor.empty();ancestor=ancestor.parent_path()){auto attributes=GetFileAttributesW(ancestor.c_str());if(attributes==INVALID_FILE_ATTRIBUTES||(attributes&FILE_ATTRIBUTE_REPARSE_POINT))return p;if(ancestor==ancestor.parent_path())break;}
  FILETIME created{},exit{},kernel{},user{};if(!GetProcessTimes(GetCurrentProcess(),&created,&exit,&kernel,&user))return p;
  p.creation_=(std::uint64_t(created.dwHighDateTime)<<32)|created.dwLowDateTime;p.directory_=directory;p.token_=UTF8(token);p.station_=name;p.enabled_=true;p.private_=true;return p;
 }
 bool Enabled()const{return enabled_;}
 bool Private()const{return private_;}
 void Disable(){enabled_=false;held_.fill(false);transient_.fill(false);}
 SHORT KeyState(int key)const{return key>=0&&key<256&&held_[key]?SHORT(-32768):0;}
 void Ready(HWND parent,HWND overlay){
  if(!enabled_)return;wchar_t executable[32768]{};GetModuleFileNameW(nullptr,executable,32768);
  std::ostringstream s;s<<"{\"schema\":1,\"processID\":"<<GetCurrentProcessId()<<",\"processCreationTime\":\""<<creation_<<"\",\"token\":"<<JSON(token_)<<",\"parentHWND\":\""<<std::uint64_t(reinterpret_cast<std::uintptr_t>(parent))<<"\",\"overlayHWND\":\""<<std::uint64_t(reinterpret_cast<std::uintptr_t>(overlay))<<"\",\"executable\":"<<JSON(UTF8(executable))<<",\"station\":"<<JSON(UTF8(station_))<<",\"noninteractiveWindowStation\":true,\"physicalInputUsed\":false,\"hostFocusUsed\":false}\n";Write("panel-ready.json",s.str());
 }
 bool Read(PanelProbeRequest& request){
  if(!enabled_)return false;try{
   std::ifstream f(directory_/L"panel-command.ini",std::ios::binary);if(!f)return false;char buffer[1025]{};f.read(buffer,sizeof(buffer));if(f.gcount()>1024)return false;std::string contents(buffer,size_t(f.gcount()));
   std::istringstream lines(contents);std::string line,token,key,action;std::uint64_t created=0;unsigned process=0;PanelProbeRequest r;
   while(std::getline(lines,line)){if(!line.empty()&&line.back()=='\r')line.pop_back();auto equal=line.find('=');if(equal==std::string::npos)continue;auto name=line.substr(0,equal),value=line.substr(equal+1);if(name=="Revision")r.revision=std::stoul(value);else if(name=="Token")token=value;else if(name=="ProcessID")process=std::stoul(value);else if(name=="CreationTime")created=std::stoull(value);else if(name=="Key")key=value;else if(name=="Action")action=value;}
   if(!r.revision||r.revision<=revision_||process!=GetCurrentProcessId()||created!=creation_||token!=token_)return false;
   if(key=="Reset"||key=="Capture"){if(action!="Press")return false;r.action=key=="Reset"?PanelProbeRequest::Action::Reset:PanelProbeRequest::Action::Capture;}
   else{if(key=="F6")r.key=VK_F6;else if(key=="Up")r.key=VK_UP;else if(key=="Down")r.key=VK_DOWN;else if(key=="Left")r.key=VK_LEFT;else if(key=="Right")r.key=VK_RIGHT;else if(key=="Shift")r.key=VK_SHIFT;else return false;
    if(action=="Press")r.action=PanelProbeRequest::Action::Press;else if(action=="Hold")r.action=PanelProbeRequest::Action::Hold;else if(action=="Release")r.action=PanelProbeRequest::Action::Release;else return false;held_[r.key]=r.action!=PanelProbeRequest::Action::Release;transient_[r.key]=r.action==PanelProbeRequest::Action::Press;
   }
   revision_=r.revision;request=r;return true;
  }catch(const std::exception&){return false;}
 }
 void EndTick(){for(unsigned key=0;key<256;key++)if(transient_[key]){held_[key]=false;transient_[key]=false;}}
 bool Capture(HWND window,std::uint32_t revision){
  RECT client{};GetClientRect(window,&client);if(client.right<=0||client.bottom<=0||client.right>4096||client.bottom>4096)return false;
  auto dc=CreateCompatibleDC(nullptr);BITMAPINFO info{};info.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);info.bmiHeader.biWidth=client.right;info.bmiHeader.biHeight=-client.bottom;info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;info.bmiHeader.biCompression=BI_RGB;void* pixels=nullptr;auto bitmap=CreateDIBSection(dc,&info,DIB_RGB_COLORS,&pixels,nullptr,0);if(!dc||!bitmap||!pixels){if(bitmap)DeleteObject(bitmap);if(dc)DeleteDC(dc);return false;}
  auto old=SelectObject(dc,bitmap);SendMessageW(window,WM_PRINTCLIENT,reinterpret_cast<WPARAM>(dc),PRF_CLIENT);GdiFlush();BITMAPFILEHEADER header{};header.bfType=0x4d42;header.bfOffBits=sizeof(header)+sizeof(BITMAPINFOHEADER);header.bfSize=header.bfOffBits+client.right*client.bottom*4;
  std::ofstream file(directory_/(L"panel-"+std::to_wstring(revision)+L".bmp"),std::ios::binary);file.write(reinterpret_cast<char*>(&header),sizeof(header));file.write(reinterpret_cast<char*>(&info.bmiHeader),sizeof(info.bmiHeader));file.write(static_cast<char*>(pixels),client.right*client.bottom*4);file.close();const bool success=bool(file);SelectObject(dc,old);DeleteObject(bitmap);DeleteDC(dc);return success;
 }
 void Record(HWND parent,HWND window,const PanelProbeRequest& r,const std::array<float,18>& values,const std::array<float,3>& clinical,unsigned selected,bool open,bool captured){
  RECT client{},parentClient{},position{},parentPosition{};GetClientRect(window,&client);GetClientRect(parent,&parentClient);GetWindowRect(window,&position);GetWindowRect(parent,&parentPosition);std::ostringstream s;
  s<<"{\"schema\":1,\"revision\":"<<r.revision<<",\"processID\":"<<GetCurrentProcessId()<<",\"processCreationTime\":\""<<creation_<<"\",\"token\":"<<JSON(token_)<<",\"expanded\":"<<(open?"true":"false")<<",\"selected\":"<<selected<<",\"client\":["<<client.right<<','<<client.bottom<<"],\"parentClient\":["<<parentClient.right<<','<<parentClient.bottom<<"],\"position\":["<<position.left-parentPosition.left<<','<<position.top-parentPosition.top<<"],\"controls\":[";for(unsigned i=0;i<18;i++)s<<(i?",":"")<<values[i];s<<"],\"clinical\":["<<clinical[0]<<','<<clinical[1]<<','<<clinical[2]<<"],\"captured\":"<<(captured?"true":"false")<<",\"physicalInputUsed\":false,\"hostFocusUsed\":false}\n";
  Write(("panel-receipt-"+std::to_string(r.revision)+".json").c_str(),s.str());Write("panel-receipt.json",s.str());
 }
};
}
