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
// physics sample is evaluated in order with its original controls, dt and
// contacts. A bounded batch composes only its final character surface; source
// physics steps are never coalesced or skipped and controls are not mixed.
// Construction/destruction belong outside engine locks and loader callbacks.
class SurfaceService {
 struct Pending {std::uint64_t sequence;std::vector<surface::wire::Request> inputs;};
 static constexpr std::size_t capacity=8;
 static constexpr std::size_t skinCapacity=64;
 std::mutex mutex_;std::condition_variable changed_;std::array<Pending,capacity> queue_;
 std::array<Pending,skinCapacity> skinQueue_;
 std::size_t first_=0,size_=0;
 std::size_t skinFirst_=0,skinSize_=0;
 bool split_=false;
 bool stopping_=false;std::uint64_t sequence_=0;
 std::atomic<bool> failed_{false};std::string error_;
 std::atomic<unsigned> preparing_{0};
 std::shared_ptr<const CompletedSurface> completed_;
 std::shared_ptr<const CompletedSurface> skinCompleted_;
 std::thread thread_,skinThread_;
 void Run(const std::wstring& worker,const std::filesystem::path& bindings,const std::string& revision,
          std::optional<surface::Controls> startup,bool modular,bool skin){
  try{
   SurfacePipeline pipeline(worker,bindings,revision,true,modular,split_&&!skin);
   if(startup)pipeline.Initialize(*startup);
   preparing_.fetch_sub(1,std::memory_order_release);
   for(;;){Pending next;
    {std::unique_lock<std::mutex> lock(mutex_);changed_.wait(lock,[&]{return stopping_||(skin?skinSize_:size_)!=0;});
     if(stopping_)return;
     if(skin){
      next=std::move(skinQueue_[skinFirst_]);skinFirst_=(skinFirst_+1)%skinCapacity;--skinSize_;
      // Retain every accepted time/control/contact sample. Only the final
      // skin snapshot coalesces; intermediate samples use the same mechanics.
      while(skinSize_&&next.inputs.size()+skinQueue_[skinFirst_].inputs.size()<=32){
       auto& tail=skinQueue_[skinFirst_];next.sequence=tail.sequence;
       next.inputs.insert(next.inputs.end(),std::make_move_iterator(tail.inputs.begin()),std::make_move_iterator(tail.inputs.end()));
       tail.inputs.clear();skinFirst_=(skinFirst_+1)%skinCapacity;--skinSize_;
      }
     }else{next=std::move(queue_[first_]);first_=(first_+1)%capacity;--size_;}
    }
    auto result=std::make_shared<CompletedSurface>();result->sequence=next.sequence;result->input=next.inputs.back();
    result->frame=pipeline.EvaluateBatch(next.inputs);
    std::atomic_store_explicit(skin?&skinCompleted_:&completed_,std::shared_ptr<const CompletedSurface>(std::move(result)),std::memory_order_release);
   }
  }catch(const std::exception& e){std::lock_guard<std::mutex> lock(mutex_);error_=e.what();failed_.store(true,std::memory_order_release);}
 }
 public:
 SurfaceService(std::wstring worker,std::filesystem::path bindings,std::string revision,std::optional<surface::Controls> startup=std::nullopt,bool modular=false){
#ifdef MALEMOD_COMPACT_MECHANICS
  split_=modular;
#endif
  preparing_=split_?2:1;
  try{
   thread_=std::thread([=]{Run(worker,bindings,revision,startup,modular,false);});
   if(split_)skinThread_=std::thread([=]{Run(worker,bindings,revision,startup,modular,true);});
  }catch(...){
   {std::lock_guard<std::mutex> lock(mutex_);stopping_=true;}changed_.notify_all();
   if(thread_.joinable())thread_.join();throw;
  }
 }
 ~SurfaceService(){ {std::lock_guard<std::mutex> lock(mutex_);stopping_=true;}changed_.notify_all();if(thread_.joinable())thread_.join();if(skinThread_.joinable())skinThread_.join(); }
 SurfaceService(const SurfaceService&)=delete;SurfaceService& operator=(const SurfaceService&)=delete;
 Submission Submit(const surface::wire::Request& request,std::uint64_t& acceptedSequence){
  return SubmitBatch({request},acceptedSequence);
 }
 Submission SubmitBatch(const std::vector<surface::wire::Request>& requests,std::uint64_t& acceptedSequence){
  acceptedSequence=0;
  if(requests.empty()||requests.size()>32)return Submission::Invalid;
  try{for(const auto& request:requests){surface::wire::Validate(request.controls);surface::wire::Validate(request.frame);if(request.reset)return Submission::Invalid;}}catch(const std::exception&){return Submission::Invalid;}
  // Resetting the process-global source requires a replacement service/worker.
  if(preparing_.load(std::memory_order_acquire))return failed_?Submission::Stopped:Submission::Loading;
  std::unique_lock<std::mutex> lock(mutex_,std::try_to_lock);
  if(!lock.owns_lock())return Submission::Busy;
  if(stopping_||failed_.load(std::memory_order_acquire))return Submission::Stopped;
  if(size_==capacity||(split_&&skinSize_==skinCapacity))return Submission::Full;
  // Allocate both copies before publishing either queue entry: rejection or
  // allocation failure must never advance just one replay.
  Pending numerical{sequence_+1,requests},skin;
  if(split_)skin={sequence_+1,requests};
  acceptedSequence=++sequence_;queue_[(first_+size_)%capacity]=std::move(numerical);++size_;
  if(split_){skinQueue_[(skinFirst_+skinSize_)%skinCapacity]=std::move(skin);++skinSize_;}
  changed_.notify_all();return Submission::Accepted;
 }
 // A rejected submission remains the caller's responsibility. Full/Busy must
 // be handled visibly by the eventual engine lifecycle, never silently ignored.
 std::shared_ptr<const CompletedSurface> Latest()const{return std::atomic_load_explicit(&completed_,std::memory_order_acquire);}
 std::shared_ptr<const CompletedSurface> LatestSkin()const{return split_?std::atomic_load_explicit(&skinCompleted_,std::memory_order_acquire):Latest();}
 bool Failed()const{return failed_.load(std::memory_order_acquire);}
 std::string Error(){std::lock_guard<std::mutex> lock(mutex_);return error_;}
};
}
