#define NOMINMAX
#include <windows.h>
#include <d3d12.h>
#include <d3d12sdklayers.h>
#include <dxgi1_6.h>
#include <d3dcompiler.h>
#include <wrl/client.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <cstring>
#include <vector>
#include <array>
#include <string>
#include <stdexcept>
#include "engine/material_capture.hpp"
using namespace malemod::witcher;
using Microsoft::WRL::ComPtr;
static void Check(bool value,const char* message){if(!value)throw std::runtime_error(message);}
static void HR(HRESULT value){if(FAILED(value))throw std::runtime_error("Material GPU fixture HRESULT="+std::to_string(value));}
static ComPtr<ID3DBlob> Compile(const char* text,const char* target){ComPtr<ID3DBlob> result,error;auto h=D3DCompile(text,std::strlen(text),nullptr,nullptr,nullptr,"main",target,D3DCOMPILE_ENABLE_STRICTNESS,0,&result,&error);if(FAILED(h)&&error)std::cerr<<static_cast<const char*>(error->GetBufferPointer());HR(h);return result;}
static std::string Read(const std::filesystem::path& path){std::ifstream f(path,std::ios::binary);return {std::istreambuf_iterator<char>(f),{}};}
int wmain(int argc,wchar_t** argv){try{
 if(argc==2&&!std::wcscmp(argv[1],L"--station")){
  auto station=CreateWindowStationW(nullptr,0,WINSTA_CREATEDESKTOP|WINSTA_ENUMDESKTOPS|WINSTA_READATTRIBUTES|WINSTA_ACCESSGLOBALATOMS,nullptr);Check(station!=nullptr,"Cannot query owned unnamed station");wchar_t name[256]{};USEROBJECTFLAGS flags{};DWORD bytes=0;Check(GetUserObjectInformationW(station,UOI_NAME,name,sizeof(name),&bytes)!=FALSE&&GetUserObjectInformationW(station,UOI_FLAGS,&flags,sizeof(flags),&bytes)!=FALSE&&!(flags.dwFlags&WSF_VISIBLE)&&_wcsicmp(name,L"WinSta0"),"Expected verified hidden station");std::wcout<<L"{\"station\":\""<<name<<L"\",\"hidden\":true}\n";CloseWindowStation(station);return 0;
 }
 #ifdef MALEMOD_MATERIAL_CAPTURE_CHURN
 constexpr unsigned size=2048;
#else
 constexpr unsigned size=256;
#endif
 Check(argc==3,"Usage: material_capture_test OUTPUT (--warp|--hardware)");const auto out=std::filesystem::absolute(argv[1]);Check(!std::filesystem::exists(out),"Fixture output must be fresh");std::filesystem::create_directories(out);
 InitializeMaterialCapture(out);Check(!MaterialCaptureEnabled(),"Absent request enabled capture");
 auto originalStation=GetProcessWindowStation();auto station=CreateWindowStationW(nullptr,0,WINSTA_CREATEDESKTOP|WINSTA_ENUMDESKTOPS|WINSTA_READATTRIBUTES|WINSTA_ACCESSGLOBALATOMS,nullptr);if(!station)throw std::runtime_error("Cannot create owned invisible fixture station error="+std::to_string(GetLastError()));wchar_t stationName[256]{};DWORD stationBytes=0;Check(GetUserObjectInformationW(station,UOI_NAME,stationName,sizeof(stationName),&stationBytes)!=FALSE,"Cannot identify fixture station");const std::wstring name=stationName;Check(SetProcessWindowStation(station)!=FALSE,"Cannot select owned fixture station");SetEnvironmentVariableW(L"MALEMOD_SEALED_SESSION",name.c_str());
#ifdef MALEMOD_MATERIAL_CAPTURE_SWAPCHAIN
 auto originalDesktop=GetThreadDesktop(GetCurrentThreadId());auto fixtureDesktop=CreateDesktopW(L"OwnedMaterialResizeFixture",nullptr,nullptr,0,DESKTOP_CREATEWINDOW|DESKTOP_READOBJECTS|DESKTOP_WRITEOBJECTS,nullptr);Check(fixtureDesktop!=nullptr&&SetThreadDesktop(fixtureDesktop),"Cannot attach fixture-only private desktop");
#endif

 #ifdef MALEMOD_MATERIAL_CAPTURE_DEBUG
 constexpr const char* magic="MMGBD1";
 #else
 constexpr const char* magic="MMGB1";
 #endif
 const auto request=[&](const std::string& expected){std::ofstream f(out/"material-capture.request");f<<magic<<' '<<expected<<" fixture07 411 "<<size<<' '<<size<<"\n";};
 request("wrong-station");InitializeMaterialCapture(out);Check(!MaterialCaptureEnabled(),"Wrong-station request enabled capture");std::string ascii;for(auto ch:name)ascii.push_back(static_cast<char>(ch));request(ascii);InitializeMaterialCapture(out);Check(MaterialCaptureEnabled(),"Valid hidden sealed request not enabled");
 ComPtr<ID3D12Debug> debug;const bool debugEnabled=SUCCEEDED(D3D12GetDebugInterface(IID_PPV_ARGS(&debug)));if(debugEnabled)debug->EnableDebugLayer();
 ComPtr<IDXGIFactory4> factory;HR(CreateDXGIFactory1(IID_PPV_ARGS(&factory)));ComPtr<IDXGIAdapter1> adapter;const bool hardware=!std::wcscmp(argv[2],L"--hardware");if(hardware){ComPtr<IDXGIFactory6> f;HR(factory.As(&f));HR(f->EnumAdapterByGpuPreference(0,DXGI_GPU_PREFERENCE_HIGH_PERFORMANCE,IID_PPV_ARGS(&adapter)));}else HR(factory->EnumWarpAdapter(IID_PPV_ARGS(&adapter)));
 DXGI_ADAPTER_DESC1 adapterInfo{};HR(adapter->GetDesc1(&adapterInfo));if(hardware)Check(!(adapterInfo.Flags&DXGI_ADAPTER_FLAG_SOFTWARE),"Hardware fixture selected software");ComPtr<ID3D12Device> device;HR(D3D12CreateDevice(adapter.Get(),D3D_FEATURE_LEVEL_11_0,IID_PPV_ARGS(&device)));
 D3D12_COMMAND_QUEUE_DESC qd{};ComPtr<ID3D12CommandQueue> queue;HR(device->CreateCommandQueue(&qd,IID_PPV_ARGS(&queue)));ComPtr<ID3D12CommandAllocator> allocator;HR(device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT,IID_PPV_ARGS(&allocator)));ComPtr<ID3D12GraphicsCommandList> list;HR(device->CreateCommandList(0,D3D12_COMMAND_LIST_TYPE_DIRECT,allocator.Get(),nullptr,IID_PPV_ARGS(&list)));
 
#ifdef MALEMOD_MATERIAL_CAPTURE_SWAPCHAIN
 {
  WNDCLASSW wc{};wc.hInstance=GetModuleHandleW(nullptr);wc.lpfnWndProc=DefWindowProcW;wc.lpszClassName=L"MaleMod.MaterialResizeFixture";Check(RegisterClassW(&wc)!=0,"Cannot register fixture window");auto window=CreateWindowExW(0,wc.lpszClassName,L"Owned hidden resize fixture",WS_OVERLAPPEDWINDOW,0,0,size,size,nullptr,nullptr,wc.hInstance,nullptr);Check(window!=nullptr,"Cannot create fixture-only hidden window");
  ComPtr<IDXGIFactory2> modern;HR(factory.As(&modern));DXGI_SWAP_CHAIN_DESC1 desc{};desc.Width=desc.Height=size;desc.Format=DXGI_FORMAT_R8G8B8A8_UNORM;desc.BufferCount=3;desc.BufferUsage=DXGI_USAGE_RENDER_TARGET_OUTPUT;desc.SampleDesc.Count=1;desc.SwapEffect=DXGI_SWAP_EFFECT_FLIP_DISCARD;desc.Scaling=DXGI_SCALING_STRETCH;ComPtr<IDXGISwapChain1> chain;HR(modern->CreateSwapChainForHwnd(queue.Get(),window,&desc,nullptr,nullptr,&chain));ComPtr<IDXGISwapChain3> latest;HR(chain.As(&latest));
  D3D12_DESCRIPTOR_HEAP_DESC heapDesc{};heapDesc.Type=D3D12_DESCRIPTOR_HEAP_TYPE_RTV;heapDesc.NumDescriptors=3;ComPtr<ID3D12DescriptorHeap> rtvHeap;HR(device->CreateDescriptorHeap(&heapDesc,IID_PPV_ARGS(&rtvHeap)));const auto base=rtvHeap->GetCPUDescriptorHandleForHeapStart();const auto increment=device->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_RTV);
  const auto views=[&](DXGI_FORMAT expected){for(unsigned i=0;i<3;i++){ComPtr<ID3D12Resource> buffer;HR(chain->GetBuffer(i,IID_PPV_ARGS(&buffer)));Check(buffer->GetDesc().Format==expected,"Swapchain returned old resource format");D3D12_CPU_DESCRIPTOR_HANDLE handle{base.ptr+SIZE_T(i)*increment};D3D12_RENDER_TARGET_VIEW_DESC view{};view.Format=expected;view.ViewDimension=D3D12_RTV_DIMENSION_TEXTURE2D;device->CreateRenderTargetView(buffer.Get(),&view,handle);}Check(MaterialCapturePinnedBytes()==0,"Observer retained swapchain buffer references");};
  views(DXGI_FORMAT_R8G8B8A8_UNORM);ComPtr<ID3D12Resource> held;HR(chain->GetBuffer(0,IID_PPV_ARGS(&held)));auto blocked=chain->ResizeBuffers(3,size,size,DXGI_FORMAT_R10G10B10A2_UNORM,0);Check(blocked==DXGI_ERROR_INVALID_CALL,"Held own GetBuffer reference did not reproduce ResizeBuffers failure");held.Reset();HR(chain->ResizeBuffers(3,size,size,DXGI_FORMAT_R10G10B10A2_UNORM,0));views(DXGI_FORMAT_R10G10B10A2_UNORM);
  UINT masks[]{1,1,1};IUnknown* presentQueues[]{queue.Get(),queue.Get(),queue.Get()};HR(latest->ResizeBuffers1(3,size,size,DXGI_FORMAT_R8G8B8A8_UNORM,0,masks,presentQueues));views(DXGI_FORMAT_R8G8B8A8_UNORM);Check(device->GetDeviceRemovedReason()==S_OK,"Corrected swapchain lifetime removed fixture device");latest.Reset();chain.Reset();DestroyWindow(window);UnregisterClassW(wc.lpszClassName,wc.hInstance);
  std::cout<<"Swapchain: own held ref INVALID_CALL, release then ResizeBuffers/1 S_OK, resource formats28->24->28, zero observer backbuffer pins\n";
 }
#endif
D3D12_DESCRIPTOR_HEAP_DESC hd{};hd.Type=D3D12_DESCRIPTOR_HEAP_TYPE_RTV;hd.NumDescriptors=128;ComPtr<ID3D12DescriptorHeap> heap;HR(device->CreateDescriptorHeap(&hd,IID_PPV_ARGS(&heap)));std::array<ComPtr<ID3D12Resource>,5> textures;std::array<D3D12_CPU_DESCRIPTOR_HANDLE,5> handles{};const auto first=heap->GetCPUDescriptorHandleForHeapStart();const auto stride=device->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_RTV);
 const DXGI_FORMAT formats[]{DXGI_FORMAT_R8G8B8A8_UNORM,DXGI_FORMAT_R16G16B16A16_FLOAT,DXGI_FORMAT_R10G10B10A2_UNORM,DXGI_FORMAT_R11G11B10_FLOAT,DXGI_FORMAT_R8G8B8A8_UNORM_SRGB};
#ifdef MALEMOD_MATERIAL_CAPTURE_CHURN
 // 48 distinct 32MiB targets create 1.5GiB of startup allocation churn.
 // Each engine reference dies immediately; the observer must evict idle views.
 const auto churn=[&](){for(unsigned i=0;i<48;i++){
  D3D12_RESOURCE_DESC desc{};desc.Dimension=D3D12_RESOURCE_DIMENSION_TEXTURE2D;desc.Width=desc.Height=size;desc.DepthOrArraySize=desc.MipLevels=1;desc.Format=DXGI_FORMAT_R16G16B16A16_FLOAT;desc.SampleDesc.Count=1;desc.Flags=D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET;D3D12_HEAP_PROPERTIES hp{};hp.Type=D3D12_HEAP_TYPE_DEFAULT;ComPtr<ID3D12Resource> scratch;HR(device->CreateCommittedResource(&hp,D3D12_HEAP_FLAG_NONE,&desc,D3D12_RESOURCE_STATE_RENDER_TARGET,nullptr,IID_PPV_ARGS(&scratch)));
  D3D12_CPU_DESCRIPTOR_HANDLE h{first.ptr+SIZE_T(5+i)*stride};device->CreateRenderTargetView(scratch.Get(),nullptr,h);MaterialCaptureRTV(device.Get(),scratch.Get(),nullptr,h);
  if(i==0)for(unsigned alias=0;alias<64;alias++){h.ptr=first.ptr+SIZE_T(64+alias)*stride;device->CreateRenderTargetView(scratch.Get(),nullptr,h);MaterialCaptureRTV(device.Get(),scratch.Get(),nullptr,h);}
 }};churn();
#endif

 for(unsigned i=0;i<5;i++){D3D12_RESOURCE_DESC desc{};desc.Dimension=D3D12_RESOURCE_DIMENSION_TEXTURE2D;desc.Width=desc.Height=size;desc.DepthOrArraySize=desc.MipLevels=1;desc.Format=formats[i];desc.SampleDesc.Count=1;desc.Flags=D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET;D3D12_HEAP_PROPERTIES hp{};hp.Type=D3D12_HEAP_TYPE_DEFAULT;HR(device->CreateCommittedResource(&hp,D3D12_HEAP_FLAG_NONE,&desc,D3D12_RESOURCE_STATE_RENDER_TARGET,nullptr,IID_PPV_ARGS(&textures[i])));const auto targetName=L"OwnedFixtureTarget"+std::to_wstring(i);HR(textures[i]->SetName(targetName.c_str()));handles[i].ptr=first.ptr+SIZE_T(i)*stride;device->CreateRenderTargetView(textures[i].Get(),nullptr,handles[i]);MaterialCaptureRTV(device.Get(),textures[i].Get(),nullptr,handles[i]);}
 // Exercise both actual descriptor-copy APIs before recording an OM binding.
 D3D12_CPU_DESCRIPTOR_HANDLE copied{first.ptr+SIZE_T(53)*stride};device->CopyDescriptorsSimple(5,copied,first,D3D12_DESCRIPTOR_HEAP_TYPE_RTV);MaterialCaptureCopyDescriptorsSimple(device.Get(),5,copied,first,D3D12_DESCRIPTOR_HEAP_TYPE_RTV);
 D3D12_CPU_DESCRIPTOR_HANDLE destinations[]{D3D12_CPU_DESCRIPTOR_HANDLE{first.ptr+SIZE_T(58)*stride},D3D12_CPU_DESCRIPTOR_HANDLE{first.ptr+SIZE_T(60)*stride}};D3D12_CPU_DESCRIPTOR_HANDLE sources[]{copied,D3D12_CPU_DESCRIPTOR_HANDLE{copied.ptr+SIZE_T(2)*stride}};UINT sizes[]{2,3};device->CopyDescriptors(2,destinations,sizes,2,sources,sizes,D3D12_DESCRIPTOR_HEAP_TYPE_RTV);MaterialCaptureCopyDescriptors(device.Get(),2,destinations,sizes,2,sources,sizes,D3D12_DESCRIPTOR_HEAP_TYPE_RTV);for(unsigned i=0;i<5;i++)handles[i].ptr=first.ptr+SIZE_T(58+i)*stride;
 Check(MaterialCapturePinnedBytes()==0,"Creation/copy metadata retained startup GPU resources");
 auto vs=Compile("float4 main(uint id:SV_VertexID):SV_Position {return float4(id==2?3:-1,id==1?3:-1,0,1);}","vs_5_1");
 auto ps=Compile("cbuffer C:register(b0){float4 color;}struct O{float4 a:SV_Target0;float4 b:SV_Target1;float4 c:SV_Target2;float4 d:SV_Target3;float4 e:SV_Target4;};O main(){O o;o.a=o.b=o.c=o.d=o.e=color;return o;}","ps_5_1");
 D3D12_ROOT_PARAMETER parameter{};parameter.ParameterType=D3D12_ROOT_PARAMETER_TYPE_32BIT_CONSTANTS;parameter.Constants.Num32BitValues=4;parameter.ShaderVisibility=D3D12_SHADER_VISIBILITY_PIXEL;D3D12_ROOT_SIGNATURE_DESC rd{};rd.NumParameters=1;rd.pParameters=&parameter;rd.Flags=D3D12_ROOT_SIGNATURE_FLAG_ALLOW_INPUT_ASSEMBLER_INPUT_LAYOUT;ComPtr<ID3DBlob> blob,error;HR(D3D12SerializeRootSignature(&rd,D3D_ROOT_SIGNATURE_VERSION_1,&blob,&error));ComPtr<ID3D12RootSignature> root;HR(device->CreateRootSignature(0,blob->GetBufferPointer(),blob->GetBufferSize(),IID_PPV_ARGS(&root)));
 D3D12_GRAPHICS_PIPELINE_STATE_DESC p{};p.pRootSignature=root.Get();p.VS={vs->GetBufferPointer(),vs->GetBufferSize()};p.PS={ps->GetBufferPointer(),ps->GetBufferSize()};p.SampleMask=UINT_MAX;p.RasterizerState.FillMode=D3D12_FILL_MODE_SOLID;p.RasterizerState.CullMode=D3D12_CULL_MODE_NONE;p.RasterizerState.DepthClipEnable=TRUE;p.DepthStencilState.DepthEnable=FALSE;p.DepthStencilState.StencilEnable=FALSE;p.PrimitiveTopologyType=D3D12_PRIMITIVE_TOPOLOGY_TYPE_TRIANGLE;p.NumRenderTargets=5;p.SampleDesc.Count=1;for(unsigned i=0;i<5;i++){p.RTVFormats[i]=formats[i];p.BlendState.RenderTarget[i].RenderTargetWriteMask=D3D12_COLOR_WRITE_ENABLE_ALL;}ComPtr<ID3D12PipelineState> pipeline;HR(device->CreateGraphicsPipelineState(&p,IID_PPV_ARGS(&pipeline)));
 const auto setup=[&](bool contiguous){list->SetPipelineState(pipeline.Get());list->SetGraphicsRootSignature(root.Get());D3D12_VIEWPORT viewport{0,0,float(size),float(size),0,1};list->RSSetViewports(1,&viewport);list->IASetPrimitiveTopology(D3D_PRIMITIVE_TOPOLOGY_TRIANGLELIST);list->OMSetRenderTargets(5,handles.data(),contiguous,nullptr);MaterialCaptureTargets(list.Get(),5,handles.data(),contiguous);};
 const auto draw=[&](bool right){D3D12_RECT rect{right?LONG(size/2):0,0,right?LONG(size):LONG(size/2),LONG(size)};list->RSSetScissorRects(1,&rect);const float color[]{right?.75f:.25f,right?.25f:.5f,right?.5f:.75f,1};list->SetGraphicsRoot32BitConstants(0,4,color,0);list->DrawInstanced(3,1,0,0);};
 MaterialCaptureDraw stock;stock.material=0;stock.epoch=1;stock.sequence=50;stock.presentationSerial=99;stock.nativePresentSerial=100;stock.drawSerial=1;stock.indexCount=3;auto source=stock;source.material=1;source.section=1;source.drawSerial=2;
 setup(true);const float zero[]{0,0,0,0};for(auto h:handles)list->ClearRenderTargetView(h,zero,0,nullptr);draw(false);GraphicsMaterialCaptureCheckpoint(410,1,50);Check(!MaterialCapturePendingDraw(),"Wrong checkpoint armed capture");GraphicsMaterialCaptureCheckpoint(411,1,50);Check(MaterialCapturePendingDraw(),"Correct checkpoint not armed");D3D12_CPU_DESCRIPTOR_HANDLE unknown{first.ptr+SIZE_T(100)*stride};D3D12_RENDER_TARGET_VIEW_DESC nullView{};nullView.Format=DXGI_FORMAT_R8G8B8A8_UNORM;nullView.ViewDimension=D3D12_RTV_DIMENSION_TEXTURE2D;device->CreateRenderTargetView(nullptr,&nullView,unknown);MaterialCaptureRTV(device.Get(),nullptr,&nullView,unknown);device->CopyDescriptorsSimple(1,handles[0],unknown,D3D12_DESCRIPTOR_HEAP_TYPE_RTV);MaterialCaptureCopyDescriptorsSimple(device.Get(),1,handles[0],unknown,D3D12_DESCRIPTOR_HEAP_TYPE_RTV);setup(false);MaterialCaptureAfterDraw(list.Get(),stock,ps->GetBufferPointer(),ps->GetBufferSize());Check(MaterialCapturePinnedBytes()==0,"Unknown copied descriptor retained stale ownership");device->CopyDescriptorsSimple(1,handles[0],first,D3D12_DESCRIPTOR_HEAP_TYPE_RTV);MaterialCaptureCopyDescriptorsSimple(device.Get(),1,handles[0],first,D3D12_DESCRIPTOR_HEAP_TYPE_RTV);setup(true);
 auto stale=stock;stale.sequence=49;MaterialCaptureAfterDraw(list.Get(),stale,ps->GetBufferPointer(),ps->GetBufferSize());
 MaterialCaptureAfterDraw(list.Get(),stock,ps->GetBufferPointer(),ps->GetBufferSize());HR(list->Close());HR(list->Reset(allocator.Get(),nullptr));MaterialCaptureReset(list.Get());Check(MaterialCaptureWritten()==0&&MaterialCapturePendingDraw(),"Unsubmitted reset failed to cancel/rearm");
 setup(false);
#ifdef MALEMOD_MATERIAL_CAPTURE_CHURN
 churn();setup(false);
#endif
 for(auto h:handles)list->ClearRenderTargetView(h,zero,0,nullptr);draw(false);MaterialCaptureAfterDraw(list.Get(),stock,ps->GetBufferPointer(),ps->GetBufferSize());draw(true);auto wrongFrame=source;wrongFrame.nativePresentSerial++;MaterialCaptureAfterDraw(list.Get(),wrongFrame,ps->GetBufferPointer(),ps->GetBufferSize());Check(MaterialCapturePendingDraw(),"Different Present interval was accepted into pair");MaterialCaptureAfterDraw(list.Get(),source,ps->GetBufferPointer(),ps->GetBufferSize());Check(!MaterialCapturePendingDraw(),"Pair capture did not stop recording");HR(list->Close());
 ComPtr<ID3D12Fence> gate;HR(device->CreateFence(0,D3D12_FENCE_FLAG_NONE,IID_PPV_ARGS(&gate)));HR(queue->Wait(gate.Get(),1));ID3D12CommandList* lists[]{list.Get()};queue->ExecuteCommandLists(1,lists);MaterialCaptureSubmitted(queue.Get(),1,reinterpret_cast<void* const*>(lists));MaterialCaptureReset(list.Get());Sleep(100);Check(MaterialCaptureWritten()==0,"Readback mapped before queue fence completion");HR(gate->Signal(1));
 for(unsigned i=0;i<200&&MaterialCaptureWritten()!=2;i++)Sleep(25);Check(MaterialCaptureWritten()==2,"Fenced material pair not written");
 auto stockMeta=Read(out/((std::string("material-fixture07-")+std::to_string(GetCurrentProcessId()))+"-mat0.json"));auto sourceMeta=Read(out/((std::string("material-fixture07-")+std::to_string(GetCurrentProcessId()))+"-mat1.json"));Check(stockMeta.find("\"completeFrame\":false")!=std::string::npos&&sourceMeta.find("\"sequence\":50")!=std::string::npos,"Exact per-draw metadata missing");
 // RGBA8 is exact within 8-bit quantization. Stock capture must contain only
 // its left half; the later source capture contains both previous and new
 // material regions. This proves the per-draw, incomplete-frame semantics.
 auto a=Read(out/("material-fixture07-"+std::to_string(GetCurrentProcessId())+"-mat0-rt0.bin"));auto b=Read(out/("material-fixture07-"+std::to_string(GetCurrentProcessId())+"-mat1-rt0.bin"));Check(a.size()==size*size*4&&b.size()==a.size(),"Unexpected fixture copy footprint");const auto pixel=[&](const std::string& data,unsigned x){auto at=(size/2)*(size*4)+x*4;return std::array<unsigned char,4>{(unsigned char)data[at],(unsigned char)data[at+1],(unsigned char)data[at+2],(unsigned char)data[at+3]};};Check(pixel(a,size/4)==std::array<unsigned char,4>{64,128,191,255}&&pixel(a,size*3/4)==std::array<unsigned char,4>{0,0,0,0},"Stock per-draw pixels differ");Check(pixel(b,size/4)==pixel(a,size/4)&&pixel(b,size*3/4)==std::array<unsigned char,4>{191,64,128,255},"Source draw or restored RT states differ");
 ComPtr<ID3D12InfoQueue> info;if(SUCCEEDED(device.As(&info)))for(UINT64 i=0;i<info->GetNumStoredMessages();i++){SIZE_T bytes=0;info->GetMessage(i,nullptr,&bytes);std::vector<unsigned char> buffer(bytes);auto* message=reinterpret_cast<D3D12_MESSAGE*>(buffer.data());HR(info->GetMessage(i,message,&bytes));if(message->Severity==D3D12_MESSAGE_SEVERITY_ERROR||message->Severity==D3D12_MESSAGE_SEVERITY_CORRUPTION)throw std::runtime_error(message->pDescription);}
 ShutdownMaterialCapture();Check(!MaterialCaptureEnabled(),"Capture shutdown failed");
#ifdef MALEMOD_MATERIAL_CAPTURE_SWAPCHAIN
 Check(SetThreadDesktop(originalDesktop)!=FALSE,"Cannot restore fixture thread desktop");CloseDesktop(fixtureDesktop);
#endif
 Check(SetProcessWindowStation(originalStation)!=FALSE,"Cannot restore fixture station");CloseWindowStation(station);
 std::cout<<"PASS vendor="<<adapterInfo.VendorId<<" hardware="<<hardware<<" debug="<<debugEnabled<<" fiveFormats=5 pair=2 defaultOff/sealed/wrongStage/staleSequence/unsubmittedReset/fence/pixels/RTrestore=PASS\n";return 0;
 }catch(const std::exception& error){ShutdownMaterialCapture();std::cerr<<error.what()<<'\n';return 1;}}
