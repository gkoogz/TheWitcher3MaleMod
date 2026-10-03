#pragma once
#include <windows.h>
#include <malemod/surface/wire.hpp>
#include <array>
#include <functional>
#include <atomic>
#include <thread>
#include "overlay_navigation.hpp"

namespace malemod::witcher {
class OverlayPanel {
 public:
 using Read=std::function<surface::Controls()>;
 using Write=std::function<bool(unsigned,float)>;
 static constexpr int width=420,height=680,trackLeft=202,trackRight=400;
 static int Row(unsigned index){return index<10?118+27*int(index-1):394+27*int(index-10);}
 static int Hit(int x,int y){for(unsigned i=1;i<18;i++)if(x>=trackLeft-8&&x<=trackRight+8&&y>=Row(i)&&y<Row(i)+25)return int(i);return -1;}
 static float Value(unsigned index,int x){const float low=index==2||index==4?0.f:1.f;const float fraction=(float(x)-trackLeft)/(trackRight-trackLeft);return std::round(low+(100-low)*(std::max)(0.f,(std::min)(1.f,fraction)));}
 static void Paint(HDC,const surface::Controls&,bool expanded,int w,int h,unsigned selected=0);
 OverlayPanel(HWND parent,Read read,Write write);
 ~OverlayPanel();
 bool Open()const{return expanded_.load(std::memory_order_acquire);}
 bool ConsumeFocusLoss(){return focusLost_.exchange(false);}
 private:
 HWND parent_=nullptr;std::atomic<HWND> window_{nullptr};Read read_;Write write_;
 std::atomic<bool> expanded_{false},stop_{false},focusLost_{false};std::thread thread_;
 int dragging_=-1;
 OverlayNavigation navigation_;
 std::array<bool,5> keys_{};bool foreground_=false;
 void PollKeys(bool foreground);
 void Click(int x,int y);void Resize();
 static LRESULT CALLBACK Procedure(HWND,UINT,WPARAM,LPARAM);
};
}
