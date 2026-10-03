#pragma once
#include "render_service.hpp"
#include <malemod/clinical/session.hpp>
#include <malemod/clinical/ambient.hpp>
#include <malemod/clinical/deposit_mesh.hpp>
#include <deque>
#include <map>

namespace malemod::witcher {
// Engine scene queries run on the VM thread. Numerical fluid work remains on
// its own worker. Deferred paths preserve the full untested crossing segment.
class ClinicalCollision {
 using V=malemod::V3;
 struct Entry {unsigned token;V from,to;float radius;bool issued=false,ready=false,hit=false;clinical::volumeFluid::FluidImpact impact;double touched=0;std::array<float,4> key{};};
 std::mutex mutex_;std::map<unsigned,Entry> entries_;std::map<std::array<float,4>,unsigned> keys_;std::deque<unsigned> queue_;unsigned next_=1,issued_=0,hits_=0;
 double now_=0;
 public:
 clinical::volumeFluid::SweepResult Sweep(V from,V to,float radius,clinical::volumeFluid::FluidImpact& impact){
  using Result=clinical::volumeFluid::SweepResult;std::lock_guard<std::mutex> lock(mutex_);const std::array<float,4> key{from.x,from.y,from.z,radius};
  auto found=keys_.find(key);
  if(found==keys_.end()){
   if(entries_.size()>=4096)return Result::deferred;
   unsigned id;do{id=next_++;if(next_>=16777216u)next_=1;}while(entries_.count(id));Entry e{id,from,to,radius};e.touched=now_;e.key=key;entries_.emplace(id,e);keys_[key]=id;queue_.push_back(id);return Result::deferred;
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
 void AdvanceTime(double seconds){std::lock_guard<std::mutex> lock(mutex_);now_=seconds;for(auto i=entries_.begin();i!=entries_.end();){auto& e=i->second;if(now_-e.touched>(e.ready?8:30)){keys_.erase(e.key);i=entries_.erase(i);}else ++i;}}
 void Clear(){std::lock_guard<std::mutex> lock(mutex_);entries_.clear();keys_.clear();queue_.clear();issued_=hits_=0;}
};
struct ClinicalDelivery {
 unsigned epoch=0;std::uint64_t serial=0;float time=0;bool active=false;unsigned throbMode=0,cueMask=0;
 double emittedVolume=0,milliseconds=0;unsigned impacts=0;
 clinical::DepositMesh deposits;
 clinical::teaching::LiquidMesh mesh; // calibrated source-unit world positions
};
struct DialogueCue {unsigned phase=0,epoch=0,sequence=0;double seconds=0;};
class ClinicalService {
 std::mutex mutex_;std::condition_variable changed_;bool stopping_=false,paused_=true;
 unsigned epoch_=0,mode_=0,action_=0,actionSerial_=0,actionEpoch_=0;double seconds_=0;
 std::shared_ptr<const RenderDelivery> input_;std::shared_ptr<const ClinicalDelivery> delivery_;
 surface::Frame::ClinicalProjection projection_{};std::string error_;
 double scale_;std::filesystem::path bakes_;
 std::deque<DialogueCue> cues_;
 public:
 ClinicalCollision collisions;
 explicit ClinicalService(double scale,std::filesystem::path bakes):scale_(scale),bakes_(std::move(bakes)),worker_([this]{Run();}){}
 ~ClinicalService(){{std::lock_guard<std::mutex> l(mutex_);stopping_=true;}changed_.notify_one();if(worker_.joinable())worker_.join();}
 void Submit(unsigned epoch,double seconds,bool paused,std::shared_ptr<const RenderDelivery> input){{std::lock_guard<std::mutex> l(mutex_);epoch_=epoch;seconds_=seconds;paused_=paused;input_=std::move(input);}changed_.notify_one();}
 void SetMode(unsigned mode){if(mode>3)throw std::invalid_argument("Invalid throb mode");std::lock_guard<std::mutex> l(mutex_);mode_=mode;}
 unsigned Mode(){std::lock_guard<std::mutex> l(mutex_);return mode_;}
 void Action(bool start){std::lock_guard<std::mutex> l(mutex_);action_=start?1:2;actionEpoch_=epoch_;++actionSerial_;changed_.notify_one();}
 std::optional<DialogueCue> PollCue(){std::lock_guard<std::mutex> l(mutex_);if(cues_.empty())return {};auto cue=cues_.front();cues_.pop_front();return cue;}
 surface::Frame::ClinicalProjection Projection(){std::lock_guard<std::mutex> l(mutex_);return projection_;}
 std::shared_ptr<const ClinicalDelivery> Latest()const{return std::atomic_load(&delivery_);}
 std::string Error(){std::lock_guard<std::mutex> l(mutex_);return error_;}
 double Scale()const{return scale_;}
 private:
 void Run(){
  clinical::Session session;clinical::AmbientClock clock;clinical::teaching::PassiveThrobGate gate;unsigned epoch=0,handled=0,cueMask=0;std::uint64_t serial=0;double last=0;bool resume=true,faulted=false,resetError=false;malemod::V3 previousActor{};
  session.audio.playPhase=[&](unsigned phase){cueMask|=1u<<phase;std::lock_guard<std::mutex> l(mutex_);if(cues_.size()<64)cues_.push_back({phase,epoch,handled,session.timeline.time});}; // delivered to the VM; empty slots stay silent
  session.fluid.settings.catchPlane=false;
  if(!session.deposits.splatBakes.LoadFile(bakes_.string())){std::lock_guard<std::mutex> l(mutex_);error_="Clinical deposit bake unavailable";return;}
  session.deposits.project=[&](const auto& contact,malemod::V3 p,auto& result){auto a=p+contact.n*2,b=p-contact.n*2;return collisions.Sweep(a,b,.02f,result)==clinical::volumeFluid::SweepResult::hit;};
  session.fluid.collisionQuery.callback=[this](auto a,auto b,float r,auto& hit){return collisions.Sweep(a,b,r,hit);};
  for(;;){unsigned nextEpoch,mode,action,actionSerial,actionEpoch;double seconds;bool paused;std::shared_ptr<const RenderDelivery> input;
   {std::unique_lock<std::mutex> l(mutex_);changed_.wait_for(l,std::chrono::milliseconds(8));if(stopping_)return;nextEpoch=epoch_;mode=mode_;action=action_;actionSerial=actionSerial_;actionEpoch=actionEpoch_;seconds=seconds_;paused=paused_;input=input_;}
   try{
    if(nextEpoch!=epoch){session.Cancel();clock.SetMode(0);collisions.Clear();epoch=nextEpoch;resume=true;faulted=false;resetError=true;cueMask=0;if(!actionSerial||actionEpoch!=epoch)handled=actionSerial;{std::lock_guard<std::mutex> l(mutex_);projection_={};cues_.clear();}std::atomic_store(&delivery_,std::shared_ptr<const ClinicalDelivery>{});}
    if(paused||!epoch||!input||input->epoch!=epoch){resume=true;continue;}
    collisions.AdvanceTime(seconds);
    clinical::NozzlePose nozzle;nozzle.position={float(input->nozzleWorld[0]/scale_),float(input->nozzleWorld[1]/scale_),float(input->nozzleWorld[2]/scale_)};nozzle.direction={float(input->nozzleDirectionWorld[0]),float(input->nozzleDirectionWorld[1]),float(input->nozzleDirectionWorld[2])};
    malemod::V3 actor{float(input->pose.actorWorld[3]/scale_),float(input->pose.actorWorld[7]/scale_),float(input->pose.actorWorld[11]/scale_)};
    double elapsed=resume?0:seconds-last;if(elapsed<0){session.Cancel();collisions.Clear();elapsed=0;resume=true;}
    if(elapsed>0)nozzle.inheritedVelocity=(actor-previousActor)*float(1/elapsed);
    const bool actionChanged=actionSerial!=handled,modeChanged=mode!=clock.mode;
    // Recover only through an explicit Start or a verified new character.
    // Unrelated successful ticks must not hide a real simulation failure.
    if(faulted&&(!actionChanged||action!=1)){handled=actionSerial;continue;}
    if(!std::isfinite(seconds)||!clinical::Session::Finite(nozzle.position)||!clinical::Session::Finite(nozzle.direction)||Length(nozzle.direction)<1e-6f||!clinical::Session::Finite(nozzle.inheritedVelocity))throw std::runtime_error("Clinical emitter pose and clock must be finite with a nonzero direction");
    if(!resume&&elapsed==0&&!actionChanged&&!modeChanged)continue;
    if(actionChanged){{std::lock_guard<std::mutex> l(mutex_);cues_.clear();}handled=actionSerial;if(action==1){collisions.Clear();gate.Reset();session.fluid.SetVariationSeed(0x6d2b79f5u+actionSerial);if(!session.Begin(nozzle.position))throw std::runtime_error(session.fluid.error);session.fluid.lastDir=Unit(nozzle.direction);session.fluid.surfaceDeposits=true;cueMask=0;faulted=false;resetError=true;}else{session.timeline.Cancel();session.audio.End();session.fluid.Clear();collisions.Clear();}}
    clock.SetMode(mode);
    if(resetError){std::lock_guard<std::mutex> l(mutex_);error_.clear();resetError=false;}
    auto started=std::chrono::steady_clock::now();
    if(!session.timeline.active&&mode){if(!session.fluid.ready||!session.fluid.passiveMode){if(!session.fluid.BeginPassive(nozzle.position))throw std::runtime_error(session.fluid.error);session.fluid.lastDir=Unit(nozzle.direction);session.fluid.surfaceDeposits=true;gate.Reset();}}
    else if(!session.timeline.active&&session.fluid.passiveMode){session.fluid.Clear();gate.Reset();}
    bool emitterStopped=false;
    auto stopEmitter=[&]{
     // The source clears fluid on a finite teleport. This is a normal actor
     // relocation, not a corrupt-emitter fault. Keep existing floor stains.
     session.timeline.Cancel();session.audio.End();session.fluid.Clear();
     collisions.Clear();gate.Reset();cueMask=0;emitterStopped=true;
     std::lock_guard<std::mutex> l(mutex_);cues_.clear();
    };
    while(elapsed>1e-7){float dt=float((std::min)(elapsed,1./60.));clock.Advance(dt);if(session.fluid.passiveMode){if(gate.Update(clock.Pulse()))session.fluid.TriggerPassiveClear();session.fluid.Advance(dt,nozzle.position,Unit(nozzle.direction),nozzle.inheritedVelocity);if(!session.fluid.ready){stopEmitter();break;}session.deposits.Add(session.fluid.impacts,std::uint32_t(seconds*1000));session.deposits.Update(std::uint32_t(seconds*1000));}else{bool wasActive=session.timeline.active;if(!session.Advance(dt,nozzle,std::uint32_t(seconds*1000)))throw std::runtime_error(session.fluid.error);if(wasActive&&!session.fluid.ready){stopEmitter();break;}if(wasActive&&!session.timeline.active)session.fluid.Clear();}elapsed-=dt;}
    last=seconds;previousActor=actor;resume=emitterStopped;
    surface::Frame::ClinicalProjection p;p.active=session.timeline.active;p.time=session.timeline.time;p.throbMode=clock.mode;p.sizeTime=clock.sizeTime;p.twitchTime=clock.twitchTime;p.lateralWobbleDegrees=session.fluid.settings.lateralWobbleDegrees;std::copy(std::begin(session.fluid.lateralGain),std::end(session.fluid.lateralGain),p.lateralGain.begin());std::copy(std::begin(session.fluid.angleGain),std::end(session.fluid.angleGain),p.angleGain.begin());
    {std::lock_guard<std::mutex> l(mutex_);projection_=p;}
    if(session.timeline.active||session.fluid.Live()||!session.deposits.marks.empty()||Latest()){
     auto out=std::make_shared<ClinicalDelivery>();out->epoch=epoch;out->serial=++serial;out->time=float(session.timeline.time);out->active=session.timeline.active;out->throbMode=mode;out->cueMask=cueMask;out->emittedVolume=session.fluid.emittedVolume;out->impacts=unsigned(session.fluid.impacts.size());out->mesh=session.fluid.mesh;out->deposits=clinical::BuildDepositMesh(session.deposits,std::uint32_t(seconds*1000));out->milliseconds=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-started).count();std::atomic_store(&delivery_,std::shared_ptr<const ClinicalDelivery>(out));
    }
   }catch(const std::exception& e){session.Cancel();collisions.Clear();gate.Reset();resume=true;faulted=true;resetError=false;handled=actionSerial;cueMask=0;std::atomic_store(&delivery_,std::shared_ptr<const ClinicalDelivery>{});std::lock_guard<std::mutex> l(mutex_);error_=e.what();projection_={};cues_.clear();}
 }
 }
 std::thread worker_;
};
}
