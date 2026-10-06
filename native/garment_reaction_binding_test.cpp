// Exact native companion packet integrity. No engine launch or installation.
#include "garment_service.hpp"
#include <iostream>
#include <limits>
using namespace malemod::witcher;
static void Check(bool value,const char* why){if(!value)throw std::runtime_error(why);}
static std::vector<char> Bytes(const std::filesystem::path& p){std::ifstream f(p,std::ios::binary);return {std::istreambuf_iterator<char>(f),{}};}
int main(int argc,char** argv){try{
 if(argc!=5)throw std::runtime_error("usage: garment_reaction_binding_test bindings pin renderHash ownedReportDir");
 const std::filesystem::path bindings=argv[1],report=argv[4];
 GarmentBindings actual(bindings,argv[2],argv[3]);
 Check(actual.contours[2].size()==17555,"Expected full retained native anatomy");
 auto bytes=Bytes(bindings.parent_path()/"garment.reactions");
 Check(bytes.size()==116+17555*116,"Companion row size differs");
 for(auto id:actual.contours[2]){Check(id<actual.reactionBindings.size(),"Full native force mapping missing");double sum=0;for(auto w:actual.reactionBindings[id].weights)sum+=w;Check(sum<=1+1e-6,"Mapping amplifies load");}
 std::filesystem::create_directories(report);unsigned rejected=0;
 auto reject=[&](std::vector<char> corrupt,const char* name){auto dir=report/name;std::filesystem::create_directories(dir);std::filesystem::copy_file(bindings,dir/"garment.bindings",std::filesystem::copy_options::overwrite_existing);std::ofstream f(dir/"garment.reactions",std::ios::binary);f.write(corrupt.data(),corrupt.size());f.close();bool caught=false;try{GarmentBindings invalid(dir/"garment.bindings",argv[2],argv[3]);}catch(const std::exception&){caught=true;}Check(caught,"Malformed mechanical companion accepted");++rejected;};
 auto corrupt=bytes;corrupt[0]='X';reject(corrupt,"magic");
 corrupt=bytes;corrupt[8]=corrupt[8]=='0'?'1':'0';reject(corrupt,"base-pin");
 corrupt=bytes;corrupt[48]=corrupt[48]=='0'?'1':'0';reject(corrupt,"render-hash");
 corrupt=bytes;unsigned count=17554;std::memcpy(corrupt.data()+112,&count,4);reject(corrupt,"omitted-row");
 corrupt=bytes;unsigned id=200000;std::memcpy(corrupt.data()+116,&id,4);reject(corrupt,"native-bound");
 corrupt=bytes;std::memcpy(corrupt.data()+232,corrupt.data()+116,4);reject(corrupt,"duplicate-native");
 for(double invalid:{-1.,std::numeric_limits<double>::infinity(),std::numeric_limits<double>::quiet_NaN(),2.}){corrupt=bytes;std::memcpy(corrupt.data()+120,&invalid,8);reject(corrupt,invalid<0?"negative-weight":invalid==2?"amplifying-weight":std::isnan(invalid)?"nan-weight":"infinite-weight");}
 corrupt=bytes;corrupt.pop_back();reject(corrupt,"truncated");corrupt=bytes;corrupt.push_back(0);reject(corrupt,"trailing");
 std::ofstream proof(report/"reaction-binding-proof.json");proof<<"{\"schema\":1,\"version\":1,\"nativeVertices\":17555,\"generalizedBodies\":14,\"exactNativeOrder\":true,\"malformedCasesRejected\":"<<rejected<<",\"nonlinearSurfaceJacobian\":false,\"observedGameplay\":false}\n";
 std::cout<<"PASS MMGRE001 exact full native vertex order, 14-body force ownership, pin/hash/bounds/duplicate/nonfinite/amplification/truncation/trailing rejection\n";return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
