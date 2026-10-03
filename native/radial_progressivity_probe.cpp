// Offline artifact exporter for target ramp quality inspection. Never installed.
#include "surface_pipeline.hpp"
#include <fstream>
#include <iostream>
#include <filesystem>
#include <iomanip>
using namespace malemod::witcher;
namespace surface=malemod::surface;
template<class T>void Write(const std::filesystem::path& p,const std::vector<T>& v){std::ofstream f(p,std::ios::binary);f.write(reinterpret_cast<const char*>(v.data()),v.size()*sizeof(T));if(!f)throw std::runtime_error("Cannot write radial audit artifact");}
int wmain(int argc,wchar_t** argv){try{
 if(argc!=5)throw std::runtime_error("Usage: radial_progressivity_probe worker binding pin output");
 const std::filesystem::path out=argv[4];if(std::filesystem::exists(out))throw std::runtime_error("Use a fresh owned output");std::filesystem::create_directories(out);
 const std::wstring pinW=argv[3];std::string pin;for(auto c:pinW){if(c>127)throw std::runtime_error("Base pin must be ASCII");pin.push_back(static_cast<char>(c));}
 TargetSurface target(argv[2],pin);Write(out/"queries.bin",target.CollarQueries());
 std::ofstream report(out/"cases.json");report<<std::setprecision(9)<<"[";unsigned count=0;
 auto run=[&](const std::string& label,surface::Controls controls){SurfacePipeline pipeline(argv[1],argv[2],pin);pipeline.Initialize({});surface::wire::Request q;q.controls=controls;auto f=pipeline.Evaluate(q);
   for(unsigned lod=0;lod<2;lod++)Write(out/(label+"-lod"+std::to_string(lod)+".bin"),f.targetPositions[lod]);
   Write(out/(label+"-collar.bin"),f.source.collarDisplacements);Write(out/(label+"-source.bin"),surface::wire::Encode(f.source));
   const auto& m=f.source.collarMetric;
   if(count++)report<<",";report<<"{\"label\":\""<<label<<"\",\"overall\":"<<controls.values[1]<<",\"radius\":"<<m.radius<<",\"length\":"<<m.length<<",\"root\":["<<m.root.x<<","<<m.root.y<<","<<m.root.z<<"],\"axis\":["<<m.axis.x<<","<<m.axis.y<<","<<m.axis.z<<"],\"up\":["<<m.up.x<<","<<m.up.y<<","<<m.up.z<<"]}";report.flush();std::cout<<label<<" exported\n"<<std::flush;
 };
 run("neutral",{});
 for(float overall:{1.f,25.f,50.f,75.f,100.f}){surface::Controls c;c.values[1]=overall;run("overall-"+std::to_string(unsigned(overall)),c);}
 for(const auto& probe:std::array<std::pair<const char*,float>,3>{{{"overall-75-minus",74.9f},{"overall-75-plus",75.1f},{"overall-100-minus",99.9f}}}){surface::Controls c;c.values[1]=probe.second;run(probe.first,c);}
 for(unsigned control:{2u,3u,4u,5u,6u,7u,8u,9u,10u})for(unsigned side=0;side<2;side++){surface::Controls c;c.values[control]=side?100.f:((control==2||control==4)?0.f:1.f);run("control-"+std::to_string(control)+"-"+std::to_string(side),c);}
 surface::Controls c;for(unsigned i=1;i<18;i++)c.values[i]=100;run("combined-max",c);report<<"]";return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
