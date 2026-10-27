#include "engine/rigid_world_frame.hpp"
#include <cstring>
#include <iostream>
#include <limits>
#include <string>

namespace R=malemod::witcher::rigid_world;
static void Check(bool value,const char* message){if(!value)throw std::runtime_error(message);}
template<class F>static void Reject(F action,const char* message){bool rejected=false;try{action();}catch(const std::invalid_argument&){rejected=true;}Check(rejected,message);}
static std::vector<D3D12_INPUT_ELEMENT_DESC> Layout(){
 return {{"POSITION",0,DXGI_FORMAT_R32G32B32_FLOAT,0,0,D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA,0},
 {"TEXCOORD",0,DXGI_FORMAT_R16G16_FLOAT,1,0,D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA,0},
 {"NORMAL",0,DXGI_FORMAT_R10G10B10A2_UNORM,2,0,D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA,0},
 {"COLOR",0,DXGI_FORMAT_R8G8B8A8_UNORM,3,0,D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA,0},
 {"INSTANCE_TRANSFORM",0,DXGI_FORMAT_R32G32B32A32_FLOAT,7,64,D3D12_INPUT_CLASSIFICATION_PER_INSTANCE_DATA,1},
 {"INSTANCE_TRANSFORM",1,DXGI_FORMAT_R32G32B32A32_FLOAT,7,80,D3D12_INPUT_CLASSIFICATION_PER_INSTANCE_DATA,1},
 {"INSTANCE_TRANSFORM",2,DXGI_FORMAT_R32G32B32A32_FLOAT,7,96,D3D12_INPUT_CLASSIFICATION_PER_INSTANCE_DATA,1},
 {"INSTANCE_LOD_PARAMS",0,DXGI_FORMAT_R32G32B32A32_FLOAT,7,48,D3D12_INPUT_CLASSIFICATION_PER_INSTANCE_DATA,1}};
}
static void UnchangedAfterRejection(std::vector<D3D12_INPUT_ELEMENT_DESC> value){auto old=value;Reject([&]{R::Rewrite(value);},"Malformed layout was accepted");Check(value.size()==old.size()&&!std::memcmp(value.data(),old.data(),old.size()*sizeof(old[0])),"Rejected layout was partially rewritten");}
int main(){try{
 unsigned checks=0;
 auto value=Layout(),old=value;Check(R::Rewrite(value)==4,"Expected first unused slot4");
 for(unsigned i=0;i<value.size();++i){
  if(i>=4&&i<=6){Check(value[i].InputSlot==4&&value[i].AlignedByteOffset==(i-4)*16&&value[i].InstanceDataStepRate==1,"Owned transform layout differs");Check(value[i].SemanticName==old[i].SemanticName&&value[i].SemanticIndex==old[i].SemanticIndex&&value[i].Format==old[i].Format,"Transform semantic changed");}
  else Check(!std::memcmp(&value[i],&old[i],sizeof(value[i])),"Unrelated native instance attribute changed");
 }++checks;
 auto none=Layout();none.erase(none.begin()+4,none.begin()+7);auto saved=none;Check(R::Rewrite(none)==UINT_MAX&&!std::memcmp(none.data(),saved.data(),none.size()*sizeof(none[0])),"No-instance fixture changed");++checks;
 auto partial=Layout();partial.erase(partial.begin()+5);UnchangedAfterRejection(partial);++checks;
 auto duplicate=Layout();duplicate[5].SemanticIndex=0;UnchangedAfterRejection(duplicate);++checks;
 auto format=Layout();format[5].Format=DXGI_FORMAT_R32G32B32_FLOAT;UnchangedAfterRejection(format);++checks;
 auto vertex=Layout();vertex[4].InputSlotClass=D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA;UnchangedAfterRejection(vertex);++checks;
 auto rate=Layout();rate[6].InstanceDataStepRate=0;UnchangedAfterRejection(rate);++checks;
 auto slot=Layout();slot[1].InputSlot=32;UnchangedAfterRejection(slot);++checks;
 auto unknown=Layout();unknown[5].SemanticIndex=3;UnchangedAfterRejection(unknown);++checks;
 auto full=Layout();for(unsigned i=0;i<32;++i)full.push_back({"SLOT_OCCUPANCY",i,DXGI_FORMAT_R32_FLOAT,i,0,D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA,0});UnchangedAfterRejection(full);++checks;
 auto mixed=Layout();mixed[4].SemanticName="instance_transform";Check(R::Rewrite(mixed)==4,"Semantic comparison was not case insensitive");++checks;
 const auto rows=R::Rows({55.25,-21.5,33.125});Check(rows==std::array<float,12>{1,0,0,55.25f,0,1,0,-21.5f,0,0,1,33.125f},"World origin matrix differs");
 const std::array<float,3> desired{55.5f,-21.75f,34.f},relative{.25f,-.25f,.875f};
 for(unsigned i=0;i<3;++i)Check(rows[i*4]*relative[0]+rows[i*4+1]*relative[1]+rows[i*4+2]*relative[2]+rows[i*4+3]==desired[i],"Owned matrix did not recover desired world point");++checks;
 Reject([]{R::Rows({std::numeric_limits<double>::quiet_NaN(),0,0});},"NaN origin accepted");++checks;
 Reject([]{R::Rows({0,std::numeric_limits<double>::infinity(),0});},"Infinite origin accepted");++checks;
 Reject([]{R::Rows({0,0,(std::numeric_limits<double>::max)()});},"Float-overflow origin accepted");++checks;
 Check(R::Rows({0,0,0})==std::array<float,12>{1,0,0,0,0,1,0,0,0,0,1,0},"Zero-origin identity differs");++checks;
 std::cout<<checks<<" rigid world-frame CPU checks passed; no device/game/window created\n";return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
