"""Rebind canonical garment donors to measured cooked Geralt surfaces."""
import re,struct,json,sys,argparse
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from mod import ROOT,digest,read_json,write_json
from bind_wolverine_v2 import nearest_triangle
from packed_mesh_format import CookedMesh,decode_render_chunks
from wcc_fbx import Document,triangles
from v2_native_binding import read_binding,cooked_resource


def bind(output=None):
    r=ROOT/'v2/build';out=Path(output)if output is not None else r/'runtime-binding';source=ROOT.parent/'XMenOriginsWolverineMaleMod/src/runtime/meridian_recipe.h';text=source.read_text()
    block=text.split('static const malemod::garments::meridian::Binding bindings[]={',1)[1].split('};',1)[0]
    records=[]
    for line in block.strip().splitlines():
        values=[float(x.rstrip('f'))for x in re.findall(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?f?',line)]
        if len(values)!=10:raise ValueError('Unknown source garment binding layout')
        records.append((np.asarray(values[:3],int),np.asarray(values[3:6]),np.asarray(values[6:9]),int(values[9])))
    if len(records)!=9002:raise ValueError('Canonical garment sample count changed')
    native_binding=read_binding(out/'geralt-source-binding.bin');vertices=[];bodyfaces=[];native_rows=[]
    fit=np.load(r/'fitted-geralt/lod0.npz');rotation=fit['rotation'];root=fit['sourceRoot'];target=fit['targetRoot']
    for resource,name in enumerate(['l_01_mg__body','t_01_mg__body_hires']):
        path,m,raw,sections=cooked_resource(resource,out);parts=[];part_rows=[];part_faces=[];physical_first=0
        index_offset=struct.unpack('<I',m.get(m.cooked,'indexBufferOffset','Uint32'))[0]
        for section in sections:
            if section['lod']!=0 or section['material']==2:continue
            count=section['vertexCount'];offset=section['positionOffset']
            q=np.frombuffer(raw,'u1',count*16,offset).reshape(-1,16)[:,:8].copy().view('<u2').reshape(-1,4)[:,:3]
            p=q/65535*np.asarray(m.scale[:3])+m.offset[:3]
            f=np.frombuffer(raw,'<u2',section['indexCount'],index_offset+section['indexFirst']*2).reshape(-1,3)
            words=np.frombuffer(raw,'<u4',count*2,section['lightingOffset']).reshape(-1,2)[:,0]
            normals=np.stack([(words>>a)&1023 for a in [0,10,20]],axis=1)/1023*2-1
            tri=p[f];agreement=np.sum(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])*normals[f].mean(1),axis=1)
            if np.mean(agreement<0)>.99:f=f[:,[0,2,1]]
            elif np.mean(agreement>0)<.99:raise ValueError('Unobserved body donor winding')
            if resource==0:
                n=int(fit['bodyCount']);auth=fit['points']*.01;body=fit['faces'];body=body[np.all(body<n,axis=1)]
                distance,_=cKDTree(auth[body].mean(1)).query(p[f].mean(1));f=f[distance<3e-5]
            parts.append(p);part_faces.append(f+physical_first)
            part_rows.append(native_binding['resources'][resource]['firstVertex']+section['firstVertex']+np.arange(count));physical_first+=count
        vertices.append(np.vstack(parts));native_rows.append(np.concatenate(part_rows));f=np.vstack(part_faces)
        # Contiguous geometry table excludes unused second LODs; native row IDs
        # remain explicit and preserve each resource's actual global offsets.
        bodyfaces.append(f+sum(len(v)for v in vertices[:-1]))
    points=np.vstack(vertices);row_ids=np.concatenate(native_rows);faces=np.vstack(bodyfaces)
    sourcepoints=[]
    for file in ['anatomy.packed','body0.packed','body1.packed']:
        raw=np.fromfile(r/'wolverine-reference/state-2'/file,'u1').reshape(-1,32);sourcepoints.append(raw[:,:12].copy().view('<f4').reshape(-1,3))
    module=(sourcepoints[0]-root)@rotation.T+target;error,anatomy_ids=cKDTree(vertices[0]).query(module*.01)
    if error.max()>3e-5:raise ValueError('Canonical anatomy donor leaves cooked module')
    body_indices=[i for i,b in enumerate(records)if b[3]];query=[]
    for i in body_indices:
        ids,w,offset,surface=records[i];bank=np.array([sourcepoints[1][j-17449]if 17449<=j<17449+15168 else sourcepoints[2][j-41435]if 41435<=j<41435+5615 else (_ for _ in ()).throw(ValueError('Unknown canonical body donor'))for j in ids]);q=(bank*w[:,None]).sum(0);query.append(((q-root)@rotation.T+target)*.01)
    donors,weights,distances=nearest_triangle(np.asarray(query),points,faces);new={i:(row_ids[d],w)for i,d,w in zip(body_indices,donors,weights)}
    sys.path.insert(0,str(ROOT.parent/'MaleMod'))
    from malemod_base.garment_fit import clear_rebound_shell
    face_block=source.read_text().split('::Face faces[]={',1)[1].split('};',1)[0]
    garment_faces=np.asarray([[int(v)for v in re.findall(r'\d+',line)]for line in face_block.strip().splitlines()])
    # Native candidate06 and rest-surface probes found up to 1.73 mm of
    # triangle-interior penetration despite positive vertex offsets. The
    # measured 3.1 mm minimum clears those chords. Move complete closed shells
    # together so their authored layer separation and topology are retained.
    offsets,band_clearance=clear_rebound_shell(np.array([x[2]for x in records]),garment_faces,2561,3247,.31)
    offsets,clearance=clear_rebound_shell(offsets,garment_faces,3247,4239,.31)
    if max(clearance['maximumNormalShift'],band_clearance['maximumNormalShift'])>.6:raise ValueError('Garment correction exceeds measured 6 mm fit budget')
    payload=bytearray(b'MMV2G02\0')+struct.pack('<I',len(records))
    for i,(ids,w,offset,surface)in enumerate(records):
        if surface:ids,w=new[i]
        else:ids=native_rows[0][anatomy_ids[ids]]
        payload+=struct.pack('<3I6fI',*ids,*w,*offsets[i],surface)
    path=out/'geralt-meridian-binding.bin';path.write_bytes(payload)
    report=dict(schema='malemod.witcher-v2-meridian-binding/1',bindingSHA256=digest(path),canonicalRecipeSHA256=digest(source),nativeBindingSHA256=digest(out/'geralt-source-binding.bin'),samples=len(records),bodySamples=len(body_indices),maximumBodyRefitDistanceMeters=float(distances.max()),canonicalAnatomyDonorErrorMeters=float(error.max()),bandClearanceAuthorUnits=band_clearance,strapClearanceAuthorUnits=clearance,observedNative=False,attachmentGatePassed=False)
    write_json(out/'meridian-binding.json',report);print(json.dumps(report,indent=2));return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path);args=parser.parse_args();bind(args.output)
