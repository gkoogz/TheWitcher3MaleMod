#define NOMINMAX
#include "control_store.hpp"
#include <iostream>
using namespace malemod::witcher;
int main(){try{
 const auto path=std::filesystem::temp_directory_path()/("MaleMod-controls-test-"+std::to_string(GetCurrentProcessId())+".bin");
 if(std::filesystem::exists(path))throw std::runtime_error("Preserve existing test file");
 ControlStore store(path);if(store.Load())throw std::runtime_error("Missing file did not retain defaults");
 malemod::surface::Controls c;c.values[0]=1;for(unsigned i=1;i<18;i++)c.values[i]=float(i*5);
 store.Save(c);if(!store.Load()||store.Load()->values!=c.values)throw std::runtime_error("Control round trip differs");
 auto bad=c;bad.values[1]=101;bool rejected=false;try{store.Save(bad);}catch(const std::invalid_argument&){rejected=true;}
 if(!rejected||store.Load()->values!=c.values)throw std::runtime_error("Rejected edit replaced valid preferences");
 {std::ofstream f(path,std::ios::binary|std::ios::trunc);f<<"unknown";}
 rejected=false;try{store.Load();}catch(const std::runtime_error&){rejected=true;}
 if(!rejected)throw std::runtime_error("Malformed saved preferences accepted");
 std::filesystem::remove(path);std::cout<<"PASS: atomic 18-control persistence; rejected edits preserve data; malformed versions rejected\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
