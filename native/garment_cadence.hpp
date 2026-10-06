#pragma once
#include <cmath>
#include <cstdint>
#include <stdexcept>

namespace malemod::witcher {
// Engine-time bookkeeping only. Numerical substeps and fabric laws belong in
// Base. A latest-request worker receives elapsed active time even when it drops
// intermediate display requests; a pause never becomes simulation catch-up.
class GarmentCadence {
 unsigned epoch_=0;
 double seconds_=0,active_=0;
 bool ready_=false,paused_=false;
 public:
 struct Sample {bool queue=false,reset=false;double activeSeconds=0;};
 void Reset(){epoch_=0;seconds_=active_=0;ready_=paused_=false;}
 Sample Advance(unsigned epoch,double seconds,bool paused,bool geometryChanged){
  if(!epoch||!std::isfinite(seconds))throw std::invalid_argument("Invalid garment engine clock");
  if(!ready_||epoch_!=epoch){epoch_=epoch;seconds_=seconds;active_=0;ready_=true;paused_=paused;return {!paused,true,active_};}
  const double elapsed=seconds-seconds_;seconds_=seconds;
  if(paused){paused_=true;return {false,false,active_};}
  if(paused_){paused_=false;return {true,false,active_};}
  if(elapsed<0||elapsed>1){active_=0;return {true,true,active_};}
  active_+=elapsed;
  return {elapsed>0||geometryChanged,false,active_};
 }
};
}
