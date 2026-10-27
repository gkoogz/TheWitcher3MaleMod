#define NOMINMAX
#include "source_host.hpp"
#include "source_binding.hpp"
#include "meridian_adapter.hpp"
#include <iostream>
#include <chrono>
int wmain(int argc,wchar_t** argv){
 if(argc!=4&&argc!=5)return 2;
 try{
  malemod::witcher::v2::SourceHost host(argv[1]);
  malemod::witcher::v2::SourceBinding binding(argv[2]);
  auto& packet=host.Input();packet.epoch=1;packet.controls.fill(50);packet.controls[0]=2;packet.seconds=1.f/60;
  std::shared_ptr<const malemod::witcher::RenderDelivery> out;
  double sourceMs=0,bindingMs=0;
  for(unsigned frame=0;frame<120;frame++){
   auto begin=std::chrono::steady_clock::now();const auto& source=host.Step();auto sampled=std::chrono::steady_clock::now();out=binding.Evaluate(source);auto completed=std::chrono::steady_clock::now();
   if(frame>=30){sourceMs+=std::chrono::duration<double,std::milli>(sampled-begin).count();bindingMs+=std::chrono::duration<double,std::milli>(completed-sampled).count();}
  }
  std::cout<<"Mean current-source wait "<<sourceMs/90<<" ms; measured Geralt conversion "<<bindingMs/90<<" ms (offline)\n";
  if(packet.completed!=120||packet.physicsServices!=120||packet.surfaceServices!=120||!out||out->resources.size()!=2)throw std::runtime_error("Missing canonical frame");
  for(const auto& row:out->floatVertices)for(float x:row.position)if(!std::isfinite(x))throw std::runtime_error("Nonfinite native binding");
  std::ofstream f(argv[3],std::ios::binary);f.write(reinterpret_cast<const char*>(out->floatVertices.data()),out->floatVertices.size()*28);if(!f)throw std::runtime_error("Cannot save native probe");
  if(argc==5){
   malemod::witcher::v2::MeridianAdapter garment(argv[4]);std::array<malemod::witcher::v2::Matrix,94> bones{};
   for(const auto& b:binding.Bones())bones[b.id]=malemod::witcher::v2::Inverse(b.inverse);
   malemod::witcher::v2::Matrix actor{};actor[0]=actor[5]=actor[10]=actor[15]=1;
   auto cloth=garment.Evaluate(binding,*out,bones,actor,packet);
   if(cloth->output.mesh.vertices.size()!=4279||cloth->output.mesh.triangles.size()!=8368)throw std::runtime_error("Canonical garment topology changed");
   for(const auto& v:cloth->output.mesh.vertices)for(float x:v.position)if(!std::isfinite(x))throw std::runtime_error("Nonfinite canonical garment");
   auto path=std::filesystem::path(argv[3]);path+=L".garment";std::ofstream g(path,std::ios::binary);g.write(reinterpret_cast<const char*>(cloth->output.mesh.vertices.data()),cloth->output.mesh.vertices.size()*sizeof(cloth->output.mesh.vertices[0]));
   // Reference cloth uses the same current packet and unmodified source donor
   // table. This distinguishes engine/body fitting from canonical construction.
   namespace M=malemod::garments::meridian;using Recipe=CanonicalMeridianRecipe;
   std::vector<M::Vec> samples(Recipe::sampleCount);
   const auto fetch=[&](unsigned surface,unsigned id){M::Vec p{};const unsigned char* raw=nullptr;if(!surface&&id<17528)raw=packet.anatomy.data()+id*32;else if(surface&&id>=17449&&id<17449+15168)raw=packet.body0.data()+(id-17449)*32;else if(surface&&id>=41435&&id<41435+5615)raw=packet.body1.data()+(id-41435)*32;else throw std::runtime_error("Invalid reference garment donor");std::memcpy(p.data(),raw,12);return p;};
   for(unsigned i:Recipe::runtimeSamples)samples[i]=M::Transport(Recipe::bindings[i],fetch);
   for(unsigned side=0;side<2;side++)for(unsigned k=0;k<6;k++){const auto& p=packet.garmentLobeControls[side*6+k];samples[Recipe::lobeControls[side][k]]={p.x,p.y,p.z};}
   std::vector<malemod::garments::reference::Vertex> reference;malemod::garments::reference::Build<Recipe>(std::move(samples),reference);
   path=std::filesystem::path(argv[3]);path+=L".garment.reference";std::ofstream original(path,std::ios::binary);for(unsigned i=0;i<Recipe::count;i++){auto p=binding.ToNative({reference[i].p[0],reference[i].p[1],reference[i].p[2]});original.write(reinterpret_cast<const char*>(p.data()),12);}
   std::cout<<"Canonical Meridian: 4279 vertices, 8368 triangles; Geralt rest pose fitted\n";
  }
  std::cout<<"Completed "<<packet.completed<<" current physics/surface frames, "<<out->floatVertices.size()<<" native rows; no game connection asserted\n";
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
