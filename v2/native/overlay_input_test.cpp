// White-box transport fixture: every input/focus function is an owned fake.
// It never reads or sends physical input, creates a window, or launches a game.
#include "engine/overlay_input.cpp"
#include <cassert>
#include <iostream>
using namespace malemod::witcher;
namespace {
HWND focus=reinterpret_cast<HWND>(1);HWND WINAPI FakeForeground(){return focus;}
SHORT WINAPI FakeAsync(int){return SHORT(-32768);}
RAWINPUT incoming{};MSG incomingMessage{};
UINT WINAPI FakeRaw(HRAWINPUT,UINT,LPVOID output,PUINT,UINT){std::memcpy(output,&incoming,sizeof(incoming));return sizeof(incoming);}
BOOL WINAPI FakePeek(LPMSG output,HWND,UINT,UINT,UINT){*output=incomingMessage;return TRUE;}
HRESULT STDMETHODCALLTYPE FakeState(void*,DWORD bytes,LPVOID output){std::memset(output,0x80,bytes);return S_OK;}
HRESULT STDMETHODCALLTYPE FakeData(void*,DWORD stride,LPDIDEVICEOBJECTDATA output,LPDWORD count,DWORD){assert(stride==sizeof(DIDEVICEOBJECTDATA));output[0]={DIK_J,0x80,0,0,0};output[1]={DIK_W,0x80,0,0,0};*count=2;return S_OK;}
}
int main(){
 for(bool open:{false,true})for(bool anatomy:{false,true}){
  assert(OverlayInputBlocks(VK_F6,open,anatomy));assert(OverlayInputBlocks('J',open,anatomy)==anatomy);
  for(unsigned key:{VK_F8,VK_UP,VK_DOWN,VK_LEFT,VK_RIGHT,VK_SHIFT,VK_LSHIFT,VK_RSHIFT})assert(OverlayInputBlocks(key,open,anatomy)==(open&&anatomy));
  for(unsigned key:std::array<unsigned,6>{'W','A','S','D',VK_ESCAPE,VK_F9})assert(!OverlayInputBlocks(key,open,anatomy));
 }
 parent=focus;expanded=true;visible=true;privateSession=false;foreground=FakeForeground;asyncOriginal=FakeAsync;rawOriginal=FakeRaw;peekOriginal=FakePeek;
 assert(AsyncHook('J')==0&&AsyncHook('W')==SHORT(-32768)&&OverlayInputPoll('J')==SHORT(-32768));
 expanded=false;assert(AsyncHook(VK_UP)==SHORT(-32768)&&AsyncHook('J')==0);visible=false;assert(AsyncHook('J')==SHORT(-32768)&&AsyncHook(VK_F6)==0);
 expanded=true;visible=true;focus=reinterpret_cast<HWND>(2);assert(AsyncHook('J')==SHORT(-32768));focus=parent.load();privateSession=true;assert(AsyncHook('J')==0);privateSession=false;
 incoming.header.dwType=RIM_TYPEKEYBOARD;incoming.data.keyboard.VKey='J';RAWINPUT output{};UINT bytes=sizeof(output);
 assert(RawHook(nullptr,RID_INPUT,&output,&bytes,sizeof(RAWINPUTHEADER))==sizeof(output));assert(output.data.keyboard.VKey==255&&output.data.keyboard.Message==WM_NULL);
 incoming.data.keyboard.Flags=RI_KEY_BREAK;RawHook(nullptr,RID_INPUT,&output,&bytes,sizeof(RAWINPUTHEADER));assert(output.data.keyboard.VKey=='J');incoming.data.keyboard.Flags=0;
 incoming.data.keyboard.VKey='W';RawHook(nullptr,RID_INPUT,&output,&bytes,sizeof(RAWINPUTHEADER));assert(output.data.keyboard.VKey=='W');
 incoming.header.dwType=RIM_TYPEMOUSE;RawHook(nullptr,RID_INPUT,&output,&bytes,sizeof(RAWINPUTHEADER));assert(std::memcmp(&incoming,&output,sizeof(output))==0);
 incomingMessage.hwnd=parent.load();incomingMessage.message=WM_KEYDOWN;incomingMessage.wParam='J';MSG msg{};assert(PeekHook(&msg,nullptr,0,0,PM_REMOVE)&&msg.message==WM_NULL);
 incomingMessage.message=WM_KEYUP;PeekHook(&msg,nullptr,0,0,PM_REMOVE);assert(msg.message==WM_KEYUP);incomingMessage.message=WM_KEYDOWN;
 incomingMessage.hwnd=reinterpret_cast<HWND>(3);PeekHook(&msg,nullptr,0,0,PM_REMOVE);assert(msg.message==WM_KEYDOWN);
 std::array<void*,14> table{};table[9]=reinterpret_cast<void*>(FakeState);table[10]=reinterpret_cast<void*>(FakeData);void** object=table.data();void* device=&object;
 devices.push_back({table.data(),nullptr,nullptr,table[9],table[10],nullptr});identities.push_back({device,parent.load()});
 std::array<unsigned char,256> state{};assert(SUCCEEDED(StateHook(device,256,state.data())));assert(state[DIK_J]==0&&state[DIK_W]==0x80&&state[DIK_F6]==0);
 std::array<DIDEVICEOBJECTDATA,2> data{};DWORD count=2;assert(SUCCEEDED(DataHook(device,sizeof(DIDEVICEOBJECTDATA),data.data(),&count,0))&&count==1&&data[0].dwOfs==DIK_W);
 identities[0].owner=reinterpret_cast<HWND>(4);StateHook(device,256,state.data());assert(state[DIK_J]==0x80);
 void* slot=reinterpret_cast<void*>(FakeState);assert(PatchSlot(&slot,reinterpret_cast<void*>(FakeData)));assert(slot==reinterpret_cast<void*>(FakeData));OverlayInputShutdown();assert(slot==reinterpret_cast<void*>(FakeState));
 const auto metrics=OverlayInputStatus();assert(metrics.asyncKeys&&metrics.rawKeys&&metrics.messages&&metrics.directKeys);
 std::cout<<"PASS Witcher imported input paths: scoped async/raw/message/DirectInput filtering, J journal fence, open/visible/focus/keyboard identity guards, raw panel bypass and restoration; all input/focus is fake, native game integration UNOBSERVED\n";
}



