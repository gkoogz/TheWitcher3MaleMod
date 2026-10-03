#pragma once
#include <malemod/surface/wire.hpp>
#include <algorithm>

namespace malemod::witcher {
// Wolverine anatomy controls: wrap selection/state; one/five unit adjustments.
// Clinical rows use the same arrow contract after the 18 morphology controls.
struct OverlayNavigation {
 unsigned selected=0;
 void Move(int direction,unsigned count=18){selected=unsigned((int(selected)+direction+int(count))%int(count));}
 float Adjust(const surface::Controls& c,int direction,bool shift)const{
  if(selected==0)return float((int(c.values[0])+direction+3)%3);
  const float low=selected==2||selected==4?0.f:1.f;
  return (std::max)(low,(std::min)(100.f,c.values[selected]+direction*(shift?5.f:1.f)));
 }
};
}
