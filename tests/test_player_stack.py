"""Guard preserved stock animation, native imports and layer ownership."""
import copy
import struct
import sys
import unittest
import zlib
import tempfile
import xml.etree.ElementTree as ET
import numpy as np
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from player_rig_redirect import redirect, header_crc, OLD_RIG, NEW_RIG
from player_stack import player_script, merge_rig, native_rig_frames, verify_template_root


def native(payload,version=164,flags=0):
    strings=b'CSkeleton\0'+OLD_RIG.encode()+b'\0'
    exports=160+len(strings);chunk=exports+24
    data=bytearray(chunk+len(payload))
    data[:4]=b'CR2W';struct.pack_into('<I',data,4,version)
    struct.pack_into('<I',data,36,flags)
    data[160:exports]=strings;data[chunk:]=payload
    struct.pack_into('<III',data,40,160,len(strings),zlib.crc32(strings))
    struct.pack_into('<II',data,exports+8,len(payload),chunk)
    struct.pack_into('<I',data,exports+20,zlib.crc32(payload))
    struct.pack_into('<III',data,88,exports,1,zlib.crc32(data[exports:chunk]))
    struct.pack_into('<I',data,32,header_crc(data,0))
    return bytes(data)


class PlayerStackTests(unittest.TestCase):
    def test_shipped_nested_patch_rejects_sdk_uncooked_flags(self):
        cooked=native(native(native(b'unchanged shipped payload',flags=6),flags=6),flags=6)
        patched,record=redirect(cooked,expected_matches=3,expected_headers=3,require_cooked=True)
        self.assertTrue(record['shippedCookedFlagsVerified'])
        self.assertTrue(patched.endswith(b'unchanged shipped payload'))
        for start in record['embeddedHeaders']:
            self.assertEqual(struct.unpack_from('<I',patched,start+36)[0],6)
            self.assertEqual(header_crc(patched,start),struct.unpack_from('<I',patched,start+32)[0])
        for bad in (native(native(b'SDK source cache')),native(native(b'uncooked nested cache'),flags=6)):
            with self.assertRaises(ValueError):redirect(bad,require_cooked=True)
        with self.assertRaises(ValueError):redirect(cooked,expected_matches=3,require_cooked=True)

    def test_source_cache_staging_is_blocked_after_loading_crash(self):
        from player_stack import preserve_compiled_templates
        with self.assertRaisesRegex(ValueError,'loading CTD'):
            preserve_compiled_templates({},None,None,{})

    def test_effective_v163_player_patch_is_explicit_and_crc_checked(self):
        original=native(native(b'flattened player root',163),163)
        with self.assertRaises(ValueError):redirect(original)
        patched,evidence=redirect(original,expected_version=163)
        self.assertEqual(evidence['formatVersion'],163)
        self.assertEqual(len(original),len(patched))
        self.assertTrue(evidence['onlyImportsAndCRCsChanged'])
        self.assertTrue(patched.endswith(b'flattened player root'))
        for start in evidence['embeddedHeaders']:
            self.assertEqual(header_crc(patched,start),struct.unpack_from('<I',patched,start+32)[0])
        mixed=native(native(b'root',164),163)
        with self.assertRaises(ValueError):redirect(mixed,expected_version=163)

    def test_gate_rejects_stock_rig_in_the_flattened_effective_root(self):
        def tree(rig):
            root=ET.Element('dump')
            props=ET.SubElement(ET.SubElement(root,'object',{'class':'CMovingPhysicalAgentComponent','id':'2'}),'properties')
            ET.SubElement(props,'prop',name='name').text='man_base'
            ET.SubElement(ET.SubElement(props,'prop',name='skeleton'),'resource',path=rig)
            for name in ('animationSets','behaviorInstanceSlots','runtimeBehaviorInstanceSlots','ragdoll','steeringBehavior'):
                ET.SubElement(ET.SubElement(props,'prop',name=name),'array',count='0')
            return ET.ElementTree(root)
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'source.xml';cooked=Path(tmp)/'cooked.xml'
            tree(OLD_RIG).write(source);tree(OLD_RIG).write(cooked)
            with self.assertRaises(ValueError):verify_template_root(cooked,source)
            tree(NEW_RIG).write(cooked)
            self.assertTrue(verify_template_root(cooked,source)['privateRigImportVerified'])

    def test_native_reference_buffer_and_joint_mapping_are_verified(self):
        names=['joint_%d'%i for i in range(104)]
        fields={'bones':{'_elements':[{'_vars':{'name':{'_value':n}}} for n in names]},
            'parentIndices':{'_elements':[{'_value':i-1} for i in range(104)]},
            'rigdata':{'_elements':[{'_vars':{field:{'_vars':{a:{'_value':v} for a,v in zip('XYZW',values)}}
                for field,values in [('Position',[.1,0,0,1]),('Rotation',[0,0,0,1]),('Scale',[1,1,1,1])]}} for _ in names]},
            'lodBoneNum_1':{'_value':40}}
        values=np.asarray([[.1,0,0,1,0,0,0,1,1,1,1,1]]*104,dtype='<f4')
        def check(raw,swap=False):
            chunk=b'property records'+raw
            root=ET.Element('dump');exports=ET.SubElement(root,'exports')
            ET.SubElement(exports,'export',index='0',dataSize=str(len(chunk)),dataOffset='0 (0x0)',crc=hex(zlib.crc32(chunk)))
            skel=ET.SubElement(root,'object',{'class':'CSkeleton','id':'0'});props=ET.SubElement(skel,'properties')
            bones=ET.SubElement(ET.SubElement(props,'prop',name='bones'),'array')
            for name in names[::-1] if swap else names:
                e=ET.SubElement(bones,'element');p=ET.SubElement(ET.SubElement(e,'object'),'properties');ET.SubElement(p,'prop',name='name').text=name
            parents=ET.SubElement(ET.SubElement(props,'prop',name='parentIndices'),'array')
            for i in range(104):ET.SubElement(parents,'element').text=str(i-1)
            ET.SubElement(props,'prop',name='lodBoneNum_1').text='40'
            for prop in ('controlRigDefinition','controlRigDefaultPropertySet','controlRigSettings','teleportDetectorData'):
                ET.SubElement(ET.SubElement(props,'prop',name=prop),'reference',id='1')
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'rig';path.write_bytes(chunk);dump=Path(tmp)/'dump.xml';ET.ElementTree(root).write(dump)
                return native_rig_frames(path,dump,fields)
        self.assertLess(check(values.tobytes()),1e-6)
        changed=values.copy();changed[94,0]+=.01
        with self.assertRaises(ValueError):check(changed.tobytes())
        with self.assertRaises(ValueError):check(values.tobytes(),swap=True)
    def test_nested_crc_patch_preserves_every_other_byte(self):
        original=native(native(b'opaque compiled stock animation'))
        patched,record=redirect(original)
        self.assertEqual(len(original),len(patched))
        self.assertTrue(record['onlyRigImportsAndCRCsChanged'])
        self.assertEqual(patched.count(NEW_RIG.encode()),2)
        for start in record['embeddedHeaders']:
            self.assertEqual(header_crc(patched,start),struct.unpack_from('<I',patched,start+32)[0])
            off,count,crc=struct.unpack_from('<III',patched,start+88)
            self.assertEqual(zlib.crc32(patched[start+off:start+off+24*count]),crc)
            size,pos=struct.unpack_from('<II',patched,start+off+8)
            self.assertEqual(zlib.crc32(patched[start+pos:start+pos+size]),struct.unpack_from('<I',patched,start+off+20)[0])
        self.assertTrue(patched.endswith(b'opaque compiled stock animation'))

    def test_crc_unknown_version_and_unowned_import_rejected(self):
        good=native(native(b'pose'))
        bad=bytearray(good);bad[32]^=1
        unknown=bytearray(good);struct.pack_into('<I',unknown,4,159)
        outside=native(native(OLD_RIG.encode()+b'\0'))
        for data in (bad,unknown,outside,native(b'pose')):
            with self.assertRaises(ValueError):redirect(bytes(data))

    def test_player_layer_appends_and_cleans_only_owned_slot(self):
        source=(Path(__file__).resolve().parents[1]/'probes/runtime/maleModPhysics.ws').read_text()
        script=player_script(source,['observed_root']+['observed_%d'%i for i in range(103)])
        self.assertIn("AttachBehavior('MaleModAnatomyLayer')",script)
        self.assertIn("DetachBehavior('MaleModAnatomyLayer')",script)
        self.assertIn('runtimeBehaviorInstanceSlots.PushBack(slot)',script)
        self.assertIn('slot.alwaysOnTopOfStack = true',script)
        self.assertIn('RemovePoseLayer();',script)
        self.assertIn('player root has ',script)
        self.assertIn('controller graph handle missing',script)
        self.assertIn('AttachBehavior rejected slot',script)
        self.assertIn('BridgeBootDetail()',script)
        self.assertIn('attempt < 10',script)
        for forbidden in ('ActivateBehaviors(', 'UpdateByOtherAnimatedComponent(', 'UnfreezePose('):
            self.assertNotIn(forbidden,script)

    def test_extension_preserves_stock_prefix_and_metadata(self):
        vars={k:{'_elements':list(range(94))} for k in ('bones','parentIndices','rigdata')}
        vars['metadata']={'_value':'control rig and LOD'}
        original={'_chunks':{'CSkeleton #0':{'_vars':vars},'Control #1':{'_vars':{'native':'unchanged'}}}}
        extended=copy.deepcopy(original)
        for k in ('bones','parentIndices','rigdata'):extended['_chunks']['CSkeleton #0']['_vars'][k]['_elements']+=list(range(94,104))
        merged=merge_rig(original,extended)
        self.assertEqual(merged['_chunks']['Control #1'],original['_chunks']['Control #1'])
        self.assertEqual(merged['_chunks']['CSkeleton #0']['_vars']['metadata'],vars['metadata'])
        extended['_chunks']['CSkeleton #0']['_vars']['parentIndices']['_elements'][2]=0
        with self.assertRaises(ValueError):merge_rig(original,extended)

    def test_extended_player_lod_updates_every_weighted_authored_joint(self):
        fields={k:{'_elements':list(range(94))} for k in ('bones','parentIndices','rigdata')}
        fields['lodBoneNum_1']={'_type':'Int32','_value':40}
        original={'_chunks':{'CSkeleton #0':{'_vars':fields},'Control #1':{'_vars':{'native':'unchanged'}}}}
        extension=copy.deepcopy(original)
        for k in ('bones','parentIndices','rigdata'):
            extension['_chunks']['CSkeleton #0']['_vars'][k]['_elements']+=list(range(94,104))
        merged=merge_rig(original,extension,full_joint_lod=True)
        actual=merged['_chunks']['CSkeleton #0']['_vars']
        # Model-space computation uses this exclusive upper bound: each added
        # joint must be evaluated even when the player selects reduced detail.
        for weighted_joint in range(94,104):self.assertLess(weighted_joint,actual['lodBoneNum_1']['_value'])
        self.assertEqual(actual['bones']['_elements'][:94],fields['bones']['_elements'])
        self.assertEqual(merged['_chunks']['Control #1'],original['_chunks']['Control #1'])
        self.assertEqual(fields['lodBoneNum_1']['_value'],40)
