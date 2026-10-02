#include "skin_output.hpp"
#define NOMINMAX
#include <d3d11.h>
#include <d3dcompiler.h>
#include <wrl/client.h>
#include <algorithm>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
using Microsoft::WRL::ComPtr;
using namespace malemod::witcher::skin;
static void Check(bool b,const char* message){if(!b)throw std::runtime_error(message);}
static void HR(HRESULT hr){if(FAILED(hr))throw std::runtime_error("D3D11 SDK comparison failed HRESULT="+std::to_string(hr));}
static std::string Read(const std::string& p){std::ifstream f(p,std::ios::binary);Check(bool(f),"Missing input");return {std::istreambuf_iterator<char>(f),{}};}
static std::string Slice(const std::string& s,const char* start,const char* end){auto a=s.find(start),b=s.find(end,a);Check(a!=s.npos&&b!=s.npos,"SDK function delimiters changed");return s.substr(a,b-a);}
struct Prepared {std::array<float,4> position,normal,tangent;};
struct Result {std::array<float,4> position,normal,tangent;};
static_assert(sizeof(Result)==48&&sizeof(Prepared)==48);
class Oracle {
 ComPtr<ID3D11Device> device_;ComPtr<ID3D11DeviceContext> context_;ComPtr<ID3D11ComputeShader> shader_;
 public:
 Oracle(const std::string& sdk){
  HR(D3D11CreateDevice(nullptr,D3D_DRIVER_TYPE_WARP,nullptr,0,nullptr,0,D3D11_SDK_VERSION,&device_,nullptr,&context_));
  auto factory=Read(sdk+"/vertexFactory.fx"),packing=Read(sdk+"/include_computeRTData.fx");
  // Compile the installed implementation itself; SDK source stays external.
  std::string source=R"(
#pragma pack_matrix(row_major)
#define STRUCTBUFFER(T) StructuredBuffer<T>
#define PT_USHORT4N uint2
#define PT_USHORT4 uint2
#define PT_UBYTE4 uint
#define PT_UBYTE4N uint
#define PT_DEC4 uint
#define PT_COLOR uint
#define PT_FLOAT16_2 uint
#define PT_FLOAT16_4 uint2
)"+Slice(packing,"float4 UnPackUShort4N(","#ifdef RT_SHARED_VERTEX_DATA")+
  Slice(factory,"STRUCTBUFFER(float4x4) b_SkinBuffer","float4 ApplySkinningWithExtraData(")+R"(
ByteAddressBuffer raw : register(t1);
struct Prepared {float4 position;float4 normal;float4 tangent;};
StructuredBuffer<Prepared> prepared : register(t2);
struct Result {float4 position;float4 normal;float4 tangent;};
RWStructuredBuffer<Result> result : register(u0);
cbuffer Constants : register(b0) {float4 qs;float4 qb;uint count;uint mode;uint2 padding;};
[numthreads(64,1,1)] void main(uint3 tid:SV_DispatchThreadID) {
 uint i=tid.x;if(i>=count)return;
 float3 p=mode?prepared[i].position.xyz:UnPackUShort4N(raw.Load2(i*24)).xyz;
 float3 n=mode?prepared[i].normal.xyz:UnPackDec4(raw.Load(i*24+16)).xyz*2-1;
 float3 t=mode?prepared[i].tangent.xyz:UnPackDec4(raw.Load(i*24+20)).xyz*2-1;
 uint4 indices=UnPackUByte4(raw.Load(i*24+8));
 float4 weights=UnPackUByte4N(raw.Load(i*24+12));float4x4 m;float wet;
 Result r;r.position=ApplySkinning(float4(p*qs.xyz+qb.xyz,1),weights,indices,float4(1,2,0,0),m,wet);
 r.normal=float4(normalize(mul(n,(float3x3)m)),0);
 r.tangent=float4(normalize(mul(t,(float3x3)m)),0);result[i]=r;
})";
  ComPtr<ID3DBlob> code,error;auto hr=D3DCompile(source.data(),source.size(),"installed-SDK-skin-oracle",nullptr,nullptr,"main","cs_5_0",D3DCOMPILE_ENABLE_STRICTNESS,0,&code,&error);
  if(FAILED(hr)){if(error)std::cerr<<static_cast<const char*>(error->GetBufferPointer());HR(hr);}
  HR(device_->CreateComputeShader(code->GetBufferPointer(),code->GetBufferSize(),nullptr,&shader_));
 }
 std::vector<Result> Run(const std::vector<std::uint8_t>& raw,const std::vector<Matrix>& palette,const std::vector<Prepared>& prepared,Point scale,Point offset,bool mode){
  auto make=[&](const void* data,UINT size,UINT stride,UINT binds,UINT misc,D3D11_USAGE usage= D3D11_USAGE_DEFAULT){
   D3D11_BUFFER_DESC desc{};desc.ByteWidth=size;desc.Usage=usage;desc.BindFlags=binds;desc.MiscFlags=misc;desc.StructureByteStride=stride;desc.CPUAccessFlags=usage==D3D11_USAGE_STAGING?D3D11_CPU_ACCESS_READ:0;
   D3D11_SUBRESOURCE_DATA init{};init.pSysMem=data;ComPtr<ID3D11Buffer> buffer;HR(device_->CreateBuffer(&desc,data?&init:nullptr,&buffer));return buffer;
  };
  const auto count=UINT(prepared.size());std::vector<Matrix> gpuPalette(2*palette.size()+1);
  // HLSL structured float4x4 storage is column-major here. The SDK's
  // explicit transpose yields the row-vector map used by ApplySkinning.
  // Test serialization is explicit; it does not assume a live palette ABI.
  for(unsigned i=0;i<palette.size();i++)for(unsigned r=0;r<4;r++)for(unsigned c=0;c<4;c++)gpuPalette[1+2*i][r*4+c]=palette[i][c*4+r];
  auto skin=make(gpuPalette.data(),UINT(gpuPalette.size()*64),64,D3D11_BIND_SHADER_RESOURCE,D3D11_RESOURCE_MISC_BUFFER_STRUCTURED);
  auto input=make(raw.data(),UINT(raw.size()),0,D3D11_BIND_SHADER_RESOURCE,D3D11_RESOURCE_MISC_BUFFER_ALLOW_RAW_VIEWS);
  auto pre=make(prepared.data(),count*48,48,D3D11_BIND_SHADER_RESOURCE,D3D11_RESOURCE_MISC_BUFFER_STRUCTURED);
  auto output=make(nullptr,count*48,48,D3D11_BIND_UNORDERED_ACCESS,D3D11_RESOURCE_MISC_BUFFER_STRUCTURED);
  struct Constants {std::array<float,4> qs,qb;UINT count,mode,pad[2];} constants{{scale[0],scale[1],scale[2],0},{offset[0],offset[1],offset[2],0},count,mode?1u:0u,{0,0}};
  auto cb=make(&constants,sizeof(constants),0,D3D11_BIND_CONSTANT_BUFFER,0);
  ComPtr<ID3D11ShaderResourceView> views[3];HR(device_->CreateShaderResourceView(skin.Get(),nullptr,&views[0]));
  D3D11_SHADER_RESOURCE_VIEW_DESC rd{};rd.Format=DXGI_FORMAT_R32_TYPELESS;rd.ViewDimension=D3D11_SRV_DIMENSION_BUFFEREX;rd.BufferEx.NumElements=UINT(raw.size()/4);rd.BufferEx.Flags=D3D11_BUFFEREX_SRV_FLAG_RAW;
  HR(device_->CreateShaderResourceView(input.Get(),&rd,&views[1]));HR(device_->CreateShaderResourceView(pre.Get(),nullptr,&views[2]));
  ComPtr<ID3D11UnorderedAccessView> uav;HR(device_->CreateUnorderedAccessView(output.Get(),nullptr,&uav));
  ID3D11ShaderResourceView* srvs[]={views[0].Get(),views[1].Get(),views[2].Get()};auto* u=uav.Get();auto* c=cb.Get();
  context_->CSSetShader(shader_.Get(),nullptr,0);context_->CSSetShaderResources(0,3,srvs);context_->CSSetConstantBuffers(0,1,&c);context_->CSSetUnorderedAccessViews(0,1,&u,nullptr);context_->Dispatch((count+63)/64,1,1);
  ID3D11UnorderedAccessView* empty=nullptr;context_->CSSetUnorderedAccessViews(0,1,&empty,nullptr);
  auto staging=make(nullptr,count*48,0,0,0,D3D11_USAGE_STAGING);context_->CopyResource(staging.Get(),output.Get());
  D3D11_MAPPED_SUBRESOURCE map{};HR(context_->Map(staging.Get(),0,D3D11_MAP_READ,0,&map));std::vector<Result> result(count);std::memcpy(result.data(),map.pData,count*48);context_->Unmap(staging.Get(),0);
  for(const auto& r:result)for(const auto& a:{r.position,r.normal,r.tangent})for(float v:a)Check(std::isfinite(v),"Nonfinite SDK shader result");return result;
 }
};
int main(int argc,char** argv){try{
 Check(argc==3,"Usage: skin_sdk_test owned.skin installed-shader-directory");auto packet=Read(argv[1]);Check(packet.size()>=40&&packet.substr(0,8)=="MMSKIN01","Invalid skin packet");
 Point scale{},offset{};std::memcpy(scale.data(),packet.data()+8,12);std::memcpy(offset.data(),packet.data()+20,12);
 unsigned bones=0,count=0;std::memcpy(&bones,packet.data()+32,4);std::memcpy(&count,packet.data()+36,4);Check(bones>0&&bones<=256&&count>0&&count<=100000&&packet.size()==40+std::size_t(count)*24,"Skin packet bounds differ");
 std::vector<std::uint8_t> raw(packet.begin()+40,packet.end());std::vector<Vertex> vertices;for(unsigned i=0;i<count;i++)vertices.push_back(Decode(raw.data()+i*24,raw.data()+i*24+16,scale,offset));
 Oracle oracle(argv[2]);float maxPosition=0,maxDirection=0,maxInverse=0;unsigned unnormalized=0;bool unbounded=false;
 for(auto& v:vertices){unsigned sum=0;for(auto w:v.weights)sum+=w;unnormalized+=sum!=255;}
 for(unsigned state=0;state<3;state++){
  std::vector<Matrix> palette(bones);for(unsigned b=0;b<bones;b++){
   float x=state*.17f+float(b)*.007f,y=state*.23f-float(b)*.005f,z=state*.31f+float(b)*.003f;
   float cx=std::cos(x),sx=std::sin(x),cy=std::cos(y),sy=std::sin(y),cz=std::cos(z),sz=std::sin(z);
   palette[b]={cz*cy,cz*sy*sx-sz*cx,cz*sy*cx+sz*sx,.2f*state,sz*cy,sz*sy*sx+cz*cx,sz*sy*cx-cz*sx,-.11f*state,-sy,cy*sx,cy*cx,.15f*state,0,0,0,.75f};
   for(unsigned r=0;r<3;r++)palette[b][r*4]*=1.f+.02f*state;
  }
  std::vector<Prepared> pre(count);auto gpu=oracle.Run(raw,palette,pre,scale,offset,false);
  for(unsigned i=0;i<count;i++){
   auto m=Blend(vertices[i],palette);auto p=Transform(m,vertices[i].position);auto n=Normalize(Transform(m,vertices[i].normal,true));auto t=Normalize(Transform(m,vertices[i].tangent,true));
   for(unsigned j=0;j<3;j++){maxPosition=std::max(maxPosition,std::abs(p[j]-gpu[i].position[j]));maxDirection=std::max({maxDirection,std::abs(n[j]-gpu[i].normal[j]),std::abs(t[j]-gpu[i].tangent[j])});}
   Point desired={p[0]+float(state)*2.5f,p[1]-float(state)*1.7f,p[2]+float(state)*3.1f};auto output=Prepare(m,desired,n,t,vertices[i].handedness,scale,offset);
   for(unsigned j=0;j<3;j++){pre[i].position[j]=output.position[j];pre[i].normal[j]=output.normal[j];pre[i].tangent[j]=output.tangent[j];unbounded|=output.position[j]<0||output.position[j]>1;}
  }
  gpu=oracle.Run(raw,palette,pre,scale,offset,true);
  for(unsigned i=0;i<count;i++){
   auto m=Blend(vertices[i],palette);auto p=Transform(m,vertices[i].position);auto n=Normalize(Transform(m,vertices[i].normal,true));auto t=Normalize(Transform(m,vertices[i].tangent,true));
   Point desired={p[0]+float(state)*2.5f,p[1]-float(state)*1.7f,p[2]+float(state)*3.1f};
   for(unsigned j=0;j<3;j++){maxInverse=std::max(maxInverse,std::abs(desired[j]-gpu[i].position[j]));maxDirection=std::max({maxDirection,std::abs(n[j]-gpu[i].normal[j]),std::abs(t[j]-gpu[i].tangent[j])});}
  }
 }
 std::cout<<"SDK comparison errors position="<<maxPosition<<" direction="<<maxDirection<<" inverse="<<maxInverse<<'\n';
 Check(unnormalized>0&&unbounded,"Required nonunit weights and large output not exercised");Check(maxPosition<2e-6f&&maxDirection<3e-6f&&maxInverse<6e-6f,"Installed shader parity failed");
 auto bad=vertices[0];bad.weights={0,0,0,0};bool rejected=false;try{Blend(bad,std::vector<Matrix>(bones));}catch(const std::invalid_argument&){rejected=true;}Check(rejected,"Zero weights accepted");
 rejected=false;try{InverseLinear(Matrix{},Point{});}catch(const std::invalid_argument&){rejected=true;}Check(rejected,"Singular map accepted");
 rejected=false;bad=vertices[0];bad.bones[0]=255;try{Blend(bad,std::vector<Matrix>(bones));}catch(const std::invalid_argument&){rejected=true;}Check(rejected,"Invalid palette index accepted");
 std::cout<<"PASS installed SDK skin shader: "<<count<<" vertices x 3 poses; "<<unnormalized<<" nonunit weight sums; max position "<<maxPosition<<" direction "<<maxDirection<<" inverse "<<maxInverse<<"; unclamped growth; no game output\n";return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
