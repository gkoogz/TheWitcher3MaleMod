#pragma once
#include <d3d12.h>
#include <array>
#include <climits>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <vector>

namespace malemod::witcher::rigid_world {
inline bool EqualSemantic(const char* a,const char* b){
 if(!a||!b)return false;
 for(;;++a,++b){unsigned x=static_cast<unsigned char>(*a),y=static_cast<unsigned char>(*b);if(x>='A'&&x<='Z')x+='a'-'A';if(y>='A'&&y<='Z')y+='a'-'A';if(x!=y)return false;if(!x)return true;}
}

// Only replace the three matrix attributes. Native LOD/skinning/other instance
// attributes retain their original slots and offsets. Validation precedes any
// mutation so unsupported layouts leave the caller's descriptor unchanged.
inline unsigned Rewrite(std::vector<D3D12_INPUT_ELEMENT_DESC>& elements){
 std::array<std::size_t,3> rows{};std::array<bool,32> occupied{};unsigned seen=0;
 for(std::size_t i=0;i<elements.size();++i){
  const auto& e=elements[i];if(!e.SemanticName||!e.SemanticName[0]||e.InputSlot>=occupied.size())throw std::invalid_argument("Malformed rigid input element");
  occupied[e.InputSlot]=true;if(!EqualSemantic(e.SemanticName,"INSTANCE_TRANSFORM"))continue;
  if(e.SemanticIndex>=3||(seen&(1u<<e.SemanticIndex)))throw std::invalid_argument("Duplicate or unknown rigid instance transform");
  if(e.Format!=DXGI_FORMAT_R32G32B32A32_FLOAT||e.InputSlotClass!=D3D12_INPUT_CLASSIFICATION_PER_INSTANCE_DATA||e.InstanceDataStepRate!=1)
   throw std::invalid_argument("Unobserved rigid instance transform format/rate");
  rows[e.SemanticIndex]=i;seen|=1u<<e.SemanticIndex;
 }
 if(!seen)return UINT_MAX;
 if(seen!=7)throw std::invalid_argument("Partial rigid instance transform");
 unsigned slot=0;while(slot<occupied.size()&&occupied[slot])++slot;
 if(slot==occupied.size())throw std::invalid_argument("No unused rigid world-frame input slot");
 for(unsigned i=0;i<3;++i){auto& e=elements[rows[i]];e.InputSlot=slot;e.AlignedByteOffset=i*16;e.InputSlotClass=D3D12_INPUT_CLASSIFICATION_PER_INSTANCE_DATA;e.InstanceDataStepRate=1;}
 return slot;
}

// Decoded carrier vertices already equal desiredWorld-packet.origin. A draw's
// immutable identity+origin instance matrix therefore recovers desiredWorld,
// independent of the separately animated native carrier's transform.
inline std::array<float,12> Rows(std::array<double,3> origin){
 std::array<float,3> p{};
 for(unsigned i=0;i<3;++i){if(!std::isfinite(origin[i]))throw std::invalid_argument("Nonfinite rigid world origin");if(std::abs(origin[i])>static_cast<double>((std::numeric_limits<float>::max)()))throw std::invalid_argument("Rigid world origin exceeds float range");p[i]=static_cast<float>(origin[i]);}
 return {1,0,0,p[0],0,1,0,p[1],0,0,1,p[2]};
}
}
