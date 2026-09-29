"""Export anonymized dataset samples and actual checkpoint embeddings.

Every public field is explicitly whitelisted. Source locations and identities
are retained only as command-line inputs, never in the browser payload.
"""
import argparse, hashlib, json, sys
from pathlib import Path
from functools import lru_cache
import numpy as np
import torch
import mujoco
from sklearn.manifold import TSNE
p=argparse.ArgumentParser();p.add_argument('project',type=Path);p.add_argument('dataset',type=Path);p.add_argument('checkpoint',type=Path);p.add_argument('snapshot',type=Path);args=p.parse_args()
sys.path.insert(0,str(args.project))
from experiments.exp3.trajectory_v3.shared_morphology import load_shared_checkpoint,attach_probe_scenes,collate_probes,embodiment_from_row
from experiments.exp3.trajectory_v3.shared_cli import make_navigator,add_current_navigation
from experiments.exp3.trajectory_v3.data import collate
from experiments.exp3.trajectory_v3.navigation import scene_hash
root=Path(__file__).resolve().parents[1];torch.set_num_threads(2)
model,record=load_shared_checkpoint(args.checkpoint);model.eval()
identity=record['training_state']['identity']['input_hashes']
rows={}
for key,name in [('data','shared_teachers.jsonl'),('probes','shared_probes.jsonl')]:
 f=args.dataset/name;assert hashlib.sha256(f.read_bytes()).hexdigest()==identity[key]
 rows[key]=[json.loads(line) for line in f.read_text().splitlines()]
def source(raw):
 path=Path(raw)
 if path.exists():return path
 if path.is_symlink():return source(path.readlink())
 candidate=path if path.is_relative_to(args.snapshot) else args.snapshot/Path(*path.parts[3:])
 return source(candidate.readlink()) if candidate.is_symlink() else candidate
def physics_folder(raw):
 folder=source(raw)
 return folder if (folder/'task.npz').exists() else folder/'physics'
def clean_scene(scene):
 return {**{k:scene[k] for k in ['world_size','start','goal','walls']},
  'terrain':[{k:v for k,v in tile.items() if k in ['kind','bounds','height_m','start_height_m','end_height_m','axis','friction']} for tile in scene['terrain']],
  'objects':[{k:obj[k] for k in ['object_id','pose','size','mass_kg','friction']} for obj in scene['objects']]}
def yaw(quat):
 w,x,y,z=quat;return float(np.arctan2(2*(w*z+x*y),1-2*(y*y+z*z)))
@lru_cache(maxsize=80)
def trajectory(raw):
 folder=physics_folder(raw);data=np.load(source(folder/'task.npz'),allow_pickle=False)
 m=mujoco.MjModel.from_binary_path(str(source(folder/'task.mjb')))
 joints={}
 for body in range(m.nbody):
  name=mujoco.mj_id2name(m,mujoco.mjtObj.mjOBJ_BODY,body) or ''
  if name=='object/box' or (name.startswith('object_') and name.endswith('/box')):
   oid=0 if name=='object/box' else int(name.split('/')[0].split('_')[1])
   joints[oid]=int(m.jnt_qposadr[m.body_jntadr[body]])
 return data['time'],data['qpos'],joints
def replay(raw,scene,interval=None,limit=160):
 times,qpos,joints=trajectory(raw)
 ids=np.arange(len(times))
 if interval is not None:ids=ids[(times>=interval[0]-1e-6)&(times<=interval[1]+1e-6)]
 assert len(ids)>0
 ids=ids[np.unique(np.linspace(0,len(ids)-1,min(len(ids),limit)).astype(int))]
 frames=[]
 for i in ids:
  objects=[]
  for obj in scene['objects']:
   offset=joints[obj['object_id']];q=qpos[i,offset:offset+7];objects.append([float(q[0]),float(q[1]),yaw(q[3:7])])
  frames.append([float(times[i]),float(qpos[i,0]),float(qpos[i,1]),yaw(qpos[i,3:7]),objects])
 return frames
probes=rows['probes'];probe_output=[]
for i,row in enumerate(probes):
 folder=source(row['recording']);scene=json.loads((folder/'input.jsonl').read_text())['scene'];assert scene_hash(scene)==row['scene_hash'];row['scene']=scene
 evidence=row['execution_evidence'];interval=evidence.get('interval',evidence.get('outcome',{}).get('interval'))
 expected=evidence.get('files',{}).get('task.npz')
 if expected:assert hashlib.sha256(source(physics_folder(row['recording'])/'task.npz').read_bytes()).hexdigest()==expected
 probe_output.append(dict(id=i,body=row['body_id'],split=row['split'],scene=clean_scene(scene),links=len(row['structure_rows']),
   target=int(row['success'] and not row['collision'] and not row['fell']),query=[evidence['start'],evidence['end']],
   rollout=replay(row['recording'],scene,interval,60)))
attach_probe_scenes(probes,model.config['scene_dim']);batch=collate_probes(probes)
features=[]
hook=model.traversal_affordance.classifier.register_forward_pre_hook(lambda module,inputs:features.append(inputs[0].detach().numpy()))
with torch.no_grad():prediction=model.traversal_probe_logits(batch).sigmoid().numpy()
hook.remove();probe_embeddings=features[0]
for row,prob in zip(probe_output,prediction):row['prediction']=float(prob)
print('Traversal samples',len(probe_output),flush=True)
plans=rows['data'];plan_output=[];plan_embeddings=[];navigator=make_navigator(model,record['controller_profiles'],record['navigation'])
for i,row in enumerate(plans):
 expected=row['teacher']['execution_evidence']['files']['task.npz']
 assert hashlib.sha256(source(physics_folder(row['teacher']['recording'])/'task.npz').read_bytes()).hexdigest()==expected
 batch=collate([row],model.config['waypoints'],scene_dim=model.config['scene_dim'])
 with torch.no_grad():
  batch=add_current_navigation(batch,[row],navigator);encoded=model._encode(batch)
  masked=encoded['tokens'][0,encoded['key_mask'][0]];plan_embeddings.append(masked.mean(0).numpy())
  loss=model.ordering.loss(encoded['selection'],encoded['mu'],encoded['sigma'],batch['rank'],batch['object_mask'],torch.Generator().manual_seed(0))
 n=len(row['scene']['objects'])
 plan_output.append(dict(id=i,body=row['body_id'],split=row['split'],scene=clean_scene(row['scene']),links=len(row['structure_rows']),
  paths=[dict(object=path['object_id'],poses=path['poses']) for path in row['plan']['paths']],rank=batch['rank'][0,:n].tolist(),
  selection=encoded['selection'][0,:n].sigmoid().tolist(),mu=encoded['mu'][0,:n].tolist(),sigma=encoded['sigma'][0,:n].tolist(),
  losses={key:float(value) for key,value in loss.items()},rollout=replay(row['teacher']['recording'],row['scene'])))
 if i%10==0:print('Plan samples',i,'/',len(plans),flush=True)
def project(embeddings,output):
 points=TSNE(n_components=2,perplexity=min(15,len(output)-1),init='pca',learning_rate='auto',random_state=7,max_iter=1200).fit_transform(np.asarray(embeddings))
 for row,point in zip(output,points):row['xy']=point.tolist()
project(probe_embeddings,probe_output);project(plan_embeddings,plan_output)
value=dict(grounding=probe_output,ordering=plan_output,projection=dict(method='t-SNE',perplexity=15,seed=7,iterations=1200,
 grounding='Query-conditioned affordance features before the classifier',ordering='Mean of valid shared encoder tokens',
 scope='Actual checkpoint features of the matching training and validation dataset. These projections do not measure generalization or compare training stages.'),
 training=dict(warmupSteps=record['config']['train']['affordance_warmup_steps'],jointSteps=record['config']['train']['steps'],
 planBatch=record['config']['train']['batch_size'],probeBatch=record['config']['train']['probe_batch_size']))
# Round for compact rendering without changing the numeric evidence used above.
def rounded(x):
 if isinstance(x,float):return round(x,5)
 if isinstance(x,list):return [rounded(v) for v in x]
 if isinstance(x,dict):return {k:rounded(v) for k,v in x.items()}
 return x
(root/'assets/learning-samples.js').write_text('window.CLEAR_LEARNING_SAMPLES='+json.dumps(rounded(value),allow_nan=False,separators=(',',':'))+';\n')
print('Exported',len(probe_output),'traversal and',len(plan_output),'plan samples',flush=True)
