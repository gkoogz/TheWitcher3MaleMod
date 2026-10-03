#pragma once
#include <windows.h>
#include <mmdeviceapi.h>
#include <audiopolicy.h>
#include <wrl/client.h>
#include <string>
#include <map>

// Mute only sessions belonging to the isolated child, never the endpoint or
// another application. Repeat because the game may create sessions after boot.
class ScopedProcessAudioMute {
 struct Original {Microsoft::WRL::ComPtr<ISimpleAudioVolume> volume;BOOL mute;};
 std::map<std::wstring,Original> originals_;
 public:
 ~ScopedProcessAudioMute(){Restore();}
 unsigned Restore(){unsigned restored=0;for(auto& entry:originals_){BOOL state=FALSE;
  if(SUCCEEDED(entry.second.volume->SetMute(entry.second.mute,nullptr))&&
     SUCCEEDED(entry.second.volume->GetMute(&state))&&state==entry.second.mute)++restored;
 }originals_.clear();return restored;}
 unsigned Mute(DWORD process);
 bool Remember(IAudioSessionControl2* session,ISimpleAudioVolume* volume){
  LPWSTR raw=nullptr;if(FAILED(session->GetSessionInstanceIdentifier(&raw))||!raw)return false;
  std::wstring id(raw);CoTaskMemFree(raw);if(originals_.count(id))return true;
  BOOL prior=FALSE;if(FAILED(volume->GetMute(&prior)))return false;
  originals_.emplace(std::move(id),Original{volume,prior});return true;
 }
};
inline unsigned SetProcessAudioMute(DWORD process,BOOL requested,ScopedProcessAudioMute* scope=nullptr) {
 using Microsoft::WRL::ComPtr;
 ComPtr<IMMDeviceEnumerator> enumerator;
 if (FAILED(CoCreateInstance(__uuidof(MMDeviceEnumerator), nullptr,
     CLSCTX_ALL, IID_PPV_ARGS(&enumerator)))) return 0;
 ComPtr<IMMDeviceCollection> devices;
 if (FAILED(enumerator->EnumAudioEndpoints(eRender, DEVICE_STATE_ACTIVE, &devices))) return 0;
 UINT count=0; devices->GetCount(&count); unsigned muted=0;
 for(UINT d=0;d<count;++d) {
  ComPtr<IMMDevice> device; if(FAILED(devices->Item(d,&device))) continue;
  ComPtr<IAudioSessionManager2> manager;
  if(FAILED(device->Activate(__uuidof(IAudioSessionManager2),CLSCTX_ALL,nullptr,
      reinterpret_cast<void**>(manager.GetAddressOf())))) continue;
  ComPtr<IAudioSessionEnumerator> sessions;
  if(FAILED(manager->GetSessionEnumerator(&sessions))) continue;
  int n=0;sessions->GetCount(&n);
  for(int i=0;i<n;++i) {
   ComPtr<IAudioSessionControl> control; if(FAILED(sessions->GetSession(i,&control))) continue;
   ComPtr<IAudioSessionControl2> identified; if(FAILED(control.As(&identified))) continue;
   DWORD pid=0;if(FAILED(identified->GetProcessId(&pid))||pid!=process) continue;
   ComPtr<ISimpleAudioVolume> volume;if(FAILED(control.As(&volume))) continue;
   if(scope&&!scope->Remember(identified.Get(),volume.Get()))continue;
   if(SUCCEEDED(volume->SetMute(requested,nullptr))) {
    BOOL state=FALSE;if(SUCCEEDED(volume->GetMute(&state))&&state==requested)++muted;
   }
  }
 }
 return muted;
}

inline unsigned MuteProcessAudio(DWORD process){return SetProcessAudioMute(process,TRUE);}
inline unsigned ScopedProcessAudioMute::Mute(DWORD process){return SetProcessAudioMute(process,TRUE,this);}
