"""Build standalone figures and an offline interactive attention inspector."""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon, Circle
from PIL import Image

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('data', type=Path)
p.add_argument('output', type=Path)
a = p.parse_args()
d = json.loads(a.data.read_text())
a.output.mkdir(parents=True, exist_ok=True)
cmap = plt.get_cmap('cividis')

def corners(pose, size):
    x, y, yaw = pose
    points = np.array([[-1,-1],[1,-1],[1,1],[-1,1]])*np.array(size[:2])/2
    rotation = np.array([[np.cos(yaw),-np.sin(yaw)],[np.sin(yaw),np.cos(yaw)]])
    return points@rotation.T+[x,y]

def weights(frame, kind='encoder', fi=1):
    raw = frame[kind] if kind == 'encoder' else frame['flow'][fi]['weights']
    matrix = np.asarray(raw).mean((0,1))
    ids = list(range(len(matrix))) if kind == 'encoder' else [i for i,b in enumerate(frame['selected']) if b]
    return matrix[ids].mean(0)

def map_plot(ax, frame, mass=None, keys=None, vmax=1):
    scene=frame['scene'];w,h=scene['world_size']
    ax.set(xlim=(-.7,w+.7),ylim=(-.7,h+.7),aspect='equal');ax.set_xticks([]);ax.set_yticks([])
    for spine in ax.spines.values():spine.set_visible(False)
    ax.set_facecolor('#f5f5f0')
    for tile in scene['terrain']:
        l,b,r,t=tile['bounds'];ax.add_patch(Rectangle((l,b),r-l,t-b,color='#d4e4dc'))
    for l,b,r,t in scene['walls']:ax.add_patch(Rectangle((l,b),r-l,t-b,color='#b3b9b7'))
    for obj in scene['objects']:ax.add_patch(Polygon(corners(obj['pose'],obj['size']),facecolor='#d8b797',edgecolor='#554a40',linewidth=.6))
    if mass is not None:
        # Paint the floor first so its large footprint cannot hide object tokens.
        layers=sorted(zip(keys,mass,strict=True),key=lambda kv: {'floor':0,'wall':1,'terrain':1,'object':2,'start':3,'goal':3}.get(kv[0]['kind'],4))
        for key,value in layers:
            color=cmap(min(1,value/vmax))
            if 'bounds' in key:
                l,b,r,t=key['bounds'];ax.add_patch(Rectangle((l,b),r-l,t-b,facecolor=color,alpha=.75,edgecolor='none'))
            elif key['kind']=='object':
                ax.add_patch(Polygon(corners(key['pose'],key['size']),facecolor=color,alpha=.9,edgecolor='#fff',linewidth=.5))
            elif 'position' in key:
                ax.add_patch(Circle(key['position'][:2],.3,facecolor='none',edgecolor=color,linewidth=2))
        for l,b,r,t in scene['walls']:ax.add_patch(Rectangle((l,b),r-l,t-b,fill=False,edgecolor='#707875',linewidth=.35))
    for obj in scene['objects']:
        ax.text(obj['pose'][0],obj['pose'][1]+max(obj['size'][:2])/2+.27,str(obj['object_id']),ha='center',va='center',fontsize=8,color='#141d24',bbox=dict(facecolor='white',alpha=.85,edgecolor='none',pad=.3))
    x,y,yaw=scene['start'];tri=np.array([[.45,0],[-.25,.22],[-.25,-.22]])@np.array([[np.cos(yaw),np.sin(yaw)],[-np.sin(yaw),np.cos(yaw)]])+[x,y]
    ax.add_patch(Polygon(tri,facecolor='#142e42',edgecolor='white',linewidth=.7))
    ax.plot(*scene['goal'],'*',color='#a43635',markersize=8,markeredgecolor='white',markeredgewidth=.4)

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'pdf.fonttype':42})
vmax=max(float(weights(f).max()) for c in d['cases'] for f in c['frames'])
fig,axs=plt.subplots(len(d['cases'])*2,5,figsize=(13,14),layout='constrained')
for ci,case in enumerate(d['cases']):
    for j,frame in enumerate(case['frames'][1:]):
        map_plot(axs[ci*2,j],frame)
        map_plot(axs[ci*2+1,j],frame,weights(frame),frame['keys'],vmax)
        axs[ci*2,j].set_title(f'{frame["time"]:.1f} s',fontsize=10)
    axs[ci*2,0].set_ylabel(case['title']+'\nObservation',fontsize=10)
    axs[ci*2+1,0].set_ylabel('Shared encoder\nattention',fontsize=10)
fig.suptitle('CLEAR attention on recorded observations',fontsize=17)
fig.colorbar(plt.cm.ScalarMappable(norm=plt.Normalize(0,vmax),cmap=cmap),ax=axs.ravel().tolist(),shrink=.45,aspect=40,label='Mean attention weight · fixed scale across frames')
fig.supxlabel('Object queries averaged across 4 layers and 4 heads. Geometry-token footprints, not pixel saliency.\nEmbodiment-token mass is retained in the interactive inspector. Attention is recomputed offline.',fontsize=9)
for ext in ['png','pdf']:fig.savefig(a.output/f'attention-overview.{ext}',dpi=180,bbox_inches='tight',metadata={'Creator':'CLEAR attention export'})
plt.close(fig)

available=[c for c in d['cases'] if c['frames'][0]['flow']]
fig,axs=plt.subplots(len(available),3,figsize=(10,4.5*len(available)),squeeze=False,layout='constrained')
flowmax=max(float(weights(c['frames'][0],'flow',k).max()) for c in available for k in range(3))
for i,case in enumerate(available):
    frame=case['frames'][0]
    for j,step in enumerate(frame['flow']):
        map_plot(axs[i,j],frame,weights(frame,'flow',j),frame['flowKeys'],flowmax)
        axs[i,j].set_title(f'Flow t = {step["t"]:.2f}')
    axs[i,0].set_ylabel(case['title'])
fig.suptitle('Object-path generation attention',fontsize=16)
fig.supxlabel('Selected object queries, mean of 4 layers and 4 heads. Flow time is integration time, not execution time.\nOnly observed spatial tokens are projected. Whole-path decision tokens remain in the inspector.',fontsize=9)
fig.colorbar(plt.cm.ScalarMappable(norm=plt.Normalize(0,flowmax),cmap=cmap),ax=axs.ravel().tolist(),shrink=.7,label='Mean attention weight')
for ext in ['png','pdf']:fig.savefig(a.output/f'attention-flow.{ext}',dpi=180,bbox_inches='tight',metadata={'Creator':'CLEAR attention export'})
plt.close(fig)
template=Path(__file__).with_name('attention_inspector.html').read_text()
for name in ('attention-overview.png', 'attention-flow.png'):
    path = a.output / name
    with Image.open(path) as source:
        clean = source.copy()
    clean.info.clear()
    clean.save(path)
template=template.replace('/*__ATTENTION_DATA__*/', 'const DATA='+json.dumps(d,separators=(',',':')).replace('<','\\u003c')+';')
(a.output/'index.html').write_text(template)
(a.output/'attention.json').write_text(json.dumps(d,separators=(',',':'))+'\n')
print('Saved offline inspector, raw numeric data, PNG and PDF figures:',a.output)
