"""Encode diverse, explicitly unexecuted scene queries with the displayed model.

Existing recorded samples retain their measured poses and predictions. A joint
t-SNE projection uses actual encoder features for every point. New query maps
show predicted object paths, never fabricated robot rollouts or success labels.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import torch
from sklearn.manifold import TSNE

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('project',type=Path)
p.add_argument('dataset',type=Path)
p.add_argument('checkpoint',type=Path)
p.add_argument('--cache',type=Path,required=True)
a=p.parse_args()
sys.path.insert(0,str(a.project))
from experiments.exp3.trajectory_v3.shared_morphology import load_shared_checkpoint
from experiments.exp3.trajectory_v3.shared_cli import make_navigator,add_current_navigation
from experiments.exp3.trajectory_v3.data import collate,decode_plan

torch.set_num_threads(2)
model,record=load_shared_checkpoint(a.checkpoint)
model.eval()
source=a.dataset/'shared_teachers.jsonl'
assert hashlib.sha256(source.read_bytes()).hexdigest()==record['training_state']['identity']['input_hashes']['data']
rows=[json.loads(line) for line in source.read_text().splitlines()]
templates={body:next(r for r in rows if r['body_id']==body) for body in ['g1','spot_arm']}
root=Path(__file__).resolve().parents[1]
file=root/'assets/learning-samples.js'
data=json.loads(file.read_text().split('=',1)[1].rstrip(';\n'))
original=[s for s in data['ordering'] if not s.get('queryOnly')]
navigator=make_navigator(model,record['controller_profiles'],record['navigation'])

outer=[[0,0,.2,12],[11.8,0,12,12],[.2,0,11.8,.2],[.2,11.8,11.8,12]]
layouts=[
    ('Alternating passages',[1.2,3.3,0.],[10.8,3.3],
     [[3.,.2,3.4,2.],[3.,4.6,3.4,11.8],[5.8,.2,6.2,7.4],
      [5.8,10.,6.2,11.8],[8.6,.2,9.,2.],[8.6,4.6,9.,11.8]],
     [[3.2,3.3,0.],[6.,8.7,0.],[8.8,3.3,0.]]),
    ('Branching maze',[1.2,6.,0.],[10.8,6.],
     [[3.4,.2,3.8,4.6],[3.4,7.4,3.8,10.],[5.8,2.,6.2,8.8],
      [8.2,3.2,8.6,11.8],[3.8,9.6,5.,10.],[7.,2.8,8.2,3.2]],
     [[3.6,6.,0.],[7.2,6.,0.],[10.5,10.,0.]]),
    ('Parallel terrain routes',[1.2,6.,0.],[10.8,6.],
     [[3.5,3.,8.5,3.3],[3.5,8.7,8.5,9.]],
     [[6.,6.,0.],[2.3,10.5,0.],[9.7,1.5,0.]])]
queries=[]
for layout,start,goal,walls,poses in layouts:
    for height in [.15,.3]:
        terrain=[dict(kind='ramp',bounds=[4.,.3,6.,2.7],axis=0,start_height_m=0.,end_height_m=height,friction=.8),
                 dict(kind='ramp',bounds=[6.,.3,8.,2.7],axis=0,start_height_m=height,end_height_m=0.,friction=.8),
                 dict(kind='stair_tread',bounds=[4.,9.3,4.5,11.7],height_m=height,friction=.8),
                 dict(kind='flat',bounds=[4.5,9.3,7.5,11.7],height_m=height*2,friction=.8),
                 dict(kind='stair_tread',bounds=[7.5,9.3,8.,11.7],height_m=height,friction=.8)]
        # Keep newly designed ramps and stairs in the open parallel-route layout.
        # Other layouts expose pure maze topology without intersecting terrain.
        if layout!='Parallel terrain routes':
            terrain=[]
        objects=[dict(object_id=i,pose=pose,size=[.8,.8,.6],mass_kg=4. if height==.15 else 11.5,friction=.4) for i,pose in enumerate(poses)]
        scene=dict(world_size=[12.,12.],start=start,goal=goal,walls=outer+walls,terrain=terrain,objects=objects)
        for body in templates:
            queries.append(dict(body=body,scene=scene,layout=layout))

def encode(sample):
    row={**templates[sample['body']],'scene':sample['scene']}
    batch=collate([row],model.config['waypoints'],scene_dim=model.config['scene_dim'],include_targets=False)
    with torch.no_grad():
        batch=add_current_navigation(batch,[row],navigator)
        encoded=model._encode(batch)
    feature=encoded['tokens'][0,encoded['key_mask'][0]].mean(0).tolist()
    n=len(sample['scene']['objects'])
    prediction=dict(selection=encoded['selection'][0,:n].sigmoid().tolist(),mu=encoded['mu'][0,:n].tolist(),sigma=encoded['sigma'][0,:n].tolist())
    return feature,prediction,batch

identity=hashlib.sha256(a.checkpoint.read_bytes()+source.read_bytes()+json.dumps([s['scene'] for s in original]+queries,sort_keys=True).encode()+Path(__file__).read_bytes()).hexdigest()
cache=json.loads(a.cache.read_text()) if a.cache.exists() else {}
features=[]
if cache.get('identity')==identity:
    features=cache['features']
    additions=cache['additions']
else:
    for i,sample in enumerate(original):
        feature,prediction,_=encode(sample)
        for key in prediction:
            np.testing.assert_allclose(prediction[key],sample[key],atol=5e-5,rtol=1e-5)
        features.append(feature)
        if i%10==0:print('Verified original query',i+1,'/',len(original),flush=True)
    additions=[]
    for i,query in enumerate(queries):
        feature,prediction,batch=encode(query)
        with torch.no_grad():
            output=model.sample(batch,steps=30,generator=torch.Generator().manual_seed(0),sample_selection=True,max_interactions=3)
        plan=decode_plan(query['scene'],output)
        paths=[dict(object=int(path.object_id),poses=np.asarray(path.poses).tolist()) for path in plan.paths]
        scene=copy.deepcopy(query['scene'])
        n=len(scene['objects'])
        additions.append(dict(id=len(original)+i,body=query['body'],split='query',queryOnly=True,
            scene=scene,links=len(templates[query['body']]['structure_rows']),paths=paths,
            rank=output['rank'][0,:n].tolist(),rollout=[],
            layout=query['layout'],scope='Unexecuted scene query. Paths are model predictions.',**prediction))
        features.append(feature)
        print('Encoded new scene',i+1,'/',len(queries),query['layout'],query['body'],flush=True)
    a.cache.write_text(json.dumps(dict(identity=identity,features=features,additions=additions),allow_nan=False))
assert len(features)==len(original)+len(additions)
assert np.isfinite(features).all()
xy=TSNE(n_components=2,perplexity=15,init='pca',learning_rate='auto',random_state=7,max_iter=1200).fit_transform(np.asarray(features))
data['ordering']=original+additions
for sample,point in zip(data['ordering'],xy):
    sample['xy']=point.tolist()
data['projection']['scope']='Actual checkpoint features. Recorded samples and unexecuted scene queries are distinguished in the explorer.'
file.write_text('window.CLEAR_LEARNING_SAMPLES='+json.dumps(data,separators=(',',':'),allow_nan=False)+';\n')
print('Saved',len(original),'recorded points and',len(additions),'unexecuted scene queries',flush=True)
