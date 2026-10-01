"""Authoring invariants for the native skin ownership regression."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from deformation_graph import add_deformation_component
from prepare_motion import scalar, reference, array


def source(prefix=''):
    item=prefix+'CItemEntity #0'; mesh=prefix+'CMeshComponent #1'
    dangle=prefix+'CAnimDangleComponent #2'; skin=prefix+'CMeshSkinningAttachment #3'
    def chunk(kind,key,parent,values):
        return dict(_type=kind,_key=key,_parentKey=parent,_flags=0,_vars=values)
    return dict(_extension=prefix,_chunks={
        item:chunk('CItemEntity',item,'',{'Components':array('array:2,0,ptr:CComponent',
            [reference('ptr:CComponent',mesh),reference('ptr:CComponent',dangle)])}),
        mesh:chunk('CMeshComponent',mesh,item,{'name':scalar('String','body')}),
        dangle:chunk('CAnimDangleComponent',dangle,item,{}),
        skin:chunk('CMeshSkinningAttachment',skin,dangle,{
            'parent':reference('ptr:CNode',dangle),'child':reference('ptr:CNode',mesh)})})


class DeformationOwnershipTests(unittest.TestCase):
    def test_direct_parent_precedes_skin_in_source_and_flat_tree(self):
        original=source(); original['_chunks']['CItemEntity #0']['_vars']['flat']=dict(
            _type='CR2W',**source('flatCompiledData::'))
        before=copy.deepcopy(original)
        result=add_deformation_component(original,'rig','graph',output='direct')
        self.assertEqual(original,before)
        def check(resource):
            chunks=resource['_chunks']; keys=list(chunks)
            helper=next(k for k,v in chunks.items() if v['_type']=='CAnimatedComponent')
            skin=next(k for k,v in chunks.items() if v['_type']=='CMeshSkinningAttachment')
            self.assertLess(keys.index(helper),keys.index(skin))
            self.assertEqual(chunks[skin]['_parentKey'],helper)
            self.assertEqual(chunks[skin]['_vars']['parent']['_vars']['_reference']['_value'],helper)
            for key,c in chunks.items():
                if c['_parentKey']:self.assertLess(keys.index(c['_parentKey']),keys.index(key))
                for value in c['_vars'].values():
                    if value.get('_type')=='CR2W':check(value)
        check(result)

    def test_invalid_owner_is_rejected_before_export(self):
        resource=source()
        resource['_chunks']['CMeshComponent #1']['_parentKey']='missing owner'
        with self.assertRaises(ValueError):add_deformation_component(resource,'rig','graph',output='direct')


if __name__=='__main__':unittest.main()
