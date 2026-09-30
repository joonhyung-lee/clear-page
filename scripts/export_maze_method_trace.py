"""Export numerical CLEAR inference for the displayed multiobject maze scene."""
import argparse,json,sys
from pathlib import Path
import numpy as np
import torch
from flow_trace_diagnostics import annotate
p=argparse.ArgumentParser();p.add_argument('project',type=Path);p.add_argument('case',type=Path);p.add_argument('checkpoint',type=Path);p.add_argument('--output',type=Path);p.add_argument('--flow-order',type=int,nargs='+');p.add_argument('--global-name',default='CLEAR_MAZE_TRACE');a=p.parse_args()
sys.path.insert(0,str(a.project))
from experiments.exp3.trajectory_v3.shared_morphology import load_shared_checkpoint,SharedTraversalPredictor
from experiments.exp3.trajectory_v3.navigation import EmbodimentSpec,TerrainNavigator
from experiments.exp3.trajectory_v3.calibration import digest
from experiments.exp3.trajectory_v3.data import collate,decode_plan
from clear.model.clear_core import CLEARCore
root=Path(__file__).resolve().parents[1];torch.set_num_threads(4)
model,record=load_shared_checkpoint(a.checkpoint)
assert model.trajectory_objective=='flow'
scene=json.loads((a.case/'scene.json').read_text());rows=json.loads((a.project/'assets/checkpoints/exp3/structures.json').read_text())['g1']
controller=record['controller_profiles'][digest(rows)]
navigator=TerrainNavigator(SharedTraversalPredictor(model,record['controller_profiles']),**record['navigation'])
context=navigator.analyze(scene,EmbodimentSpec(rows,.35,controller)).model_context()
batch=collate([dict(scene=scene,structure_rows=rows,navigation_context=context)],model.config['waypoints'],scene_dim=model.config['scene_dim'],include_targets=False)
with torch.no_grad():h=model._encode(batch)
traces=[]
for seed in range(4):
 raw=[]
 with torch.no_grad():
  out=CLEARCore.sample(model,batch,steps=30,generator=torch.Generator().manual_seed(seed),sample_selection=True,max_interactions=2,trace=raw)
  reference=model.sample(batch,steps=30,generator=torch.Generator().manual_seed(seed),sample_selection=True,max_interactions=2)
 assert torch.equal(out['code'],reference['path_code'])
 decoded=[]
 for t,code in raw:
  plan=decode_plan(scene,dict(selected=out['selected'],rank=out['rank'],path_code=code))
  decoded.append([{'object':int(path.object_id),'poses':np.asarray(path.poses).tolist()} for path in plan.paths])
 rng=torch.Generator().manual_seed(seed)
 selection_draw=torch.rand(h['selection'].shape,generator=rng)
 priority=h['mu']+h['sigma']*torch.randn(h['mu'].shape,generator=rng)
 active=torch.nonzero(out['selected'][0]).flatten().tolist()
 assert sorted(active,key=lambda i:float(priority[0,i]))==sorted(active,key=lambda i:int(out['rank'][0,i]))
 traces.append(dict(seed=seed,priority=priority[0].tolist(),selectionDraw=selection_draw[0].tolist(),rank=out['rank'][0].tolist(),selected=out['selected'][0].tolist(),times=[float(t) for t,_ in raw],states=decoded))
 print('sample',seed,'selected',traces[-1]['selected'],flush=True)
public_scene={k:scene[k] for k in ['world_size','start','goal','walls','objects','terrain']}
# Strip all non-geometric source metadata before publishing.
public_scene['objects']=[{k:o[k] for k in ['object_id','pose','size','mass_kg','friction']} for o in scene['objects']]
value=dict(scene=public_scene,selection=h['selection'][0].sigmoid().tolist(),mu=h['mu'][0].tolist(),sigma=h['sigma'][0].tolist(),traces=traces,settings=dict(steps=30,noiseStd=float(model.flow.noise_std),waypoints=model.config['waypoints']),note='Actual checkpoint inference on the displayed scene. Generation time is not execution time. Validation and collision refinement are separate.')
# The recorded plan supplies a concrete illustration of supervision. It is
# not represented as a training-set example or an optimization history.
reference_data=json.loads((a.case/'planner.json').read_text())
plan=reference_data['plan']['paths']
rank=torch.full_like(batch['object_mask'],-1,dtype=torch.long)
for order,path in enumerate(plan):rank[0,int(path['object_id'])]=order
with torch.no_grad():
 losses=model.ordering.loss(h['selection'],h['mu'],h['sigma'],rank,batch['object_mask'],torch.Generator().manual_seed(0))
value['supervision']={'paths':[{'object':int(path['object_id']),'poses':path['poses']} for path in plan], 'rank':rank[0].tolist(),'losses':{k:float(v) for k,v in losses.items()},'scope':reference_data.get('scope','Recorded plan used to illustrate the implemented training targets. This is not an optimization replay or a claim that this scene was in the training set.')}
if reference_data.get('scope'):
 # Keep the end-to-end samples above unchanged. A separate conditional
 # generation demonstrates the flow head when the reference supplies order.
 value['referenceFlow']=[]
 if a.flow_order:
  assert len(set(a.flow_order))==len(a.flow_order) and all(0<=i<len(scene['objects']) for i in a.flow_order)
  rank=torch.full_like(rank,-1)
  for order,i in enumerate(a.flow_order):rank[0,i]=order
  value['conditionedOrder']=a.flow_order
 selected=(rank>=0)&batch['object_mask']
 for seed in range(4):
  raw=[]
  with torch.no_grad():
   model.flow.sample(h['objects'],h['embodiment'],h['scene'],rank,selected,30,
    torch.Generator().manual_seed(seed),key_mask=model.flow_key_mask(h,batch['object_mask']),trace=raw)
  states=[]
  for t,code in raw:
   decoded=decode_plan(scene,dict(selected=selected,rank=rank,path_code=code))
   states.append([dict(object=int(path.object_id),poses=np.asarray(path.poses).tolist()) for path in decoded.paths])
  value['referenceFlow'].append(dict(seed=seed,rank=rank[0].tolist(),selected=selected[0].tolist(),times=[float(t) for t,_ in raw],states=states))
 value['flowScope']='Conditional generation given the designated teaser reference interaction with Object 0. The reference selection is supplied to the flow head, not predicted by OrderNet. These are unexecuted checkpoint predictions.'
 if a.flow_order:
  value['flowScope']='Actual flow-head inference conditioned on the supplied illustrative order. This order is not an OrderNet prediction or a recorded execution. Ghost motion previews the generated paths; feasibility is checked separately.'
annotate(value)
(a.output or root/'assets/maze-method-trace.js').write_text('window.'+a.global_name+' = '+json.dumps(value,separators=(',',':'))+';\n')
print('Saved numerical maze trace',flush=True)
