#pragma once
#include <array>
#include <cmath>
#include <stdexcept>
namespace malemod::witcher::v2 {
using Point=std::array<float,3>;
using Matrix=std::array<float,16>;
inline Matrix Multiply(const Matrix& a,const Matrix& b){Matrix out{};for(unsigned i=0;i<4;i++)for(unsigned j=0;j<4;j++)for(unsigned k=0;k<4;k++)out[i*4+j]+=a[i*4+k]*b[k*4+j];return out;}
inline Point Transform(const Matrix& m,Point p){Point out{};for(unsigned i=0;i<3;i++){out[i]=m[i*4+3];for(unsigned j=0;j<3;j++)out[i]+=m[i*4+j]*p[j];}return out;}
inline Matrix Inverse(const Matrix& a){
 for(float x:a)if(!std::isfinite(x))throw std::runtime_error("Nonfinite native pose");
 if(a[12]||a[13]||a[14]||a[15]!=1)throw std::runtime_error("Nonaffine native pose");
 const double d=double(a[0])*(double(a[5])*a[10]-double(a[6])*a[9])-double(a[1])*(double(a[4])*a[10]-double(a[6])*a[8])+double(a[2])*(double(a[4])*a[9]-double(a[5])*a[8]);
 if(std::abs(d)<1e-8)throw std::runtime_error("Singular native pose");
 Matrix out={a[5]*a[10]-a[6]*a[9],a[2]*a[9]-a[1]*a[10],a[1]*a[6]-a[2]*a[5],0,a[6]*a[8]-a[4]*a[10],a[0]*a[10]-a[2]*a[8],a[2]*a[4]-a[0]*a[6],0,a[4]*a[9]-a[5]*a[8],a[1]*a[8]-a[0]*a[9],a[0]*a[5]-a[1]*a[4],0,0,0,0,1};
 for(unsigned i=0;i<3;i++)for(unsigned j=0;j<3;j++)out[i*4+j]=float(out[i*4+j]/d);
 for(unsigned i=0;i<3;i++)for(unsigned j=0;j<3;j++)out[i*4+3]-=out[i*4+j]*a[j*4+3];return out;
}
}
