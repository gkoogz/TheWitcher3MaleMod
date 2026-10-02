#define NOMINMAX
#include "overlay_panel.hpp"
#include <windowsx.h>
#include <string>

namespace malemod::witcher {
namespace {
constexpr const wchar_t* labels[]={L"State",L"Overall size",L"Length",L"Width",L"Glans size",L"Scrotum size",L"Hang",L"Rest angle",L"Forward offset",L"Vertical offset",L"Shaft stiffness",L"Shaft weight",L"Shaft bounce",L"Shaft response",L"Scrotum stiffness",L"Scrotum weight",L"Scrotum bounce",L"Scrotum response"};
void Box(HDC dc,int x,int y,int w,int h,COLORREF color){auto brush=CreateSolidBrush(color);RECT r{x,y,x+w,y+h};FillRect(dc,&r,brush);DeleteObject(brush);}
void Text(HDC dc,const wchar_t* text,int x,int y,int w,int h,COLORREF color){SetTextColor(dc,color);RECT r{x,y,x+w,y+h};DrawTextW(dc,text,-1,&r,DT_LEFT|DT_VCENTER|DT_SINGLELINE);}
}
void OverlayPanel::Paint(HDC dc,const surface::Controls& c,bool expanded,int w,int h){
 const int saved=SaveDC(dc);SetMapMode(dc,MM_ANISOTROPIC);SetWindowExtEx(dc,expanded?width:92,expanded?height:32,nullptr);SetViewportExtEx(dc,w,h,nullptr);SetBkMode(dc,TRANSPARENT);
 auto font=CreateFontW(-14,0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,CLEARTYPE_QUALITY,DEFAULT_PITCH,L"Segoe UI");SelectObject(dc,font);
 const COLORREF bg=RGB(20,28,37),fg=RGB(226,234,240),dim=RGB(151,168,183),accent=RGB(88,200,183),line=RGB(52,68,83);
 Box(dc,0,0,width,height,bg);if(!expanded){Box(dc,0,0,3,32,accent);Text(dc,L"Anatomy",13,0,78,32,fg);RestoreDC(dc,saved);DeleteObject(font);return;}
 Box(dc,0,0,width,2,accent);Text(dc,L"MaleMod  /  Anatomy",16,8,310,22,fg);Text(dc,L"Shape and material response",16,31,330,18,dim);Text(dc,L"\x00d7",388,8,22,26,dim);
 const wchar_t* states[]={L"Rigid",L"Intermediate",L"Flexible"};
 for(unsigned i=0;i<3;i++){const int x=16+int(i)*132;Box(dc,x,57,124,28,c.values[0]==float(i)?accent:line);Text(dc,states[i],x+10,57,112,28,c.values[0]==float(i)?bg:fg);}
 Text(dc,L"SHAPE",16,94,180,20,dim);Text(dc,L"PHYSICS",16,370,180,20,dim);
 for(unsigned i=1;i<18;i++){
  int y=Row(i);Text(dc,labels[i],16,y,150,24,fg);wchar_t number[32]{};swprintf_s(number,L"%.0f",c.values[i]);Text(dc,number,165,y,32,24,dim);
  const float low=i==2||i==4?0.f:1.f;const int x=trackLeft+int((trackRight-trackLeft)*(c.values[i]-low)/(100-low));
  Box(dc,trackLeft,y+11,trackRight-trackLeft,3,line);Box(dc,trackLeft,y+11,x-trackLeft,3,accent);Box(dc,x-3,y+6,6,13,accent);
 }
 Box(dc,16,631,126,30,line);Text(dc,L"Reset defaults",28,631,114,30,fg);Text(dc,L"Editing pauses gameplay",160,633,245,26,dim);
 RestoreDC(dc,saved);DeleteObject(font);
}
OverlayPanel::OverlayPanel(HWND parent,Read read,Write write):parent_(parent),read_(std::move(read)),write_(std::move(write)),thread_([this]{
 WNDCLASSW wc{};wc.lpfnWndProc=Procedure;wc.hInstance=GetModuleHandleW(nullptr);wc.lpszClassName=L"MaleMod.Anatomy.Overlay";wc.hCursor=LoadCursorW(nullptr,MAKEINTRESOURCEW(32512));RegisterClassW(&wc);
 RECT r{};GetWindowRect(parent_,&r);auto window=CreateWindowExW(WS_EX_TOOLWINDOW|WS_EX_NOACTIVATE|WS_EX_LAYERED,wc.lpszClassName,L"MaleMod anatomy",WS_POPUP,r.left+24,r.top+110,92,32,parent_,nullptr,wc.hInstance,this);
 if(!window)return;window_.store(window);SetLayeredWindowAttributes(window,0,245,LWA_ALPHA);SetTimer(window,1,40,nullptr);
 MSG msg{};while(!stop_.load()&&GetMessageW(&msg,nullptr,0,0)>0){TranslateMessage(&msg);DispatchMessageW(&msg);}if(IsWindow(window))DestroyWindow(window);window_.store(nullptr);
}){}
OverlayPanel::~OverlayPanel(){stop_=true;auto w=window_.load();if(w)PostMessageW(w,WM_CLOSE,0,0);if(thread_.joinable())thread_.join();}
void OverlayPanel::Resize(){auto w=window_.load();if(w){RECT r{};GetClientRect(parent_,&r);const float scale=(std::max)(.5f,(std::min)(1.f,float(r.bottom-150)/height));SetWindowPos(w,nullptr,0,0,Open()?int(width*scale):92,Open()?int(height*scale):32,SWP_NOACTIVATE|SWP_NOMOVE|SWP_NOZORDER);}}
void OverlayPanel::Click(int x,int y){
 if(!Open()){expanded_=true;Resize();return;}
 if(x>=378&&y<44){expanded_=false;dragging_=-1;Resize();return;}
 if(y>=57&&y<85&&x>=16&&x<404){write_(0,float((x-16)/132));return;}
 if(y>=631&&y<661&&x>=16&&x<142){for(unsigned i=0;i<18;i++)write_(i,i?50.f:2.f);return;}
 dragging_=Hit(x,y);if(dragging_>=1)write_(unsigned(dragging_),Value(unsigned(dragging_),x));
}
LRESULT CALLBACK OverlayPanel::Procedure(HWND window,UINT message,WPARAM wp,LPARAM lp){
 auto* self=reinterpret_cast<OverlayPanel*>(GetWindowLongPtrW(window,GWLP_USERDATA));
 if(message==WM_NCCREATE){self=static_cast<OverlayPanel*>(reinterpret_cast<CREATESTRUCTW*>(lp)->lpCreateParams);SetWindowLongPtrW(window,GWLP_USERDATA,reinterpret_cast<LONG_PTR>(self));}
 if(!self)return DefWindowProcW(window,message,wp,lp);
 RECT client{};GetClientRect(window,&client);
 const int x=client.right?GET_X_LPARAM(lp)*(self->Open()?width:92)/client.right:0;
 const int y=client.bottom?GET_Y_LPARAM(lp)*(self->Open()?height:32)/client.bottom:0;
 switch(message){
  case WM_MOUSEACTIVATE:return MA_NOACTIVATE;
  case WM_LBUTTONDOWN:self->Click(x,y);if(self->dragging_>=0)SetCapture(window);InvalidateRect(window,nullptr,FALSE);return 0;
  case WM_MOUSEMOVE:if(self->dragging_>=1&&(wp&MK_LBUTTON)){self->write_(unsigned(self->dragging_),Value(unsigned(self->dragging_),x));InvalidateRect(window,nullptr,FALSE);}return 0;
  case WM_LBUTTONUP:case WM_CANCELMODE:self->dragging_=-1;if(GetCapture()==window)ReleaseCapture();return 0;
  case WM_TIMER:{const bool visible=IsWindow(self->parent_)&&IsWindowVisible(self->parent_)&&GetForegroundWindow()==self->parent_;ShowWindow(window,visible?SW_SHOWNOACTIVATE:SW_HIDE);InvalidateRect(window,nullptr,FALSE);if(!IsWindow(self->parent_))PostMessageW(window,WM_CLOSE,0,0);return 0;}
  case WM_PAINT:{PAINTSTRUCT paint{};auto dc=BeginPaint(window,&paint);RECT rect{};GetClientRect(window,&rect);Paint(dc,self->read_(),self->Open(),rect.right,rect.bottom);EndPaint(window,&paint);return 0;}
  case WM_CLOSE:DestroyWindow(window);return 0;
  case WM_DESTROY:self->expanded_=false;PostQuitMessage(0);return 0;
 }
 return DefWindowProcW(window,message,wp,lp);
}
}
