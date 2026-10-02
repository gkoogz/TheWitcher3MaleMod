#include "surface_transport.hpp"
#include <fstream>
#include <chrono>
#include <algorithm>
#include <cstdio>
using namespace malemod;
int wmain(int argc,wchar_t** argv){
 if(argc!=4)return 2;
 try{
  std::ifstream prefs(argv[2]);surface::wire::Request q;
  const unsigned order[18]={0,1,2,3,5,7,8,9,4,6,10,11,12,13,14,15,16,17};
  for(unsigned i:order)if(!(prefs>>q.controls.values[i]))throw std::runtime_error("Incomplete controls");
  witcher::SurfaceClient client(argv[1]);surface::Output output;std::vector<double> timings;
  for(int i=0;i<120;i++){
   auto start=std::chrono::steady_clock::now();output=client.Evaluate(q,10000);
   timings.push_back(std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count());
  }
  auto bytes=surface::wire::Encode(output);std::ofstream file(argv[3],std::ios::binary);file.write(reinterpret_cast<const char*>(bytes.data()),bytes.size());if(!file)throw std::runtime_error("Cannot write replay");
  auto workerTimings=client.LastWorkerTimings();std::printf("{\"lastStepMs\":%.5f,\"lastReadMs\":%.5f,\"lastEncodeMs\":%.5f}\n",workerTimings[0],workerTimings[1],workerTimings[2]);
  auto geometry=client.LastGeometryTimings();std::printf("{\"geometryMs\":[");for(unsigned i=0;i<16;i++)std::printf("%s%.5f",i?",":"",geometry[i]);std::puts("]}");
  std::sort(timings.begin()+1,timings.end());
  std::printf("{\"frames\":120,\"vertices\":%zu,\"bytes\":%zu,\"startupMs\":%.5f,\"medianMs\":%.5f,\"p95Ms\":%.5f,\"maximumMs\":%.5f}\n",output.anatomy.positions.size(),bytes.size(),timings[0],timings[60],timings[114],timings[119]);
 }catch(const std::exception& e){std::fprintf(stderr,"%s\n",e.what());return 1;}
}
