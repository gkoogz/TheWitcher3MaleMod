#pragma once
#include <windows.h>
#include <array>
#include <cstdint>
namespace malemod::witcher {
struct PanelProbeRequest {
 enum class Action { Press, Hold, Release, Reset, Capture };
 std::uint32_t revision=0;int key=0;Action action=Action::Capture;
};

#ifndef MALEMOD_OWNED_PANEL_PROBE

class PanelProbe {
public:
 static PanelProbe FromEnvironment(HWND,bool){return {};}
 bool Enabled()const{return false;}
 bool Private()const{return false;}
 void Disable(){}
 SHORT KeyState(int)const{return 0;}
 void Ready(HWND,HWND){}
 bool Read(PanelProbeRequest&){return false;}
 void EndTick(){}
 bool Capture(HWND,std::uint32_t){return false;}
 void Record(HWND,HWND,const PanelProbeRequest&,const std::array<float,18>&,const std::array<float,3>&,unsigned,bool,bool){}
};
#endif
}
#ifdef MALEMOD_OWNED_PANEL_PROBE
#include "../dev/sandbox/panel_probe/transport.hpp"
#endif
