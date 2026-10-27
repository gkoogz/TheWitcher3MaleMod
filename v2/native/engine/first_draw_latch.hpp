#pragma once
#include <memory>
#include <utility>
namespace malemod::witcher {
// The caller serializes publication and selection. Present invalidates; it
// cannot select the next native frame before the SDK has published its pose.
template<class Body,class Garment,class Fluid=void> class FirstDrawLatch {
public:
 struct Selection {std::shared_ptr<const Body> body;std::shared_ptr<const Garment> garment;std::shared_ptr<const Fluid> fluid;};
 const Selection& Select(Selection latest){
  if(!latest.body){Invalidate();return selected_;}
  if(!selected_.body||selected_.body->epoch!=latest.body->epoch)selected_=std::move(latest);
  return selected_;
 }
 void Invalidate(){selected_={};}
private:Selection selected_;
};
}
