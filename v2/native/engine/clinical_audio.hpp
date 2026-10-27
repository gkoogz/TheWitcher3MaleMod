#pragma once
#include <windows.h>
#include <mmsystem.h>
#include <filesystem>
#include <fstream>
#include <vector>
#include <array>
#include <cstdint>
#include <cstring>
namespace malemod::witcher {
// The same mono PCM admission, xorshift pool selection and PlaySound transport
// used by the canonical adapter. Private recordings are local install inputs.
class ClinicalAudio {
 std::array<std::vector<std::filesystem::path>,2> phases_;
 std::vector<std::filesystem::path> idle_;
 unsigned random_=0x7f4a7c15u,played_=0,failed_=0,idleSerial_=0;
 bool playing_=false;
 static unsigned U16(const unsigned char* p){return unsigned(p[0])|(unsigned(p[1])<<8);}
 static unsigned U32(const unsigned char* p){return U16(p)|(U16(p+2)<<16);}
public:
 static bool Valid(const std::filesystem::path& path){
  std::ifstream f(path,std::ios::binary|std::ios::ate);if(!f)return false;const auto size=f.tellg();f.seekg(0);unsigned char root[12]{};f.read(reinterpret_cast<char*>(root),12);
  if(size<44||!f||std::memcmp(root,"RIFF",4)||std::memcmp(root+8,"WAVE",4))return false;
  bool format=false,data=false;
  for(std::streamoff pos=12;pos+8<=size;){f.seekg(pos);unsigned char head[8]{};f.read(reinterpret_cast<char*>(head),8);if(!f)return false;auto bytes=U32(head+4);const auto next=pos+8+bytes+(bytes&1);if(next>size)return false;
   if(!std::memcmp(head,"fmt ",4)&&bytes>=16){unsigned char fmt[16]{};f.read(reinterpret_cast<char*>(fmt),16);if(!f)return false;format=U16(fmt)==1&&U16(fmt+2)==1&&U32(fmt+4)==44100&&U16(fmt+12)==2&&U16(fmt+14)==16;}
   if(!std::memcmp(head,"data",4))data=bytes>=2;pos=next;
  }return format&&data;
 }
 void Load(const std::filesystem::path& root){
  LARGE_INTEGER now{};QueryPerformanceCounter(&now);random_=unsigned(now.LowPart)^unsigned(now.HighPart)^GetTickCount()^GetCurrentProcessId()^GetCurrentThreadId();if(!random_)random_=0x7f4a7c15u;
  for(unsigned phase=0;phase<2;phase++){auto dir=root/L"TeachingAudio"/(L"Phase"+std::to_wstring(phase+1));if(std::filesystem::is_directory(dir))for(const auto& file:std::filesystem::directory_iterator(dir))if(file.is_regular_file()&&file.path().extension()==L".wav"&&phases_[phase].size()<64&&Valid(file.path()))phases_[phase].push_back(file.path());}
  for(unsigned i=0;i<22;i++){wchar_t name[40]{};swprintf_s(name,i<3?L"standard-%02u.wav":L"custom-%02u.wav",i<3?i+1:i-2);auto path=root/L"WolverineIdle"/name;if(!Valid(path)){idle_.clear();break;}idle_.push_back(path);}
 }
 void Stop(){if(playing_)PlaySoundW(nullptr,nullptr,0);playing_=false;}
 bool Play(const std::filesystem::path& path){const bool ok=PlaySoundW(path.c_str(),nullptr,SND_FILENAME|SND_ASYNC|SND_NODEFAULT)!=FALSE;if(ok){playing_=true;++played_;}else ++failed_;return ok;}
 bool Phase(unsigned phase){if(phase>1||phases_[phase].empty())return false;random_^=random_<<13;random_^=random_>>17;random_^=random_<<5;return Play(phases_[phase][random_%phases_[phase].size()]);}
 bool Idle(){if(idle_.size()!=22)return false;unsigned seed=GetTickCount()+(++idleSerial_)*0x9e3779b9u;seed^=seed<<13;seed^=seed>>17;seed^=seed<<5;return Play(idle_[seed%22]);}
 unsigned PhaseCount(unsigned phase)const{return phase<2?unsigned(phases_[phase].size()):0;}
 unsigned IdleCount()const{return unsigned(idle_.size());}
 unsigned Played()const{return played_;}unsigned Failed()const{return failed_;}
};
}
