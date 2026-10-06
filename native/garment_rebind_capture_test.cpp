// Rebind routes from exact full native captured surfaces. No inferred geometry,
// reskinning, game launch or rest walker; retained physical mesh stays identical.
#include "garment_service.hpp"
#include <iostream>
#include <map>
using namespace malemod::witcher;
namespace G=malemod::garments;
static void Check(bool value,const char* why){if(!value)throw std::runtime_error(why);}
int main(int argc,char** argv){try{
 if(argc!=6)throw std::runtime_error("usage: garment_rebind_capture_test old.input newBindings pin renderHash new.input");
 auto input=garment_capture::ReadInput(argv[1]);const auto before=input;
 GarmentBindings bindings(argv[2],argv[3],argv[4]);
 Check(input.anatomy.size()==bindings.contours[2].size()&&input.anatomyTriangles==bindings.triangles,"New binding does not match captured full anatomy");
 std::map<unsigned,G::Sample> body;
 for(const auto& sample:input.bodySurface){const auto& d=sample.lineage.donors;Check(d[0].surface==G::Surface::Body&&d[0].weight==1,"Capture body is not an exact native donor");for(unsigned i=1;i<d.size();i++)Check(d[i].weight==0,"Capture body includes extra lineage");Check(body.emplace(d[0].vertex,sample).second,"Capture body native IDs overlap");}
 for(unsigned i=0;i<input.anatomy.size();i++)Check(input.anatomy[i].lineage.donors[0].vertex==bindings.contours[2][i],"New binding changed captured native anatomy order");
 for(unsigned side=0;side<2;side++){input.rearStraps[side].clear();for(auto id:bindings.contours[side+3]){auto p=body.find(id);Check(p!=body.end(),"New measured strap leaves exact captured body samples");input.rearStraps[side].push_back(p->second);}}
 input.anatomyRegions=bindings.anatomyRegions;input.restRevision++;
 if(input.anatomyMass==0)input.anatomyMass=G::CurrentSourceMasses({}).Total();
 garment_capture::WriteInput(argv[5],input);auto read=garment_capture::ReadInput(argv[5]);
 Check(read.anatomyMass==input.anatomyMass&&read.anatomyTriangles==before.anatomyTriangles&&read.bodyTriangles==before.bodyTriangles,"Rebound native capture changed mass/topology");
 auto unchanged=[](const auto& a,const auto& b){if(a.size()!=b.size())return false;for(unsigned i=0;i<a.size();i++){if(a[i].position!=b[i].position||a[i].normal!=b[i].normal)return false;for(unsigned d=0;d<a[i].lineage.donors.size();d++)if(a[i].lineage.donors[d].surface!=b[i].lineage.donors[d].surface||a[i].lineage.donors[d].vertex!=b[i].lineage.donors[d].vertex||a[i].lineage.donors[d].weight!=b[i].lineage.donors[d].weight)return false;}return true;};
 Check(unchanged(read.anatomy,before.anatomy)&&unchanged(read.bodySurface,before.bodySurface)&&unchanged(read.waist,before.waist)&&unchanged(read.opening,before.opening),"Rebound route mutated original physical coordinates/normals/lineage");
 Check(unchanged(read.rearStraps[0],input.rearStraps[0])&&unchanged(read.rearStraps[1],input.rearStraps[1]),"Native capture lost new exact strap donors");
 std::cout<<"PASS new routes rebound only from full exact native body samples; original anatomy/body/waist/opening coordinates, normals, lineage and topology unchanged; MMGFC006 mass="<<read.anatomyMass<<"\n";return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
