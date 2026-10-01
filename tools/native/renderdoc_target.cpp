// Diagnostic client only. Build with matching RenderDoc 1.46 replay headers
// and import library. Nothing is installed into the game.
#include "renderdoc_replay.h"
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <string>

// Required by RenderDoc before DLL initialization. Without this marker, a
// probe becomes a capture target itself and can connect to its own port.
extern "C" __declspec(dllexport) void renderdoc__replay__marker() {}

static std::string Quote(const char* text) {
  std::string out="\"";
  for(const unsigned char* p=(const unsigned char*)text;*p;++p) {
    if(*p=='"'||*p=='\\'){out+='\\';out+=char(*p);}
    else if(*p<32){char escaped[7];std::sprintf(escaped,"\\u%04x",unsigned(*p));out+=escaped;}
    else out+=char(*p);
  }
  return out+'"';
}
int main(int argc,char** argv) {
  if(argc<3||argc>5)return 2;
  unsigned port=unsigned(std::strtoul(argv[1],nullptr,10));
  unsigned expectedPID=unsigned(std::strtoul(argv[2],nullptr,10));
  unsigned seconds=argc>=4?unsigned(std::strtoul(argv[3],nullptr,10)):8;
  bool requestCapture=argc==5&&std::string(argv[4])=="capture";
  if(port<38920||port>38999||!expectedPID||seconds<1||seconds>45)return 2;
  GlobalEnvironment env;env.enumerateGPUs=false;
  RENDERDOC_InitialiseReplay(env,{});
  auto* target=RENDERDOC_CreateTargetControl("",port,"MaleMod mesh investigation",false);
  if(!target){std::puts("{\"connected\":false,\"graphicsAPIReady\":false}");RENDERDOC_ShutdownReplay();return 3;}
  unsigned pid=target->GetPID();
  std::string name=target->GetTarget().c_str(),api;
  bool matched=pid==expectedPID&&name=="witcher3";
  bool ready=false,requested=false,captured=false;
  unsigned frame=0;uint64_t bytes=0;std::string path,reason;
  if(matched) {
    auto start=std::chrono::steady_clock::now();
    while(target->Connected()&&std::chrono::steady_clock::now()-start<std::chrono::seconds(seconds)) {
      auto m=target->ReceiveMessage(nullptr);
      if(m.type==TargetControlMessageType::RegisterAPI) {
        api=m.apiUse.name.c_str();reason=m.apiUse.supportMessage.c_str();
        ready=m.apiUse.supported&&m.apiUse.presenting&&!api.empty();
        if(ready&&requestCapture&&!requested){target->TriggerCapture(1);requested=true;}
        if(ready&&!requestCapture)break;
      }
      if(m.type==TargetControlMessageType::NewCapture) {
        captured=true;frame=m.newCapture.frameNumber;bytes=m.newCapture.byteSize;path=m.newCapture.path.c_str();
        if(requested)break;
      }
    }
  }
  std::printf("{\"connected\":%s,\"target\":%s,\"pid\":%u,\"expectedPID\":%u,\"targetMatched\":%s,\"graphicsAPI\":%s,\"graphicsAPIReady\":%s,\"supportMessage\":%s,\"captureRequested\":%s,\"captureObserved\":%s,\"frame\":%u,\"captureBytes\":%llu,\"capturePath\":%s}\n",
    target->Connected()?"true":"false",Quote(name.c_str()).c_str(),pid,expectedPID,matched?"true":"false",
    Quote(api.c_str()).c_str(),ready?"true":"false",Quote(reason.c_str()).c_str(),requested?"true":"false",
    captured?"true":"false",frame,(unsigned long long)bytes,Quote(path.c_str()).c_str());
  target->Shutdown();RENDERDOC_ShutdownReplay();
  return !matched?4:!ready?5:requestCapture&&!captured?6:0;
}
