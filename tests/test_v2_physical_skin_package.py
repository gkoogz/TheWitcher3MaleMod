import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from build_v2_physical_skin_package import validate_source_delta,GRAPH,LOWER


class PhysicalPackageGuards(unittest.TestCase):
    def setUp(self):
        self.maps={'characters/malemod/anatomy/lod%d-%s.xbm'%(lod,kind):'raw'+str(lod)+kind
            for lod in(0,1)for kind in('natural-diffuse','erect-diffuse','normal','specular')}
        self.removed={'characters/malemod/anatomy/lod%d-ambient.xbm'%lod for lod in(0,1)}
        self.original={p:'historical'for p in set(self.maps)|self.removed|{GRAPH,LOWER,'garment.w2mesh','upper.w2mesh'}}
        self.fresh={p:sha for p,sha in self.original.items()if p not in self.removed}
        self.fresh.update(self.maps);self.fresh.update({GRAPH:'physical',LOWER:'R-only'})

    def verify(self):validate_source_delta(self.original,self.fresh,self.maps,self.removed,'physical')

    def test_exact_raw_maps_and_graph_last_delta_allowed(self):self.verify()

    def test_historical_graph_overwrite_or_baked_map_rejected(self):
        for key in(GRAPH,next(iter(self.maps))):
            old=self.fresh[key];self.fresh[key]='historical'
            with self.assertRaises(ValueError):self.verify()
            self.fresh[key]=old

    def test_carrier_mutation_and_extra_old_shader_cache_rejected(self):
        self.fresh['garment.w2mesh']='changed'
        with self.assertRaises(ValueError):self.verify()
        self.fresh['garment.w2mesh']='historical';self.fresh['shaderDx12_0.cache']='old'
        with self.assertRaises(ValueError):self.verify()

    def test_cannot_remove_an_extra_stock_input_or_keep_unused_ambient(self):
        self.fresh.pop('upper.w2mesh')
        with self.assertRaises(ValueError):self.verify()
        self.fresh['upper.w2mesh']='historical';self.fresh[next(iter(self.removed))]='baked'
        with self.assertRaises(ValueError):self.verify()


if __name__=='__main__':unittest.main()
