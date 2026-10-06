#include "garment_failure_capture.hpp"
#include <iostream>
#include <cstring>
#include <string>
using namespace malemod::witcher::garment_capture;
static void Check(bool b,const char* message){if(!b)throw std::runtime_error(message);}
int main(int argc,char** argv){try{
 if(argc!=2)throw std::invalid_argument("Expected fresh owned test directory");auto dir=std::filesystem::path(argv[1]);std::filesystem::create_directories(dir);
 Input in;in.characterEpoch=4;in.topologyRevision=7;in.restRevision=11;in.deltaTime=.013;in.gravity={.1,.2,-9};in.anatomyMass=16.5;
 in.anatomy.resize(8);for(unsigned i=0;i<8;i++){in.anatomy[i].position={double(i),i*.2,i*.3};in.anatomy[i].lineage.donors[0]={Surface::Anatomy,i,1};}
 in.waist.assign(in.anatomy.begin(),in.anatomy.begin()+3);in.opening=in.waist;in.rearStraps[0]=in.waist;in.rearStraps[1]=in.waist;
 in.anatomyTriangles={{0,1,2},{3,4,5}};in.bodySurface=in.waist;in.bodyTriangles={{0,1,2}};in.bodyContacts={{{0,0,0},{0,0,1},.2}};
 for(unsigned k=0;k<4;k++)in.anatomyRegions[k]={2*k,2*k+1};
 for(unsigned i=0;i<in.waist[0].lineage.donors.size();i++)in.waist[0].lineage.donors[i]={Surface::Body,i,1./in.waist[0].lineage.donors.size()};
 auto path=dir/L"version6.input";WriteInput(path,in);auto read=ReadInput(path);
 Check(read.anatomyMass==in.anatomyMass,"Captured measured generalized mass changed");
 Check(read.characterEpoch==4&&read.topologyRevision==7&&read.restRevision==11&&read.deltaTime==in.deltaTime&&read.gravity==in.gravity,"Capture scalar fields changed");
 Check(read.anatomyRegions==in.anatomyRegions&&read.anatomyTriangles==in.anatomyTriangles&&read.bodyTriangles==in.bodyTriangles,"Complete topology/semantic groups changed");
 Check(read.anatomy.size()==8&&read.bodySurface.size()==3,"Capture removed anatomy/body samples");
 for(unsigned i=0;i<in.waist[0].lineage.donors.size();i++){const auto& a=read.waist[0].lineage.donors[i];const auto& b=in.waist[0].lineage.donors[i];Check(a.surface==b.surface&&a.vertex==b.vertex&&a.weight==b.weight,"Expanded exact material lineage changed");}
 for(unsigned i=0;i<8;i++)Check(read.anatomy[i].position==in.anatomy[i].position&&read.anatomy[i].lineage.donors[0].vertex==i&&read.anatomy[i].lineage.donors[0].weight==1,"Capture donor lineage changed");
 std::ifstream f(path,std::ios::binary);std::vector<char> bytes((std::istreambuf_iterator<char>(f)),{});
 auto write=[&](const wchar_t* name,const std::vector<char>& b){std::ofstream out(dir/name,std::ios::binary);out.write(b.data(),b.size());};
 auto version5=bytes;version5.resize(version5.size()-sizeof(in.anatomyMass));version5[7]='5';write(L"version5.input",version5);
 auto old5=ReadInput(dir/L"version5.input");Check(old5.anatomyMass==0&&old5.anatomyRegions==in.anatomyRegions&&old5.waist[0].lineage.donors[15].weight==in.waist[0].lineage.donors[15].weight,"Version5 compatibility lost expanded lineage or invented a mass calibration");
 auto writeLegacy=[&](unsigned version){std::ofstream out(dir/(L"version"+std::to_wstring(version)+L".input"),std::ios::binary);auto put=[&](const auto& x){out.write(reinterpret_cast<const char*>(&x),sizeof(x));};std::string magic="MMGFC00"+std::to_string(version);out.write(magic.data(),8);put(in.frame.origin);put(in.frame.lateral);put(in.frame.forward);put(in.frame.up);put(in.characterEpoch);put(in.topologyRevision);if(version>1)put(in.restRevision);put(in.gravity);put(in.deltaTime);
 auto samples=[&](const auto& rows){std::uint32_t n=unsigned(rows.size());put(n);for(const auto& s:rows){put(s.position);put(s.normal);for(unsigned i=0;i<4;i++){const auto& d=s.lineage.donors[i];put(d.surface);put(d.vertex);put(d.weight);}}};
 for(const auto* rows:{&in.waist,&in.opening,&in.anatomy,&in.rearStraps[0],&in.rearStraps[1]})samples(*rows);
 std::uint32_t n=unsigned(in.anatomyTriangles.size());put(n);for(auto t:in.anatomyTriangles)put(t);n=unsigned(in.bodyContacts.size());put(n);for(auto c:in.bodyContacts){put(c.a);put(c.b);put(c.radius);}
 if(version>=3){samples(in.bodySurface);n=unsigned(in.bodyTriangles.size());put(n);for(auto t:in.bodyTriangles)put(t);}if(version>=4)for(const auto& region:in.anatomyRegions){n=unsigned(region.size());put(n);for(auto id:region)put(id);}};
 for(unsigned version=1;version<=4;version++){writeLegacy(version);auto old=ReadInput(dir/(L"version"+std::to_wstring(version)+L".input"));Check(old.anatomy.size()==8&&(version<3||old.bodySurface.size()==3)&&old.anatomyRegions==(version==4?in.anatomyRegions:AnatomyRegions{}),"Legacy full anatomy/body/groups compatibility failed");for(unsigned i=4;i<old.waist[0].lineage.donors.size();i++)Check(old.waist[0].lineage.donors[i].weight==0,"Legacy capture invented extra donors");}
 auto rejected=[&](const wchar_t* name){bool failed=false;try{ReadInput(dir/name);}catch(const std::runtime_error&){failed=true;}Check(failed,"Malformed capture was accepted");};
 for(double mass:{-1.,std::numeric_limits<double>::infinity(),std::numeric_limits<double>::quiet_NaN()}){auto invalidMass=in;invalidMass.anatomyMass=mass;WriteInput(dir/L"invalid-mass.input",invalidMass);rejected(L"invalid-mass.input");}
 auto bad=in;bad.anatomyRegions[1][0]=bad.anatomyRegions[0][0];WriteInput(dir/L"overlap.input",bad);rejected(L"overlap.input");
 bad=in;bad.anatomyRegions[0][0]=8;WriteInput(dir/L"outside.input",bad);rejected(L"outside.input");
 auto truncated=bytes;truncated.pop_back();write(L"truncated.input",truncated);rejected(L"truncated.input");
 auto trailing=bytes;trailing.push_back(0);write(L"trailing.input",trailing);rejected(L"trailing.input");
 auto capacity=bytes;std::uint32_t oversized=unsigned(Lineage{}.donors.size()+1);std::memcpy(capacity.data()+8,&oversized,sizeof(oversized));write(L"capacity.input",capacity);rejected(L"capacity.input");
 std::cout<<"PASS full anatomy/body/semantic capture version6 exact expanded lineage and measured mass roundtrip, versions1..5 compatibility and invalid mass/capacity/overlapping/outside/truncated/trailing rejection\n";return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
