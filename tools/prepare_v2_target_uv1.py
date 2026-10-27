"""Attribute-only target-detail UV1 candidate; never cook, adopt or stage."""
import argparse,hashlib,json,re,sys
from pathlib import Path
import numpy as np
from mod import ROOT,digest,read_json,write_json
from wcc_fbx import Document
from packed_mesh_format import CookedMesh
from scipy.spatial import cKDTree


def runtime_half(uv):
    # Observed WCC UV packing truncates float32 mantissas rather than using
    # NumPy's round-to-nearest float16 conversion. Native audit checks every
    # used source row and both actual sides of the stock weld bit for bit.
    result=np.asarray(uv,dtype='<f4').copy();result[...,1]=np.float32(1)-result[...,1]
    bits=result.view('<u4');exponent=((bits>>23)&255).astype(np.int32)-112
    sign=((bits>>16)&0x8000).astype('<u2');mantissa=bits&0x7fffff
    out=sign.copy();normal=(exponent>0)&(exponent<31)
    out[normal]|=((exponent[normal]<<10)|(mantissa[normal]>>13)).astype('<u2')
    for power in range(-10,1):
        take=exponent==power;out[take]|=((mantissa[take]|0x800000)>>(14-power)).astype('<u2')
    out[exponent>=31]|=0x7c00
    return out


def target_chart(points,faces,seam,target,extend):
    points=np.asarray(points);faces=np.asarray(faces);seam=np.asarray(seam,dtype=int);target=np.asarray(target)
    if len(seam)!=len(target)or target.shape[1:]!=(2,)or not np.isfinite(target).all():raise ValueError('Invalid target UV boundary')
    unique,selected=np.unique(seam,return_index=True)
    for row in unique:
        values=target[seam==row]
        if not np.all(runtime_half(values)==runtime_half(values[0])):raise ValueError('Shared source vertex has contradictory stock target UV')
    result=extend(points,faces,unique,target[selected],target[selected].mean(0),3)
    result[unique]=target[selected]
    if not np.isfinite(result).all():raise ValueError('Target UV extension is not finite')
    return result


def actual_stock_boundary(cooked,lod,points,authored_uv,seam_body):
    mesh=CookedMesh(Path(cooked).read_bytes(),allow_multi_section=True);data=Path(str(cooked)+'.1.buffer').read_bytes()
    section=next(s for s in mesh.skin_sections(data)if s['lod']==lod and s['material']==0);count=section['vertexCount']
    packed=np.frombuffer(data,'<u2',count*8,section['positionOffset']).reshape(count,8)[:,:3]
    positions=packed.astype(float)/65535*np.asarray(mesh.scale[:3])+np.asarray(mesh.offset[:3])
    words=np.frombuffer(data,'<u2',count*2,section['uvOffset']).reshape(count,2)
    values=words.view('<f2').astype(float);tree=cKDTree(positions);selected=[]
    runtime=np.asarray(authored_uv,dtype=float).copy();runtime[:,1]=1-runtime[:,1]
    for body in seam_body:
        nearby=tree.query_ball_point(points[int(body)]*.01,.00005)
        if not nearby:raise ValueError('Weld body row has no baseline native position match')
        error=np.max(abs(values[nearby]-runtime[int(body)]),axis=1);minimum=error.min()
        if minimum>.0011:raise ValueError('Weld body row leaves exact stock UV chart')
        best=words[np.asarray(nearby)[error==minimum]]
        if not np.all(best==best[0]):raise ValueError('Ambiguous actual stock UV0 weld seed')
        selected.append(best[0])
    selected=np.asarray(selected,dtype='<u2');fbx=selected.view('<f2').astype(float);fbx[:,1]=1-fbx[:,1]
    np.testing.assert_array_equal(runtime_half(fbx),selected)
    return fbx,selected


def uv1_layers(mesh):
    layers=[n for n in mesh.children if(n.name=='LayerElementUV'and n.values==[1])or(n.name=='LayerElementReflectionUV'and n.values==[0])]
    if len(layers)!=2 or any(n.child('MappingInformationType').values!=['ByVertice']or n.child('ReferenceInformationType').values!=['Direct']for n in layers):
        raise ValueError('Expected exact direct SecondUV and ReflectionUV aliases')
    if not np.array_equal(layers[0].array('UV'),layers[1].array('UV')):raise ValueError('Observed UV1 aliases disagree')
    return layers


def signature(document):
    """Hash every original property, excluding only UV1 numerical arrays."""
    result=hashlib.sha256()
    def visit(node,skip_uv=False):
        skip_uv=skip_uv or(node.name=='LayerElementUV'and node.values==[1])or(node.name=='LayerElementReflectionUV'and node.values==[0])
        result.update(node.name.encode()+b'\0')
        if not(skip_uv and node.name=='UV'):
            for prop in node.props:result.update(prop.encode())
        for child in node.children:visit(child,skip_uv)
    for node in document.nodes:visit(node)
    return result.hexdigest()


def edit_uv1(mesh,body_count,module_uv):
    layers=uv1_layers(mesh);size=len(mesh.array('Vertices'))//3
    if np.asarray(module_uv).shape!=(size-body_count,2):raise ValueError('Target UV row count differs from exact transport FBX')
    values=layers[0].array('UV').reshape(-1,2).copy();stock=values[:body_count].copy();before=values.copy()
    values[body_count:]=module_uv
    for layer in layers:layer.set_array('UV',values)
    np.testing.assert_array_equal(values[:body_count],stock)
    return dict(stockUV1SHA256=hashlib.sha256(stock.tobytes()).hexdigest(),changedSourceRows=int(np.any(values[body_count:]!=before[body_count:],axis=1).sum()))


def material_sidecar(original):
    import xml.etree.ElementTree as ET
    root=ET.fromstring(original);materials=list(root.find('materials'))
    if [m.attrib['name']for m in materials]!=['Material0','NaturalLOD0','ErectLOD0','NaturalLOD1','ErectLOD1']:raise ValueError('Transport material state identities differ')
    if any(p.attrib.get('name')=='DetailTile'for m in materials for p in m):raise ValueError('Preserve unexpected DetailTile override')
    if any(p.attrib.get('name')=='DetailPower'for p in materials[0]):raise ValueError('Stock material must remain untouched')
    pattern=rb'(<param name="DetailPower" type="Float" value=")0("\s*/>)'
    changed,count=re.subn(pattern,rb'\g<1>0.5\g<2>',original)
    if count!=4:raise ValueError('Expected four explicit source DetailPower0 overrides')
    if changed.replace(b'value="0.5"',b'value="0"')!=original:raise ValueError('Unexpected sidecar mutation')
    return changed


def prepare(output,source,donors,fit_directory,import_receipt,baseline_info):
    output,source,donors,fit_directory,import_receipt=map(Path,(output,source,donors,fit_directory,import_receipt))
    if output.exists()or not output.resolve().is_relative_to((ROOT/'v2/build/materials').resolve()):raise ValueError('Use a fresh owned UV1-only job')
    imported=read_json(import_receipt)
    baseline_info=Path(baseline_info);baseline=read_json(baseline_info)
    cooked=Path(baseline['cooked'])/'characters/models/geralt/body/model/l_01_mg__body.w2mesh'
    if digest(source)!=imported['mesh']['fbxSHA256']:raise ValueError('Transport FBX differs from official import receipt')
    states=source.with_suffix('.material-states.json');state=read_json(states)
    if state['outputSHA256']!=digest(source)or any(r['transportOnlyDuplicateFaces']!=1 for r in state['lods']):raise ValueError('Both exact state transport triangles must be retained')
    sys.path.insert(0,str(ROOT.parent/'Work/dependencies/base-wolverine'))
    from malemod_base.graft import extend_seam_field
    document=Document(source);before=signature(document);reports=[];output.mkdir(parents=True)
    for lod,mesh in enumerate(document.meshes):
        donor_path=donors/f'lod{lod}-material-donor.npz';fit_path=fit_directory/f'lod{lod}.npz'
        donor=np.load(donor_path);fit=np.load(fit_path);n=int(fit['bodyCount']);points=fit['points']
        np.testing.assert_array_equal(mesh.array('Vertices').reshape(-1,3),points)
        uv0=next(x for x in mesh.children if x.name=='LayerElementUV'and x.values==[0]).array('UV').reshape(-1,2)
        np.testing.assert_array_equal(uv0[:n],donor['bodyUV'])
        boundary,native_words=actual_stock_boundary(cooked,lod,points[:n],uv0[:n],fit['seamBody'])
        target=target_chart(points[n:],donor['moduleFaces'],donor['seamModule'],boundary,extend_seam_field)
        np.testing.assert_array_equal(runtime_half(target[donor['seamModule']]),native_words)
        report=edit_uv1(mesh,n,target);runtime=target.copy();runtime[:,1]=1-runtime[:,1]
        field_path=output/f'lod{lod}-target-uv1.npz'
        np.savez_compressed(field_path,moduleUV1FBX=target,moduleUV1Runtime=runtime,weldNativeUV0Words=native_words,weldUV1FBX=boundary,
            seamModule=donor['seamModule'],seamBody=fit['seamBody'],stockUV0FBX=uv0[:n],stockUV1FBX=uv1_layers(mesh)[0].array('UV').reshape(-1,2)[:n])
        reports.append(dict(lod=lod,bodyCount=n,sourceRows=len(target),exactWeldSamples=len(donor['seamModule']),
            exactWeldRuntimeHalfUV=True,maximumWeldFBXDoubleDifference=float(np.max(abs(target[donor['seamModule']]-uv0[fit['seamBody']]))),
            actualNativeHalfSeeds=True,targetField=str(field_path),targetFieldSHA256=digest(field_path),
            sourceUV0SHA256=hashlib.sha256(uv0[n:].tobytes()).hexdigest(),donorSHA256=digest(donor_path),fitSHA256=digest(fit_path),**report))
    if signature(document)!=before:raise ValueError('Non-UV1 FBX property changed')
    target=output/'geralt-anatomy-target-uv1.fbx';document.save(target)
    if signature(Document(target))!=before:raise ValueError('Serialized candidate changed non-UV1 properties')
    target.with_suffix('.xml').write_bytes(material_sidecar(source.with_suffix('.xml').read_bytes()))
    proof=dict(schema='malemod.target-stock-detail-uv1/1',sourceFBX=str(source),sourceFBXSHA256=digest(source),
        importReceipt=str(import_receipt),importReceiptSHA256=digest(import_receipt),sourceXMLSHA256=digest(source.with_suffix('.xml')),
        materialStatesReceiptSHA256=digest(states),outputFBX=str(target),outputFBXSHA256=digest(target),outputXMLSHA256=digest(target.with_suffix('.xml')),
        baselineInfo=str(baseline_info),baselineInfoSHA256=digest(baseline_info),baselineCookedSHA256=digest(cooked),baselineBufferSHA256=digest(Path(str(cooked)+'.1.buffer')),
        nonUV1PropertiesSHA256=before,allOtherFBXPropertiesByteIdentical=True,stockUV1Unchanged=True,sourceUV0Unchanged=True,
        materialDelta='Only four source DetailPower Float0→0.5; DetailTile inherited from graph default25; stock material unchanged',
        UV1Convention='FBX target chart, runtime(u,1-v) once; both SecondUV and ReflectionUV aliases',lods=reports,
        nativeRoundtripVerified=False,nativeGameplayObserved=False,globallyAdopted=False)
    write_json(output/'uv1-candidate.json',proof);return proof


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source',type=Path,default=ROOT/'v2/build/materials/anatomy-01/geralt-anatomy-transport.fbx')
    parser.add_argument('--donors',type=Path,default=ROOT/'v2/build/materials/source-anatomy-01')
    parser.add_argument('--fit',type=Path,default=ROOT/'v2/build/fitted-geralt')
    parser.add_argument('--import-receipt',type=Path,default=ROOT/'v2/build/materials/anatomy-01/imports.json')
    parser.add_argument('--baseline-info',type=Path,required=True)
    a=parser.parse_args();print(json.dumps(prepare(a.output,a.source,a.donors,a.fit,a.import_receipt,a.baseline_info),indent=2))
