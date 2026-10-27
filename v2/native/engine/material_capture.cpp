// Explicit, sealed material-channel observer. It never changes shader inputs.
#define NOMINMAX
#include <windows.h>
#include <d3d12.h>
#include <d3d12sdklayers.h>
#include <dxgi1_4.h>
#include <wrl/client.h>
#include <array>
#include <algorithm>
#include <atomic>
#include <condition_variable>
#include <fstream>
#include <iomanip>
#include <map>
#include <memory>
#include <mutex>
#include <sstream>
#include <string>
#include <stdexcept>
#include <thread>
#include <set>
#include <tuple>
#include <vector>
#include "material_capture.hpp"

namespace malemod::witcher {
namespace {
using Microsoft::WRL::ComPtr;
constexpr UINT64 pinLimit=512ull*1024*1024,readbackLimit=128ull*1024*1024;
struct View {ComPtr<ID3D12Resource> resource;D3D12_RESOURCE_DESC resourceDesc{};D3D12_RENDER_TARGET_VIEW_DESC viewDesc{};UINT64 bytes=0;std::uint64_t touched=0;std::uintptr_t identity=0;std::string name;};
// Borrowed interface pointers are never dereferenced from this registry.
// They are pinned only at an actually observed owned draw using its exact OM
// snapshot, where the D3D12 application contract requires those resources alive
// through GPU completion. Create/Copy descriptor overwrites revoke provenance.
struct BorrowedView {ID3D12Resource* resource=nullptr;D3D12_RESOURCE_DESC resourceDesc{};D3D12_RENDER_TARGET_VIEW_DESC viewDesc{};UINT64 bytes=0;unsigned stride=0;std::string name;};
struct Target {std::shared_ptr<View> view;ComPtr<ID3D12Resource> readback;D3D12_PLACED_SUBRESOURCE_FOOTPRINT footprint{};UINT rows=0;UINT64 rowBytes=0,bytes=0;};
struct Capture {MaterialCaptureDraw draw;unsigned stage=0;std::uint64_t armSequence=0;std::array<Target,5> targets;std::vector<unsigned char> shader;ComPtr<ID3D12Fence> fence;UINT64 fenceValue=0;std::uintptr_t queueAddress=0;bool submitted=false,signalFailed=false;std::string stem;};
struct Queue {ComPtr<ID3D12CommandQueue> queue;ComPtr<ID3D12Fence> fence;UINT64 next=0;};
struct DescriptorInfo {UINT64 width=0;unsigned height=0,resourceFormat=0,viewFormat=0,dimension=0,samples=0,flags=0;std::uint64_t touched=0;std::string name;};
struct Counters {std::uint64_t rtvSeen=0,rtvSizeMatch=0,rtvEligible=0,rtvRecorded=0,rtvRetained=0,rtvBudgetRejected=0,budgetEvictions=0,descriptorCopies=0,knownCopied=0,swapchainExcluded=0,omSeen=0,omFive=0,omKnown=0,omMissing=0,ownedDraws=0,listMissing=0,nonDirect=0,pairMismatch=0;};
struct DeviceWatch {ComPtr<ID3D12Device> device;ComPtr<ID3D12InfoQueue1> info;DWORD cookie=0;bool registered=false,reported=false;};
struct State {
 std::atomic<bool> enabled{false},pending{false};std::atomic<unsigned> written{0};
 std::mutex mutex,eventMutex;std::condition_variable wake;std::thread worker;bool stopping=false,armed=false,done=false;
 std::filesystem::path directory;std::string requestId;unsigned stage=0,width=0,height=0,epoch=0,mask=0,attempts=0;std::uint64_t minSequence=0,pairSequence=0,pairPresentation=0,pairPresent=0;UINT64 pinned=0;
 std::map<SIZE_T,BorrowedView> descriptors;std::vector<std::weak_ptr<View>> trackedViews;
 Counters counters;std::uint64_t clock=0;unsigned rtvStride=0,missingLogged=0,namesLogged=0;std::map<SIZE_T,DescriptorInfo> descriptorInfo;
 std::set<std::tuple<UINT64,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned>> rtvPatterns;std::set<unsigned> omCounts;
 std::map<void*,std::array<BorrowedView,5>> lists;
 std::map<void*,std::vector<std::shared_ptr<Capture>>> recordings;
 std::map<void*,Queue> queues;std::vector<std::shared_ptr<Capture>> captures;
 bool debugRequested=false;std::atomic<bool> debugConfigured{false};std::atomic<unsigned> debugMessages{0},debugErrors{0};std::vector<DeviceWatch> devices;
};
State& S(){static auto* value=new State;return *value;}
void Event(const std::string&,const std::string&);
std::string Quoted(const char*,std::size_t);
std::set<ID3D12Resource*> RefreshPins(State& s){
 std::set<ID3D12Resource*> resources;s.pinned=0;
 for(auto i=s.trackedViews.begin();i!=s.trackedViews.end();)if(auto view=i->lock()){if(view->resource&&resources.insert(view->resource.Get()).second)s.pinned+=view->bytes;++i;}else i=s.trackedViews.erase(i);
 return resources;
}
void HR(HRESULT value){if(FAILED(value))throw std::runtime_error("D3D12 material capture call failed");}
bool Sealed(std::string& name){
 wchar_t expected[256]{},actual[256]{};DWORD bytes=0;USEROBJECTFLAGS flags{};auto station=GetProcessWindowStation();
 auto count=GetEnvironmentVariableW(L"MALEMOD_SEALED_SESSION",expected,256);
 if(!count||count>=256||!GetUserObjectInformationW(station,UOI_NAME,actual,sizeof(actual),&bytes)||!GetUserObjectInformationW(station,UOI_FLAGS,&flags,sizeof(flags),&bytes)||(flags.dwFlags&WSF_VISIBLE)||!_wcsicmp(actual,L"WinSta0")||_wcsicmp(actual,expected))return false;
 name.clear();for(auto* p=actual;*p;++p){if(*p>127)return false;name.push_back(char(*p));}return true;
}
bool Identifier(const std::string& value){return !value.empty()&&value.size()<=64&&value.find_first_not_of("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")==std::string::npos;}
void Event(const std::string& what,const std::string& details={}){auto& s=S();std::lock_guard<std::mutex> lock(s.eventMutex);std::ofstream f(s.directory/"material-capture-events.jsonl",std::ios::app);f<<"{\"event\":\""<<what<<"\",\"pid\":"<<GetCurrentProcessId();if(!details.empty())f<<','<<details;f<<"}\n";}
std::string Quoted(const char* text,std::size_t limit=4096){std::ostringstream value;value<<'"';if(text)for(std::size_t i=0;i<limit&&text[i];++i){auto ch=static_cast<unsigned char>(text[i]);if(ch=='"'||ch=='\\')value<<'\\'<<char(ch);else if(ch<32||ch>=127)value<<"\\u00"<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(ch)<<std::dec;else value<<char(ch);}value<<'"';return value.str();}
std::string ObjectName(ID3D12Object* object){wchar_t wide[256]{};UINT bytes=sizeof(wide)-sizeof(wchar_t);if(SUCCEEDED(object->GetPrivateData(WKPDID_D3DDebugObjectNameW,&bytes,wide))){std::string name;for(unsigned i=0;i<bytes/sizeof(wchar_t)&&wide[i];++i)name.push_back(wide[i]<128?char(wide[i]):'?');return name;}char text[256]{};bytes=sizeof(text)-1;if(SUCCEEDED(object->GetPrivateData(WKPDID_D3DDebugObjectName,&bytes,text)))return std::string(text,text+std::min<UINT>(bytes,255));return {};}
// Metadata on the exact GetBuffer object has the object's own lifetime. This
// does not retain it and cannot become a stale pointer blacklist after reuse.
const GUID backbufferTag{0x7792bc61,0xc693,0x4598,{0x9e,0xcd,0x72,0xd8,0xe3,0x3b,0x9c,0x54}};
constexpr UINT backbufferValue=0x4d4d4242;
bool Backbuffer(ID3D12Resource* resource){UINT value=0,bytes=sizeof(value);return resource&&SUCCEEDED(resource->GetPrivateData(backbufferTag,&bytes,&value))&&bytes==sizeof(value)&&value==backbufferValue;}
void CALLBACK DebugMessage(D3D12_MESSAGE_CATEGORY category,D3D12_MESSAGE_SEVERITY severity,D3D12_MESSAGE_ID id,LPCSTR description,void*)noexcept{try{
 auto& s=S();if(!s.enabled.load())return;if(severity<=D3D12_MESSAGE_SEVERITY_ERROR){if(s.debugErrors.fetch_add(1)>=128)return;}else if(s.debugMessages.fetch_add(1)>=256)return;std::ostringstream j;j<<"\"category\":"<<unsigned(category)<<",\"severity\":"<<unsigned(severity)<<",\"messageID\":"<<unsigned(id)<<",\"description\":"<<Quoted(description);
 if(severity<=D3D12_MESSAGE_SEVERITY_ERROR){void* frames[24]{};auto count=CaptureStackBackTrace(0,24,frames,nullptr);j<<",\"stack\":[";for(unsigned i=0;i<count;i++)j<<(i?",":"")<<'"'<<frames[i]<<'"';j<<']';}Event("d3d12-validation",j.str());
}catch(...){}}
void CheckDevicesLocked(State& s){
 if(!s.debugRequested)return;for(auto& watch:s.devices){if(watch.reported)continue;const auto reason=watch.device->GetDeviceRemovedReason();if(SUCCEEDED(reason))continue;watch.reported=true;std::ostringstream j;j<<"\"reason\":\"0x"<<std::hex<<unsigned(reason)<<std::dec<<"\",\"device\":\""<<watch.device.Get()<<"\"";
  ComPtr<ID3D12DeviceRemovedExtendedData1> dred;auto query=watch.device.As(&dred);j<<",\"dredQueryHRESULT\":\"0x"<<std::hex<<unsigned(query)<<std::dec<<'"';
  if(SUCCEEDED(query)){D3D12_DRED_AUTO_BREADCRUMBS_OUTPUT1 output{};auto result=dred->GetAutoBreadcrumbsOutput1(&output);j<<",\"breadcrumbsHRESULT\":\"0x"<<std::hex<<unsigned(result)<<std::dec<<"\",\"breadcrumbs\":[";unsigned nodes=0;
   if(SUCCEEDED(result))for(auto* node=output.pHeadAutoBreadcrumbNode;node&&nodes<128;node=node->pNext,++nodes){const auto last=node->pLastBreadcrumbValue?*node->pLastBreadcrumbValue:0;const auto begin=last>8?last-8:0;const auto end=std::min<UINT>(node->BreadcrumbCount,last+8);j<<(nodes?",":"")<<"{\"list\":\""<<node->pCommandList<<"\",\"queue\":\""<<node->pCommandQueue<<"\",\"listName\":"<<Quoted(node->pCommandListDebugNameA,256)<<",\"queueName\":"<<Quoted(node->pCommandQueueDebugNameA,256)<<",\"count\":"<<node->BreadcrumbCount<<",\"last\":"<<last<<",\"historyFirst\":"<<begin<<",\"history\":[";if(node->pCommandHistory)for(UINT i=begin;i<end;i++)j<<(i==begin?"":",")<<unsigned(node->pCommandHistory[i]);j<<"]}";}
   j<<']';D3D12_DRED_PAGE_FAULT_OUTPUT1 fault{};result=dred->GetPageFaultAllocationOutput1(&fault);j<<",\"pageFaultHRESULT\":\"0x"<<std::hex<<unsigned(result)<<std::dec<<'"';
   if(SUCCEEDED(result)){j<<",\"pageFaultVA\":\"0x"<<std::hex<<fault.PageFaultVA<<std::dec<<"\"";const auto allocations=[&](const char* label,const D3D12_DRED_ALLOCATION_NODE1* head){j<<",\""<<label<<"\":[";unsigned count=0;for(auto* n=head;n&&count<64;n=n->pNext,++count)j<<(count?",":"")<<"{\"name\":"<<Quoted(n->ObjectNameA,256)<<",\"type\":"<<unsigned(n->AllocationType)<<",\"object\":\""<<n->pObject<<"\"}";j<<']';};allocations("existingAllocations",fault.pHeadExistingAllocationNode);allocations("recentFreedAllocations",fault.pHeadRecentFreedAllocationNode);}
  }Event("device-removed-dred",j.str());
 }
}
void Snapshot(const char* reason){auto& s=S();RefreshPins(s);const auto& c=s.counters;std::ostringstream j;j<<"\"reason\":\""<<reason<<"\",\"rtvSeen\":"<<c.rtvSeen<<",\"rtvSizeMatch\":"<<c.rtvSizeMatch<<",\"rtvEligible\":"<<c.rtvEligible<<",\"rtvRecorded\":"<<c.rtvRecorded<<",\"descriptorCopies\":"<<c.descriptorCopies<<",\"knownCopied\":"<<c.knownCopied<<",\"swapchainExcluded\":"<<c.swapchainExcluded<<",\"rtvRetained\":"<<c.rtvRetained<<",\"rtvBudgetRejected\":"<<c.rtvBudgetRejected<<",\"budgetEvictions\":"<<c.budgetEvictions<<",\"omSeen\":"<<c.omSeen<<",\"omFive\":"<<c.omFive<<",\"omKnown\":"<<c.omKnown<<",\"omMissing\":"<<c.omMissing<<",\"ownedDraws\":"<<c.ownedDraws<<",\"listMissing\":"<<c.listMissing<<",\"nonDirect\":"<<c.nonDirect<<",\"pairMismatch\":"<<c.pairMismatch<<",\"retainedViews\":"<<s.trackedViews.size()<<",\"knownDescriptors\":"<<s.descriptors.size()<<",\"boundLists\":"<<s.lists.size()<<",\"pinnedBytes\":"<<s.pinned<<",\"rtvStride\":"<<s.rtvStride;Event("observer-counters",j.str());}
void Write(const Capture& c){
 auto& s=S();std::ostringstream json;json<<"{\n\"schema\":\"malemod.native-material-capture/1\",\n\"request\":\""<<s.requestId<<"\",\n\"pid\":"<<GetCurrentProcessId()<<",\n\"checkpoint\":"<<c.stage<<",\n\"armSequence\":"<<c.armSequence<<",\n\"requestedPublishedSequence\":"<<c.armSequence<<",\n\"epoch\":"<<c.draw.epoch<<",\n\"sequence\":"<<c.draw.sequence<<",\n\"presentationSerial\":"<<c.draw.presentationSerial<<",\n\"nativePresentSerial\":"<<c.draw.nativePresentSerial<<",\n\"drawSerial\":"<<c.draw.drawSerial<<",\n\"resource\":"<<c.draw.resource<<",\n\"lod\":"<<c.draw.lod<<",\n\"section\":"<<c.draw.section<<",\n\"material\":"<<c.draw.material<<",\n\"indexFirst\":"<<c.draw.indexFirst<<",\n\"indexCount\":"<<c.draw.indexCount<<",\n\"depthFunc\":"<<c.draw.depthFunc<<",\n\"depthWrite\":"<<c.draw.depthWrite<<",\n\"cullMode\":"<<c.draw.cullMode<<",\n\"frontCounterClockwise\":"<<c.draw.frontCounterClockwise<<",\n\"queueFence\":"<<c.fenceValue<<",\n\"queueAddress\":\""<<std::hex<<c.queueAddress<<std::dec<<"\",\n\"completeFrame\":false,\n\"scope\":\"Five active native color targets immediately after this owned material draw. Other regions may be incomplete or from earlier draws; compare the owned visible regions only. Rows retain native copy padding.\",\n\"pixelShader\":\""<<c.stem<<".ps\",\n\"targets\":[\n";
 {std::ofstream f(s.directory/(c.stem+".ps"),std::ios::binary);f.write(reinterpret_cast<const char*>(c.shader.data()),std::streamsize(c.shader.size()));if(!f)throw std::runtime_error("Cannot write captured pixel shader");}
 for(unsigned i=0;i<5;i++){
  const auto& t=c.targets[i];const auto filename=c.stem+"-rt"+std::to_string(i)+".bin";void* mapped=nullptr;D3D12_RANGE read{0,SIZE_T(t.bytes)};HR(t.readback->Map(0,&read,&mapped));
  {std::ofstream f(s.directory/filename,std::ios::binary);f.write(static_cast<const char*>(mapped),std::streamsize(t.bytes));D3D12_RANGE noWrite{0,0};t.readback->Unmap(0,&noWrite);if(!f)throw std::runtime_error("Cannot write material target");}
  const auto& d=t.view->resourceDesc;const auto& v=t.view->viewDesc;json<<(i?",\n":"")<<"{\"slot\":"<<i<<",\"file\":\""<<filename<<"\",\"resourceFormat\":"<<unsigned(d.Format)<<",\"viewFormat\":"<<unsigned(v.Format)<<",\"resourceIdentity\":\"0x"<<std::hex<<t.view->identity<<std::dec<<"\",\"name\":"<<Quoted(t.view->name.c_str(),256)<<",\"copyFormat\":"<<unsigned(t.footprint.Footprint.Format)<<",\"width\":"<<d.Width<<",\"height\":"<<d.Height<<",\"sampleCount\":"<<d.SampleDesc.Count<<",\"sampleQuality\":"<<d.SampleDesc.Quality<<",\"mipLevels\":"<<d.MipLevels<<",\"rowPitch\":"<<t.footprint.Footprint.RowPitch<<",\"rowBytes\":"<<t.rowBytes<<",\"rows\":"<<t.rows<<",\"offset\":"<<t.footprint.Offset<<",\"bytes\":"<<t.bytes<<",\"subresource\":0,\"beforeState\":4,\"restoredState\":4}";
 }
 json<<"\n]}\n";std::ofstream f(s.directory/(c.stem+".json"));f<<json.str();if(!f)throw std::runtime_error("Cannot write capture metadata");s.written.fetch_add(1);
}
void Worker(){
 auto& s=S();for(;;){std::vector<std::shared_ptr<Capture>> ready;bool stop=false;
  {std::unique_lock<std::mutex> lock(s.mutex);s.wake.wait_for(lock,std::chrono::milliseconds(50));stop=s.stopping;
   try{CheckDevicesLocked(s);}catch(...){Event("dred-query-failed");}for(auto i=s.captures.begin();i!=s.captures.end();){auto& c=*i;if(c->submitted&&!c->signalFailed&&c->fence){auto value=c->fence->GetCompletedValue();if(value==UINT64_MAX){try{CheckDevicesLocked(s);}catch(...){Event("dred-query-failed");}Event("device-removed");i=s.captures.erase(i);continue;}if(value>=c->fenceValue){for(auto& target:c->targets)target.view->resource.Reset();ready.push_back(c);i=s.captures.erase(i);continue;}}++i;}
  }
  for(const auto& c:ready)try{Write(*c);}catch(...){Event("write-failed");}
  if(stop)return;
 }
}
}
void InitializeMaterialCapture(const std::filesystem::path& directory)noexcept{try{
 auto& s=S();if(s.enabled.load())return;std::string station;if(!Sealed(station))return;
 const auto marker=directory/"material-capture.request";std::error_code ec;auto size=std::filesystem::file_size(marker,ec);if(ec||size>512)return;
 std::ifstream input(marker);std::string magic,expected,id;unsigned stage=0,width=0,height=0;input>>magic>>expected>>id>>stage>>width>>height;input>>std::ws;
 if(!input.eof()||(magic!="MMGB1"&&magic!="MMGBD1")||expected!=station||!Identifier(id)||stage>=1000||width<256||height<256||width>4096||height>2160)return;
 std::lock_guard<std::mutex> lock(s.mutex);s.directory=directory;s.requestId=id;s.stage=stage;s.width=width;s.height=height;s.stopping=false;s.done=false;s.debugRequested=magic=="MMGBD1";s.enabled=true;s.worker=std::thread(Worker);Event("explicit-sealed-request-enabled",std::string("\"debugRequested\":")+(s.debugRequested?"true":"false"));
}catch(...){}}
bool MaterialCaptureEnabled()noexcept{return S().enabled.load();}
bool MaterialCapturePendingDraw()noexcept{return S().pending.load();}
void MaterialCaptureBeforeDevice(void* pointer)noexcept{try{
 auto& s=S();if(!s.enabled.load()||!s.debugRequested||s.debugConfigured.exchange(true))return;
 const auto get=[&](REFCLSID clsid,REFIID iid,void** output)->HRESULT{
  if(pointer)return static_cast<ID3D12DeviceFactory*>(pointer)->GetConfigurationInterface(clsid,iid,output);
  auto library=GetModuleHandleW(L"d3d12.dll");if(!library)return E_NOINTERFACE;auto function=reinterpret_cast<decltype(&D3D12GetDebugInterface)>(GetProcAddress(library,"D3D12GetDebugInterface"));return function?function(iid,output):E_NOINTERFACE;
 };
 ComPtr<ID3D12DeviceRemovedExtendedDataSettings1> dred;auto dredResult=get(CLSID_D3D12DeviceRemovedExtendedData,IID_PPV_ARGS(&dred));if(SUCCEEDED(dredResult)){dred->SetAutoBreadcrumbsEnablement(D3D12_DRED_ENABLEMENT_FORCED_ON);dred->SetPageFaultEnablement(D3D12_DRED_ENABLEMENT_FORCED_ON);dred->SetBreadcrumbContextEnablement(D3D12_DRED_ENABLEMENT_FORCED_ON);}
 ComPtr<ID3D12Debug> debug;auto debugResult=get(CLSID_D3D12Debug,IID_PPV_ARGS(&debug));if(SUCCEEDED(debugResult))debug->EnableDebugLayer();std::ostringstream j;j<<"\"path\":\""<<(pointer?"ID3D12DeviceFactory.GetConfigurationInterface":"D3D12GetDebugInterface")<<"\",\"debugHRESULT\":\"0x"<<std::hex<<unsigned(debugResult)<<"\",\"dredHRESULT\":\"0x"<<unsigned(dredResult)<<"\"";Event("debug-before-first-device",j.str());
}catch(...){try{Event("debug-configuration-failed");}catch(...){}}}
void MaterialCaptureDevice(void* pointer)noexcept{try{
 auto& s=S();if(!s.enabled.load()||!s.debugRequested||!pointer)return;std::lock_guard<std::mutex> lock(s.mutex);auto* device=static_cast<ID3D12Device*>(pointer);for(const auto& watch:s.devices)if(watch.device.Get()==device)return;if(s.devices.size()>=4)return;
 DeviceWatch watch;watch.device=device;auto query=device->QueryInterface(IID_PPV_ARGS(&watch.info));HRESULT registration=E_NOINTERFACE;if(SUCCEEDED(query)){registration=watch.info->RegisterMessageCallback(DebugMessage,D3D12_MESSAGE_CALLBACK_FLAG_NONE,nullptr,&watch.cookie);watch.registered=SUCCEEDED(registration);}s.devices.push_back(std::move(watch));std::ostringstream j;j<<"\"device\":\""<<device<<"\",\"infoQueryHRESULT\":\"0x"<<std::hex<<unsigned(query)<<"\",\"registerHRESULT\":\"0x"<<unsigned(registration)<<"\"";Event("native-validation-device",j.str());
}catch(...){try{Event("validation-device-failed");}catch(...){}}}
void GraphicsMaterialCaptureCheckpoint(unsigned stage,unsigned epoch,std::uint64_t sequence)noexcept{try{
 auto& s=S();if(!s.enabled.load()||!epoch||!sequence)return;std::lock_guard<std::mutex> lock(s.mutex);if(stage!=s.stage||s.armed||s.done)return;s.armed=true;s.epoch=epoch;s.minSequence=sequence;s.pending=true;Event("checkpoint-armed");Snapshot("armed");
}catch(...){}}
void MaterialCaptureSwapChain(void* pointer)noexcept{try{
 auto& s=S();if(!s.enabled.load()||!pointer)return;auto* chain=static_cast<IDXGISwapChain*>(pointer);DXGI_SWAP_CHAIN_DESC desc{};auto result=chain->GetDesc(&desc);if(FAILED(result)||!desc.BufferCount||desc.BufferCount>16)return;
 // Every GetBuffer reference is temporary and leaves scope before the caller
 // forwards ResizeBuffers. No persistent chain or backbuffer ComPtr is stored.
 std::vector<ComPtr<ID3D12Resource>> buffers;std::set<ID3D12Resource*> identities;
 for(unsigned i=0;i<desc.BufferCount;i++){ComPtr<ID3D12Resource> buffer;if(FAILED(chain->GetBuffer(i,IID_PPV_ARGS(&buffer))))continue;const UINT value=backbufferValue;if(FAILED(buffer->SetPrivateData(backbufferTag,sizeof(value),&value))){std::lock_guard<std::mutex> lock(s.mutex);s.done=true;s.pending=false;Event("swapchain-tag-failed");return;}identities.insert(buffer.Get());buffers.push_back(std::move(buffer));}
 std::lock_guard<std::mutex> lock(s.mutex);unsigned revoked=0;
 for(auto i=s.descriptors.begin();i!=s.descriptors.end();)if(identities.count(i->second.resource)){i=s.descriptors.erase(i);++revoked;}else ++i;
 for(auto i=s.lists.begin();i!=s.lists.end();)if(std::any_of(i->second.begin(),i->second.end(),[&](const auto& view){return identities.count(view.resource)!=0;}))i=s.lists.erase(i);else ++i;
 std::set<ID3D12Resource*> unsafe;const auto inspect=[&](const std::shared_ptr<Capture>& capture){const auto completed=capture->submitted&&!capture->signalFailed&&capture->fence?capture->fence->GetCompletedValue():0;const bool safe=capture->submitted&&!capture->signalFailed&&capture->fence&&completed!=UINT64_MAX&&completed>=capture->fenceValue;if(!safe)for(const auto& target:capture->targets)if(target.view->resource&&Backbuffer(target.view->resource.Get()))unsafe.insert(target.view->resource.Get());};
 for(const auto& capture:s.captures)inspect(capture);for(const auto& record:s.recordings)for(const auto& capture:record.second)inspect(capture);
 unsigned released=0;for(auto& weak:s.trackedViews)if(auto view=weak.lock())if(view->resource&&Backbuffer(view->resource.Get())&&!unsafe.count(view->resource.Get())){view->resource.Reset();++released;}RefreshPins(s);
 std::ostringstream j;j<<"\"chain\":\""<<chain<<"\",\"format\":"<<unsigned(desc.BufferDesc.Format)<<",\"buffers\":"<<desc.BufferCount<<",\"observedObjects\":"<<buffers.size()<<",\"revokedDescriptors\":"<<revoked<<",\"releasedOwnViews\":"<<released<<",\"unsafeCopyObjects\":"<<unsafe.size()<<",\"objects\":[";for(std::size_t i=0;i<buffers.size();i++){const auto d=buffers[i]->GetDesc();j<<(i?",":"")<<"{\"resource\":\""<<buffers[i].Get()<<"\",\"format\":"<<unsigned(d.Format)<<'}';}j<<']';Event("actual-swapchain-buffers-excluded",j.str());
}catch(...){try{Event("swapchain-observation-failed");}catch(...){}}}
void MaterialCaptureResizeResult(void* chain,const char* method,unsigned buffers,unsigned width,unsigned height,unsigned format,long result)noexcept{try{
 if(!S().enabled.load())return;std::ostringstream j;j<<"\"chain\":\""<<chain<<"\",\"method\":"<<Quoted(method,64)<<",\"buffers\":"<<buffers<<",\"width\":"<<width<<",\"height\":"<<height<<",\"requestedFormat\":"<<format<<",\"HRESULT\":\"0x"<<std::hex<<unsigned(result)<<'"';Event("actual-swapchain-resize-result",j.str());MaterialCaptureSwapChain(chain);
}catch(...){}}
void MaterialCaptureRTV(void* devicePointer,void* resourcePointer,const D3D12_RENDER_TARGET_VIEW_DESC* descriptor,D3D12_CPU_DESCRIPTOR_HANDLE handle)noexcept{try{
 auto& s=S();if(!s.enabled.load()||!handle.ptr)return;std::lock_guard<std::mutex> lock(s.mutex);if(s.done)return;++s.counters.rtvSeen;
 // An overwrite always revokes the previous descriptor claim, including null,
 // foreign-sized and excluded swapchain resources. No startup AddRef occurs.
 s.descriptors.erase(handle.ptr);
 if(!devicePointer||!resourcePointer)return;
 auto* resource=static_cast<ID3D12Resource*>(resourcePointer);auto d=resource->GetDesc();s.rtvStride=static_cast<ID3D12Device*>(devicePointer)->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_RTV);
 DescriptorInfo info{d.Width,d.Height,unsigned(d.Format),unsigned(descriptor?descriptor->Format:d.Format),unsigned(d.Dimension),d.SampleDesc.Count,unsigned(d.Flags),++s.clock,{}};
 if(d.Width==s.width&&d.Height==s.height){info.name=ObjectName(resource);if(s.namesLogged++<4096){std::ostringstream j;j<<"\"descriptor\":\""<<std::hex<<handle.ptr<<std::dec<<"\",\"resource\":\""<<resource<<"\",\"width\":"<<d.Width<<",\"height\":"<<d.Height<<",\"resourceFormat\":"<<unsigned(d.Format)<<",\"viewFormat\":"<<info.viewFormat<<",\"name\":"<<Quoted(info.name.c_str(),256);Event("fullsize-rtv-created",j.str());}}
 if(s.descriptorInfo.size()>=512&&!s.descriptorInfo.count(handle.ptr)){auto oldest=std::min_element(s.descriptorInfo.begin(),s.descriptorInfo.end(),[](const auto& a,const auto& b){return a.second.touched<b.second.touched;});s.descriptorInfo.erase(oldest);}s.descriptorInfo[handle.ptr]=info;
 const auto pattern=std::make_tuple(info.width,info.height,info.resourceFormat,info.viewFormat,info.dimension,info.samples,info.flags);
 if(s.rtvPatterns.size()<32&&s.rtvPatterns.insert(pattern).second){std::ostringstream j;j<<"\"width\":"<<info.width<<",\"height\":"<<info.height<<",\"resourceFormat\":"<<info.resourceFormat<<",\"viewFormat\":"<<info.viewFormat<<",\"dimension\":"<<info.dimension<<",\"samples\":"<<info.samples<<",\"flags\":"<<info.flags<<",\"expectedWidth\":"<<s.width<<",\"expectedHeight\":"<<s.height;Event("rtv-observed-pattern",j.str());}
 if(d.Width==s.width&&d.Height==s.height)++s.counters.rtvSizeMatch;
 if(d.Dimension!=D3D12_RESOURCE_DIMENSION_TEXTURE2D||d.Width!=s.width||d.Height!=s.height||d.DepthOrArraySize!=1||d.SampleDesc.Count!=1||!(d.Flags&D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET))return;
 D3D12_RENDER_TARGET_VIEW_DESC v{};if(descriptor)v=*descriptor;else{v.Format=d.Format;v.ViewDimension=D3D12_RTV_DIMENSION_TEXTURE2D;}
 if(v.ViewDimension!=D3D12_RTV_DIMENSION_TEXTURE2D||v.Texture2D.MipSlice||v.Texture2D.PlaneSlice||v.Format==DXGI_FORMAT_UNKNOWN)return;
 if(Backbuffer(resource)){++s.counters.swapchainExcluded;return;}++s.counters.rtvEligible;
 UINT64 bytes=0;static_cast<ID3D12Device*>(devicePointer)->GetCopyableFootprints(&d,0,1,0,nullptr,nullptr,nullptr,&bytes);
 if(!bytes||bytes>readbackLimit||s.descriptors.size()>=4096){++s.counters.rtvBudgetRejected;return;}
 s.descriptors[handle.ptr]={resource,d,v,bytes,s.rtvStride,info.name};++s.counters.rtvRecorded;
}catch(...){}}
void MaterialCaptureTargets(void* pointer,unsigned count,const D3D12_CPU_DESCRIPTOR_HANDLE* handles,bool contiguous)noexcept{try{
 auto& s=S();if(!s.enabled.load())return;std::lock_guard<std::mutex> lock(s.mutex);if(s.done)return;++s.counters.omSeen;
 if(s.omCounts.size()<16&&s.omCounts.insert(count).second)Event("om-observed-count","\"count\":"+std::to_string(count));
 if(count!=5||!handles){s.lists.erase(pointer);return;}++s.counters.omFive;if(s.lists.size()>=256&&!s.lists.count(pointer))return;
 unsigned stride=0;if(contiguous){auto first=s.descriptors.find(handles[0].ptr);if(first!=s.descriptors.end())stride=first->second.stride;}
 std::array<BorrowedView,5> views{};bool complete=!contiguous||stride;
 for(unsigned i=0;i<5&&complete;i++){const auto address=contiguous?handles[0].ptr+SIZE_T(i)*stride:handles[i].ptr;auto f=s.descriptors.find(address);if(f==s.descriptors.end()){complete=false;break;}views[i]=f->second;for(unsigned j=0;j<i;j++)if(views[j].resource==views[i].resource){complete=false;break;}}
 if(!complete){++s.counters.omMissing;if(s.missingLogged++<12){std::ostringstream j;j<<"\"list\":\""<<pointer<<"\",\"contiguous\":"<<(contiguous?"true":"false")<<",\"stride\":"<<stride<<",\"handles\":[";for(unsigned i=0;i<(contiguous&&!stride?1u:5u);i++){const auto address=contiguous?handles[0].ptr+SIZE_T(i)*stride:handles[i].ptr;j<<(i?",":"")<<"{\"address\":\""<<std::hex<<address<<std::dec<<"\",\"known\":"<<(s.descriptors.count(address)?"true":"false");auto d=s.descriptorInfo.find(address);if(d!=s.descriptorInfo.end())j<<",\"width\":"<<d->second.width<<",\"height\":"<<d->second.height<<",\"resourceFormat\":"<<d->second.resourceFormat<<",\"viewFormat\":"<<d->second.viewFormat;j<<'}';}j<<']';Event("om-five-map-missing",j.str());}s.lists.erase(pointer);return;}
 // Only an exact OM snapshot is retained here, not an interface reference.
 // A later CPU descriptor overwrite does not rewrite a recorded OM binding.
 s.lists[pointer]=std::move(views);++s.counters.omKnown;
}catch(...){}}
void MaterialCaptureCopyDescriptors(void* devicePointer,unsigned destinationRanges,const D3D12_CPU_DESCRIPTOR_HANDLE* destinations,const unsigned* destinationSizes,unsigned sourceRanges,const D3D12_CPU_DESCRIPTOR_HANDLE* sources,const unsigned* sourceSizes,D3D12_DESCRIPTOR_HEAP_TYPE type)noexcept{try{
 auto& s=S();if(!s.enabled.load()||type!=D3D12_DESCRIPTOR_HEAP_TYPE_RTV)return;std::lock_guard<std::mutex> lock(s.mutex);if(s.done)return;++s.counters.descriptorCopies;
 const auto invalidate=[&](){s.descriptors.clear();Event("descriptor-copy-unbounded-invalidated");};
 if(!devicePointer||!destinations||!sources||!destinationRanges||!sourceRanges||destinationRanges>128||sourceRanges>128){invalidate();return;}
 const auto stride=static_cast<ID3D12Device*>(devicePointer)->GetDescriptorHandleIncrementSize(type);if(!stride){invalidate();return;}
 const auto flatten=[&](unsigned ranges,const D3D12_CPU_DESCRIPTOR_HANDLE* starts,const unsigned* sizes,std::vector<SIZE_T>& output){for(unsigned i=0;i<ranges;i++){const auto count=sizes?sizes[i]:1u;if(count>4096-output.size()||(count&&starts[i].ptr>SIZE_MAX-SIZE_T(count-1)*stride))return false;for(unsigned j=0;j<count;j++)output.push_back(starts[i].ptr+SIZE_T(j)*stride);}return true;};
 std::vector<SIZE_T> dst,src;if(!flatten(destinationRanges,destinations,destinationSizes,dst)||!flatten(sourceRanges,sources,sourceSizes,src)||dst.size()!=src.size()){invalidate();return;}
 // Snapshot all sources before revoking destinations, including self/overlap.
 std::vector<BorrowedView> snapshot;snapshot.reserve(src.size());for(auto address:src){auto f=s.descriptors.find(address);snapshot.push_back(f==s.descriptors.end()?BorrowedView{}:f->second);}
 for(auto address:dst)s.descriptors.erase(address);for(std::size_t i=0;i<dst.size();i++)if(snapshot[i].resource&&s.descriptors.size()<4096){s.descriptors[dst[i]]=snapshot[i];++s.counters.knownCopied;}
}catch(...){}}
void MaterialCaptureCopyDescriptorsSimple(void* device,unsigned count,D3D12_CPU_DESCRIPTOR_HANDLE destination,D3D12_CPU_DESCRIPTOR_HANDLE source,D3D12_DESCRIPTOR_HEAP_TYPE type)noexcept{
 MaterialCaptureCopyDescriptors(device,1,&destination,&count,1,&source,&count,type);
}
void MaterialCaptureAfterDraw(void* pointer,const MaterialCaptureDraw& draw,const void* shader,std::size_t shaderBytes)noexcept{try{
 auto& s=S();if(!s.enabled.load()||draw.resource||draw.lod||draw.material>1||!shader||!shaderBytes||shaderBytes>1048576)return;
 std::lock_guard<std::mutex> lock(s.mutex);if(!s.armed||s.done||draw.epoch!=s.epoch||draw.sequence<s.minSequence||(s.mask&(1u<<draw.material))||s.attempts>=4)return;++s.counters.ownedDraws;
 if(draw.sequence-s.minSequence>180){s.done=true;s.pending=false;Event("sequence-window-expired");Snapshot("expired");return;}
 // The two per-draw captures must belong to the same observed Present interval
 // and exact latched body publication. Never silently compare different poses.
 if(s.mask&&(draw.sequence!=s.pairSequence||draw.presentationSerial!=s.pairPresentation||draw.nativePresentSerial!=s.pairPresent)){++s.counters.pairMismatch;return;}
 auto* list=static_cast<ID3D12GraphicsCommandList*>(pointer);if(list->GetType()!=D3D12_COMMAND_LIST_TYPE_DIRECT){++s.counters.nonDirect;return;}auto found=s.lists.find(pointer);if(found==s.lists.end()||std::any_of(found->second.begin(),found->second.end(),[](const auto& view){return !view.resource;})){++s.counters.listMissing;return;}
 auto capture=std::make_shared<Capture>();capture->draw=draw;capture->stage=s.stage;capture->armSequence=s.minSequence;capture->shader.assign(static_cast<const unsigned char*>(shader),static_cast<const unsigned char*>(shader)+shaderBytes);capture->stem="material-"+s.requestId+"-"+std::to_string(GetCurrentProcessId())+"-mat"+std::to_string(draw.material);
 ComPtr<ID3D12Device> device;HR(list->GetDevice(IID_PPV_ARGS(&device)));
 auto identities=RefreshPins(s);UINT64 prospective=s.pinned;if(s.trackedViews.size()+5>128){++s.counters.rtvBudgetRejected;return;}
 for(unsigned i=0;i<5;i++){
  const auto& source=found->second[i];auto view=std::make_shared<View>();
  // This AddRef occurs only at the actual native draw using this exact recorded
  // OM binding. The application must keep the resource alive until its GPU work
  // finishes; no borrowed creation-time pointer is touched at startup/expiry.
  view->resource=source.resource;const auto actual=source.resource->GetDesc();
  if(Backbuffer(source.resource)){++s.counters.swapchainExcluded;return;}
  if(actual.Dimension!=source.resourceDesc.Dimension||actual.Width!=source.resourceDesc.Width||actual.Height!=source.resourceDesc.Height||actual.Format!=source.resourceDesc.Format||actual.SampleDesc.Count!=1){Event("active-target-metadata-mismatch");return;}
  view->resourceDesc=source.resourceDesc;view->viewDesc=source.viewDesc;view->bytes=source.bytes;view->name=source.name;view->identity=reinterpret_cast<std::uintptr_t>(source.resource);
  if(identities.insert(source.resource).second){if(prospective>pinLimit-source.bytes){++s.counters.rtvBudgetRejected;return;}prospective+=source.bytes;}capture->targets[i].view=std::move(view);
 }
 UINT64 totalReadback=0;for(unsigned i=0;i<5;i++){auto& target=capture->targets[i];device->GetCopyableFootprints(&target.view->resourceDesc,0,1,0,&target.footprint,&target.rows,&target.rowBytes,&target.bytes);totalReadback+=target.bytes;if(!target.bytes||target.bytes>readbackLimit||totalReadback>2*readbackLimit)throw std::runtime_error("Unbounded material readback");D3D12_HEAP_PROPERTIES heap{};heap.Type=D3D12_HEAP_TYPE_READBACK;D3D12_RESOURCE_DESC desc{};desc.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER;desc.Width=target.bytes;desc.Height=1;desc.DepthOrArraySize=1;desc.MipLevels=1;desc.SampleDesc.Count=1;desc.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR;HR(device->CreateCommittedResource(&heap,D3D12_HEAP_FLAG_NONE,&desc,D3D12_RESOURCE_STATE_COPY_DEST,nullptr,IID_PPV_ARGS(&target.readback)));}
 // Allocate every destination before recording any commands. Failure cannot
 // leave a native target in COPY_SOURCE. All five are restored immediately.
 // Retain every resource before the first recorded GPU command. Container
 // allocation failure must occur before a copy can reference those resources.
 auto& records=s.recordings[pointer];records.reserve(records.size()+1);s.captures.reserve(s.captures.size()+1);s.trackedViews.reserve(s.trackedViews.size()+5);records.push_back(capture);s.captures.push_back(capture);for(auto& target:capture->targets)s.trackedViews.push_back(target.view);s.pinned=prospective;s.counters.rtvRetained+=5;
 std::array<D3D12_RESOURCE_BARRIER,5> barriers{};for(unsigned i=0;i<5;i++){auto& b=barriers[i];b.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;b.Transition={capture->targets[i].view->resource.Get(),0,D3D12_RESOURCE_STATE_RENDER_TARGET,D3D12_RESOURCE_STATE_COPY_SOURCE};}list->ResourceBarrier(5,barriers.data());
 for(unsigned i=0;i<5;i++){auto& t=capture->targets[i];D3D12_TEXTURE_COPY_LOCATION from{},to{};from.pResource=t.view->resource.Get();from.Type=D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;to.pResource=t.readback.Get();to.Type=D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;to.PlacedFootprint=t.footprint;list->CopyTextureRegion(&to,0,0,0,&from,nullptr);auto& b=barriers[i];std::swap(b.Transition.StateBefore,b.Transition.StateAfter);}list->ResourceBarrier(5,barriers.data());
 if(!s.mask){s.pairSequence=draw.sequence;s.pairPresentation=draw.presentationSerial;s.pairPresent=draw.nativePresentSerial;}s.mask|=1u<<draw.material;++s.attempts;if(s.mask==3){s.done=true;s.pending=false;s.descriptors.clear();s.lists.clear();}Event(draw.material?"source-copy-recorded":"stock-copy-recorded");
}catch(...){try{Event("record-failed");}catch(...){}}}
void MaterialCaptureSubmitted(void* pointer,unsigned count,void* const* lists)noexcept{try{
 auto& s=S();if(!s.enabled.load()||!pointer||!lists)return;std::lock_guard<std::mutex> lock(s.mutex);try{CheckDevicesLocked(s);}catch(...){Event("dred-query-failed");}std::vector<std::shared_ptr<Capture>> pending;for(unsigned i=0;i<count;i++){auto f=s.recordings.find(lists[i]);if(f!=s.recordings.end())for(auto& c:f->second)if(!c->submitted)pending.push_back(c);}if(pending.empty())return;
 // ExecuteCommandLists has already run. Even a later fence-allocation or
 // Signal failure must retain these resources across Reset/shutdown.
 for(auto& c:pending){c->submitted=true;c->signalFailed=true;}
 auto& q=s.queues[pointer];if(!q.fence){q.queue=static_cast<ID3D12CommandQueue*>(pointer);ComPtr<ID3D12Device> device;HR(q.queue->GetDevice(IID_PPV_ARGS(&device)));HR(device->CreateFence(0,D3D12_FENCE_FLAG_NONE,IID_PPV_ARGS(&q.fence)));}auto value=++q.next;auto result=q.queue->Signal(q.fence.Get(),value);for(auto& c:pending){c->fence=q.fence;c->fenceValue=value;c->queueAddress=reinterpret_cast<std::uintptr_t>(pointer);c->signalFailed=FAILED(result);}if(FAILED(result))try{CheckDevicesLocked(s);}catch(...){Event("dred-query-failed");}s.wake.notify_one();
}catch(...){try{Event("submission-failed-resources-retained");}catch(...){}}}
void MaterialCaptureReset(void* pointer)noexcept{try{
 auto& s=S();if(!s.enabled.load())return;std::lock_guard<std::mutex> lock(s.mutex);s.lists.erase(pointer);auto f=s.recordings.find(pointer);if(f==s.recordings.end())return;for(const auto& c:f->second)if(!c->submitted){s.mask&=~(1u<<c->draw.material);s.done=false;s.pending=s.attempts<4;s.captures.erase(std::remove(s.captures.begin(),s.captures.end(),c),s.captures.end());Event("unsubmitted-list-reset-cancelled");}s.recordings.erase(f);RefreshPins(s);
}catch(...){}}
void ShutdownMaterialCapture()noexcept{try{
 auto& s=S();if(!s.enabled.exchange(false))return;s.pending=false;{std::lock_guard<std::mutex> lock(s.mutex);s.stopping=true;s.wake.notify_one();}if(s.worker.joinable())s.worker.join();
 std::lock_guard<std::mutex> lock(s.mutex);s.descriptors.clear();s.lists.clear();s.recordings.clear();
 for(auto& watch:s.devices)if(watch.registered)watch.info->UnregisterMessageCallback(watch.cookie);s.devices.clear();
 // Completed captures have been written. Retain any unsignalled/in-flight
 // resources until process teardown rather than freeing memory still in use.
 for(auto i=s.captures.begin();i!=s.captures.end();)if(!(*i)->submitted)i=s.captures.erase(i);else ++i;
 Event("shutdown");
}catch(...){}}
#ifdef MALEMOD_MATERIAL_CAPTURE_TESTING
unsigned MaterialCaptureWritten(){return S().written.load();}
std::uint64_t MaterialCapturePinnedBytes(){auto& s=S();std::lock_guard<std::mutex> lock(s.mutex);RefreshPins(s);return s.pinned;}
#endif
}
