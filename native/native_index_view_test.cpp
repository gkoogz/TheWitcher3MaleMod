#include "native_index_view.hpp"
#include <stdexcept>
using malemod::witcher::NativeIndexFirst;
int main(){
 auto check=[](bool b){if(!b)throw std::runtime_error("Native index view regression");};
 // Captured lower/upper full allocations and the engine's rebased LOD1 views.
 check(NativeIndexFirst(0x1000,486936,0x1000,486936,0,121491)==0);
 check(NativeIndexFirst(0x1000,486936,0x1000+242982,243954,0,121977)==121491);
 check(NativeIndexFirst(0x1000,101466,0x1000+62838,38628,0,19314)==31419);
 check(NativeIndexFirst(0x1000,101466,0x1000,101466,31419,19314)==31419);
 check(!NativeIndexFirst(0x1000,101466,0x1001,38628,0,19314));
 check(!NativeIndexFirst(0x1000,101466,0x1000+62838,38630,0,19314));
 check(!NativeIndexFirst(0x1000,101466,0x1000+62838,38628,1,19314));
 check(!NativeIndexFirst(0x1000,101466,0xfff,38628,0,19314));
 check(!NativeIndexFirst(0x1000,101466,0x1000,101466,0xffffffff,1));
}
