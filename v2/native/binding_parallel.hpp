#pragma once
#include <ppl.h>
#include <xmmintrin.h>

namespace malemod::witcher::v2::binding_parallel {
// Native transport is x64/SSE. Preserve the caller's rounding, denormal and
// exception state without leaving that policy on a borrowed PPL worker.
class ScopedMXCSR {
 unsigned previous_;
public:
 explicit ScopedMXCSR(unsigned desired) noexcept:previous_(_mm_getcsr()){_mm_setcsr(desired);}
 ~ScopedMXCSR() noexcept{_mm_setcsr(previous_);}
 ScopedMXCSR(const ScopedMXCSR&)=delete;
 ScopedMXCSR& operator=(const ScopedMXCSR&)=delete;
};

template<class Action> void FourPartitions(unsigned count,Action action){
 if(count<4096){action(0,count);return;}
 const unsigned callerMXCSR=_mm_getcsr();
 concurrency::parallel_for(0u,4u,[&](unsigned block){
  ScopedMXCSR restore(callerMXCSR);
  action(count*block/4,count*(block+1)/4);
 });
}
}
