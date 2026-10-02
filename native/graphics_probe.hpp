#pragma once
#include <cstdint>
namespace malemod::witcher {
bool InitializeGraphicsProbe();
std::uint32_t GraphicsProbeFlags();
void ReleaseGraphicsProbeOwnedResources(); // after hooks are disabled, outside loader locks
#ifdef MALEMOD_GRAPHICS_PROBE_TESTING
unsigned TestOwnedDraw(void* list,std::uint32_t indices);
#endif
}
