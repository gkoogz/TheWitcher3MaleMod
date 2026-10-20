#pragma once
#include "runtime_controller.hpp"
#include "modular_render.hpp"
#include <condition_variable>
#include <thread>
namespace malemod::witcher {
// Expensive geometry runs independently from numerical stepping and display.
// Only display endpoints coalesce; the ordered physics worker is unchanged.
class ModularService {
 public:struct Result {std::shared_ptr<const RuntimeDelivery> source;std::shared_ptr<const ModularFrame> frame;unsigned epoch=0;};
 private:
 std::shared_ptr<ModularRenderer> renderer_;std::mutex mutex_;std::condition_variable changed_;bool stop_=false;
 std::shared_ptr<const RuntimeDelivery> pending_;unsigned epoch_=0,inFlightEpoch_=0;std::uint64_t inFlight_=0;
 std::shared_ptr<const Result> latest_;std::string error_;std::thread worker_;
 public:
 explicit ModularService(std::shared_ptr<ModularRenderer> renderer):renderer_(std::move(renderer)),worker_([this]{
  for(;;){std::shared_ptr<const RuntimeDelivery> source;unsigned epoch;
   {std::unique_lock<std::mutex> lock(mutex_);changed_.wait(lock,[&]{return stop_||pending_;});if(stop_)return;source=std::move(pending_);epoch=epoch_;inFlight_=source->surface->sequence;inFlightEpoch_=epoch;}
   try{const auto& f=source->surface->frame;auto state=renderer_->Drive(f.source,f.modularPivot,f.modularRadians,f.modularShape,source->surface->input.controls.values[6]);auto next=std::make_shared<Result>(Result{source,renderer_->Evaluate(state),epoch});std::atomic_store(&latest_,std::shared_ptr<const Result>(next));}
   catch(const std::exception& e){std::lock_guard<std::mutex> lock(mutex_);error_=e.what();}
  }
 }){}
 ~ModularService(){{std::lock_guard<std::mutex> lock(mutex_);stop_=true;}changed_.notify_one();worker_.join();}
 void Submit(std::shared_ptr<const RuntimeDelivery> source,unsigned epoch){std::lock_guard<std::mutex> lock(mutex_);auto done=Latest();if((done&&done->epoch==epoch&&done->source->surface->sequence>=source->surface->sequence)||(inFlightEpoch_==epoch&&inFlight_==source->surface->sequence))return;pending_=std::move(source);epoch_=epoch;changed_.notify_one();}
 std::shared_ptr<const Result> Latest()const{return std::atomic_load(&latest_);}
 std::string Error(){std::lock_guard<std::mutex> lock(mutex_);return error_;}
};
}
