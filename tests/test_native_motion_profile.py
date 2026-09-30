import sys, unittest, copy
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from native_motion_profile import apply_profile
from prepare_motion import scalar,array


class NativeEnvelopeTests(unittest.TestCase):
    def test_native_limits_and_links_preserve_a_feasible_rest_shape(self):
        names=['mm_shaft_%02d'%i for i in range(8)]+['mm_scrotum_l','mm_scrotum_r']
        all_names=['pelvis','l_thigh']+names
        values={'nodeNames':array('array:2,0,String',[scalar('String',n) for n in all_names])}
        for k in ['linkAs','linkBs','linkTypes','linkLengths']:
            values[k]=array('array:2,0,Float',[scalar('Float' if k=='linkLengths' else 'Int32',0)])
        resource={'_chunks':{'CDyngResource #0':{'_vars':values}}}
        worlds=np.tile(np.eye(4),(10,1,1));worlds[:,1,3]=np.arange(10)*.04
        apply_profile(resource,names,worlds)
        read=lambda k:np.array([x['_value'] for x in values[k]['_elements']])
        limits=read('nodeDistances')
        np.testing.assert_array_equal(limits[:3],0)
        self.assertLess(limits.max(),.04/2)
        points=worlds[:,:3,3]
        lengths=np.linalg.norm(points[read('linkAs')-2]-points[read('linkBs')-2],axis=1)
        np.testing.assert_allclose(lengths,read('linkLengths'))
        self.assertEqual(len(lengths),13)
        broken=worlds.copy();broken[1]=broken[0]
        with self.assertRaises(ValueError):apply_profile(copy.deepcopy(resource),names,broken)
