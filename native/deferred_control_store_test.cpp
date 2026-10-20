#define NOMINMAX
#include "deferred_control_store.hpp"
#include <iostream>
int main(int argc,char** argv){try{
 if(argc!=2)throw std::invalid_argument("Expected an owned output directory");
 const auto path=std::filesystem::path(argv[1])/("controls-test-"+std::to_string(GetCurrentProcessId())+".bin");
 if(std::filesystem::exists(path))throw std::runtime_error("Preserve existing test output");
 malemod::surface::Controls expected;
 {
  malemod::witcher::DeferredControlStore store(path);
  for(unsigned i=1;i<=100;i++){expected.values[3]=float(i);store.Save(expected);}
  // No synchronous durable write is permitted in the input loop.
  if(std::filesystem::exists(path))throw std::runtime_error("Slider input performed synchronous file I/O");
  auto invalid=expected;invalid.values[3]=101;bool rejected=false;
  try{store.Save(invalid);}catch(const std::invalid_argument&){rejected=true;}
  if(!rejected)throw std::runtime_error("Invalid pending preference accepted");
 } // Controlled destruction must flush the last edit, including early shutdown.
 malemod::witcher::ControlStore persisted(path);
 if(!persisted.Load()||persisted.Load()->values!=expected.values)throw std::runtime_error("Final coalesced preference was lost");
 std::filesystem::remove(path);
 std::cout<<"PASS: 100 edits deferred, final value flushed, invalid edit preserved prior request\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
