"""Check a real compiler output, deterministic authoring and negative contracts."""
import argparse,json,struct,tempfile
from pathlib import Path
from unittest.mock import patch
import soft_cloth_material as cloth
from mod import digest,write_json

def verify(graph,source,report):
    graph,source=Path(graph),Path(source)
    receipt=cloth.inspect(graph);checks=[]
    with tempfile.TemporaryDirectory(prefix='soft-cloth-proof-',dir=graph.parent)as directory:
        a,b=Path(directory)/'a.w2mg',Path(directory)/'b.w2mg';cloth.author(source,a);cloth.author(source,b)
        if a.read_bytes()!=b.read_bytes():raise ValueError('Soft authoring is not deterministic')
        checks.append('deterministic-authored-native-bytes')
    def negative(tag,change):
        state=cloth._graph(graph);change(state)
        with patch.object(cloth,'_graph',return_value=state):
            try:cloth.inspect(graph)
            except ValueError:checks.append(tag);return
        raise ValueError('Invalid optical contract accepted: '+tag)
    def scalar(state,name,value):
        proof=receipt[name];state[2][proof['exportOrdinal']-1][2]['scalar']=('Float',struct.pack('<f',value))
    negative('wrong-opacity-rejected',lambda s:scalar(s,'Opacity',1))
    negative('wrong-roughness-rejected',lambda s:scalar(s,'Roughness',.1))
    negative('wrong-specularity-rejected',lambda s:scalar(s,'Specularity',.2))
    def blend(s):
        r,_,objects,*_=s;i=next(i for i,v in enumerate(objects)if v[0]=='CMaterialGraph');objects[i][2]['blendMode']=('ERenderingBlendMode',struct.pack('<H',r.names.index('Normal')))
    negative('opaque-blend-path-rejected',blend)
    def normal(s):
        _,_,objects,name,_,array=s;i=next(i for i,v in enumerate(objects)if v[0]=='CMaterialBlockForwardLight');socket=next(i for i in array(objects[i][2],'sockets')if name(objects[i][2])=='WorldNormal');objects[socket][2]['connections']=('array:2,0,ptr:CGraphConnection',struct.pack('<I',0))
    negative('disconnected-normal-lighting-rejected',normal)
    def distortion(s):
        _,_,objects,name,*_=s;i=next(i for i,v in enumerate(objects)if 'parameterName'in v[2]and name(v[2],'parameterName')=='ShapeRefraction');objects[i][2]['scalar']=('Float',struct.pack('<f',.1))
    negative('glass-distortion-rejected',distortion)
    def compilation(s):
        _,_,objects,name,_,array=s;root=next(i for i,v in enumerate(objects)if v[0]=='CMaterialGraph');normal=next(i for i,v in enumerate(objects)if 'parameterName'in v[2]and name(v[2],'parameterName')=='Normal');ids=[i for i in array(objects[root][2],'pixelParameterBlocks')if i!=normal];objects[root][2]['pixelParameterBlocks']=('array:2,0,ptr:CMaterialParameter',struct.pack('<I',len(ids))+b''.join(struct.pack('<i',i+1)for i in ids))
    negative('missing-compiled-normal-rejected',compilation)
    result=dict(graphSHA256=digest(graph),sourceSHA256=digest(source),opticalContract=receipt,checks=checks,nativeMaterialObserved=False);write_json(Path(report),result);return result


def verify_cooked(graph,source,compiler,report):
    import copy
    graph,source,compiler=Path(graph),Path(source),Path(compiler)
    receipt=cloth.inspect_cooked(graph,source,compiler);checks=[]
    source_state=cloth._graph(source)
    def negative(tag,change):
        state=copy.deepcopy(cloth._graph(graph));change(state)
        with patch.object(cloth,'_graph',side_effect=lambda p: state if Path(p)==graph else source_state):
            try:cloth.inspect_cooked(graph,source,compiler)
            except ValueError:checks.append(tag);return
        raise ValueError('Invalid cooked cloth accepted: '+tag)
    def blend(s):
        r,_,o,*_=s;i=next(i for i,v in enumerate(o)if v[0]=='CMaterialGraph');o[i][2]['blendMode']=('ERenderingBlendMode',struct.pack('<H',r.names.index('Normal')))
    negative('cooked-blend-rejected',blend)
    def scalar(s):
        _,_,o,*_=s;i=next(i for i,v in enumerate(o)if v[0]=='CMaterialParameterScalar');o[i][2]['scalar']=('Float',struct.pack('<f',123))
    negative('runtime-scalar-mutation-rejected',scalar)
    def texture(s):
        _,_,o,*_=s;i=next(i for i,v in enumerate(o)if v[0]=='CMaterialParameterTexture');o[i][2]['texture']=('handle:ITexture',struct.pack('<i',0))
    negative('runtime-texture-mutation-rejected',texture)
    def payload(s):
        _,_,o,*_=s;i=next(i for i,v in enumerate(o)if v[0]=='CMaterialGraph');k,f,p,t=o[i];o[i]=(k,f,p,bytes([8])+t[1:])
    negative('runtime-layout-count-rejected',payload)
    def cookedflag(s):
        _,_,o,*_=s;i=next(i for i,v in enumerate(o)if v[0]=='CMaterialGraph');k,f,p,t=o[i];o[i]=(k,0,p,t)
    negative('noncooked-flag-rejected',cookedflag)
    write_json(Path(report),dict(opticalContract=receipt,checks=checks,nativeMaterialObserved=False));return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('graph',type=Path);p.add_argument('--source',required=True,type=Path);p.add_argument('--report',required=True,type=Path);a=p.parse_args();print(json.dumps(verify(a.graph,a.source,a.report),indent=2))
