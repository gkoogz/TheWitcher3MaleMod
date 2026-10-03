#pragma once
#include "surface_pipeline.hpp"
#include <condition_variable>
#include <thread>

namespace malemod::witcher {
struct CompletedSurface {
 std::uint64_t sequence=0;
 surface::wire::Request input;
 SurfaceFrame frame;
};
enum class Submission {Accepted,Busy,Full,Stopped,Invalid,Loading};
// Engine integration owns one service per character lifetime. Each accepted
// request is evaluated in order with its original controls, dt and contacts.
// No coalescing, skipped physics steps, interpolation or stale-control mixing.
// Construction/destruction belong outside engine locks and loader callbacks.
class SurfaceService {
 struct Pending {std::uint64_t sequence;surface::wire::Request input;};
 static constexpr std::size_t capacity=8;
 std::mutex mutex_;std::condition_variable changed_;std::array<Pending,capacity> queue_;
 std::size_t first_=0,size_=0;
 bool stopping_=false;std::uint64_t sequence_=0;
 std::atomic<bool> failed_{false};std::string error_;
 std::atomic<bool> preparing_{false};
 std::shared_ptr<const CompletedSurface> completed_;
 std::thread thread_;
 public:
 SurfaceService(std::wstring worker,std::filesystem::path bindings,std::string revision,std::optional<surface::Controls> startup=std::nullopt):
  preparing_(startup.has_value()),thread_([this,worker=std::move(worker),bindings=std::move(bindings),revision=std::move(revision),startup]{
   try{
    SurfacePipeline pipeline(worker,bindings,revision);
    if(startup)pipeline.Initialize(*startup);
    preparing_.store(false,std::memory_order_release);
    for(;;){Pending next;
     {std::unique_lock<std::mutex> lock(mutex_);changed_.wait(lock,[&]{return stopping_||size_!=0;});
      if(stopping_)return;next=queue_[first_];first_=(first_+1)%capacity;--size_;}
     auto result=std::make_shared<CompletedSurface>();result->sequence=next.sequence;result->input=next.input;
     result->frame=pipeline.Evaluate(next.input);
     std::atomic_store_explicit(&completed_,std::shared_ptr<const CompletedSurface>(std::move(result)),std::memory_order_release);
    }
   }catch(const std::exception& e){std::lock_guard<std::mutex> lock(mutex_);error_=e.what();failed_.store(true,std::memory_order_release);}
  }){}
 ~SurfaceService(){ {std::lock_guard<std::mutex> lock(mutex_);stopping_=true;}changed_.notify_one();if(thread_.joinable())thread_.join(); }
 SurfaceService(const SurfaceService&)=delete;SurfaceService& operator=(const SurfaceService&)=delete;
 Submission Submit(const surface::wire::Request& request,std::uint64_t& acceptedSequence){
  acceptedSequence=0;
  try{surface::wire::Validate(request.controls);surface::wire::Validate(request.frame);}catch(const std::exception&){return Submission::Invalid;}
  // Resetting the process-global source requires a replacement service/worker.
  if(request.reset)return Submission::Invalid;
  if(preparing_.load(std::memory_order_acquire))return failed_?Submission::Stopped:Submission::Loading;
  std::unique_lock<std::mutex> lock(mutex_,std::try_to_lock);
  if(!lock.owns_lock())return Submission::Busy;
  if(stopping_||failed_.load(std::memory_order_acquire))return Submission::Stopped;
  if(size_==capacity)return Submission::Full;
  acceptedSequence=++sequence_;queue_[(first_+size_)%capacity]={acceptedSequence,request};++size_;changed_.notify_one();return Submission::Accepted;
 }
 // A rejected submission remains the caller's responsibility. Full/Busy must
 // be handled visibly by the eventual engine lifecycle, never silently ignored.
 std::shared_ptr<const CompletedSurface> Latest()const{return std::atomic_load_explicit(&completed_,std::memory_order_acquire);}
 bool Failed()const{return failed_.load(std::memory_order_acquire);}
 std::string Error(){std::lock_guard<std::mutex> lock(mutex_);return error_;}
};
}
