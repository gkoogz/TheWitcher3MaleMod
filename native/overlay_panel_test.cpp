#define NOMINMAX
#include "overlay_panel.hpp"
#include <fstream>
#include <iostream>
using namespace malemod::witcher;
static void Check(bool b,const char* text){if(!b)throw std::runtime_error(text);}
int wmain(int argc,wchar_t** argv){try{
 Check(argc==2,"Usage: overlay_panel_test owned-preview.bmp");
 malemod::surface::Controls c;
 OverlayNavigation navigation;navigation.Move(-1);Check(navigation.selected==17,"Selection does not wrap upward");navigation.Move(1);Check(navigation.selected==0,"Selection does not wrap downward");
 Check(navigation.Adjust(c,1,true)==0&&navigation.Adjust(c,-1,false)==1,"State does not match Wolverine cycling");
 for(unsigned i=1;i<18;i++){navigation.selected=i;Check(navigation.Adjust(c,1,false)==51&&navigation.Adjust(c,-1,true)==45,"Arrow/Shift step differs from Wolverine");}
 for(unsigned i=1;i<18;i++){
  Check(OverlayPanel::Hit(OverlayPanel::trackLeft,OverlayPanel::Row(i)+12)==int(i),"Slider hit region selects wrong control");
  auto low=OverlayPanel::Value(i,OverlayPanel::trackLeft-100),high=OverlayPanel::Value(i,OverlayPanel::trackRight+100);auto candidate=c;candidate.values[i]=low;malemod::surface::wire::Validate(candidate);candidate.values[i]=high;malemod::surface::wire::Validate(candidate);
  Check(low==float(i==2||i==4?0:1)&&high==100,"Slider limits differ from Base contract");
 }
 Check(OverlayPanel::Hit(80,OverlayPanel::Row(1))==-1,"Label hit edits a slider");
 auto dc=CreateCompatibleDC(nullptr);BITMAPINFO info{};info.bmiHeader.biSize=40;info.bmiHeader.biWidth=OverlayPanel::width;info.bmiHeader.biHeight=-OverlayPanel::height;info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;info.bmiHeader.biCompression=BI_RGB;void* data=nullptr;auto bitmap=CreateDIBSection(dc,&info,DIB_RGB_COLORS,&data,nullptr,0);Check(bitmap&&data&&dc,"Preview allocation failed");auto old=SelectObject(dc,bitmap);
 OverlayPanel::Paint(dc,c,true,OverlayPanel::width,OverlayPanel::height);
 BITMAPFILEHEADER header{};header.bfType=0x4d42;header.bfOffBits=sizeof(header)+sizeof(BITMAPINFOHEADER);header.bfSize=header.bfOffBits+OverlayPanel::width*OverlayPanel::height*4;
 std::ofstream f(argv[1],std::ios::binary);Check(bool(f),"Preview output failed");f.write(reinterpret_cast<const char*>(&header),sizeof(header));f.write(reinterpret_cast<const char*>(&info.bmiHeader),sizeof(info.bmiHeader));f.write(static_cast<const char*>(data),OverlayPanel::width*OverlayPanel::height*4);Check(bool(f),"Preview write failed");SelectObject(dc,old);DeleteObject(bitmap);DeleteDC(dc);
 std::cout<<"PASS: 17 slider hit regions and limits match Base, native GDI panel renders all 18 controls; game visibility/input and focus remain unverified\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
