#pragma once
#include <malemod/clinical/canonical_runtime.hpp>
#include <malemod/clinical/canonical_settings.hpp>
#include <malemod/surface/canonical_packet.hpp>
#include "source_binding.hpp"
#include <memory>

namespace malemod::witcher {
struct ClinicalDelivery {
 std::uint64_t sequence=0;
 unsigned epoch=0;
 clinical::teaching::LiquidMesh liquid;
 clinical::DepositMesh deposits;
};
namespace v2 {
class ClinicalAdapter {
 clinical::CanonicalRuntime runtime_;
 std::array<float,3> previousRoot_{};bool rootValid_=false;
public:
 clinical::CanonicalRuntime& Runtime(){return runtime_;}
 const clinical::CanonicalRuntime& Runtime()const{return runtime_;}
 // Native phase assets and baked splat data are loaded outside shared Base.
 bool LoadBakes(const std::filesystem::path& path){return runtime_.Engine().deposits.splatBakes.LoadFile(path.string());}
 bool LoadSettings(const std::filesystem::path& path,std::string& error){std::ifstream input(path);if(!input){error="Cannot open TeachingFluid.ini";return false;}return clinical::ReadCanonicalFluidSettings(input,runtime_.Engine().fluid.settings,error);}
 void Reset(){runtime_.Reset();rootValid_=false;}
 void Cancel(){runtime_.Cancel();rootValid_=false;}
 void Suspend(std::uint32_t now){runtime_.Suspend(now);rootValid_=false;}
 void Before(surface::canonical::Packet& packet,std::uint32_t now,bool focused,bool visible){packet.features=runtime_.Before(now,focused,visible);}
 std::shared_ptr<const ClinicalDelivery> After(const surface::canonical::Packet& packet,const SourceBinding& binding,const Matrix& pelvis,const Matrix& actor,float /*coreSeconds*/,std::uint32_t now){
  const auto& out=packet.featureOutput;clinical::NozzlePose pose;
  const auto p=binding.ToNative(out.nozzlePosition);
  auto back=out.nozzlePosition;for(unsigned a=0;a<3;a++)back[a]-=out.nozzleDirection[a];
  const auto q=binding.ToNative(back);auto world=Transform(actor,Transform(pelvis,p)),worldBack=Transform(actor,Transform(pelvis,q));
  const auto root=Transform(actor,{0,0,0});
  pose.position={world[0]*100,world[1]*100,world[2]*100};pose.direction=Unit({world[0]-worldBack[0],world[1]-worldBack[1],world[2]-worldBack[2]});
  // Use the source fluid renderer's bounded elapsed clock. The independent
  // anatomy solver may normalize an SDK hitch to1/60, which is not fluid dt.
  const float elapsed=runtime_.FluidElapsedSeconds(now);
  if(rootValid_&&elapsed>0)pose.inheritedVelocity={(root[0]-previousRoot_[0])*100/elapsed,(root[1]-previousRoot_[1])*100/elapsed,(root[2]-previousRoot_[2])*100/elapsed};
  previousRoot_=root;rootValid_=true;
  // Canonical fluid rejection is local to the clinical feature. Its source
  // renderer cancels/retries it while ordinary anatomy and physics continue.
  runtime_.After(out,pose,now);
  const auto& engine=runtime_.Engine();
  if(!engine.fluid.ready&&!runtime_.LastError().empty())rootValid_=false;
  auto delivery=std::make_shared<ClinicalDelivery>();delivery->epoch=packet.epoch;delivery->sequence=packet.completed;delivery->liquid=engine.fluid.mesh;delivery->deposits=clinical::BuildDepositMesh(engine.deposits,now);return delivery;
 }
};
}
}
