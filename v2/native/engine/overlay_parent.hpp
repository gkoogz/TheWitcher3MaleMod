#pragma once
#include "overlay_panel_probe.hpp"

namespace malemod::witcher {
inline bool EligibleOverlayParent(HWND window,bool ownedProbeAuthorized){
 DWORD process=0;RECT client{};GetWindowThreadProcessId(window,&process);
 if(!window||process!=GetCurrentProcessId()||GetWindow(window,GW_OWNER)||
    !GetClientRect(window,&client)||client.right<640||client.bottom<480)return false;
 if(IsWindowVisible(window))return true;
 // A sealed engine viewport can render while its host HWND stays hidden.
 // Only the explicit, validated development transport may use that parent.
 wchar_t name[64]{};
 return GetClassNameW(window,name,64)&&!wcscmp(name,L"W2ViewportClass")&&
        PanelProbe::FromEnvironment(window,ownedProbeAuthorized).Enabled();
}
}
