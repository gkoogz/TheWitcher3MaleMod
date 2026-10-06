"""Frozen native bodies require explicit, complete runtime adoption proof."""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import readopt_body_runtime as adoption
from mod import ROOT


class BodyAdoptionGates(unittest.TestCase):
    def setUp(self):
        self.package=ROOT/'publish/unit-adoption-package'
        self.job=ROOT/'build/body-boundary/unit-adoption-job'
        self.path=ROOT/'build/full-runtime/unit-adoption-manifest.json'
        self.base=ROOT/'unit-base'
        self.pin='b'*40;self.old='a'*40;self.adapter='c'*40
        self.files=[dict(path='mod0000MaleModBodyBoundary/content/blob0.bundle',sha256='bundle',bytes=1)]
        self.artifacts=[self.job/'part0.npz',self.job/'lower.fbx']
        self.hashes={Path(adoption.__file__):'recipe',self.package/'build-manifest.json':'manifest'}
        base=[];character=[];native=[]
        for i,name in enumerate(adoption.BASE_INPUTS):
            value='base'+str(i);self.hashes[self.base/name]=value;base.append(dict(path=name,sha256=value))
        for i,name in enumerate(adoption.CHARACTER_INPUTS):
            value='character'+str(i);self.hashes[ROOT/name]=value;character.append(dict(path=name,sha256=value,sourceSHA256=value))
        for i,path in enumerate(self.artifacts):
            value='native'+str(i);self.hashes[path]=value;native.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=value))
        self.receipt=dict(kind='frozen-native-body-runtime-adoption',runtimeBaseCommit=self.pin,nativeBuildBaseCommit=self.old,nativeBuildAdapterCommit=self.adapter,
                          package=self.package.relative_to(ROOT).as_posix(),packageManifestSHA256='manifest',files=self.files,
                          bodyJob=self.job.relative_to(ROOT).as_posix(),frozenBaseInputs=base,frozenCharacterInputs=character,nativeArtifacts=native,recipeSHA256='recipe')
        self.manifest=dict(baseCommit=self.old,files=self.files)

    def validate(self,receipt):
        def read(path):
            return receipt if Path(path)==self.path else dict(baseCommit=self.old,nativeHandleVerified=True)
        def original(repo,commit,name):
            return self.hashes[Path(repo)/name]
        with patch.object(adoption,'read_json',side_effect=read),patch.object(adoption,'verify_package',return_value=self.manifest),patch.object(adoption,'digest',side_effect=lambda p:self.hashes[Path(p)]),patch.object(adoption,'text_source_hash',side_effect=lambda p:self.hashes[Path(p)]),patch.object(adoption,'original_hash',side_effect=original),patch.object(adoption,'artifact_closure',return_value=self.artifacts):
            return adoption.validate_adoption(self.path,self.package,self.pin,dict(base=self.base))

    def test_complete_receipt_accepts_historical_native_pin(self):
        self.assertIs(self.validate(self.receipt),self.receipt)

    def test_omitted_source_native_or_package_file_is_rejected(self):
        for field in ['frozenBaseInputs','nativeArtifacts','files']:
            receipt=copy.deepcopy(self.receipt);receipt[field].pop()
            with self.subTest(field=field),self.assertRaises(ValueError):self.validate(receipt)

    def test_wrong_runtime_or_native_pin_is_rejected(self):
        for field in ['runtimeBaseCommit','nativeBuildBaseCommit']:
            receipt=copy.deepcopy(self.receipt);receipt[field]='0'*40
            with self.subTest(field=field),self.assertRaises(ValueError):self.validate(receipt)

    def test_changed_character_bytes_are_rejected(self):
        receipt=copy.deepcopy(self.receipt);receipt['frozenCharacterInputs'][0]['sha256']='changed'
        with self.assertRaises(ValueError):self.validate(receipt)

    def test_changed_native_bytes_are_rejected(self):
        receipt=copy.deepcopy(self.receipt);receipt['nativeArtifacts'][0]['sha256']='changed'
        with self.assertRaises(ValueError):self.validate(receipt)

    def test_changed_recipe_or_package_manifest_is_rejected(self):
        for field in ['recipeSHA256','packageManifestSHA256']:
            receipt=copy.deepcopy(self.receipt);receipt[field]='changed'
            with self.subTest(field=field),self.assertRaises(ValueError):self.validate(receipt)


if __name__=='__main__':unittest.main()
