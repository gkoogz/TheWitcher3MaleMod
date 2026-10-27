#include "engine/draw_frame_selection.hpp"
#include <iostream>
#include <stdexcept>
using namespace malemod::witcher;
namespace malemod::witcher {
namespace {std::shared_ptr<const RenderDelivery> body;std::shared_ptr<const GarmentRenderFeed> garment;std::shared_ptr<const FluidRenderFeed> fluid;}
std::shared_ptr<const RenderDelivery> LiveRenderLatest(){return body;}
void LiveRenderFeed(std::shared_ptr<const RenderDelivery> value){body=std::move(value);}
std::shared_ptr<const GarmentRenderFeed> GarmentRendererLatest(){return garment;}
std::shared_ptr<const FluidRenderFeed> FluidRendererLatest(){return fluid;}
}
static void Check(bool ok,const char* message){if(!ok)throw std::runtime_error(message);}
static DrawFrameLatch::Selection Publish(unsigned epoch,unsigned sequence,bool liquid=true){
 FramePublicationLock publish(FramePublicationMutex());
 auto b=std::make_shared<RenderDelivery>();b->epoch=epoch;b->sequence=sequence;
 auto d=std::make_shared<GarmentDelivery>();d->epoch=epoch;d->serial=sequence;
 auto g=std::make_shared<GarmentRenderFeed>();g->input=d;
 auto f=std::make_shared<FluidRenderFeed>();f->epoch=epoch;f->sequence=sequence;f->origin={double(sequence),0,0};
 body=b;garment=g;fluid=liquid?f:nullptr;return {body,garment,fluid};
}
static void Present(){FramePublicationLock present(FramePublicationMutex());InvalidateDrawFrame();}
int main(){try{
 auto a=Publish(1,1596);SelectDrawFrame();Present();auto b=Publish(1,1597);
 // A fluid carrier may be the first owned draw. It must latch CURRENT B for
 // every component, rather than the previous publication A at Present.
 auto opaque=SelectDrawFrame();Check(opaque.body==b.body&&opaque.garment==b.garment&&opaque.fluid==b.fluid,"fluid-first draw did not adopt current matching trio");
 auto c=Publish(1,1598);auto clear=SelectDrawFrame(),bodyDraw=SelectDrawFrame(),clothDraw=SelectDrawFrame();
 Check(clear.fluid==b.fluid&&bodyDraw.body==b.body&&clothDraw.garment==b.garment,"mid-frame update split opaque/clear/body/cloth");
 Check(clear.fluid->origin==b.fluid->origin,"fluid geometry reused a newer carrier origin");
 // An old per-kind/list or bundle upload may remain alive but is never the
 // next frame's source. No command-list reset is required for adoption.
 auto retainedOpaque=a.fluid,retainedClear=b.fluid;Present();auto next=SelectDrawFrame();
 Check(next.fluid==c.fluid&&next.fluid!=retainedOpaque&&next.fluid!=retainedClear,"previous material uploads overrode new first-draw owner");
 // Clear/switch/mismatched publications cannot resurrect persistent deposits.
 Present();auto empty=Publish(1,1599,false);Check(!SelectDrawFrame().fluid,"empty current fluid reused previous deposits");
 Present();Publish(2,1);Check(SelectDrawFrame().fluid->epoch==2,"character switch retained old fluid epoch");
 Present();auto invalid=Publish(2,2);{FramePublicationLock publish(FramePublicationMutex());fluid=retainedClear;}
 Check(!SelectDrawFrame().fluid,"different-sequence fluid accepted against body frame");
 {FramePublicationLock publish(FramePublicationMutex());body.reset();}
 auto stopped=SelectDrawFrame();Check(!stopped.body&&!stopped.garment&&!stopped.fluid,"suspend retained geometry owners");
 std::cout<<"shared first-draw body/garment/fluid ownership: PASS\n";return 0;
}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}}
