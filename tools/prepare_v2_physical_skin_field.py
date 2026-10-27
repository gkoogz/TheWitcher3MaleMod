"""Physical blend in source COLOR.R only; UV1-03 remains an immutable reference."""
import argparse,hashlib,json,re,shutil
from pathlib import Path
import numpy as np
from mod import ROOT,digest,read_json,write_json
from wcc_fbx import Document


def quantize(weights):
    weights=np.asarray(weights,dtype=float)
    if not np.isfinite(weights).all()or np.any(weights<0)or np.any(weights>1):raise ValueError('Physical blend weights outside0..1')
    encoded=np.floor(weights*255+.5).astype(np.uint8);error=np.abs(encoded.astype(float)/255-weights)
    if error.max(initial=0)>.5/255+1e-15:raise ValueError('Physical weight exceeds halfUNORM8 error')
    return encoded,error


def preserved_signature(document,counts):
    digest_=hashlib.sha256();mesh_ids={id(mesh):counts[lod]for lod,mesh in enumerate(document.meshes)}
    def visit(node,body=None,color=False):
        body=mesh_ids.get(id(node),body);color=color or node.name=='LayerElementColor';digest_.update(node.name.encode()+b'\0')
        for prop in node.props:
            if color and node.name=='Colors':
                values=np.asarray(prop.value).reshape(-1,4).copy();values[body:,0]=0;digest_.update(values.tobytes())
            else:digest_.update(prop.encode())
        for child in node.children:visit(child,body,color)
    for node in document.nodes:visit(node)
    return digest_.hexdigest()


def edit_r(mesh,body_count,encoded):
    layers=[n for n in mesh.children if n.name=='LayerElementColor']
    if len(layers)!=2 or not np.array_equal(layers[0].array('Colors'),layers[1].array('Colors')):raise ValueError('Expected exact mirrored native color sets')
    for layer in layers:
        if layer.child('MappingInformationType').values!=['ByVertice']or layer.child('ReferenceInformationType').values!=['Direct']:raise ValueError('Unobserved color mapping')
        before=layer.array('Colors').reshape(-1,4);after=before.copy()
        if len(encoded)!=len(after)-body_count:raise ValueError('Physical weight row count differs')
        after[body_count:,0]=np.asarray(encoded,dtype=float)/255
        np.testing.assert_array_equal(after[:body_count],before[:body_count]);np.testing.assert_array_equal(after[:,1:],before[:,1:])
        layer.set_array('Colors',after)


def atlas_proof(uv,weights,encoded):
    unique,groups=np.unique(uv,axis=0,return_inverse=True);examples=[];count=0
    for group in range(len(unique)):
        ids=np.flatnonzero(groups==group)
        if len(ids)>1 and np.ptp(encoded[ids])>0:
            count+=1
            if len(examples)<10:examples.append(dict(uv=unique[group].tolist(),rows=ids.tolist(),physicalWeightRange=[float(weights[ids].min()),float(weights[ids].max())],RByteRange=[int(encoded[ids].min()),int(encoded[ids].max())]))
    return dict(overlappedUVGroupsWithDistinctPhysicalR=count,examples=examples,fieldStoredPerVertex=True,UV0BakingUsed=False)


def physical_xml(original):
    # Ambient is removed from the new physical instance contract, not painted.
    changed,count=re.subn(rb'^[ \t]*<param name="Ambient" type="handle:ITexture" value="characters\\malemod\\anatomy\\lod[01]-ambient\.xbm" />\r?\n',b'',original,flags=re.M)
    if count!=4:raise ValueError('Expected four disconnected bakedAmbient overrides')
    return changed


def prepare(output,reference,donors,fit):
    output,reference,donors,fit=map(Path,(output,reference,donors,fit))
    if output.exists()or not output.resolve().is_relative_to((ROOT/'v2/build/materials').resolve()):raise ValueError('Use a fresh owned physical field job')
    ref=read_json(reference);source=Path(ref['outputFBX'])
    if digest(source)!=ref['outputFBXSHA256']:raise ValueError('Frozen UV1-03 reference changed')
    document=Document(source);counts=[int(np.load(fit/f'lod{lod}.npz')['bodyCount'])for lod in(0,1)]
    original=preserved_signature(document,counts);reports=[];output.mkdir(parents=True)
    for lod,mesh in enumerate(document.meshes):
        path=donors/f'lod{lod}-material-donor.npz';data=np.load(path);weights=data['seamBlend'];encoded,error=quantize(weights);count=counts[lod]
        if not np.all(encoded[data['seamModule']]==255)or not np.all(encoded[data['seamDistanceNative']>=3]==0):raise ValueError('Weld/far physical field endpoints differ')
        colors=next(n for n in mesh.children if n.name=='LayerElementColor').array('Colors').reshape(-1,4)
        original_stock=colors[:count].copy();original_gba=colors[count:,1:].copy()
        if not np.all(colors[count:,3].astype(np.float32)==np.float32(1)):raise ValueError('Original source alpha is not native255')
        edit_r(mesh,count,encoded)
        field=output/f'lod{lod}-physical-field.npz';np.savez_compressed(field,originalWeights=weights,expectedR=encoded,
            seamModule=data['seamModule'],farRows=np.flatnonzero(data['seamDistanceNative']>=3),bodyCount=count)
        reports.append(dict(lod=lod,bodyCount=count,moduleRows=len(encoded),sourceDonor=str(path),sourceDonorSHA256=digest(path),
            originalFieldSHA256=hashlib.sha256(weights.tobytes()).hexdigest(),fieldPath=str(field),fieldSHA256=digest(field),expectedRByteSHA256=hashlib.sha256(encoded.tobytes()).hexdigest(),
            maximumQuantizationError=float(error.max()),halfLSBBound=.5/255,weldR255=True,farDistance3cmR0=True,
            stockRGBAByteSHA256=hashlib.sha256(original_stock.tobytes()).hexdigest(),sourceGBAByteSHA256=hashlib.sha256(original_gba.tobytes()).hexdigest(),
            atlas=atlas_proof(data['moduleUV'],weights,encoded)))
    if preserved_signature(document,counts)!=original:raise ValueError('Non-source-R FBX values changed')
    target=output/'geralt-physical-skin.fbx';document.save(target)
    if preserved_signature(Document(target),counts)!=original:raise ValueError('Serialized FBX changed protected properties')
    xml=source.with_suffix('.xml');target.with_suffix('.xml').write_bytes(physical_xml(xml.read_bytes()))
    for lod in(0,1):shutil.copy2(reference.parent/f'lod{lod}-target-uv1.npz',output/f'lod{lod}-target-uv1.npz')
    proof=dict(schema='malemod.physical-source-skin-field/1',reference=str(reference),referenceSHA256=digest(reference),sourceFBXSHA256=digest(source),
        outputFBX=str(target),outputFBXSHA256=digest(target),outputXMLSHA256=digest(target.with_suffix('.xml')),preservedPropertiesSHA256=original,
        onlySourceColorRChanged=True,stockRGBAUnchanged=True,sourceGBAUnchanged=True,sourceAlphaNative255=True,
        geometryUV0UV1BonesNormalsTangentsUnchanged=True,normalTransport='Perpixel cotangent worldnormal in graph; no A field encoding',
        XMLDelta='Only remove four unused bakedAmbient source overrides from03; all scalar overrides/stock material retained',
        lods=reports,nativeRRoundtripVerified=False,nativeGameplayObserved=False,globallyAdopted=False)
    write_json(output/'physical-field.json',proof);return proof


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--reference',type=Path,default=ROOT/'v2/build/materials/target-uv1-03/uv1-candidate.json')
    p.add_argument('--donors',type=Path,default=ROOT/'v2/build/materials/source-anatomy-01');p.add_argument('--fit',type=Path,default=ROOT/'v2/build/fitted-geralt')
    a=p.parse_args();print(json.dumps(prepare(a.output,a.reference,a.donors,a.fit),indent=2))
