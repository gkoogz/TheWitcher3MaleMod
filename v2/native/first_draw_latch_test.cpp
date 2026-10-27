#include "engine/first_draw_latch.hpp"
#include <stdexcept>
#include <iostream>
using namespace malemod::witcher;
struct Packet {unsigned epoch;unsigned sequence;};
using Latch=FirstDrawLatch<Packet,Packet>;
static void Check(bool ok,const char* what){if(!ok)throw std::runtime_error(what);}
static Latch::Selection Pair(unsigned epoch,unsigned serial){return {std::make_shared<Packet>(Packet{epoch,serial}),std::make_shared<Packet>(Packet{epoch,serial})};}
int main(){try{
 Latch owner;auto a=Pair(1,1596),b=Pair(1,1597),c=Pair(1,1598);
 // Previous implementation selected A at Present before late B existed.
 // Present now only invalidates; first owned depth draw sees late B.
 owner.Select(a);owner.Invalidate();auto lower=owner.Select(b);
 Check(lower.body==b.body&&lower.garment==b.garment,"first native draw must select current pair B");
 // Other lists and materials keep the same immutable owner through updates.
 auto upper=owner.Select(c),cloth=owner.Select(c);
 Check(upper.body==b.body&&cloth.garment==b.garment,"mid-frame publication must not split body/cloth");
 // Reset/bundle lifetime bookkeeping has no selection authority. Retained A
 // can stay alive on parent/list; new direct draws still consume selected B.
 auto retainedBundle=a;auto retainedOldList=a;auto direct=owner.Select(c);
 Check(direct.body!=retainedBundle.body&&direct.garment!=retainedOldList.garment,"cached old upload must not replace shared frame owner");
 // Next render frame, without a command-list Reset, adopts C together.
 owner.Invalidate();auto next=owner.Select(c);
 Check(next.body==c.body&&next.garment==c.garment,"recording reuse must not hold previous frame");
 // Character switches and suspension suppress stale owners immediately.
 auto other=Pair(2,1);Check(owner.Select(other).body==other.body,"epoch changes must retire previous character");
 Check(!owner.Select({}).body,"empty publication must suppress stale body");
 auto recovery=owner.Select(b);Check(recovery.body==b.body,"recovery first draw must relatch");
 std::cout<<"first-draw shared owner: PASS\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
