"""Add recorded complex terrain and manipulation scenes to the checkpoint embedding explorer.

Added points are evaluation replays, never training labels. The projection
is recomputed from the same checkpoint features for every original and new row.
"""
import argparse,json,hashlib,sys,subprocess
from pathlib import Path
import numpy as np
import torch
from sklearn.manifold import TSNE
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('project',type=Path);p.add_argument('dataset',type=Path);p.add_argument('checkpoint',type=Path);p.add_argument('replay',type=Path,nargs='+')
p.add_argument('--physics-python',default=sys.executable,help='Interpreter with the MuJoCo version that wrote the replay')
p.add_argument('--feature-cache',type=Path,help='Private cache of encoded inputs, keyed by source and checkpoint hashes')
a=p.parse_args();sys.path.insert(0,str(a.project))
from experiments.exp3.trajectory_v3.shared_morphology import load_shared_checkpoint
from experiments.exp3.trajectory_v3.shared_cli import make_navigator,add_current_navigation
from experiments.exp3.trajectory_v3.data import collate
model,record=load_shared_checkpoint(a.checkpoint);model.eval();torch.set_num_threads(2)
file=a.dataset/'shared_teachers.jsonl';assert hashlib.sha256(file.read_bytes()).hexdigest()==record['training_state']['identity']['input_hashes']['data']
rows=[json.loads(x) for x in file.read_text().splitlines()]
root=Path(__file__).resolve().parents[1];out=root/'assets/learning-samples.js';d=json.loads(out.read_text().split('=',1)[1].rstrip(';\n'))
original=[s for s in d['ordering'] if s['split'] in ('train','val','validation')]
assert len(original)==len(rows)
contexts=[]
for replay in a.replay:
 scene=json.loads((replay/'scene.json').read_text());plan=json.loads((replay/'planner.json').read_text())
 base=next(r for r in rows if r['body_id']==plan['body_id'])
 contexts.append((replay,scene,plan,base,{**base,'scene':scene,'split':'evaluation'}))
extras=[c[-1] for c in contexts]
navigator=make_navigator(model,record['controller_profiles'],record['navigation']);features=[];predictions=[]
identity=hashlib.sha256(a.checkpoint.read_bytes()+file.read_bytes()+json.dumps(extras,sort_keys=True).encode()+Path(__file__).read_bytes()).hexdigest()
cached=json.loads(a.feature_cache.read_text()) if a.feature_cache and a.feature_cache.exists() else None
if cached and cached['identity']==identity:
 features=cached['features'];predictions=cached['predictions']
 print('Reused verified feature cache',flush=True)
else:
 for i,row in enumerate([*rows,*extras]):
  batch=collate([row],model.config['waypoints'],scene_dim=model.config['scene_dim'],include_targets=False)
  with torch.no_grad():
   batch=add_current_navigation(batch,[row],navigator);h=model._encode(batch)
   features.append(h['tokens'][0,h['key_mask'][0]].mean(0).tolist())
   predictions.append(dict(selection=h['selection'][0].sigmoid().tolist(),mu=h['mu'][0].tolist(),sigma=h['sigma'][0].tolist()))
  if i%10==0:print('Encoded',i+1,'of',len(rows)+len(extras),flush=True)
 if a.feature_cache:
  a.feature_cache.parent.mkdir(parents=True,exist_ok=True)
  a.feature_cache.write_text(json.dumps(dict(identity=identity,features=features,predictions=predictions),allow_nan=False))
joint_reader='''import json,sys,mujoco
m=mujoco.MjModel.from_binary_path(sys.argv[1]);addresses={}
for b in range(m.nbody):
 name=m.body(b).name
 if name=='object/box':key=0
 elif name.startswith('object_') and name.endswith('/box'):key=int(name.split('/')[0].split('_')[1])
 else:continue
 addresses[key]=int(m.jnt_qposadr[m.body_jntadr[b]])
print(json.dumps(addresses))
'''
def yaw(q):
 w,x,y,z=q;return float(np.arctan2(2*(w*z+x*y),1-2*(y*y+z*z)))
added=[]
for index,(replay,scene,plan,base,extra) in enumerate(contexts):
 source=replay/'task.npz';source=source if source.exists() else replay/'physics/task.npz'
 states=np.load(source)
 if 'body_id' in states:assert str(states['body_id'])==plan['body_id']
 if 'scene' in states:
  recorded_scene=json.loads(str(states['scene']))
  for key in ('world_size','start','goal','walls','terrain','objects'):
   assert recorded_scene[key]==scene[key],f'Replay and context disagree: {key}'
 assert np.isfinite(states['qpos']).all() and np.isfinite(states['time']).all()
 assert (np.diff(states['time'])>0).all()
 np.testing.assert_allclose(states['qpos'][0,:2],scene['start'][:2],atol=1e-5)
 object_joints={int(k):v for k,v in json.loads(subprocess.check_output([a.physics_python,'-c',joint_reader,str(source.with_suffix('.mjb'))],text=True)).items()}
 frames=[]
 for i in np.unique(np.linspace(0,len(states['time'])-1,160).astype(int)):
  q=states['qpos'][i];objects=[]
  for obj in scene['objects']:
   j=object_joints[obj['object_id']];objects.append([float(q[j]),float(q[j+1]),yaw(q[j+3:j+7])])
  frames.append([float(states['time'][i]),float(q[0]),float(q[1]),yaw(q[3:7]),objects,float(q[2])])
 for obj,pose in zip(scene['objects'],frames[0][4]):
  np.testing.assert_allclose(pose[:2],obj['pose'][:2],atol=1e-5)
  assert abs(np.arctan2(np.sin(pose[2]-obj['pose'][2]),np.cos(pose[2]-obj['pose'][2])))<1e-5
 clean={k:scene[k] for k in ['world_size','start','goal','walls']}
 clean['terrain']=[{k:v for k,v in tile.items() if k in ['kind','bounds','height_m','start_height_m','end_height_m','axis','friction']} for tile in scene['terrain']]
 clean['objects']=[{k:o[k] for k in ['object_id','pose','size','mass_kg','friction']} for o in scene['objects']]
 ids=[o['object_id'] for o in scene['objects']];ranks=[-1]*len(ids);paths=[]
 for rank,path in enumerate(plan['plan']['paths']):
  i=ids.index(path['object_id']);assert ranks[i]==-1
  ranks[i]=rank;paths.append(dict(object=i,poses=path['poses']))
 prediction={k:v[:len(ids)] for k,v in predictions[len(rows)+index].items()}
 new=dict(id=len(original)+index,body=plan['body_id'],split='evaluation',scene=clean,links=len(base['structure_rows']),paths=paths,rank=ranks,rollout=frames,**prediction)
 new['scope']=('Recorded navigation in a mixed terrain maze. The recorded plan uses no object interaction.' if not paths else
               'Recorded manipulation in a maze with an 11.5 kg object and two 4 kg objects. Predictions use the displayed checkpoint.')
 added.append(new)
assert len(features)==len(predictions)==len(original)+len(added)
assert np.isfinite(features).all()
points=TSNE(n_components=2,perplexity=15,init='pca',learning_rate='auto',random_state=7,max_iter=1200).fit_transform(np.asarray(features))
d['ordering']=[*original,*added]
for sample,xy in zip(d['ordering'],points):sample['xy']=xy.tolist()
d['projection']['scope']='Checkpoint features from training and validation samples plus explicitly marked evaluation replays.'
out.write_text('window.CLEAR_LEARNING_SAMPLES='+json.dumps(d,separators=(',',':'),allow_nan=False)+';\n')
print('Published',len(d['ordering']),'actual encoded scenes with',len(added),'additional evaluation replays',flush=True)
