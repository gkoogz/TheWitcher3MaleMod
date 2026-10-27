#pragma once
#include <malemod/surface/wire.hpp>
#include <malemod/controls/canonical_menu.hpp>

namespace malemod::witcher {
// Canonical gameplay rows wrap; numeric controls move by one/five units.
struct OverlayNavigation {
 unsigned selected=0;
 void Move(int direction,unsigned count=controls::menu::RowCount){selected=unsigned((int(selected)+direction+int(count))%int(count));}
 void MoveMenu(int direction,bool){Move(direction);}
 float Adjust(const surface::Controls& c,int direction,bool shift)const{
  const int core=controls::menu::CoreIndex(selected);
  return core>=0?controls::menu::AdjustCore(c.values,unsigned(core),direction,shift):0.f;
 }
};
}
