#pragma once
#include <windows.h>
namespace malemod::witcher {
// Call early, before the executable creates its keyboard. Only its own imported
// USER32/DirectInput paths are patched. No process/global input hook is used.
bool OverlayInputInstall(HMODULE executable);
void OverlayInputPublish(HWND ownedParent,bool expanded,bool anatomyVisible,bool privateProbe=false);
void OverlayInputShutdown();
SHORT OverlayInputPoll(int key); // Raw panel polling bypasses the engine fence.
bool OverlayInputBlocks(unsigned key,bool expanded,bool anatomyVisible);
struct OverlayInputMetrics {unsigned imports=0,asyncKeys=0,rawKeys=0,messages=0,directKeys=0,keyboards=0;};
OverlayInputMetrics OverlayInputStatus();
}
