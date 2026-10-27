#pragma once
#include <mutex>
namespace malemod::witcher {
// Publish and latch a matching body/garment pair together across game and
// render threads. Geometry construction occurs outside this short section.
inline std::mutex& FramePublicationMutex(){static auto* mutex=new std::mutex;return *mutex;}
using FramePublicationLock=std::lock_guard<std::mutex>;
}
