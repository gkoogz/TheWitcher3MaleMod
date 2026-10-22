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
 std::uint64_t highestSubmitted_=0;unsigned submittedEpoch_=0;
 std::optional<surface::Controls> requested_;
 std::chrono::steady_clock::time_point shapeChanged_{};
 std::shared_ptr<const Result> latest_;std::string error_;std::thread worker_;
 public:
 explicit ModularService(std::shared_ptr<ModularRenderer> renderer):renderer_(std::move(renderer)),worker_([this]{
  for(;;){std::shared_ptr<const RuntimeDelivery> source;unsigned epoch;
   {std::unique_lock<std::mutex> lock(mutex_);changed_.wait(lock,[&]{return stop_||pending_;});if(stop_)return;
    // Direct display deforms the current prepared mesh while a control is
    // being edited. Let it own that interaction: repeatedly recutting the
    // socket competes with input presentation and immediately becomes stale.
    // This holds only display fitting; ordered numerical samples keep running.
    for(;;){
     auto shown=Latest();bool refit=false;
     if(shown&&shown->epoch==epoch_&&shown->source->surface->input.controls.values[0]==pending_->surface->input.controls.values[0]
       &&shown->source->surface->input.controls.values[7]==pending_->surface->input.controls.values[7])
      for(unsigned i=1;i<=9;i++)refit|=shown->source->surface->input.controls.values[i]!=pending_->surface->input.controls.values[i];
     auto deadline=shapeChanged_+std::chrono::milliseconds(250);
     if(!refit||std::chrono::steady_clock::now()>=deadline)break;
     changed_.wait_until(lock,deadline);if(stop_)return;
    }
    source=std::move(pending_);epoch=epoch_;inFlight_=source->surface->sequence;inFlightEpoch_=epoch;}
   try{const auto& f=source->surface->frame;auto state=renderer_->Drive(f.source,f.modularPivot,f.modularRadians,f.modularShape,source->surface->input.controls.values[6]);auto next=std::make_shared<Result>(Result{source,renderer_->Evaluate(state),epoch});std::atomic_store(&latest_,std::shared_ptr<const Result>(next));}
   catch(const std::exception& e){
    // Explicit private-session opt-in: retain one exact failing input, not a
    // rolling capture bank. Normal game launches have no diagnostic path.
    if(const char* prefix=std::getenv("MALEMOD_COMPOUND_FAILURE_PREFIX"))try{
     auto path=std::filesystem::path(std::string(prefix)+"-source.bin");
     if(!std::filesystem::exists(path)){const auto& f=source->surface->frame;
      auto write=[](const std::filesystem::path& p,const auto& bytes){std::ofstream out(p,std::ios::binary);out.write(reinterpret_cast<const char*>(bytes.data()),bytes.size());};
      write(path,surface::wire::Encode(f.source));if(f.modularShape)write(std::string(prefix)+"-shape.bin",surface::wire::Encode(*f.modularShape));
      std::ofstream info(std::string(prefix)+"-state.txt");info<<e.what()<<'\n'<<f.modularRadians<<'\n';for(auto x:f.modularPivot)info<<x<<' ';info<<'\n';for(auto x:source->surface->input.controls.values)info<<x<<' ';
     }
    }catch(...){/* Preserve the original renderer failure. */}
    std::lock_guard<std::mutex> lock(mutex_);error_=e.what();
   }
  }
 }){}
 ~ModularService(){{std::lock_guard<std::mutex> lock(mutex_);stop_=true;}changed_.notify_one();worker_.join();}
 void Submit(std::shared_ptr<const RuntimeDelivery> source,unsigned epoch){
  std::lock_guard<std::mutex> lock(mutex_);auto done=Latest();
  if((submittedEpoch_==epoch&&highestSubmitted_>=source->surface->sequence)||(done&&done->epoch==epoch&&done->source->surface->sequence>=source->surface->sequence))return;
  bool shapeChange=!requested_||submittedEpoch_!=epoch;
  if(requested_)for(unsigned i=0;i<=9;i++)shapeChange|=requested_->values[i]!=source->surface->input.controls.values[i];
  if(shapeChange)shapeChanged_=std::chrono::steady_clock::now();
  requested_=source->surface->input.controls;highestSubmitted_=source->surface->sequence;submittedEpoch_=epoch;
  pending_=std::move(source);epoch_=epoch;changed_.notify_one();
 }
 std::shared_ptr<const Result> Latest()const{return std::atomic_load(&latest_);}
 std::string Error(){std::lock_guard<std::mutex> lock(mutex_);return error_;}
};
}
