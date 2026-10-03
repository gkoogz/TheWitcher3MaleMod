"""Prevent stale source-color atlases from silently surviving resumed cooks."""
import sys
import unittest
import tempfile
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from build_body_boundary import verified_material,verify_texture_metadata,material_policy,character_ambient


class MaterialReceipts(unittest.TestCase):
    def receipt(self):
        return dict(baseCommit='pin',materials=[dict(channel='diffuse',stockSHA256='stock',sourceSHA256='source',nativeSHA256='native',atlasSHA256='atlas',resolution=[8192,4096])])

    def test_verified_reuse_retains_original_atlas_provenance(self):
        row=verified_material(self.receipt(),'diffuse','pin','stock','source','native')
        self.assertEqual(row['atlasSHA256'],'atlas')
        self.assertTrue(row['reusedNativeImport'])

    def test_changed_source_target_native_or_base_is_rejected(self):
        for args in [('other','stock','source','native'),('pin','other','source','native'),('pin','stock','other','native'),('pin','stock','source','other')]:
            with self.subTest(args=args),self.assertRaises(ValueError):
                verified_material(self.receipt(),'diffuse',*args)

    def test_unreceipted_or_duplicate_material_is_rejected(self):
        for record in [{},dict(baseCommit='pin',materials=[]),dict(baseCommit='pin',materials=self.receipt()['materials']*2)]:
            with self.subTest(record=record),self.assertRaises(ValueError):
                verified_material(record,'diffuse','pin','stock','source','native')

    def test_missing_authored_atlas_hash_is_rejected(self):
        r=self.receipt();del r['materials'][0]['atlasSHA256']
        with self.assertRaises(ValueError):verified_material(r,'diffuse','pin','stock','source','native')

    def test_normal_native_encoding_is_verified_not_assumed(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'normal.xml'
            def write(group,compression):
                path.write_text('<dump><objects><object class="CBitmapTexture"><properties>'+''.join('<prop name="'+k+'">'+str(v)+'</prop>' for k,v in dict(textureGroup=group,compression=compression,width=16,height=16).items())+'</properties></object></objects></dump>')
            write('CharacterNormal','TCM_Normals')
            self.assertTrue(verify_texture_metadata(path,*material_policy('normal'))['nativeMetadataVerified'])
            write('WorldDiffuse','TCM_DXTNoAlpha')
            with self.assertRaises(ValueError):verify_texture_metadata(path,*material_policy('normal'))

    def test_character_ambient_transfers_packed_channels_without_treating_them_as_ao(self):
        from PIL import Image
        from mod import settings
        sys.path.insert(0,str(settings()['base']))
        image=Image.new('RGBA',(3,1))
        image.putdata([(197,134,8,255),(241,148,22,255),(255,162,33,255)])
        result,receipt=character_ambient(image,[[0,0],[.4,0],[.8,0]])
        self.assertEqual(result.getpixel((0,0)),(241,148,22,255))
        self.assertEqual(receipt['channels'],dict(R='detail mask',G='roughness',B='specularity'))
        self.assertEqual(receipt['sampleCount'],3)


if __name__=='__main__':unittest.main()
