#pragma once
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <vector>

namespace malemod::witcher::skin {
using Point=std::array<float,3>;
// Decoded actor-local skin deltas, row-major storage, column-vector algebra.
// This is NOT a claim about the live GPU palette's memory representation.
using Matrix=std::array<float,16>;
struct Vertex {Point position,normal,tangent;float handedness;std::array<std::uint8_t,4> bones,weights;};
inline std::uint32_t Word(const std::uint8_t* p){std::uint32_t v;std::memcpy(&v,p,4);return v;}
inline Point Dec10(std::uint32_t word){return {2.f*float(word&1023)/1023.f-1.f,2.f*float((word>>10)&1023)/1023.f-1.f,2.f*float((word>>20)&1023)/1023.f-1.f};}
inline Vertex Decode(const std::uint8_t* positionSkin,const std::uint8_t* tangentFrame,Point scale,Point offset){
 Vertex v{};for(unsigned i=0;i<3;i++){std::uint16_t q;std::memcpy(&q,positionSkin+2*i,2);v.position[i]=(float(q)/65535.f)*scale[i]+offset[i];}
 std::memcpy(v.bones.data(),positionSkin+8,4);std::memcpy(v.weights.data(),positionSkin+12,4);
 v.normal=Dec10(Word(tangentFrame));const auto t=Word(tangentFrame+4);v.tangent=Dec10(t);v.handedness=2.f*float(t>>30)/3.f-1.f;return v;
}
inline Matrix Blend(const Vertex& v,const std::vector<Matrix>& palette){
 std::array<float,4> weights{};float sum=0;for(unsigned k=0;k<4;k++){weights[k]=float(v.weights[k])/255.f;sum+=weights[k];}
 if(sum==0)throw std::invalid_argument("Zero shader skin weight sum");
 Matrix result{};
 for(unsigned k=0;k<4;k++){
  // The SDK fetches all four matrices, including zero-weight influences.
  if(v.bones[k]>=palette.size())throw std::invalid_argument("Skin index outside decoded palette");
  const auto& m=palette[v.bones[k]];for(float x:m)if(!std::isfinite(x))throw std::invalid_argument("Nonfinite skin delta");
  if(m[12]!=0||m[13]!=0||m[14]!=0)throw std::invalid_argument("Nonaffine decoded skin delta");
  for(unsigned i=0;i<16;i++)result[i]+=(i==15?1.f:m[i])*(weights[k]/sum);
 }
 return result;
}
inline Point Transform(const Matrix& m,Point p,bool direction=false){
 Point out{};for(unsigned i=0;i<3;i++){out[i]=direction?0.f:m[i*4+3];for(unsigned j=0;j<3;j++)out[i]+=m[i*4+j]*p[j];}return out;
}
inline Point Normalize(Point p){float n=std::sqrt(p[0]*p[0]+p[1]*p[1]+p[2]*p[2]);if(!std::isfinite(n)||n<1e-12f)throw std::invalid_argument("Degenerate lighting direction");for(float& x:p)x/=n;return p;}
// Inverse of the blended linear map, not a blend of inverse bone maps.
inline Point InverseLinear(const Matrix& m,Point p){
 for(float x:m)if(!std::isfinite(x))throw std::invalid_argument("Nonfinite inverse skin map");
 for(float x:p)if(!std::isfinite(x))throw std::invalid_argument("Nonfinite inverse skin input");
 const double d=double(m[0])*(double(m[5])*m[10]-double(m[6])*m[9])-double(m[1])*(double(m[4])*m[10]-double(m[6])*m[8])+double(m[2])*(double(m[4])*m[9]-double(m[5])*m[8]);
 if(!std::isfinite(d)||std::abs(d)<1e-8)throw std::invalid_argument("Singular blended skin transform");
 const std::array<double,9> inv={double(m[5])*m[10]-double(m[6])*m[9],double(m[2])*m[9]-double(m[1])*m[10],double(m[1])*m[6]-double(m[2])*m[5],double(m[6])*m[8]-double(m[4])*m[10],double(m[0])*m[10]-double(m[2])*m[8],double(m[2])*m[4]-double(m[0])*m[6],double(m[4])*m[9]-double(m[5])*m[8],double(m[1])*m[8]-double(m[0])*m[9],double(m[0])*m[5]-double(m[1])*m[4]};
 Point out{};for(unsigned i=0;i<3;i++){double x=0;for(unsigned j=0;j<3;j++)x+=inv[i*3+j]*p[j];out[i]=float(x/d);}return out;
}
struct FloatOutput {Point position,normal,tangent;float handedness;};
// Desired positions/directions are already in actor-local posed space. Remove
// the native skin map before submission so the shader applies it exactly once.
// Directions follow the game's linear-map-and-normalize convention.
inline FloatOutput Prepare(const Matrix& m,Point desired,Point normal,Point tangent,float sign,Point scale,Point offset){
 if(!std::isfinite(sign)||sign<-1||sign>1)throw std::invalid_argument("Invalid tangent handedness");
 for(float x:desired)if(!std::isfinite(x))throw std::invalid_argument("Nonfinite target position");
 for(unsigned i=0;i<3;i++)desired[i]-=m[i*4+3];
 auto p=InverseLinear(m,desired);for(unsigned i=0;i<3;i++){
  if(!std::isfinite(scale[i])||scale[i]<=0||!std::isfinite(offset[i]))throw std::invalid_argument("Invalid native quantization");
  p[i]=(p[i]-offset[i])/scale[i];
 }
 // Unbounded float input; a ushort UNORM stream would clamp large growth.
 // Selecting/allocating such a native stream is a separate renderer gate.
 return {p,Normalize(InverseLinear(m,normal)),Normalize(InverseLinear(m,tangent)),sign};
}
}
