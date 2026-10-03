#pragma once
#include "runtime_controller.hpp"
#include <functional>

namespace malemod::witcher {
enum class HostTick {Accepted=0,Paused=1,Loading=2,Busy=3,Full=4,Invalid=5,Failed=6,Dormant=7,Computing=8};
class RuntimeHost {
 using Factory=std::function<std::unique_ptr<RuntimeController>()>;
 std::mutex mutex_;std::condition_variable changed_;bool stopping_=false;
 std::uint32_t requested_=0,active_=0;std::string error_;
 std::unique_ptr<RuntimeController> controller_;
 std::thread manager_;
 public:
 explicit RuntimeHost(Factory factory):manager_([this,factory=std::move(factory)]{
  for(;;){std::uint32_t epoch=0;std::unique_ptr<RuntimeController> retired;
   {std::unique_lock<std::mutex> lock(mutex_);changed_.wait(lock,[&]{return stopping_||requested_!=active_;});if(stopping_)return;epoch=requested_;active_=0;retired=std::move(controller_);}
   // Stop/join numerical workers only on this manager, outside the host lock.
   retired.reset();if(!epoch)continue;
   try{auto next=factory();std::lock_guard<std::mutex> lock(mutex_);if(!stopping_&&epoch==requested_){controller_=std::move(next);active_=epoch;error_.clear();}}
   catch(const std::exception& e){std::lock_guard<std::mutex> lock(mutex_);error_=e.what();if(epoch==requested_)active_=epoch;}
  }
 }){}
 ~RuntimeHost(){ {std::lock_guard<std::mutex> lock(mutex_);stopping_=true;}changed_.notify_one();if(manager_.joinable())manager_.join();controller_.reset();}
 RuntimeHost(const RuntimeHost&)=delete;RuntimeHost& operator=(const RuntimeHost&)=delete;
 HostTick Tick(std::uint32_t epoch,PoseSample sample,bool paused,const surface::Controls& controls,std::uint64_t& sequence,const surface::Frame::ClinicalProjection& clinical={}){
  sequence=0;std::unique_lock<std::mutex> lock(mutex_,std::try_to_lock);if(!lock.owns_lock())return HostTick::Busy;
  if(stopping_)return HostTick::Failed;
  if(requested_!=epoch){requested_=epoch;changed_.notify_one();}
  if(!epoch)return HostTick::Dormant;
  if(active_!=epoch)return HostTick::Loading;if(!controller_)return HostTick::Failed;
  try{switch(controller_->Tick(sample,paused,controls,sequence,clinical)){
   case RuntimeTick::Accepted:return HostTick::Accepted;case RuntimeTick::Paused:return HostTick::Paused;
   case RuntimeTick::Loading:return HostTick::Loading;case RuntimeTick::Computing:return HostTick::Computing;
   case RuntimeTick::Busy:return HostTick::Busy;case RuntimeTick::Full:return HostTick::Full;
   case RuntimeTick::Invalid:return HostTick::Invalid;default:error_=controller_->Error();return HostTick::Failed;
  }}catch(const std::exception& e){error_=e.what();return HostTick::Failed;}
 }
 std::shared_ptr<const RuntimeDelivery> Poll(std::uint32_t epoch){
  std::unique_lock<std::mutex> lock(mutex_,std::try_to_lock);if(!lock.owns_lock()||!epoch||active_!=epoch||requested_!=epoch||!controller_)return {};
  controller_->Publish();return controller_->Latest();
 }
 std::string Error(){std::lock_guard<std::mutex> lock(mutex_);return error_;}
};
}
