#pragma once
#include <windows.h>
#include <malemod/surface/wire.hpp>
#include <malemod/controls/canonical_menu.hpp>
#include <array>
#include <functional>
#include <atomic>
#include <thread>
#include "overlay_navigation.hpp"
#include "overlay_panel_probe.hpp"
namespace malemod::witcher {
class OverlayPanel {
 public:
 using Read=std::function<surface::Controls()>;
 using Write=std::function<bool(unsigned,float)>;
 using FeatureState=controls::menu::State;
 using FeatureAction=controls::menu::Action;
 using ReadFeatures=std::function<FeatureState()>;
 using WriteFeature=std::function<void(FeatureAction,float)>;
 // Compatibility for the previous fixture; production uses typed features.
 using ReadClinical=std::function<std::array<float,3>()>;
 using WriteClinical=std::function<void(unsigned,float)>;
 static constexpr int width=controls::menu::Width,height=controls::menu::Height,trackLeft=controls::menu::TrackLeft,trackRight=controls::menu::TrackRight;
 static int Row(unsigned core){return controls::menu::RowY(controls::menu::MenuRow(core));}
 static int Hit(int x,int y){for(unsigned i=1;i<18;i++)if(x>=trackLeft-8&&x<=trackRight+8&&y>=Row(i)&&y<Row(i)+24)return int(i);return -1;}
 static float Value(unsigned index,int x){return controls::menu::SliderValue(index,x);}
 static void Paint(HDC,const surface::Controls&,bool expanded,int w,int h,unsigned selected=0,FeatureState features={});
 OverlayPanel(HWND,Read,Write,ReadFeatures,WriteFeature,bool ownedProbeAuthorized=false);
 OverlayPanel(HWND,Read,Write,ReadClinical clinical={},WriteClinical action={},bool ownedProbeAuthorized=false);
 ~OverlayPanel();
 bool Open()const{return expanded_.load(std::memory_order_acquire);}
 bool ConsumeFocusLoss(){return focusLost_.exchange(false);}
 private:
 HWND parent_=nullptr;std::atomic<HWND> window_{nullptr};Read read_;Write write_;ReadFeatures features_;WriteFeature action_;
 FeatureState paintedFeatures_{};
 PanelProbe probe_;std::atomic<bool> expanded_{true},stop_{false},focusLost_{false};
 int dragging_=-1;OverlayNavigation navigation_;
 std::array<bool,10> keys_{};bool foreground_=false;
 surface::Controls paintedControls_;unsigned paintedSelection_=0;bool paintedExpanded_=false,painted_=false;
 FeatureState Features()const{return features_?features_():FeatureState{};}
 void Action(FeatureAction action,float value=0){if(action_)action_(action,value);}
 void WriteCore(unsigned index,float value){Action(FeatureAction::CancelTeaching);write_(index,value);}
 void Adjust(int direction,bool shift);void PollKeys(bool foreground);
 void Click(int x,int y);void Resize();void Run();
 static LRESULT CALLBACK Procedure(HWND,UINT,WPARAM,LPARAM);
 std::thread thread_;
};
}
