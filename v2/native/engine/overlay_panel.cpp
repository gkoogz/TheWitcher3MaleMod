#define NOMINMAX
#include "overlay_panel.hpp"
#include "overlay_input.hpp"
#include <windowsx.h>
#include <string>
#include <malemod/controls/presentation.hpp>
#include <malemod/controls/menu_theme.hpp>
namespace malemod::witcher {
namespace {
namespace Menu=controls::menu;
COLORREF Color(Menu::Color c){return RGB(c.r,c.g,c.b);}
int CALLBACK FindFont(const LOGFONTW*,const TEXTMETRICW*,DWORD,LPARAM found){*reinterpret_cast<bool*>(found)=true;return 0;}
HFONT MenuFont(HDC dc,int height){LOGFONTW candidate{};candidate.lfCharSet=DEFAULT_CHARSET;wcscpy_s(candidate.lfFaceName,Menu::Font);bool present=false;EnumFontFamiliesExW(dc,&candidate,FindFont,reinterpret_cast<LPARAM>(&present),0);return CreateFontW(-height,0,0,0,Menu::FontWeight,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,ANTIALIASED_QUALITY,DEFAULT_PITCH,present?Menu::Font:Menu::FallbackFont);}
void Box(HDC dc,int x,int y,int w,int h,COLORREF color){auto brush=CreateSolidBrush(color);RECT r{x,y,x+w,y+h};FillRect(dc,&r,brush);DeleteObject(brush);}
void Text(HDC dc,const wchar_t* text,int x,int y,int w,int h,COLORREF color,bool right=false){SetTextColor(dc,color);RECT r{x,y,x+w,y+h};DrawTextW(dc,text,-1,&r,(right?DT_RIGHT:DT_LEFT)|DT_VCENTER|DT_SINGLELINE);}
}
void OverlayPanel::Paint(HDC dc,const surface::Controls& baseline,bool expanded,int w,int h,unsigned selected,FeatureState f){
 surface::Controls c=baseline;if(f.displayAnimated)c.values=f.displayControls;
 const int saved=SaveDC(dc);SetMapMode(dc,MM_ANISOTROPIC);SetWindowExtEx(dc,expanded?width:Menu::CollapsedWidth,expanded?height:Menu::CollapsedHeight,nullptr);SetViewportExtEx(dc,w,h,nullptr);SetBkMode(dc,TRANSPARENT);
 auto font=MenuFont(dc,int(Menu::TextHeight));auto heading=MenuFont(dc,int(Menu::HeadingHeight));SelectObject(dc,font);
 const COLORREF bg=Color(Menu::Background),fg=Color(Menu::Text),dim=Color(Menu::Muted),accent=Color(Menu::Accent),line=Color(Menu::Track),selection=Color(Menu::Selection);
 Box(dc,0,0,width,height,bg);SelectObject(dc,heading);Text(dc,Menu::WideTitle,14,3,110,31,fg);SelectObject(dc,font);Text(dc,L"F6",expanded?330:108,3,56,31,dim,true);
 if(expanded){
 for(unsigned row=0;row<Menu::RowCount;row++){
  const int y=Menu::RowY(row);const wchar_t* group=row==0?L"STATE":row==3?L"SHAPE":row==12?L"PHYSICS":row==20?L"WARDROBE":nullptr;
  if(group)Text(dc,group,14,y-18,372,18,dim);
  const bool active=selected==row;const auto tc=active?accent:fg;if(active){Box(dc,8,y,width-16,24,selection);Box(dc,8,y,2,24,accent);}
  const int core=Menu::CoreIndex(row);const wchar_t* label=core>=0?controls::WideLabels[core]:row==1?L"Throb":row==2?L"Idle chatter":L"Bottom";
  Text(dc,label,14,y,154,24,tc);wchar_t number[32]{};const wchar_t* value=nullptr;
  if(row==0)value=controls::WideStates[(std::min)(2u,unsigned(c.values[0]))];
  else if(row==1)value=controls::WideThrobModes[(std::min)(3u,f.throbMode)];
  else if(row==2)value=f.idleChatter?L"On":L"Off";
  else if(row==20)value=controls::WideGarments[(std::min)(1u,f.garment)];
  if(value){Text(dc,value,174,y,212,24,tc,true);continue;}
  const float low=core==2||core==4?0.f:1.f;const float fraction=(std::max)(0.f,(std::min)(1.f,(c.values[core]-low)/(100-low)));const int px=trackLeft+int((trackRight-trackLeft)*fraction);
  Box(dc,trackLeft,y+11,trackRight-trackLeft,3,line);Box(dc,trackLeft,y+11,px-trackLeft,3,accent);Box(dc,px-2,y+7,4,11,tc);
  swprintf_s(number,L"%.0f",c.values[core]);Text(dc,number,342,y,44,24,tc,true);
 }
 Box(dc,14,Menu::StatusY,width-28,1,line);Text(dc,f.transformAvailable?L"Live":f.anatomyVisible?L"Transform unavailable":L"Waiting for character",14,Menu::StatusY+4,372,20,f.transformAvailable?dim:accent);
 Text(dc,Menu::WideNavigation,14,Menu::StatusY+26,372,20,dim);wchar_t help[96]{};
 if(f.teachingActive)swprintf_s(help,L"Ejaculation %.1fs",f.teachingSeconds);else wcscpy_s(help,L"J Ejaculation   F8 Reset");Text(dc,help,14,Menu::StatusY+48,372,20,dim);
 }
 RestoreDC(dc,saved);DeleteObject(heading);DeleteObject(font);
}
OverlayPanel::OverlayPanel(HWND parent,Read read,Write write,ReadFeatures features,WriteFeature action,bool authorized):parent_(parent),read_(std::move(read)),write_(std::move(write)),features_(std::move(features)),action_(std::move(action)),probe_(PanelProbe::FromEnvironment(parent,authorized)),thread_([this]{Run();}){}
OverlayPanel::OverlayPanel(HWND parent,Read read,Write write,ReadClinical clinical,WriteClinical action,bool authorized):OverlayPanel(parent,std::move(read),std::move(write),[clinical]{FeatureState f;if(clinical){auto c=clinical();f.throbMode=unsigned(c[0]);f.idleChatter=c[1]!=0;f.garment=unsigned(c[2]);}return f;},[action](FeatureAction a,float value){if(action){if(a==FeatureAction::SetGarment)action(18,value);else if(a==FeatureAction::ResetDefaults)action(19,0);}},authorized){}
void OverlayPanel::Run(){
 WNDCLASSW wc{};wc.lpfnWndProc=Procedure;wc.hInstance=GetModuleHandleW(nullptr);wc.lpszClassName=L"MaleMod.Anatomy.Overlay";wc.hCursor=LoadCursorW(nullptr,MAKEINTRESOURCEW(32512));RegisterClassW(&wc);
 auto window=CreateWindowExW(WS_EX_TOOLWINDOW|WS_EX_NOACTIVATE|WS_EX_LAYERED,wc.lpszClassName,L"MaleMod anatomy",WS_POPUP,0,0,width,height,parent_,nullptr,wc.hInstance,this);
 if(!window)return;window_.store(window);SetLayeredWindowAttributes(window,0,245,LWA_ALPHA);Resize();SetTimer(window,1,40,nullptr);
 if(probe_.Enabled()){PollKeys(true);try{probe_.Ready(parent_,window);}catch(const std::exception&){probe_.Disable();OutputDebugStringW(L"MaleMod: owned panel probe ready receipt failed\n");}}
 MSG msg{};while(!stop_.load()&&GetMessageW(&msg,nullptr,0,0)>0){TranslateMessage(&msg);DispatchMessageW(&msg);}if(IsWindow(window))DestroyWindow(window);window_.store(nullptr);
}
OverlayPanel::~OverlayPanel(){stop_=true;auto w=window_.load();if(w)PostMessageW(w,WM_CLOSE,0,0);if(thread_.joinable())thread_.join();OverlayInputPublish(nullptr,false,false);}
void OverlayPanel::Resize(){auto w=window_.load();if(w){RECT r{};GetClientRect(parent_,&r);POINT origin{0,0};ClientToScreen(parent_,&origin);const int logicalW=Open()?width:Menu::CollapsedWidth,logicalH=Open()?height:Menu::CollapsedHeight;const float scale=(std::max)(.5f,(std::min)(1.f,(std::min)(float(r.bottom-16)/logicalH,float(r.right-16)/logicalW)));SetWindowPos(w,nullptr,origin.x+int(14*scale),origin.y+int(14*scale),int(logicalW*scale),int(logicalH*scale),SWP_NOACTIVATE|SWP_NOZORDER);}}
void OverlayPanel::Adjust(int direction,bool shift){
 const unsigned row=navigation_.selected;auto f=Features();const int core=Menu::CoreIndex(row);
 if(core>=0)WriteCore(unsigned(core),navigation_.Adjust(read_(),direction,shift));
 else if(row==1){Action(FeatureAction::CancelTeaching);Action(FeatureAction::SetThrob,float((int(f.throbMode)+direction+4)%4));}
 else if(row==2){Action(FeatureAction::CancelTeaching);Action(FeatureAction::SetIdleChatter,f.idleChatter?0.f:1.f);}
 else if(row==20)Action(FeatureAction::SetGarment,f.garment?0.f:1.f);
}
void OverlayPanel::Click(int x,int y){
 if(!Open()){expanded_=true;Resize();return;}if(y<36){expanded_=false;dragging_=-1;Resize();return;}
 for(unsigned row=0;row<Menu::RowCount;row++)if(y>=Menu::RowY(row)&&y<Menu::RowY(row)+24){navigation_.selected=row;const int core=Menu::CoreIndex(row);if(core>0&&x>=trackLeft-8&&x<=trackRight+8){dragging_=core;WriteCore(unsigned(core),Value(unsigned(core),x));}else if(core<=0)Adjust(1,false);break;}
}
void OverlayPanel::PollKeys(bool foreground){
 OverlayInputPublish(parent_,Open(),Features().anatomyVisible,probe_.Private());
 if(foreground_&&!foreground){focusLost_=true;Action(FeatureAction::CancelTeaching);}constexpr int codes[]={VK_F6,VK_UP,VK_DOWN,VK_LEFT,VK_RIGHT,VK_RETURN,VK_SPACE,VK_F8,'J',VK_F9};std::array<bool,10> now{},edge{};
 const auto keyState=[this](int key){return probe_.Private()?probe_.KeyState(key):OverlayInputPoll(key);};for(unsigned i=0;i<10;i++){now[i]=(keyState(codes[i])&0x8000)!=0;edge[i]=foreground&&foreground_&&now[i]&&!keys_[i];}keys_=now;foreground_=foreground;if(!foreground)return;
 if(edge[0]){expanded_=!Open();dragging_=-1;Resize();}OverlayInputPublish(parent_,Open(),Features().anatomyVisible,probe_.Private());if(!Features().anatomyVisible)return;
 if(edge[8])Action(FeatureAction::ToggleTeaching);if(edge[9])Action(FeatureAction::ToggleLighting);if(!Open())return;
 if(edge[1])navigation_.Move(-1);if(edge[2])navigation_.Move(1);if(edge[7])Action(FeatureAction::ResetDefaults);
 const int direction=edge[3]?-1:edge[4]?1:0;if(direction)Adjust(direction,(keyState(VK_SHIFT)&0x8000)!=0);
}
LRESULT CALLBACK OverlayPanel::Procedure(HWND window,UINT message,WPARAM wp,LPARAM lp){
 auto* self=reinterpret_cast<OverlayPanel*>(GetWindowLongPtrW(window,GWLP_USERDATA));if(message==WM_NCCREATE){self=static_cast<OverlayPanel*>(reinterpret_cast<CREATESTRUCTW*>(lp)->lpCreateParams);SetWindowLongPtrW(window,GWLP_USERDATA,reinterpret_cast<LONG_PTR>(self));}if(!self)return DefWindowProcW(window,message,wp,lp);
 RECT client{};GetClientRect(window,&client);const int x=client.right?GET_X_LPARAM(lp)*(self->Open()?width:Menu::CollapsedWidth)/client.right:0;const int y=client.bottom?GET_Y_LPARAM(lp)*(self->Open()?height:Menu::CollapsedHeight)/client.bottom:0;
 switch(message){
 case WM_MOUSEACTIVATE:return MA_NOACTIVATE;
 case WM_LBUTTONDOWN:self->Click(x,y);if(self->dragging_>=0)SetCapture(window);InvalidateRect(window,nullptr,FALSE);return 0;
 case WM_MOUSEMOVE:if(self->dragging_>=1&&(wp&MK_LBUTTON)){self->WriteCore(unsigned(self->dragging_),Value(unsigned(self->dragging_),x));InvalidateRect(window,nullptr,FALSE);}return 0;
 case WM_LBUTTONUP:case WM_CANCELMODE:self->dragging_=-1;if(GetCapture()==window)ReleaseCapture();return 0;
 case WM_TIMER:{PanelProbeRequest request;const bool probe=self->probe_.Private(),command=self->probe_.Read(request);const bool foreground=IsWindow(self->parent_)&&(probe||(IsWindowVisible(self->parent_)&&GetForegroundWindow()==self->parent_));self->PollKeys(foreground);
  if(command&&request.action==PanelProbeRequest::Action::Reset&&self->Open()&&self->Features().anatomyVisible)self->Action(FeatureAction::ResetDefaults);
  const auto features=self->Features();const bool visible=foreground&&features.anatomyVisible;self->Resize();if(bool(IsWindowVisible(window))!=visible)ShowWindow(window,visible?SW_SHOWNOACTIVATE:SW_HIDE);
  const auto controls=self->read_();if(visible&&(features!=self->paintedFeatures_||!self->painted_||controls.values!=self->paintedControls_.values||self->Open()!=self->paintedExpanded_||self->navigation_.selected!=self->paintedSelection_))InvalidateRect(window,nullptr,FALSE);
  if(command){try{const bool captured=request.action==PanelProbeRequest::Action::Capture&&self->probe_.Capture(window,request.revision);const auto f=self->Features();self->probe_.Record(self->parent_,window,request,self->read_().values,{float(f.throbMode),f.idleChatter?1.f:0.f,float(f.garment)},self->navigation_.selected,self->Open(),captured,visible,features.anatomyVisible,foreground);}catch(const std::exception&){self->probe_.Disable();OutputDebugStringW(L"MaleMod: owned panel probe command receipt failed\n");}}
  self->probe_.EndTick();if(command&&request.action==PanelProbeRequest::Action::Press)self->PollKeys(foreground);if(!IsWindow(self->parent_))PostMessageW(window,WM_CLOSE,0,0);return 0;}
 case WM_PRINTCLIENT:Paint(reinterpret_cast<HDC>(wp),self->read_(),self->Open(),client.right,client.bottom,self->navigation_.selected,self->Features());return 0;
 case WM_ERASEBKGND:return 1;
 case WM_SIZE:self->painted_=false;InvalidateRect(window,nullptr,FALSE);return 0;
 case WM_PAINT:{PAINTSTRUCT paint{};auto dc=BeginPaint(window,&paint);const auto controls=self->read_();const auto features=self->Features();const bool expanded=self->Open();
  if(client.right>0&&client.bottom>0){auto back=CreateCompatibleDC(dc);auto bitmap=CreateCompatibleBitmap(dc,client.right,client.bottom);if(back&&bitmap){auto old=SelectObject(back,bitmap);Paint(back,controls,expanded,client.right,client.bottom,self->navigation_.selected,features);BitBlt(dc,0,0,client.right,client.bottom,back,0,0,SRCCOPY);SelectObject(back,old);self->painted_=true;}if(bitmap)DeleteObject(bitmap);if(back)DeleteDC(back);}
  self->paintedControls_=controls;self->paintedFeatures_=features;self->paintedExpanded_=expanded;self->paintedSelection_=self->navigation_.selected;EndPaint(window,&paint);return 0;}
 case WM_CLOSE:DestroyWindow(window);return 0;
 case WM_DESTROY:self->expanded_=false;PostQuitMessage(0);return 0;
 }return DefWindowProcW(window,message,wp,lp);
}
}


