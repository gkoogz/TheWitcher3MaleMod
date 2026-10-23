#pragma once
#include <malemod/surface/modular_dynamic.hpp>
#include <malemod/surface/compound_dynamic.hpp>
#include <malemod/surface/strip_lighting.hpp>
#include <tuple>
#include <map>
#include <optional>
#include <unordered_map>
#include <future>

// Included after ModularVertex/Part/Frame: native data lives only in this adapter.
namespace malemod::witcher {
class ModularDynamicRenderer {
 using Vec=surface::PresentationPoint;using State=surface::modular::State;
 struct Material {std::array<float,2> uv;std::array<float,3> normal,tangent;float sign;std::array<unsigned,4> bones;std::array<float,4> weights,color;std::array<float,2> reflection;};
 static_assert(sizeof(Material)==92);
 // Triangle donors contain at most twelve bones; a ramp blends two donors.
 // Preserve sorted accumulation order without heap nodes for every corner.
 struct Weights {
  std::array<std::pair<unsigned,double>,24> entries{};unsigned count=0;
  auto begin(){return entries.begin();} auto end(){return entries.begin()+count;}
  auto begin()const{return entries.begin();} auto end()const{return entries.begin()+count;}
  void clear(){count=0;}
  double& operator[](unsigned bone){
   unsigned i=0;while(i<count&&entries[i].first<bone)++i;
   if(i<count&&entries[i].first==bone)return entries[i].second;
   if(count==entries.size())throw std::runtime_error("Material donor bone capacity exceeded");
   for(unsigned j=count;j>i;--j)entries[j]=entries[j-1];entries[i]={bone,0};++count;return entries[i].second;
  }
 };
 struct Attribute {Vec normal{},tangent{};std::array<double,2> uv{},reflection{};double sign=1;Weights weights;std::array<double,4> color{};};
 struct Row {unsigned vertex=0,shading=0;std::uint32_t bones=0,weights=0,color=0;std::array<std::uint16_t,2> uv{},reflection{};Vec tangent{};double sign=1;bool compoundChart=false;};
 struct Layout {unsigned resource=0,lod=0,first=0,count=0;std::vector<Row> rows;std::shared_ptr<const std::vector<unsigned>> indices,controlVertices;std::shared_ptr<const std::vector<surface::PresentationBinding>> presentation;};
 const surface::modular::Asset& asset_;const surface::modular::Plan& plan_;const RenderContract& contract_;
 surface::modular::DynamicMount mount_;std::vector<std::array<Material,3>> bodyMaterial_,moduleMaterial_;
 std::vector<unsigned char> fixed_,resource_;std::vector<Vec> fixedPoints_,assetNormals_;
 std::array<unsigned char,4> winding_{};std::array<Layout,4> layouts_;
 std::optional<surface::modular::DynamicResult> cached_;State cachedState_;
 std::vector<unsigned> assetToSurface_;
 std::unique_ptr<surface::CompoundDynamicPlan> compound_;
 std::optional<surface::CompoundContactCache> compoundCache_;
 std::optional<surface::modular::DynamicResult> supportCache_;
 std::vector<std::array<Attribute,3>> compoundAttributes_;
 static Attribute Mix(const std::array<Attribute,3>& values,Vec weights){
  Attribute out;out.sign=0;
  for(unsigned k=0;k<3;k++){const auto& a=values[k];double w=weights[k];
   out.normal=surface::Add(out.normal,surface::Scale(a.normal,w));out.tangent=surface::Add(out.tangent,surface::Scale(a.tangent,w));out.sign+=a.sign*w;
   for(unsigned j=0;j<2;j++){out.uv[j]+=a.uv[j]*w;out.reflection[j]+=a.reflection[j]*w;}
   for(unsigned j=0;j<4;j++)out.color[j]+=a.color[j]*w;
   for(auto b:a.weights)out.weights[b.first]+=b.second*w;
  }out.normal=Unit(out.normal);out.tangent=Unit(out.tangent);out.sign=out.sign<0?-1:1;return out;
 }
 void BuildCompound(const State& state,const std::vector<Attribute>& ramp){
  using namespace surface;if(!compound_)return;
  supportCache_=*cached_;const auto& support=supportCache_->surface;
  auto posed=mount_.Pose(asset_,plan_,state,cached_->fitTranslation,cached_->advances,cached_->suspensionTranslation,cached_->clearedBindings,cached_->materialRoot);
  try{compoundCache_=compound_->Build(*supportCache_,asset_,state,posed);}catch(const std::exception& e){throw std::runtime_error(std::string("Compound attachment: ")+e.what());}auto& cache=*compoundCache_;
  std::vector<std::array<Attribute,3>> supportAttributes(support.faces.size()),sourceAttributes(compound_->sourceCorners.size());
  for(unsigned i=0;i<support.faces.size();i++)for(unsigned k=0;k<3;k++){auto c=support.faces[i][k];supportAttributes[i][k]=c.domain==2?ramp[c.vertex]:AttributeFor(c);}
  for(unsigned i=0;i<sourceAttributes.size();i++)for(unsigned k=0;k<3;k++){const auto& c=compound_->sourceCorners[i][k];sourceAttributes[i][k]=AttributeFor({0,1,c.parent,c.weights});}
  std::vector<Attribute> endpoints(cache.rest.size());
  for(unsigned i=0;i<support.faces.size();i++)for(unsigned k=0;k<3;k++)endpoints[support.faces[i][k].vertex]=supportAttributes[i][k];
  for(auto sample:cache.supportSamples)endpoints[sample.vertex]=Mix(supportAttributes.at(sample.parent),sample.donor);
  for(auto face:cache.faces)if(face[0].domain==0)for(auto c:face)endpoints[c.vertex]=Mix(supportAttributes.at(c.parent),c.donor);
  for(auto sample:cache.sourceSamples)endpoints[sample.vertex]=Mix(sourceAttributes.at(sample.parent),sample.donor);
  std::vector<Attribute> patch(cache.rest.size());
  for(unsigned row=0;row<cache.rings.size();row++)for(unsigned col=0;col<cache.rings[row].size();col++){
   double t=compound_->reference.parameters[row];auto a=cache.rings.front()[col],b=cache.rings.back()[col];
   patch[cache.rings[row][col]]=Mix({endpoints[a],endpoints[b],{}},{1-t,t,0});
  }
  auto& mesh=cached_->surface;mesh.points=cache.rest;mesh.faces.clear();compoundAttributes_.clear();
  for(auto face:cache.faces){std::array<SurfaceJoinCorner,3> output;std::array<Attribute,3> attributes;
   bool wraps=face[0].domain==2&&(std::max)({face[0].curve,face[1].curve,face[2].curve})-(std::min)({face[0].curve,face[1].curve,face[2].curve})>compound_->reference.footprint.size()*.5;
   for(unsigned k=0;k<3;k++){auto c=face[k];auto& a=attributes[k];
    if(c.domain<2)a=Mix(c.domain==0?supportAttributes.at(c.parent):sourceAttributes.at(c.parent),c.donor);
    else{auto it=std::lower_bound(cache.curveKnots.begin(),cache.curveKnots.end(),c.curve);if(it==cache.curveKnots.end()||std::abs(*it-c.curve)>1e-8)throw std::runtime_error("Missing compound material curve knot");
     const auto column=it-cache.curveKnots.begin();a=patch[cache.rings[c.row][column]];
     // Texture density follows measured retained-skin arclength. Original
     // vertex indices cluster around detailed regions and stretch the map
     // into visible vertical panels if used as a circumference coordinate.
     double u=cache.frameCoordinates[column]/cache.framePeriod;if(wraps&&u<.5)u+=1;
     a.uv={.7625+.225*u,.395+.09*compound_->reference.parameters[c.row]};}
    double sum=0;for(auto weight:a.weights)sum+=weight.second;
    if(sum<.99)throw std::runtime_error("Incomplete compound material vertex "+std::to_string(c.vertex)+" domain "+std::to_string(c.domain)+" parent "+std::to_string(c.parent)+" row "+std::to_string(c.row)+" sum "+std::to_string(sum));
    Vec w{};w[k]=1;output[k]={c.vertex,3,unsigned(compoundAttributes_.size()),w};
   }mesh.faces.push_back(output);compoundAttributes_.push_back(attributes);
  }
  auto geometry=Normals(mesh.points,mesh.faces);const unsigned old=unsigned(templateNormals_.size());
  templateNormals_.resize(mesh.points.size());templateGeometry_=geometry;useFixed_.resize(mesh.points.size(),0);nativeFixed_.resize(mesh.points.size());
  for(unsigned i=old;i<mesh.points.size();i++)templateNormals_[i]=geometry[i];
  for(auto sample:cache.supportSamples){auto f=support.faces.at(sample.parent);Vec n{},p{};bool fixed=true;for(unsigned k=0;k<3;k++){n=Add(n,Scale(templateNormals_[f[k].vertex],sample.donor[k]));p=Add(p,Scale(nativeFixed_[f[k].vertex],sample.donor[k]));if(sample.donor[k]>1e-10)fixed&=useFixed_[f[k].vertex]!=0;}templateNormals_[sample.vertex]=Unit(n);if(fixed){useFixed_[sample.vertex]=1;nativeFixed_[sample.vertex]=p;}}
  // New patch uses its own geometric tangent, not a tangent inherited from a
  // rotated source texture island. Keep mirrored source aliases separately.
  for(unsigned i=0;i<mesh.faces.size();i++)if(cache.faces[i][0].domain==2){auto f=mesh.faces[i];auto& a=compoundAttributes_[i];auto p=Sub(mesh.points[f[1].vertex],mesh.points[f[0].vertex]),q=Sub(mesh.points[f[2].vertex],mesh.points[f[0].vertex]);
   double u=a[1].uv[0]-a[0].uv[0],v=a[1].uv[1]-a[0].uv[1],x=a[2].uv[0]-a[0].uv[0],y=a[2].uv[1]-a[0].uv[1],det=u*y-v*x;
   if(std::abs(det)>1e-20){auto tangent=Scale(Sub(Scale(p,y),Scale(q,v)),1/det),bitangent=Scale(Sub(Scale(q,u),Scale(p,x)),1/det);for(unsigned k=0;k<3;k++){auto n=geometry[f[k].vertex];a[k].tangent=Unit(Sub(tangent,Scale(n,Dot(n,tangent))));a[k].sign=Dot(Cross(n,a[k].tangent),bitangent)<0?-1:1;}}
  }
 }
 void CompoundControls(ModularControlTopology& controls,const std::vector<surface::LiveControlBinding>& module){
  using namespace surface;if(!compoundCache_)return;const auto& cache=*compoundCache_;
  auto blend=[](const std::array<LiveControlBinding,3>& v,Vec w){LiveControlBinding b;b.fixed=true;for(unsigned k=0;k<3;k++){b.shaft+=v[k].shaft*w[k];b.lobe+=v[k].lobe*w[k];b.body+=v[k].body*w[k];b.crown+=v[k].crown*w[k];if(w[k]>1e-10)b.fixed&=v[k].fixed;}return b;};
  for(auto sample:cache.supportSamples){auto f=cache.supportFaces.at(sample.parent);controls.bindings[sample.vertex]=blend({controls.bindings[f[0]],controls.bindings[f[1]],controls.bindings[f[2]]},sample.donor);controls.compoundDonors.push_back({sample.vertex,f,sample.donor});}
  std::vector<unsigned> sourceMap(compound_->sourceVertices.size(),~0u);
  for(auto sample:cache.sourceSamples)for(unsigned k=0;k<3;k++)if(sample.donor[k]==1)sourceMap.at(cache.sourceFaces.at(sample.parent)[k])=sample.vertex;
  for(auto sample:cache.sourceSamples){auto f=cache.sourceFaces.at(sample.parent);controls.bindings[sample.vertex]=blend({module[compound_->sourceVertices[f[0]]],module[compound_->sourceVertices[f[1]]],module[compound_->sourceVertices[f[2]]]},sample.donor);}
  for(auto sample:cache.sourceSamples){auto f=cache.sourceFaces.at(sample.parent);bool original=false;for(unsigned k=0;k<3;k++)original|=sample.donor[k]==1;
   if(original)continue;
   for(auto& id:f){id=sourceMap.at(id);if(id==~0u)throw std::runtime_error("Missing compound control source parent");}
   controls.compoundDonors.push_back({sample.vertex,f,sample.donor});
  }
  for(unsigned row=1;row+1<cache.rings.size();row++)for(unsigned col=0;col<cache.rings[row].size();col++){double t=compound_->reference.parameters[row];auto a=cache.rings.front()[col],b=cache.rings.back()[col];controls.bindings[cache.rings[row][col]]=blend({controls.bindings[a],controls.bindings[b],{}},{1-t,t,0});}
 }
 struct Shade {unsigned vertex;Vec tangent;double sign;bool compoundChart;};std::vector<Shade> shading_;
 std::array<std::vector<std::array<std::optional<Row>,3>>,4> bodyRows_,moduleRows_;
 std::vector<Vec> templateNormals_,templateGeometry_,nativeFixed_;std::vector<unsigned char> useFixed_;
 std::shared_ptr<const ModularControlTopology> controlTopology_;
 double controlBodyRadius_=1;
 static Vec Unit(Vec x,Vec fallback={1,0,0}){double n=surface::Dot(x,x);return n>1e-24?surface::Scale(x,1/std::sqrt(n)):fallback;}
 static Vec Transport(Vec v,Vec a,Vec b){using namespace surface;auto axis=Cross(a,b);double cosine=std::clamp(Dot(a,b),-1.,1.);if(cosine<-.9999){auto side=Cross(a,Vec{1,0,0});if(Dot(side,side)<1e-6)side=Cross(a,Vec{0,1,0});side=Unit(side);return Sub(Scale(side,2*Dot(side,v)),v);}return Add(Add(v,Cross(axis,v)),Scale(Cross(axis,Cross(axis,v)),1/(1+cosine)));}
 static std::uint16_t Half(float f){
  std::uint32_t b;std::memcpy(&b,&f,4);const unsigned sign=b>>16&0x8000;int e=int((b>>23)&255)-127+15;unsigned m=b&0x7fffff;
  if(e<=0){if(e< -10)return std::uint16_t(sign);m=(m|0x800000)>>(1-e);return std::uint16_t(sign+((m+0x1000)>>13));}if(e>=31)throw std::runtime_error("Material half overflow");return std::uint16_t(sign+(unsigned(e)<<10)+((m+0x1000)>>13));
 }
 static std::uint32_t Pack(Vec v,unsigned high){v=Unit(v);unsigned word=high<<30;for(unsigned k=0;k<3;k++)word|=unsigned(std::clamp((v[k]+1)*.5,0.,1.)*1023+.5)<<(10*k);return word;}
 static std::vector<Vec> Normals(const std::vector<Vec>& points,const std::vector<std::array<surface::SurfaceJoinCorner,3>>& faces){
  using namespace surface;std::vector<Vec> n(points.size());for(auto f:faces){auto a=f[0].vertex,b=f[1].vertex,c=f[2].vertex;
   if(a>=points.size()||b>=points.size()||c>=points.size())throw std::runtime_error("Prepared mesh triangle index leaves its vertex buffer: "+std::to_string(a)+","+std::to_string(b)+","+std::to_string(c)+" of "+std::to_string(points.size()));
   auto face=Cross(Sub(points[b],points[a]),Sub(points[c],points[a]));for(auto i:{a,b,c})n[i]=Add(n[i],face);}for(auto& x:n)x=Unit(x);return n;
 }
 Attribute AttributeFor(surface::SurfaceJoinCorner c)const{
  using namespace surface;if(c.domain==3)return Mix(compoundAttributes_.at(c.parent),c.donor);const auto& tri=c.domain==0?bodyMaterial_.at(c.parent):moduleMaterial_.at(c.parent);Attribute a;a.sign=0;
  for(unsigned k=0;k<3;k++){const double w=c.donor[k];const auto& m=tri[k];for(unsigned j=0;j<2;j++){a.uv[j]+=m.uv[j]*w;a.reflection[j]+=m.reflection[j]*w;}for(unsigned j=0;j<3;j++){a.normal[j]+=m.normal[j]*w;a.tangent[j]+=m.tangent[j]*w;}for(unsigned j=0;j<4;j++){a.color[j]+=m.color[j]*w;a.weights[m.bones[j]]+=m.weights[j]*w;}a.sign+=m.sign*w;}
  a.normal=Unit(a.normal);a.tangent=Unit(a.tangent);a.sign=a.sign<0?-1:1;return a;
 }
 Row MakeRow(unsigned vertex,Attribute a,unsigned resource,unsigned lod)const{
  const auto& r=contract_.resources[resource];const unsigned begin=r.firstPalette+lod*r.paletteCount/2,end=begin+r.paletteCount/2;
  std::array<std::pair<double,unsigned>,24> weights{};unsigned weightCount=0;for(auto item:a.weights)if(item.second>1e-12)weights[weightCount++]={item.second,item.first};
  std::sort(weights.begin(),weights.begin()+weightCount,[](auto a,auto b){return a.first!=b.first?a.first>b.first:a.second<b.second;});weightCount=(std::min)(weightCount,4u);double sum=0;for(unsigned k=0;k<weightCount;k++)sum+=weights[k].first;if(sum<=0)throw std::runtime_error("Dynamic skin has no measured donors at vertex "+std::to_string(vertex));
  std::array<unsigned,4> skin{},quant{};std::array<double,4> fraction{};unsigned total=0;Row row;row.vertex=vertex;row.tangent=a.tangent;row.sign=a.sign;
  unsigned fallback=begin;while(fallback<end&&contract_.nativeBones[fallback]!=9)++fallback;if(fallback==end)throw std::runtime_error("Observed palette has no pelvic binding");skin.fill(fallback-r.firstPalette);
  for(unsigned k=0;k<weightCount;k++){const double value=255*weights[k].first/sum;quant[k]=unsigned(std::floor(value));fraction[k]=value-quant[k];total+=quant[k];}
  while(total<255){auto best=std::max_element(fraction.begin(),fraction.end());quant[best-fraction.begin()]++;*best=-1;total++;}
  for(unsigned k=0;k<weightCount;k++)if(quant[k]){unsigned bone=begin;while(bone<end&&contract_.nativeBones[bone]!=weights[k].second)++bone;if(bone==end)throw std::runtime_error("Dynamic skin bone "+std::to_string(weights[k].second)+" byte weight "+std::to_string(quant[k])+" leaves resource "+std::to_string(resource)+" LOD "+std::to_string(lod)+" vertex "+std::to_string(vertex));skin[k]=bone-r.firstPalette;}
  for(unsigned k=0;k<4;k++){row.bones|=skin[k]<<(8*k);row.weights|=quant[k]<<(8*k);row.color|=unsigned(std::clamp(a.color[k],0.,1.)*255+.5)<<(8*k);}
  for(unsigned k=0;k<2;k++){row.uv[k]=Half(float(a.uv[k]));row.reflection[k]=Half(float(a.reflection[k]));}return row;
 }
 void Build(const State& state){
  using namespace surface;cached_=mount_.Evaluate(asset_,plan_,state);cachedState_=state;auto& mesh=cached_->surface;templateGeometry_=Normals(mesh.points,mesh.faces);templateNormals_=templateGeometry_;useFixed_.assign(mesh.points.size(),0);nativeFixed_.assign(mesh.points.size(),{});
  assetToSurface_.assign(asset_.rest.size(),~0u);
  for(auto c:cached_->moduleVertices)for(unsigned k=0;k<3;k++)if(c.donor[k]>1-1e-10)assetToSurface_[asset_.faces[c.parent][k]]=c.vertex;
  std::vector<std::optional<SurfaceJoinCorner>> donors(mesh.points.size());
  for(auto f:mesh.faces)for(auto c:f)if(c.domain<2){
   donors[c.vertex]=c;auto a=AttributeFor(c);
   if(c.domain==0){templateNormals_[c.vertex]=a.normal;bool fixed=true;Vec position{};for(unsigned k=0;k<3;k++)if(c.donor[k]>1e-10){auto id=mount_.faces[c.parent][k];fixed&=fixed_[id]!=0;position=Add(position,Scale(fixedPoints_[id],c.donor[k]));}if(fixed){useFixed_[c.vertex]=1;nativeFixed_[c.vertex]=position;}}
   else{Vec before{};for(unsigned k=0;k<3;k++)before=Add(before,Scale(assetNormals_[asset_.faces[c.parent][k]],c.donor[k]));templateNormals_[c.vertex]=Unit(Transport(a.normal,Unit(before),templateGeometry_[c.vertex]));}
  }
  std::vector<Attribute> ramp(mesh.points.size());const auto& rings=mesh.rings;
  for(unsigned column=0;column<rings[0].size();column++){
   const auto bodyCorner=*donors[rings.front()[column]],moduleCorner=*donors[rings.back()[column]];auto a=AttributeFor(bodyCorner),b=AttributeFor(moduleCorner);
   // Continue the proximal anatomy chart through the ramp. Body-chart
   // extrusion crosses unrelated abdominal texture landmarks.
   for(unsigned row=0;row<rings.size();row++){
    const unsigned id=rings[row][column];const double t=.5*(1-std::cos(3.14159265358979323846*row/(rings.size()-1)));auto& value=ramp[id];value=a;
    value.uv={b.uv[0],.02*(1-t)+b.uv[1]*t};value.weights.clear();for(auto w:a.weights)value.weights[w.first]+=w.second*(1-t);for(auto w:b.weights)value.weights[w.first]+=w.second*t;for(unsigned k=0;k<4;k++)value.color[k]=a.color[k]*(1-t)+b.color[k]*t;value.normal=templateNormals_[id];
   }
  }
  std::vector<Vec> rampTangents(mesh.points.size()),rampBitangents(mesh.points.size());
  for(auto f:mesh.faces)if(f[0].domain==2){auto a=f[0].vertex,b=f[1].vertex,c=f[2].vertex;auto p=Sub(mesh.points[b],mesh.points[a]),q=Sub(mesh.points[c],mesh.points[a]);auto u=ramp[a].uv,v=ramp[b].uv,w=ramp[c].uv;double du=v[0]-u[0],dv=v[1]-u[1],eu=w[0]-u[0],ev=w[1]-u[1],det=du*ev-dv*eu;if(std::abs(det)<1e-15)continue;double area=std::sqrt(Dot(Cross(p,q),Cross(p,q)));auto tangent=Scale(Sub(Scale(p,ev),Scale(q,dv)),area/det),bitangent=Scale(Sub(Scale(q,du),Scale(p,eu)),area/det);for(auto i:{a,b,c}){rampTangents[i]=Add(rampTangents[i],tangent);rampBitangents[i]=Add(rampBitangents[i],bitangent);}}
  for(auto ring:rings)for(auto i:ring){auto n=templateNormals_[i];ramp[i].tangent=Unit(Sub(rampTangents[i],Scale(n,Dot(n,rampTangents[i]))),ramp[i].tangent);ramp[i].sign=Dot(Cross(n,ramp[i].tangent),rampBitangents[i])<0?-1:1;}
  BuildCompound(state,ramp);
  using Key=std::array<unsigned,7>;
  struct KeyHash {std::size_t operator()(const Key& key)const{std::size_t h=0;for(auto x:key)h^=std::hash<unsigned>{}(x)+0x9e3779b9+(h<<6)+(h>>2);return h;}};
  std::vector<unsigned> faceResources;faceResources.reserve(mesh.faces.size());std::set<unsigned> lowerPalette;
  const auto& lower=contract_.resources[0];for(unsigned i=lower.firstPalette;i<lower.firstPalette+lower.paletteCount/2;i++)lowerPalette.insert(contract_.nativeBones[i]);
  for(auto face:mesh.faces){unsigned resource=face[0].domain==0?resource_[face[0].parent]:0;
   if(face[0].domain>=2)for(auto c:face)for(auto w:(c.domain==2?ramp[c.vertex]:AttributeFor(c)).weights)if(w.second>1e-10&&!lowerPalette.count(w.first))resource=1;
   if(compoundCache_){auto original=compoundCache_->faces[faceResources.size()];if(original[0].domain==0){auto parent=supportCache_->surface.faces[original[0].parent][0];if(parent.domain==0)resource=resource_[parent.parent];}}
   faceResources.push_back(resource);
  }
  std::array<std::future<void>,4> jobs;
  for(unsigned index=0;index<4;index++)jobs[index]=std::async(std::launch::async,[&,index]{
   auto& layout=layouts_[index];layout={};layout.resource=index/2;layout.lod=index%2;layout.first=contract_.lods[index].firstIndex;layout.count=contract_.lods[index].indexCount;
   std::vector<std::optional<Row>> rampRows(mesh.points.size());
   std::unordered_map<Key,unsigned,KeyHash> aliases;aliases.reserve(mesh.points.size());auto indices=std::make_shared<std::vector<unsigned>>();
   for(unsigned fi=0;fi<mesh.faces.size();fi++){auto face=mesh.faces[fi];if(faceResources[fi]!=layout.resource)continue;std::array<unsigned,3> tri;
    for(unsigned k=0;k<3;k++){auto c=face[k];int original=-1;
     if(c.domain<2)for(unsigned j=0;j<3;j++)if(c.donor[j]==1&&c.donor[(j+1)%3]==0&&c.donor[(j+2)%3]==0)original=int(j);
     Row row;
     if(original>=0){auto& saved=(c.domain==0?bodyRows_[index]:moduleRows_[index]).at(c.parent)[original];if(!saved)saved=MakeRow(c.vertex,AttributeFor(c),layout.resource,layout.lod);row=*saved;row.vertex=c.vertex;}
     else if(c.domain==2){auto& saved=rampRows[c.vertex];if(!saved)saved=MakeRow(c.vertex,ramp[c.vertex],layout.resource,layout.lod);row=*saved;}
     else row=MakeRow(c.vertex,AttributeFor(c),layout.resource,layout.lod);
     if(c.domain==1){Vec before{};for(unsigned j=0;j<3;j++)before=Add(before,Scale(assetNormals_[asset_.faces[c.parent][j]],c.donor[j]));row.tangent=Transport(row.tangent,Unit(before),templateGeometry_[c.vertex]);}
     row.compoundChart=compoundCache_&&compoundCache_->faces[fi][k].domain==2;
     Key key{c.vertex,row.uv[0],row.uv[1],row.bones,row.weights,row.sign<0?0u:1u,unsigned(row.compoundChart)};auto found=aliases.find(key);
     if(found==aliases.end()){unsigned id=unsigned(layout.rows.size());aliases.emplace(key,id);layout.rows.push_back(row);tri[k]=id;}else{tri[k]=found->second;layout.rows[tri[k]].tangent=Add(layout.rows[tri[k]].tangent,row.tangent);}
    }if(!winding_[index])std::swap(tri[1],tri[2]);indices->insert(indices->end(),tri.begin(),tri.end());
   }
   for(auto& row:layout.rows)row.tangent=Unit(row.tangent);layout.indices=std::move(indices);
  });
  for(auto& job:jobs)job.get();
  std::vector<PresentationBinding> ownership(mesh.points.size());
  for(auto c:cached_->moduleVertices){std::array<double,15> votes{};double crown=0;for(unsigned k=0;k<3;k++){auto id=asset_.faces[c.parent][k];const auto& binding=cached_->clearedBindings?cached_->clearedBindings->at(id):asset_.bindings[id];for(auto v:binding.influences)votes[v.frame]+=v.weight*c.donor[k];if(state.crownWeights)crown+=state.crownWeights->at(id)*c.donor[k];}unsigned f=unsigned(std::max_element(votes.begin(),votes.end())-votes.begin());if(crown>1-1e-8)f=12;ownership[c.vertex]={f,f?1.:0.};}
  if(compoundCache_)for(auto sample:compoundCache_->sourceSamples){auto f=compoundCache_->sourceFaces[sample.parent];std::array<double,15> votes{};for(unsigned k=0;k<3;k++)for(auto v:asset_.bindings[compound_->sourceVertices[f[k]]].influences)votes[v.frame]+=v.weight*sample.donor[k];unsigned frame=unsigned(std::max_element(votes.begin(),votes.end())-votes.begin());ownership[sample.vertex]={frame,frame?1.:0.};}
  for(auto& layout:layouts_){auto bindings=std::make_shared<std::vector<PresentationBinding>>();bindings->reserve(layout.rows.size());for(auto row:layout.rows)bindings->push_back(ownership[row.vertex]);layout.presentation=bindings;}
  // Prepare ownership once, alongside the native layout. Display edits reuse
  // exactly these vertices/aliases while a precise fit runs independently.
  auto controls=std::make_shared<ModularControlTopology>();
  controls->bindings.resize(mesh.points.size());
  controlBodyRadius_=0;
  for(auto id:rings.front()){auto q=Sub(mesh.points[id],cached_->anchor);controlBodyRadius_=(std::max)(controlBodyRadius_,std::hypot(q[1],q[2]));}
  for(unsigned i=0;i<mount_.body.size();i++){
   auto& binding=controls->bindings[i];binding.fixed=fixed_[i]!=0;
   auto q=Sub(mesh.points[i],cached_->anchor);const double radius=std::hypot(q[1],q[2]);
   const double front=std::clamp((q[0]+controlBodyRadius_*.5)/(controlBodyRadius_*.5),0.,1.);
   binding.body=ControlSmooth(front)*(1-ControlSmooth((radius/controlBodyRadius_-1)/1.5));
  }
  std::vector<bool> bodySeen(mesh.points.size());
  for(auto f:mesh.faces)controls->faces.push_back({f[0].vertex,f[1].vertex,f[2].vertex});
  for(auto f:compoundCache_?supportCache_->surface.faces:mesh.faces){
   if(f[0].domain==0)for(auto c:f){
    auto& binding=controls->bindings[c.vertex];binding.fixed=useFixed_[c.vertex]!=0;
    auto q=Sub(mesh.points[c.vertex],cached_->anchor);
    const double radius=std::hypot(q[1],q[2]);
    const double front=std::clamp((q[0]+controlBodyRadius_*.5)/(controlBodyRadius_*.5),0.,1.);
    binding.body=ControlSmooth(front)*(1-ControlSmooth((radius/controlBodyRadius_-1)/1.5));
    if(!bodySeen[c.vertex]){bodySeen[c.vertex]=true;controls->bodyDonors.push_back({c.vertex,mount_.faces[c.parent],c.donor});}
   }
  }
  std::vector<LiveControlBinding> moduleControl(asset_.rest.size());
  auto own=[](const surface::modular::Binding& b){LiveControlBinding out;for(auto v:b.influences){if(v.frame>=13)out.lobe+=v.weight;else if(v.frame>=1)out.shaft+=v.weight;}return out;};
  for(unsigned i=0;i<moduleControl.size();i++){moduleControl[i]=own(asset_.bindings[i]);if(state.crownWeights)moduleControl[i].crown=state.crownWeights->at(i);}
  // Generated neck strips are evaluated from their two endpoint owners by
  // Plan::Evaluate. Their placeholder asset binding is not their ownership.
  for(const auto& loft:asset_.lofts){
   auto a=own(loft.firstOwner),b=own(loft.lastOwner);const double t=ControlSmooth(loft.t);
   moduleControl[loft.vertex]={a.shaft*(1-t)+b.shaft*t,a.lobe*(1-t)+b.lobe*t,0,0,false};
  }
  for(auto c:cached_->moduleVertices){
   auto& binding=controls->bindings[c.vertex];
   for(unsigned k=0;k<3;k++){
    const auto id=asset_.faces[c.parent][k];const double w=c.donor[k];
    binding.lobe+=w*moduleControl[id].lobe;binding.shaft+=w*moduleControl[id].shaft;
    binding.crown+=w*moduleControl[id].crown;
   }
  }
  for(unsigned row=0;row<rings.size();row++){
   const double t=.5*(1-std::cos(3.14159265358979323846*row/(rings.size()-1)));
   for(auto id:rings[row]){
    auto& binding=controls->bindings[id];binding.shaft=ControlSmooth(t);
    binding.body=1-binding.shaft;binding.lobe=binding.crown=0;
    binding.fixed=useFixed_[id]!=0;
   }
  }
  CompoundControls(*controls,moduleControl);
  controls->normals=std::make_shared<OrderedNormals>(unsigned(mesh.points.size()),controls->faces);
  controlTopology_=controls;
  for(unsigned i=0;i<asset_.lofts.size();i++){
   const auto& l=asset_.lofts[i];auto v=assetToSurface_[l.vertex],a=assetToSurface_[l.start],b=assetToSurface_[l.end];
   if(v==~0u||a==~0u||b==~0u)continue;
   controls->lofts.push_back({v,a,b,l.t});controls->sourceLofts.push_back(i);
  }
  for(unsigned row=1;row+1<rings.size();row++){
   const double t=.5*(1-std::cos(3.14159265358979323846*row/(rings.size()-1)));
   for(unsigned column=0;column<rings[0].size();column++)controls->lofts.push_back({rings[row][column],rings.front()[column],rings.back()[column],t});
  }
  controls->compoundLoftStart=unsigned(controls->lofts.size());
  if(compoundCache_){controls->compoundRings=compoundCache_->rings;controls->compoundParameters=compound_->reference.parameters;}
  if(compoundCache_)for(unsigned row=1;row+1<compoundCache_->rings.size();row++)for(unsigned col=0;col<compoundCache_->rings[row].size();col++)controls->lofts.push_back({compoundCache_->rings[row][col],compoundCache_->rings.front()[col],compoundCache_->rings.back()[col],compound_->reference.parameters[row]});
  for(auto& layout:layouts_){auto ids=std::make_shared<std::vector<unsigned>>();ids->reserve(layout.rows.size());for(auto row:layout.rows)ids->push_back(row.vertex);layout.controlVertices=ids;}
  shading_.clear();std::map<std::tuple<unsigned,double,double,double,double,bool>,unsigned> cache;
  for(auto& layout:layouts_)for(auto& row:layout.rows){auto key=std::make_tuple(row.vertex,row.tangent[0],row.tangent[1],row.tangent[2],row.sign,row.compoundChart);auto pair=cache.emplace(key,unsigned(shading_.size()));row.shading=pair.first->second;if(pair.second)shading_.push_back({row.vertex,row.tangent,row.sign,row.compoundChart});}
 }
 public:
 ModularDynamicRenderer(const surface::modular::Asset& asset,const surface::modular::Plan& plan,const RenderContract& contract,const std::filesystem::path& dynamic,const std::filesystem::path& materials,const std::string& geometryHash,const std::string& dynamicHash,const std::string& nativeHash)
 :asset_(asset),plan_(plan),contract_(contract),mount_(dynamic){
  if(mount_.geometryHash!=geometryHash||std::filesystem::file_size(materials)>128*1024*1024)throw std::invalid_argument("Dynamic material/source identity differs");std::ifstream in(materials,std::ios::binary);auto bytes=[&](void* p,std::size_t n){if(!in.read(static_cast<char*>(p),n))throw std::invalid_argument("Truncated dynamic materials");};auto text=[&](unsigned n){std::string s(n,'\0');bytes(s.data(),n);return s;};auto u=[&]{unsigned n;bytes(&n,4);return n;};
  if(text(8)!="MMMAT001"||text(64)!=geometryHash||text(64)!=dynamicHash||text(64)!=nativeHash)throw std::invalid_argument("Dynamic material hashes differ");auto nv=u(),nf=u(),nm=u();if(nv!=mount_.body.size()||nf!=mount_.faces.size()||nm!=asset_.faces.size())throw std::invalid_argument("Dynamic material counts differ");
  bytes(winding_.data(),4);fixed_.resize(nv);fixedPoints_.resize(nv);resource_.resize(nf);bytes(fixed_.data(),nv);bytes(fixedPoints_.data(),nv*24);bytes(resource_.data(),nf);bodyMaterial_.resize(nf);moduleMaterial_.resize(nm);bytes(bodyMaterial_.data(),nf*sizeof(bodyMaterial_[0]));bytes(moduleMaterial_.data(),nm*sizeof(moduleMaterial_[0]));if(in.peek()!=EOF)throw std::invalid_argument("Trailing dynamic material bytes");
  if(!mount_.compoundData.empty())compound_=std::make_unique<surface::CompoundDynamicPlan>(mount_.compoundData,asset_,mount_);
  // Lazily prepare only retained source corners. Some excised stock corners
  // have bones outside the carrier palette and must never enter native rows.
  for(unsigned index=0;index<4;index++){
   bodyRows_[index].resize(bodyMaterial_.size());if(index/2==0)moduleRows_[index].resize(moduleMaterial_.size());
  }
  assetNormals_.resize(asset.rest.size());for(auto f:asset.faces){auto n=surface::Cross(surface::Sub(asset.rest[f[1]],asset.rest[f[0]]),surface::Sub(asset.rest[f[2]],asset.rest[f[0]]));for(auto id:f)assetNormals_[id]=surface::Add(assetNormals_[id],n);}for(auto& n:assetNormals_)n=Unit(n);
 }
 std::shared_ptr<ModularFrame> Evaluate(const State& state){
  using namespace surface;const auto start=std::chrono::steady_clock::now();bool rebuild=!cached_;
  // Pulse strain belongs to reposing. Rebuilding from live pulse dimensions
  // both stalls the display and fits a different socket around frozen material.
  const auto& restFrames=state.hasShapeFrames?state.shapeFrames:state.frames;
  if(cached_){for(unsigned k=0;k<3;k++)rebuild|=std::abs(state.scales[1][k]/(state.shaftMaterial?state.materialScale[k]:1)-cachedState_.scales[1][k])>.002;rebuild|=Dot(restFrames[1].basis[0],cachedState_.frames[1].basis[0])<.99998;rebuild|=Dot(Sub(restFrames[1].origin,cachedState_.frames[1].origin),Sub(restFrames[1].origin,cachedState_.frames[1].origin))>1e-6;}
  // A new zero-motion morphology can change socket stations without changing
  // root radius/angle (for example mechanical state or distal shape controls).
  // Cached ownership and temporal presentation must adopt that material too.
  if(cached_)rebuild|=state.shaftMaterial!=cachedState_.shaftMaterial||state.hangControl!=cachedState_.hangControl;
  if(rebuild){try{Build(surface::modular::RestMaterialState(asset_.bindings,state));}catch(...){
   // A failed topology preparation must never be reused as a completed cache.
   // The display service retains its last complete frame while this retries.
   cached_.reset();compoundCache_.reset();supportCache_.reset();controlTopology_.reset();throw;
  }}const auto built=std::chrono::steady_clock::now();
  std::array<double,4> poseMs{};
  std::vector<Vec> beforeRelief,detailNormals,posedAsset;auto points=mount_.Repose(compoundCache_?*supportCache_:*cached_,asset_,plan_,state,&beforeRelief,&detailNormals,&poseMs,compoundCache_?&posedAsset:nullptr);
  if(compoundCache_){auto source=compound_->Source(posedAsset,state);beforeRelief=compoundCache_->Evaluate(source,beforeRelief);points=compoundCache_->Evaluate(source,points);detailNormals.resize(points.size());}
  const auto posed=std::chrono::steady_clock::now();
  auto pair=controlTopology_->normals->Pair(points,beforeRelief,plan_.Arena());
  auto geometric=std::move(pair.first),smoothGeometry=std::move(pair.second);std::vector<Vec> normals(points.size());
  const auto normaled=std::chrono::steady_clock::now();
  std::vector<Vec> measured(points.size());if(state.surfaceNormals)for(auto c:cached_->moduleVertices){Vec n{};double weight=0;for(unsigned k=0;k<3;k++){auto value=state.surfaceNormals->at(asset_.faces[c.parent][k]);if(Dot(value,value)>1e-12){n=Add(n,Scale(value,c.donor[k]));weight+=c.donor[k];}}if(weight>1-1e-8)measured[c.vertex]=Unit(n);}
  std::vector<Vec> baseline(points.size());
  plan_.For(unsigned(points.size()),[&](unsigned i){baseline[i]=Unit(Transport(templateNormals_[i],templateGeometry_[i],geometric[i]));normals[i]=Dot(measured[i],measured[i])>1e-12?measured[i]:baseline[i];});
  // Retained source normals describe the pre-relief skin. Carry their detail
  // through the new geometric normal; otherwise real folds remain flat-lit.
  if(asset_.skin)for(auto c:cached_->moduleVertices){bool affected=false;for(unsigned k=0;k<3;k++)affected|=c.donor[k]>0&&asset_.skin->Active(asset_.faces[c.parent][k]);if(affected&&Dot(measured[c.vertex],measured[c.vertex])>1e-12)normals[c.vertex]=Unit(Transport(measured[c.vertex],smoothGeometry[c.vertex],geometric[c.vertex]));}
  for(unsigned i=0;i<points.size();i++)if(Dot(detailNormals[i],detailNormals[i])>0)normals[i]=Unit(Add(normals[i],detailNormals[i]));
  // Reconcile AFTER geometric relief transport and fine normal detail. The
  // earlier ordering constrained the neck against pre-relief endpoint normals,
  // then changed the retained sac below it, reintroducing its horizontal join.
  // Endpoint vertices are not loft interiors, so these final fields are stable
  // throughout this loop and shared by every incident generated strip.
  plan_.For(unsigned(asset_.lofts.size()),[&](unsigned index){const auto& loft=asset_.lofts[index];auto i=assetToSurface_[loft.vertex],a=assetToSurface_[loft.start],b=assetToSurface_[loft.end];if(i==~0u||a==~0u||b==~0u)return;
   auto n=BlendEndpointNormal(normals[i],normals[a],loft.t);
   normals[i]=Unit(BlendEndpointNormal(n,normals[b],1-loft.t));
  });
  // Carry retained shading directions through the geometrically conformed
  // entry. Shared endpoint normals alone do not constrain the adjacent strip.
  const auto& rootRings=cached_->surface.rings;
  for(unsigned row=1;row+1<rootRings.size();row++){
   const double t=.5*(1-std::cos(3.14159265358979323846*row/(rootRings.size()-1)));
   for(unsigned column=0;column<rootRings[0].size();column++){
    auto id=rootRings[row][column],a=rootRings.front()[column],b=rootRings.back()[column];
    normals[id]=BlendEndpointNormal(BlendEndpointNormal(normals[id],normals[a],t),normals[b],1-t);
   }
  }
  if(compoundCache_){
   const auto& rings=compoundCache_->rings;std::vector<Vec> first,last;double perimeter=0,length=0;
   for(unsigned col=0;col<rings.front().size();col++){auto a=rings.front()[col],b=rings.back()[col];first.push_back(normals[a]);last.push_back(normals[b]);length+=std::sqrt(Dot(Sub(points[a],points[b]),Sub(points[a],points[b])));auto edge=Sub(points[rings.front()[(col+1)%rings.front().size()]],points[a]);perimeter+=std::sqrt(Dot(edge,edge));}
   length/=rings.front().size();
   PeriodicNormalField firstField(first,compoundCache_->frameCoordinates,compoundCache_->framePeriod),lastField(last,compoundCache_->frameCoordinates,compoundCache_->framePeriod);
   for(unsigned row=1;row+1<rings.size();row++){
    double t=compound_->reference.parameters[row];if(t>=.25&&t<=.75)continue;
    auto a=t<.25?firstField.At(t*length/perimeter):first;auto b=t>.75?lastField.At((1-t)*length/perimeter):last;
    for(unsigned col=0;col<rings[row].size();col++){auto id=rings[row][col];normals[id]=BlendEndpointNormal(BlendEndpointNormal(normals[id],a[col],t),b[col],1-t);}
   }
  }
  const auto shaded=std::chrono::steady_clock::now();
  std::vector<Vec> livePatchTangents(points.size());std::vector<double> livePatchSigns(points.size());
  if(compoundCache_)for(const auto& d:StripDifferentials(points,compoundCache_->rings,compoundCache_->frameCoordinates,compoundCache_->framePeriod)){
   auto n=normals[d.vertex];auto t=Unit(Sub(d.tangent,Scale(n,Dot(n,d.tangent))));
   livePatchTangents[d.vertex]=contract_.calibration.VectorToTarget(t);
   livePatchSigns[d.vertex]=Dot(Cross(n,t),d.meridian)<0?-1:1;
  }
  auto controlPoints=points;
  plan_.For(unsigned(points.size()),[&](unsigned i){normals[i]=contract_.calibration.VectorToTarget(normals[i]);points[i]=useFixed_[i]?nativeFixed_[i]:contract_.calibration.PointToTarget(points[i]);});
  std::vector<std::uint32_t> packedNormal(points.size()),packedTangent(shading_.size());
  plan_.For(unsigned(points.size()),[&](unsigned i){packedNormal[i]=Pack(normals[i],1);});
  plan_.For(unsigned(shading_.size()),[&](unsigned i){const auto& row=shading_[i];auto v=row.vertex;auto tangent=contract_.calibration.VectorToTarget(Transport(row.tangent,templateGeometry_[v],geometric[v]));double sign=row.sign;
   // Preserve the retained chart aliases at the rims. Only rows belonging to
   // the connector's dedicated UV rectangle use its live material direction.
   if(livePatchSigns[v]&&row.compoundChart){tangent=livePatchTangents[v];sign=livePatchSigns[v];}
   tangent=Unit(Sub(tangent,Scale(normals[v],Dot(normals[v],tangent))));packedTangent[i]=Pack(tangent,sign<0?0:3);});
  const auto packed=std::chrono::steady_clock::now();
  auto frame=std::make_shared<ModularFrame>();frame->frames=state.frames;frame->rebuilt=rebuild;frame->materialScale=state.materialScale;
  frame->controlTopology=controlTopology_;frame->controlPoints=std::move(controlPoints);
  frame->controlTangents.resize(controlTopology_->sourceLofts.size());
  plan_.For(unsigned(controlTopology_->sourceLofts.size()),[&](unsigned index){auto i=controlTopology_->sourceLofts[index];
   const auto& l=asset_.lofts[i];
   auto a=surface::modular::Direction(l.first,l.firstOwner,asset_.reference,state);
   auto b=surface::modular::Direction(l.last,l.lastOwner,asset_.reference,state);
   frame->controlTangents[index]={a,b};
  });
  {
   const auto& rings=cached_->surface.rings;const auto& p=frame->controlPoints;
   const double dt=.5*(1-std::cos(3.14159265358979323846/(rings.size()-1)));
   for(unsigned row=1;row+1<rings.size();row++)for(unsigned column=0;column<rings[0].size();column++)
    frame->controlTangents.push_back({Scale(Sub(p[rings[1][column]],p[rings[0][column]]),1/dt),Scale(Sub(p[rings.back()[column]],p[rings[rings.size()-2][column]]),1/dt)});
  }
  if(compoundCache_){const auto& rings=compoundCache_->rings;const auto& p=frame->controlPoints;double first=compound_->reference.parameters[1],last=1-compound_->reference.parameters[compound_->reference.parameters.size()-2];for(unsigned row=1;row+1<rings.size();row++)for(unsigned col=0;col<rings[row].size();col++)frame->controlTangents.push_back({Scale(Sub(p[rings[1][col]],p[rings[0][col]]),1/first),Scale(Sub(p[rings.back()[col]],p[rings[rings.size()-2][col]]),1/last)});}
  frame->controlFrame.root=Add(state.frames[1].origin,cached_->fitTranslation);
  if(state.shaftMaterial)frame->controlFrame.root=Add(surface::modular::SocketMaterialState(state,cached_->materialRoot).shapeFrames[1].origin,cached_->fitTranslation);
  frame->controlFrame.tip=Add(state.frames[12].origin,cached_->fitTranslation);
  frame->controlFrame.lobes=Add(Scale(Add(state.frames[13].origin,state.frames[14].origin),.5),Add(cached_->fitTranslation,cached_->suspensionTranslation));
  frame->controlFrame.bodyOrigin=cached_->anchor;frame->controlFrame.basis=state.shapeFrames[1].basis;
  frame->controlFrame.radius=state.sectionRadius;frame->controlFrame.bodyRadius=controlBodyRadius_;
  if(state.shaftMaterial){auto material=surface::modular::SocketMaterialState(state,cached_->materialRoot);for(unsigned i=1;i<=12;i++)frame->frames[i]=material.frames[i];}
  for(unsigned i=1;i<15;i++)frame->frames[i].origin=Add(frame->frames[i].origin,cached_->fitTranslation);
  for(unsigned i=13;i<15;i++)frame->frames[i].origin=Add(frame->frames[i].origin,cached_->suspensionTranslation);
  for(unsigned i=1;i<15;i++){frame->frames[i].origin=contract_.calibration.PointToTarget(frame->frames[i].origin);for(auto& v:frame->frames[i].basis)v=contract_.calibration.VectorToTarget(v);}

  for(unsigned index=0;index<4;index++){const auto& layout=layouts_[index];auto& part=frame->parts[index];part.resource=layout.resource;part.lod=layout.lod;part.carrierFirst=layout.first;part.carrierCount=layout.count;part.indices=layout.indices;part.presentation=layout.presentation;part.controlVertices=layout.controlVertices;part.vertices.reserve(layout.rows.size());const auto& r=contract_.resources[layout.resource];
   part.vertices.resize(layout.rows.size());plan_.For(unsigned(layout.rows.size()),[&](unsigned index){const auto& row=layout.rows[index];const auto i=row.vertex;ModularVertex v;for(unsigned k=0;k<3;k++)v.position[k]=float((points[i][k]-r.bias[k])/r.scale[k]);v.bones=row.bones;v.weights=row.weights;v.normal=packedNormal[i];v.tangent=packedTangent[row.shading];v.uv=row.uv;v.color=row.color;v.reflection=row.reflection;part.vertices[index]=v;});
  }const auto done=std::chrono::steady_clock::now();
  auto ms=[](auto a,auto b){return std::chrono::duration<double,std::milli>(b-a).count();};
  frame->stageMilliseconds={ms(start,built),ms(built,posed),ms(posed,normaled),ms(normaled,shaded),ms(shaded,packed),ms(packed,done)};
  frame->poseMilliseconds=poseMs;
  frame->milliseconds=ms(start,done);return frame;
 }
};
}
