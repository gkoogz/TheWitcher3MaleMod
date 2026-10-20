#pragma once
#include <malemod/surface/attachment_hinge.hpp>
#include <malemod/surface/root_articulation.hpp>
#include <malemod/surface/runtime.hpp>
namespace malemod::witcher {
constexpr float FixedCollarReferenceAngle=35;
struct FixedAngleRegion {
 surface::root_motion::Point origin{};
 double gain=1,downwardDegrees=30,upwardDegrees=55;
};
inline surface::root_articulation::Rotation FixedCollarFlow(const FixedAngleRegion& region,float slider){
 #ifdef MALEMOD_DILATING_COLLAR
 // The expanded socket is validated over this mechanical interval. Keep the
 // same endpoint for the visible surface, guide and nozzle presentation.
 const double control=std::clamp(double(slider),10.,90.);
 #else
 const double control=std::clamp(double(slider),1.,100.);
 #endif
 const double angle=(50-control)/(control<50?49.:50.)*((control<50?region.upwardDegrees:region.downwardDegrees)*3.141592653589793/180.)*region.gain;
 return {region.origin,{1,0,0},{0,0,1},angle};
}
inline void PresentFixedCollarSource(surface::Output& source,float slider,const FixedAngleRegion& region){
 const auto flow=FixedCollarFlow(region,slider);
 auto p=[](surface::Point x){return surface::root_motion::Point{x.x,x.y,x.z};};
 auto native=[](surface::root_motion::Point x){return surface::Point{float(x[0]),float(x[1]),float(x[2])};};
 for(auto& x:source.shaftGuide)x=native(flow.Apply(p(x)));
 for(auto& x:source.restGuide)x=native(flow.Apply(p(x)));
 source.nozzleDirection=native(flow.Vector(p(source.nozzleDirection)));
 source.nozzlePosition=native(flow.Apply(p(source.nozzlePosition)));
}
}
