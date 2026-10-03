#include "clinical_service.hpp"
#include <iostream>
using namespace malemod;using namespace malemod::witcher;
static void Check(bool v,const char* s){if(!v)throw std::runtime_error(s);}
template<class Predicate> static void Await(Predicate predicate,const char* message){for(unsigned i=0;i<15000;i++){if(predicate())return;std::this_thread::sleep_for(std::chrono::milliseconds(2));}Check(false,message);}
static void CheckService(const std::filesystem::path& bake){
 ClinicalService service(.02,bake);auto input=std::make_shared<RenderDelivery>();input->epoch=1;input->nozzleWorld={0,0,2};
 service.Submit(1,0,false,input);std::this_thread::sleep_for(std::chrono::milliseconds(30));service.Action(true);
 Await([&]{auto out=service.Latest();return out&&out->active;},"Clinical start not published");
 service.Submit(1,.05,false,input);Await([&]{auto out=service.Latest();return out&&out->time>.04f;},"Clinical clock did not advance");
 clinical::volumeFluid::FluidImpact impact;service.collisions.Sweep({0,0,10},{0,0,5},1,impact);auto prior=service.collisions.Next();service.Action(true);
 Await([&]{auto out=service.Latest();return out&&out->active&&out->time==0;},"Clinical restart not published");service.collisions.Result(prior.token,true,{0,0,6},{0,0,1});Check(service.collisions.Counts()[0]==0,"Prior sequence's deferred scene result survived restart");
 service.Submit(1,.10,false,input);Await([&]{auto out=service.Latest();return out&&out->time>.04f;},"Restarted clock did not advance");
 service.Submit(1,100,true,input);std::this_thread::sleep_for(std::chrono::milliseconds(30));float before=service.Latest()->time;
 service.Submit(1,100,false,input);std::this_thread::sleep_for(std::chrono::milliseconds(30));Check(service.Latest()->time==before,"Paused interval advanced the timeline");
 service.Submit(1,100.05,false,input);Await([&]{auto out=service.Latest();return out&&out->time>before+.04f;},"Clinical clock did not resume");Check(service.Latest()->time<.11f,"Resume caught up paused time");
 auto invalid=std::make_shared<RenderDelivery>(*input);invalid->nozzleWorld[0]=std::numeric_limits<double>::quiet_NaN();service.Submit(1,100.10,false,invalid);
 Await([&]{return !service.Error().empty();},"Invalid emitter did not fault");Check(!service.Latest()&&!service.Projection().active,"Failed simulation left stale visible liquid");Check(!service.PollCue(),"Failed simulation left dialogue cues");
 service.Submit(1,100.20,false,input);std::this_thread::sleep_for(std::chrono::milliseconds(30));Check(!service.Error().empty()&&!service.Latest(),"Unrelated valid tick silently recovered a fault");
 service.Action(true);Await([&]{auto out=service.Latest();return out&&out->active&&service.Error().empty();},"Explicit valid Start did not recover clinical fault");
 auto teleported=std::make_shared<RenderDelivery>(*input);teleported->nozzleWorld[2]=5;service.Submit(1,100.25,false,teleported);
 Await([&]{auto out=service.Latest();return out&&!out->active&&out->mesh.indices.empty();},"Source fluid teleport guard was ignored");Check(!service.Projection().active&&service.Error().empty(),"Valid teleport retained a timeline or became a fatal fault");Check(!service.PollCue()&&service.collisions.Counts()[0]==0,"Valid teleport retained old cues or contacts");
 service.SetMode(1);service.Submit(1,100.30,false,teleported);Await([&]{return service.Projection().throbMode==1;},"Ambient mode did not adopt after teleport");
 auto relocated=std::make_shared<RenderDelivery>(*teleported);relocated->nozzleWorld[2]=8;auto priorSerial=service.Latest()->serial;service.Submit(1,100.35,false,relocated);Await([&]{auto out=service.Latest();return out&&out->serial>priorSerial&&!out->active;},"Passive emitter teleport did not publish cancellation");
 Check(service.Error().empty(),"Passive finite teleport became a fatal fault");priorSerial=service.Latest()->serial;service.Submit(1,100.40,false,relocated);Await([&]{auto out=service.Latest();return out&&out->serial>priorSerial;},"Ambient emitter did not reinitialize at relocated position");auto priorPhase=service.Projection().sizeTime;service.Submit(1,100.45,false,relocated);Await([&]{return service.Projection().sizeTime>priorPhase+.04f;},"Ambient throb did not resume automatically after relocation");Check(service.Error().empty(),"Automatically resumed ambient reported a fault");
 service.SetMode(0);service.Submit(1,100.50,false,input);service.Action(true);Await([&]{auto out=service.Latest();return out&&out->active&&service.Error().empty();},"Explicit Start failed after benign emitter relocation");
 // A new character clears the old character's active timeline/output, pending
 // scene contacts and cues; it must not inherit the previous Start command.
 service.collisions.Sweep({7,0,10},{7,0,5},1,impact);prior=service.collisions.Next();auto next=std::make_shared<RenderDelivery>(*input);next->epoch=2;
 service.Submit(2,200,false,next);Await([&]{return !service.Latest()&&service.collisions.Counts()[0]==0;},"Character change retained old clinical output or contacts");
 Check(!service.Projection().active&&!service.PollCue()&&service.Error().empty(),"Character reset retained timeline, cues or fault");service.collisions.Result(prior.token,true,{7,0,6},{0,0,1});Check(service.collisions.Counts()[0]==0,"Old character's scene result was accepted");
 service.Action(true);Await([&]{auto out=service.Latest();return out&&out->epoch==2&&out->active&&out->time==0;},"New character's explicit Start failed");Check(service.Latest()->deposits.vertices.empty(),"New character inherited prior deposits");
}
int main(int argc,char** argv){try{
 clinical::Session reset;reset.timeline.Start();reset.deposits.marks.emplace_back();reset.Cancel();Check(!reset.timeline.active&&reset.deposits.marks.empty()&&!reset.fluid.Live(),"Pinned Base Cancel did not remove character deposits and fluid");
 ClinicalCollision c;clinical::volumeFluid::FluidImpact impact;
 using R=clinical::volumeFluid::SweepResult;
 Check(c.Sweep({0,0,10},{0,0,5},1,impact)==R::deferred,"Untested path became a miss");auto q=c.Next();Check(q.token&&q.from.z==10&&q.to.z==5,"Initial query differs");
 c.Result(q.token,false,{},{});Check(c.Sweep({0,0,10},{0,0,3},1,impact)==R::deferred,"Extended path discarded");q=c.Next();Check(q.from.z==5&&q.to.z==3,"Previously tested crossing repeated or skipped");
 c.Result(q.token,true,{0,0,4},{0,0,1});Check(c.Sweep({0,0,10},{0,0,2},1,impact)==R::hit&&impact.p.z==4&&impact.n.z==1,"Delayed hit lost its particle path");Check(c.Counts()[0]==0,"Consumed path leaked");
 Check(c.Sweep({1,0,10},{1,0,5},1,impact)==R::deferred,"Second path not queued");auto old=c.Next();c.Clear();Check(c.Sweep({1,0,10},{1,0,5},1,impact)==R::deferred,"Fresh epoch not queued");q=c.Next();Check(q.token!=old.token,"Epoch reused an in-flight query token");c.Result(old.token,true,{1,0,6},{0,0,1});Check(c.Sweep({1,0,10},{1,0,5},1,impact)==R::deferred,"Stale epoch hit accepted");c.Result(q.token,false,{},{});Check(c.Sweep({1,0,10},{1,0,5},1,impact)==R::miss,"Known miss not released");
 c.Sweep({2,0,10},{2,0,5},1,impact);q=c.Next();c.Result(q.token,false,{},{});c.AdvanceTime(9);Check(c.Counts()[0]==0,"Abandoned floor anchors leaked past retry lifetime");
 // Expiration must remove the original key after a tested miss extends its
 // internal from point, so a later particle can reuse that same origin.
 c.Sweep({3,0,10},{3,0,5},1,impact);q=c.Next();c.Result(q.token,false,{},{});c.Sweep({3,0,10},{3,0,3},1,impact);c.AdvanceTime(40);
 Check(c.Counts()[0]==0,"Extended pending path did not expire");Check(c.Sweep({3,0,10},{3,0,2},1,impact)==R::deferred,"Expired extended path left a stale key");q=c.Next();Check(q.from.z==10&&q.to.z==2,"Reused origin kept an expired segment");c.Clear();
 for(unsigned i=0;i<4096;i++)Check(c.Sweep({float(i),0,10},{float(i),0,5},1,impact)==R::deferred,"Queue capacity changed");Check(c.Counts()[0]==4096,"Queue limit differs");c.AdvanceTime(71);Check(c.Counts()[0]==0,"Full abandoned queue did not expire");
 if(argc>1){CheckService(argv[1]);std::cout<<"PASS clinical lifecycle: queued start/restart, pause/resume, fault cleanup and explicit recovery, benign active/passive teleports with automatic ambient resume, character epoch/output/contact/cue/deposit isolation\n";}
 std::cout<<"PASS deferred engine scene paths retain crossings, accept delayed hits, consume misses, reject stale epoch results and expire abandoned anchors\n";return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
