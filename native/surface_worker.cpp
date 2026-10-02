#include "surface_transport.hpp"
#include <memory>
#include <cstdio>
#include <chrono>
using namespace malemod;
int wmain(int argc,wchar_t** argv){
 if(argc!=4||std::wstring(argv[1])!=L"--worker")return 2;
 try{
  const auto parentID=wcstoul(argv[3],nullptr,10);if(!parentID||parentID==GetCurrentProcessId())return 3;
  witcher::Handle parent(OpenProcess(SYNCHRONIZE,FALSE,parentID));witcher::Require(parent.value!=nullptr,"Open parent lifetime");
  witcher::Channel channel(argv[2],false);std::unique_ptr<surface::Session> session;surface::Controls previous;
  std::uint32_t lastSequence=0;
  for(;;){
   HANDLE waits[2]={channel.request.value,parent.value};auto result=WaitForMultipleObjects(2,waits,FALSE,INFINITE);
   if(result!=WAIT_OBJECT_0)return result==WAIT_OBJECT_0+1?0:4;
   std::atomic_thread_fence(std::memory_order_acquire);auto& p=*channel.packet;
   bool quit=false;
   try{
    if(p.magic!=witcher::packetMagic||p.version!=surface::wire::version||p.sequence!=lastSequence+1||p.length>surface::wire::maximumBytes)throw std::invalid_argument("Invalid surface request identity");
    lastSequence=p.sequence;
    if(p.operation==2){if(p.length)throw std::invalid_argument("Unexpected shutdown payload");p.length=0;p.status=1;quit=true;}
    else if(p.operation==1){
     surface::wire::Bytes input(p.payload,p.payload+p.length);auto q=surface::wire::DecodeRequest(input);
     if(q.reset&&session)throw std::invalid_argument("Reset requires a new isolated worker process");
     if(!session){session=std::make_unique<surface::Session>(q.controls);previous=q.controls;}
     else if(previous.values!=q.controls.values){session->SetControls(q.controls);previous=q.controls;}
     auto start=std::chrono::steady_clock::now();session->Step(q.frame);auto stepped=std::chrono::steady_clock::now();
     auto state=session->Read();auto captured=std::chrono::steady_clock::now();auto output=surface::wire::Encode(state);auto encoded=std::chrono::steady_clock::now();
     p.stepMs=std::chrono::duration<float,std::milli>(stepped-start).count();p.readMs=std::chrono::duration<float,std::milli>(captured-stepped).count();p.encodeMs=std::chrono::duration<float,std::milli>(encoded-captured).count();
     auto diagnostics=session->ReadDiagnostics();for(unsigned i=0;i<16;i++)p.geometryMs[i]=float(diagnostics.geometryMilliseconds[i]);
     std::memcpy(p.payload,output.data(),output.size());p.length=std::uint32_t(output.size());p.status=1;
    }else throw std::invalid_argument("Unknown surface operation");
   }catch(const std::exception& e){auto message=std::string(e.what());if(message.size()>4096)message.resize(4096);std::memcpy(p.payload,message.data(),message.size());p.length=std::uint32_t(message.size());p.status=2;}
   std::atomic_thread_fence(std::memory_order_release);if(!SetEvent(channel.reply.value))return 5;if(quit)return 0;
  }
 }catch(const std::exception& e){std::fprintf(stderr,"%s\n",e.what());return 6;}
}
