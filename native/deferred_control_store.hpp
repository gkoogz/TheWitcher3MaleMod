#pragma once
#include "control_store.hpp"
#include <chrono>
#include <condition_variable>
#include <mutex>
#include <thread>

namespace malemod::witcher {
// Persistence is not part of the input critical section. Match the source
// adapter's 700 ms quiet period; keep only the most recent validated values.
class DeferredControlStore {
 ControlStore store_;
 std::mutex mutex_;std::condition_variable changed_;
 std::optional<surface::Controls> pending_;
 std::chrono::steady_clock::time_point due_;
 bool stop_=false;std::thread worker_;
public:
 explicit DeferredControlStore(std::filesystem::path path):store_(std::move(path)),worker_([this]{
  std::unique_lock<std::mutex> lock(mutex_);
  for(;;){
   changed_.wait(lock,[&]{return stop_||pending_.has_value();});
   if(stop_&&!pending_)return;
   const auto deadline=due_;
   if(!stop_&&changed_.wait_until(lock,deadline,[&]{return stop_||due_!=deadline;})&&!stop_)continue;
   if(!stop_&&std::chrono::steady_clock::now()<due_)continue;
   auto value=*pending_;pending_.reset();lock.unlock();
   try{store_.Save(value);}catch(const std::exception&){OutputDebugStringW(L"MaleMod: deferred control persistence failed\n");}
   lock.lock();
  }
 }){}
 ~DeferredControlStore(){{std::lock_guard<std::mutex> lock(mutex_);stop_=true;}changed_.notify_one();worker_.join();}
 std::optional<surface::Controls> Load()const{return store_.Load();}
 void Save(const surface::Controls& value){
  surface::wire::Validate(value);
  {std::lock_guard<std::mutex> lock(mutex_);pending_=value;due_=std::chrono::steady_clock::now()+std::chrono::milliseconds(700);}
  changed_.notify_one();
 }
};
}
