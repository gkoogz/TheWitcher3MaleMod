#pragma once
// Mechanically retained observed VM scene-query handoff from archived v1.
// Numerical fluid algorithms are supplied exclusively by canonical Base.
#include <malemod/clinical/fluid_types.h>
#include <mutex>
#include <deque>
#include <map>
#include <array>
namespace malemod::witcher {
class ClinicalCollision {
 using V=malemod::V3;
 struct Entry {unsigned token;V from,to;float radius;bool issued=false,ready=false,hit=false;clinical::volumeFluid::FluidImpact impact;double touched=0;bool projection=false;std::array<float,5> key{};};
 std::mutex mutex_;std::map<unsigned,Entry> entries_;std::map<std::array<float,5>,unsigned> keys_;std::deque<unsigned> queue_;unsigned next_=1,issued_=0,hits_=0;
 double now_=0;
 public:
 clinical::volumeFluid::SweepResult Sweep(V from,V to,float radius,clinical::volumeFluid::FluidImpact& impact,bool projection=false){
  using Result=clinical::volumeFluid::SweepResult;std::lock_guard<std::mutex> lock(mutex_);const std::array<float,5> key{from.x,from.y,from.z,radius,projection?1.f:0.f};
  auto found=keys_.find(key);
  if(found==keys_.end()){
   if(entries_.size()>=4096)return Result::deferred;
   unsigned id;do{id=next_++;if(next_>=16777216u)next_=1;}while(entries_.count(id));Entry e{id,from,to,radius};e.touched=now_;e.key=key;e.projection=projection;entries_.emplace(id,e);keys_[key]=id;queue_.push_back(id);return Result::deferred;
  }
  auto& e=entries_.at(found->second);
  e.touched=now_;
  if(!e.ready){if(!e.issued)e.to=to;return Result::deferred;}
  if(e.hit){auto direction=to-from;float d=Dot(direction,direction);auto q=e.impact.p-from;float t=d>1e-12f?Dot(q,direction)/d:0;
   if(t>=-.05f&&t<=1.05f&&Length(q-direction*t)<=radius*2){impact=e.impact;entries_.erase(e.token);keys_.erase(found);return Result::hit;}
   e.from=from;e.to=to;e.ready=e.issued=false;queue_.push_back(e.token);return Result::deferred;
  }
  auto direction=to-from;float d=Dot(direction,direction);auto tested=e.to-from;
  const bool covered=d<1e-12f||(Dot(tested,direction)>=d&&Length(Cross(tested,Unit(direction)))<=radius*.25f);
  if(covered){entries_.erase(e.token);keys_.erase(found);return Result::miss;}
  // Extend an already tested miss. Keep the original key/path so a late floor
  // hit is applied to its particle rather than thrown away as stale data.
  if(Length(Cross(tested,Unit(direction)))<=radius*.25f)e.from=e.to;
  else e.from=from;
  e.to=to;e.ready=e.issued=false;queue_.push_back(e.token);return Result::deferred;
 }
 struct Query {unsigned token=0;V from{},to{};float radius=0;};
 Query Next(){std::lock_guard<std::mutex> lock(mutex_);while(!queue_.empty()){unsigned id=queue_.front();queue_.pop_front();auto f=entries_.find(id);if(f!=entries_.end()&&!f->second.issued){auto& e=f->second;e.issued=true;++issued_;return {id,e.from,e.to,e.radius};}}return {};}
 void Result(unsigned token,bool hit,V p,V n){std::lock_guard<std::mutex> lock(mutex_);auto i=entries_.find(token);if(i==entries_.end())return;auto& e=i->second;if(!e.issued||e.ready)return;e.ready=true;e.hit=hit;if(hit)++hits_;e.impact.p=p;e.impact.n=Unit(n);e.impact.kind=clinical::volumeFluid::FLUID_IMPACT_WORLD;}
 std::array<unsigned,3> Counts(){std::lock_guard<std::mutex> lock(mutex_);return {unsigned(entries_.size()),issued_,hits_};}
 // A live moving path refreshes touched each solver step. Retired nodes must
 // release their completed/pending slots promptly or early clear flow fills
 // all 4096 slots and later opaque pumps can never request a receiver. Surface
 // anchors retry on the Base schedule, so they have a separate three-second
 // lifetime and key namespace. Neither limit consumes extra VM queries.
 void AdvanceTime(double seconds){std::lock_guard<std::mutex> lock(mutex_);now_=seconds;for(auto i=entries_.begin();i!=entries_.end();){auto& e=i->second;if(now_-e.touched>(e.projection?3:.35)){keys_.erase(e.key);i=entries_.erase(i);}else ++i;}}
 void Clear(){std::lock_guard<std::mutex> lock(mutex_);entries_.clear();keys_.clear();queue_.clear();issued_=hits_=0;}
};
}
