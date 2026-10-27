#include "clinical_collision.hpp"
#include <iostream>
using namespace malemod;using namespace malemod::witcher;
static void Check(bool v,const char* s){if(!v)throw std::runtime_error(s);}
int main(){try{
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
 // Completed and pending abandoned particles free capacity quickly, while
 // a surface anchor with the same geometry retains its separate retry lease.
 c.Sweep({20,0,10},{20,0,5},1,impact);auto particle=c.Next();
 c.Sweep({20,0,10},{20,0,5},1,impact,true);auto anchor=c.Next();Check(particle.token!=anchor.token,"Projection alias consumed moving-particle ownership");
 c.Result(anchor.token,true,{20,0,6},{0,0,1});c.AdvanceTime(40.4);Check(c.Counts()[0]==1,"Abandoned moving path blocked native queue capacity");
 Check(c.Sweep({20,0,10},{20,0,5},1,impact,true)==R::hit&&impact.p.z==6,"Source anchor retry lifetime was shortened with particles");c.Clear();
 for(unsigned i=0;i<4096;i++)Check(c.Sweep({float(i),0,10},{float(i),0,5},1,impact)==R::deferred,"Queue capacity changed");Check(c.Counts()[0]==4096,"Queue limit differs");c.AdvanceTime(71);Check(c.Counts()[0]==0,"Full abandoned queue did not expire");
 std::cout<<"PASS canonical adapter deferred query lifecycle, late hit, prefix miss extension, stale token rejection, projection leases,4096capacity\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
