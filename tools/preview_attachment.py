"""Render a local geometry inspection; this is not an in-game screenshot."""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from mod import ROOT,read_json
from wcc_fbx import Document,triangles


def main():
    record=read_json(ROOT/'generated/attachment.json')
    fbx=(ROOT/record['fitReport']).with_name('geralt-anatomy.fbx')
    parts=[(fbx,'attachment'),(ROOT/'build/inspection/candidates/t_01_mg__body_hires.fbx','torso'),
           (ROOT/'build/exports/geralt-upper.fbx','feet')]
    surfaces=[]
    for path,label in parts:
        if not path.exists():continue
        mesh=Document(path).meshes[0];p=mesh.array('Vertices').reshape(-1,3);f=triangles(mesh)
        normals=mesh.child('LayerElementNormal').array('Normals').reshape(-1,3)[f].mean(1)
        normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-20)
        light=np.array([.35,.65,.67]);shade=.45+.45*np.maximum(normals@light,0)
        colors=np.c_[shade*.85,shade*.94,shade,np.ones(len(shade))]
        surfaces.append((p[f],colors))
    fig=plt.figure(figsize=(13,8),facecolor='#f5f6f7')
    fig.suptitle('Geralt attachment — offline native geometry inspection',fontsize=17,y=.96)
    for index,(az,title) in enumerate([(90,'Front'),(0,'Side'),(50,'Three-quarter')]):
        ax=fig.add_subplot(1,3,index+1,projection='3d',computed_zorder=True)
        ax.set_facecolor('#f5f6f7')
        for tri,colors in surfaces:ax.add_collection3d(Poly3DCollection(tri,facecolors=colors,edgecolors='none'))
        ax.set(xlim=(-67,67),ylim=(-27,51),zlim=(0,168),title=title)
        ax.set_box_aspect((134,78,168));ax.view_init(4,az);ax.set_axis_off()
    fig.text(.5,.05,'Stock torso and waist preserved • Fitted Base reference • Native skinning\nHead/hands omitted from this inspection; live physics and game appearance are not verified here.',ha='center',fontsize=10,color='#505a65')
    output=ROOT/'build/attachment/geralt-anatomy-preview.png';fig.savefig(output,dpi=140,bbox_inches='tight')
    print(output)


if __name__=='__main__':main()
