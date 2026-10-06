// Offline measured-input interchange. The adapter's authoritative native
// capture writer owns MMGFC006; the text stream only transfers explicit values.
#include <string>
#include "garment_failure_capture.hpp"
#include <iostream>
using namespace malemod::witcher::garment_capture;
int wmain(int argc,wchar_t** argv){try{
 if(argc!=3)throw std::runtime_error("text-input native-output");
 std::ifstream stream(argv[1]);std::string magic;stream>>magic;if(magic!="MMGFTXT1")throw std::runtime_error("Unknown measured text input");
 auto point=[&](Point& p){for(auto& x:p)stream>>x;};
 Input in;point(in.frame.origin);point(in.frame.lateral);point(in.frame.forward);point(in.frame.up);stream>>in.characterEpoch>>in.topologyRevision>>in.restRevision;point(in.gravity);stream>>in.deltaTime>>in.anatomyMass;
 auto sample=[&](Sample& s){point(s.position);point(s.normal);for(auto& d:s.lineage.donors){unsigned surface;stream>>surface>>d.vertex>>d.weight;if(surface>1)throw std::runtime_error("Unknown source surface");d.surface=Surface(surface);}};
 auto samples=[&](std::vector<Sample>& out){unsigned count=0;stream>>count;if(!stream||count>262144)throw std::runtime_error("Measured sample budget or count");out.resize(count);for(auto& s:out)sample(s);};
 for(auto* out:{&in.waist,&in.opening,&in.anatomy,&in.rearStraps[0],&in.rearStraps[1]})samples(*out);
 auto triangles=[&](auto& out){unsigned count=0;stream>>count;if(!stream||count>524288)throw std::runtime_error("Measured triangle budget or count");out.resize(count);for(auto& t:out)for(auto& x:t)stream>>x;};
 triangles(in.anatomyTriangles);unsigned count=0;stream>>count;if(!stream||count>64)throw std::runtime_error("Measured capsule budget or count");in.bodyContacts.resize(count);for(auto& c:in.bodyContacts){point(c.a);point(c.b);stream>>c.radius;}samples(in.bodySurface);triangles(in.bodyTriangles);
 for(auto& region:in.anatomyRegions){stream>>count;if(!stream||count>in.anatomy.size())throw std::runtime_error("Measured region budget or count");region.resize(count);for(auto& id:region)stream>>id;}
 if(!stream)throw std::runtime_error("Incomplete measured text values");stream>>std::ws;if(stream.peek()!=EOF)throw std::runtime_error("Trailing measured text values");
 WriteInput(argv[2],in);auto read=ReadInput(argv[2]);
 // The same native writer must replay byte-identically, including all16 donors.
 auto roundtrip=std::filesystem::path(argv[2]);roundtrip+=L".roundtrip";WriteInput(roundtrip,read);
 std::ifstream a(argv[2],std::ios::binary),b(roundtrip,std::ios::binary);std::string av((std::istreambuf_iterator<char>(a)),{}),bv((std::istreambuf_iterator<char>(b)),{});if(av!=bv)throw std::runtime_error("Native measured capture roundtrip differs");
 std::cout<<"MMGFC006 native writer/reader byte roundtrip passed: "<<read.anatomy.size()<<" anatomy samples, "<<read.bodySurface.size()<<" body samples\n";return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
