#include "binding_parallel.hpp"
#include <array>
#include <atomic>
#include <vector>
#include <stdexcept>
#include <iostream>
namespace bp=malemod::witcher::v2::binding_parallel;
namespace {
void Check(bool ok,const char* reason){if(!ok)throw std::runtime_error(reason);}
struct ExpectedFailure {};
void PartitionCoverage(){
 for(unsigned count:{0u,4095u,4096u,78337u}){
  std::vector<unsigned char> visits(count);std::atomic<unsigned> calls{0};
  bp::FourPartitions(count,[&](unsigned first,unsigned last){
   ++calls;for(unsigned i=first;i<last;i++)++visits[i];
  });
  Check(calls==(count<4096?1u:4u),"Partition task count changed");
  for(auto visit:visits)Check(visit==1,"Partition missed or repeated a row");
 }
}
void AllFloatingPointModesAndRestoration(){
 const unsigned original=_mm_getcsr();
 for(unsigned rounding=0;rounding<4;rounding++)for(unsigned ftz=0;ftz<2;ftz++)for(unsigned daz=0;daz<2;daz++){
  const unsigned desired=(original&~0xe040u)|(rounding<<13)|(ftz<<15)|(daz<<6);
  bp::ScopedMXCSR mainScope(desired);std::atomic<unsigned> calls{0};
  bp::FourPartitions(78337,[&](unsigned,unsigned){Check(_mm_getcsr()==desired,"Task lost calling MXCSR");++calls;});
  Check(calls==4,"FP test did not exercise four task scopes");
  for(bool throws:{false,true})concurrency::parallel_for(0u,4u,[&](unsigned block){
   const unsigned before=_mm_getcsr();
   {
    bp::ScopedMXCSR seeded((before&~0xe040u)|(((rounding+block+1)%4)<<13)|((1-ftz)<<15)|((1-daz)<<6));
    const unsigned previous=_mm_getcsr();bool caught=false;
    try{
     bp::ScopedMXCSR scope(desired);Check(_mm_getcsr()==desired,"RAII did not apply calling state");
     volatile float a=1.f,b=10.f,c=a/b;(void)c;
     if(throws)throw ExpectedFailure{};
    }catch(const ExpectedFailure&){caught=true;}
    Check(caught==throws&&_mm_getcsr()==previous,"Normal or exceptional exit leaked worker MXCSR");
   }
   Check(_mm_getcsr()==before,"Outer worker FP fixture failed to restore prior state");
  });
  bool propagated=false;
  try{
   bp::FourPartitions(78337,[&](unsigned first,unsigned){
    Check((_mm_getcsr()&0xffc0u)==(desired&0xffc0u),"Exception task lost calling FP controls");
    _mm_setcsr(desired^0x6000u);
    if(first==0)throw ExpectedFailure{};
   });
  }catch(const ExpectedFailure&){propagated=true;}
  Check(propagated,"Task failure was swallowed");
  Check((_mm_getcsr()&0xffc0u)==(desired&0xffc0u),"Parallel work changed caller FP controls");
 }
 Check(_mm_getcsr()==original,"Test failed to restore caller's complete MXCSR");
}
}
int main(){try{
 PartitionCoverage();AllFloatingPointModesAndRestoration();
 std::cout<<"Binding partitions: exact coverage/four-task bound,16 FP modes and normal/exception full-MXCSR restoration passed\n";
 return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
