#include "garment_cadence.hpp"
#include <iostream>
#include <limits>
#include <stdexcept>
using malemod::witcher::GarmentCadence;
static void Check(bool value,const char* message){if(!value)throw std::runtime_error(message);}
static void Near(double a,double b){Check(std::abs(a-b)<1e-10,"Garment active time differs");}
int main(){try{
 GarmentCadence c;auto s=c.Advance(1,100,false,true);
 Check(s.queue&&s.reset,"Initial generation does not reset/queue");Near(s.activeSeconds,0);
 Check(!c.Advance(1,100,false,false).queue,"Duplicate display tick queues numerical work");
 const double solved=s.activeSeconds;
 // Intermediate latest requests can be overwritten without losing their time.
 for(unsigned i=1;i<=6;i++){s=c.Advance(1,100+i/60.,false,false);Check(s.queue&&!s.reset,"Same geometry pointer stalls new pose ticks");}
 Near(s.activeSeconds-solved,.1);
 s=c.Advance(1,100.1,false,true);Check(s.queue,"Changed morphology at same pose is not queued");Near(s.activeSeconds,.1);
 s=c.Advance(1,110,true,false);Check(!s.queue&&!s.reset,"Pause queues dynamics");Near(s.activeSeconds,.1);
 s=c.Advance(1,200,false,false);Check(s.queue&&!s.reset,"Resume does not submit current pose");Near(s.activeSeconds,.1);
 s=c.Advance(1,200.025,false,false);Near(s.activeSeconds,.125);
 s=c.Advance(1,199,false,false);Check(s.queue&&s.reset,"Rewound engine clock retains stale cloth");Near(s.activeSeconds,0);
 s=c.Advance(1,201,false,false);Check(s.queue&&s.reset,"Large discontinuity silently clips elapsed time");Near(s.activeSeconds,0);
 s=c.Advance(2,201.1,false,false);Check(s.queue&&s.reset,"Character replacement retains old clock");Near(s.activeSeconds,0);
 s=c.Advance(2,202.1,false,false);Check(!s.reset,"Accepted one-second active span discarded");Near(s.activeSeconds,1);
 bool rejected=false;try{c.Advance(2,std::numeric_limits<double>::quiet_NaN(),false,false);}catch(const std::invalid_argument&){rejected=true;}Check(rejected,"Nonfinite engine clock accepted");
 c.Reset();s=c.Advance(2,202.1,false,false);Check(s.queue&&s.reset,"Explicit reset retains elapsed cloth time");Near(s.activeSeconds,0);
 // A slow first fit consumes wall time while the producer continues accepting
 // ordinary foreground ticks. Coalescing those requests must not refit again.
 c.Reset();malemod::witcher::GarmentWorkerClock worker;
 s=c.Advance(3,0,false,true);auto w=worker.Advance(3,7,s.activeSeconds);Check(w.reset,"Initial worker state retained stale fabric");Near(w.elapsed,0);
 for(unsigned i=1;i<=1200;i++)s=c.Advance(3,i/60.,false,false);
 w=worker.Advance(3,7,s.activeSeconds);Check(!w.reset,"Slow fitting creates a repeated rest-reset loop");Near(w.elapsed,20);
 s=c.Advance(3,50,true,false);s=c.Advance(3,100,false,false);
 w=worker.Advance(3,7,s.activeSeconds);Check(!w.reset,"Pause changes worker generation");Near(w.elapsed,0);
 w=worker.Advance(3,8,s.activeSeconds);Check(w.reset,"Explicit generation replacement keeps old cloth");Near(w.elapsed,0);
 w=worker.Advance(4,8,0);Check(w.reset,"Character replacement keeps old worker clock");
 w=worker.Advance(4,8,.2);Check(!w.reset,"Normal worker span refits fabric");Near(w.elapsed,.2);
 w=worker.Advance(4,8,.1);Check(w.reset,"Rewound worker clock retains stale fabric");
 std::cout<<"PASS cloth cadence: same-geometry moving poses, overwritten-request elapsed time, pause/resume exclusion, morphology ticks, discontinuity/epoch/reset and finite guards\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
