#pragma once
#include "source_binding.hpp"
#include "engine/skin_output.hpp"
#include <malemod/clinical/canonical_body_collision.hpp>
namespace malemod::witcher::v2 {
class ClinicalBody {
 clinical::CanonicalBodyCollision body_;
 unsigned vertexCount_=0;
public:
 clinical::CanonicalBodyCollision& Body(){return body_;}
 explicit ClinicalBody(const std::filesystem::path& path){
  std::ifstream f(path,std::ios::binary);char magic[8]{};unsigned count=0;f.read(magic,8);f.read(reinterpret_cast<char*>(&vertexCount_),4);f.read(reinterpret_cast<char*>(&count),4);
  if(std::memcmp(magic,"MMV2T01\0",8)||!vertexCount_||vertexCount_>100000||!count||count>100000)throw std::runtime_error("Native receiver topology differs");
  std::vector<clinical::CanonicalBodyCollision::Triangle> faces;faces.reserve(count);
  for(unsigned i=0;i<count;i++){std::array<unsigned,5> row{};f.read(reinterpret_cast<char*>(row.data()),20);if(row[0]>=vertexCount_||row[1]>=vertexCount_||row[2]>=vertexCount_||row[3]>1)throw std::runtime_error("Native receiver face differs");faces.push_back({row[0],row[1],row[2],static_cast<unsigned char>(row[3]),row[4]});}
  if(!f||f.peek()!=EOF)throw std::runtime_error("Native receiver data is truncated");body_.SetTopology(std::move(faces));
 }
 void Update(const SourceBinding& binding,const RenderDelivery& render,const std::array<Matrix,94>& poses,const Matrix& actor,const surface::canonical::Packet& packet){
  if(render.floatVertices.size()!=vertexCount_)throw std::runtime_error("Native receiver vertices differ");
  std::vector<malemod::V3> vertices(vertexCount_);
  for(const auto& r:binding.Resources()){
   std::vector<skin::Matrix> palette;for(unsigned k=0;k<r.paletteCount;k++){const auto& b=binding.Bones()[r.firstPalette+k];palette.push_back(Multiply(poses[b.id],b.inverse));}
   for(unsigned i=r.firstVertex;i<r.firstVertex+r.lodVertexCount[0];i++){
    const auto& row=render.floatVertices[i];skin::Vertex v{};std::memcpy(v.bones.data(),&row.bones,4);std::memcpy(v.weights.data(),&row.weights,4);Point native{};for(unsigned a=0;a<3;a++)native[a]=row.position[a]*r.scale[a]+r.bias[a];auto p=Transform(actor,skin::Transform(skin::Blend(v,palette),native));vertices[i]={p[0]*100,p[1]*100,p[2]*100};
   }
  }
  body_.Refit(std::move(vertices));
  const auto& out=packet.featureOutput;auto emitter=Transform(actor,Transform(binding.PelvisDelta(poses[9]),binding.ToNative(out.nozzlePosition)));body_.SetEmitter({emitter[0]*100,emitter[1]*100,emitter[2]*100},out.nozzleValid!=0);
 }
};
}
