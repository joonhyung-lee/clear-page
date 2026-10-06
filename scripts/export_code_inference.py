"""Export model inference and the corresponding scene’s recorded execution.

Only numerical model outputs and geometric execution data are published. The
recorded chord decoder and push margin remain explicit, separate from raw flow.
"""
import argparse,copy,hashlib,json,sys
from pathlib import Path
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[1]

def main():
 p=argparse.ArgumentParser();p.add_argument('--structures',type=Path,required=True);p.add_argument('--replay',type=Path,required=True);a=p.parse_args()
 project=ROOT/'clear-standalone-anonymous/runtime';sys.path.insert(0,str(project))
 from experiments.exp3.trajectory_v3.shared_morphology import load_shared_checkpoint,SharedTraversalPredictor
 from experiments.exp3.trajectory_v3.navigation import EmbodimentSpec,TerrainNavigator,clearance
 from experiments.exp3.trajectory_v3.calibration import digest
 from experiments.exp3.trajectory_v3.data import collate,decode_plan,scene_features
 from experiments.exp3.trajectory_v3.scenes import path_collision
 from experiments.exp3.trajectory_v3.contracts import ObjectPath,ObjectMotionPlan
 from experiments.exp3.trajectory_v3.plan_audit import GeometryOnlyPredictor
 from experiments.exp3.trajectory_v3.oracle_capability import approach_point,robot_after
 from clear.model.clear_core import CLEARCore
 torch.set_num_threads(2)
 checkpoint=project/'assets/checkpoints/exp3/paper/seed0/clear.pt'
 source=json.loads((a.replay/'planner.json').read_text());episode=json.loads((a.replay/'episode.json').read_text())
 source_scene=json.loads((a.replay/'scene.json').read_text())
 scene={k:source_scene[k] for k in ['world_size','start','goal','walls','terrain','objects']}
 scene['objects']=[{k:o[k] for k in ['object_id','pose','size','mass_kg','friction']} for o in scene['objects']]
 sha=hashlib.sha256(checkpoint.read_bytes()).hexdigest();assert sha==source['checkpoint_sha256']
 model,record=load_shared_checkpoint(checkpoint);rows=json.loads(a.structures.read_text())['g1']
 spec=EmbodimentSpec(rows,source['candidate_validator']['footprint_radius_m'],record['controller_profiles'][digest(rows)])
 nav=TerrainNavigator(SharedTraversalPredictor(model,record['controller_profiles']),**record['navigation'])
 context=nav.analyze(scene,spec).model_context()
 batch=collate([dict(scene=scene,structure_rows=rows,navigation_context=context)],model.config['waypoints'],scene_dim=model.config['scene_dim'],include_targets=False)
 batch={k:v.repeat(source['candidates'],*([1]*(v.dim()-1))) for k,v in batch.items()}
 seed=source['proposal_rng_seed'];steps=source['flow_steps']
 with torch.no_grad():
  h=model._encode(batch);trace=[]
  out=CLEARCore.sample(model,batch,steps=steps,generator=torch.Generator().manual_seed(seed),sample_selection=True,max_interactions=source['max_interactions'],trace=trace)
  reference=model.sample(batch,steps=steps,generator=torch.Generator().manual_seed(seed),sample_selection=True,max_interactions=source['max_interactions'])
  assert torch.equal(out['code'],reference['path_code'])
 # Identify the executed proposal by its endpoints, reversing only the logged margin.
 margin=next(e['margin_m'] for e in source['decision_trace'] if e.get('event')=='push_margin')
 matches=[]
 for i,proposal in enumerate(source['raw_proposals']):
  if [p['object_id'] for p in proposal['paths']]!=[p['object_id'] for p in source['plan']['paths']]:continue
  errs=[]
  for raw,executed in zip(proposal['paths'],source['plan']['paths']):
   start=np.array(executed['poses'][0]);end=np.array(executed['poses'][-1]);direction=end[:2]-start[:2];direction/=np.linalg.norm(direction)
   end[:2]-=margin*direction;errs.append(np.linalg.norm(end-np.array(raw['poses'][-1])))
  if max(errs)<1e-6:matches.append(i)
 assert len(matches)==1;recorded_candidate=matches[0];chosen=0
 reproduced=decode_plan(scene,dict(selected=out['selected'],rank=out['rank'],path_code=out['code']),batch_index=chosen)
 # CPU and GPU noise streams differ. Keep the fresh CPU draw distinct from
 # the archived execution reference instead of asserting false reproducibility.
 rng=torch.Generator().manual_seed(seed);draw=torch.rand(h['selection'].shape,generator=rng);score=h['mu']+h['sigma']*torch.randn(h['mu'].shape,generator=rng)
 active=[i for i,r in enumerate(out['rank'][chosen]) if r>=0]
 assert sorted(active,key=lambda i:float(score[chosen,i]))==[p.object_id for p in reproduced.paths]
 states=[]
 for t,code in trace:
  plan=decode_plan(scene,dict(selected=out['selected'],rank=out['rank'],path_code=code),batch_index=chosen)
  states.append(dict(t=float(t),paths=[dict(object=x.object_id,poses=x.poses) for x in plan.paths]))
 # Capture actual encoded components and attention using the same observation.
 layers=[layer[0] for layer in model.encoder.trunk.layers]
 for layer in layers:layer.store_attn=True
 with torch.no_grad():captured=model._encode(batch)
 for key in ['tokens','selection','mu','sigma']:torch.testing.assert_close(h[key],captured[key],atol=2e-6,rtol=1e-5)
 attention=torch.stack([layer.attn[chosen] for layer in layers]).mean((0,1))[1:4]
 torch.testing.assert_close(attention.sum(-1),torch.ones(3),atol=2e-6,rtol=0)
 _,metadata=scene_features(scene,model.config['scene_dim'],with_metadata=True)
 keys=[dict(kind='embodiment')]+[dict(kind='object',object=i) for i in range(len(scene['objects']))]+metadata
 assert len(keys)==attention.shape[-1]
 # Recheck the executed references and approach/goal routing with the logged geometry contract.
 validation=source['candidate_validator'];radius=validation['footprint_radius_m']
 geometry=TerrainNavigator(GeometryOnlyPredictor(),**validation['navigation'])
 from types import SimpleNamespace
 body=SimpleNamespace(footprint_radius_m=radius)
 work=copy.deepcopy(scene);initial_open=geometry.analyze(work,body).goal_route
 assert initial_open is None,'This explanatory scene must require opening a route'
 routes=[];checks=[]
 final=ObjectMotionPlan.from_dict(source['plan'])
 for path in final.paths:
  assert np.allclose(path.start,work['objects'][path.object_id]['pose'])
  collision=path_collision(work,path);assert not collision
  approach=geometry.analyze(work,body).route_to(approach_point(path));assert approach is not None
  routes.append(dict(kind='approach',object=path.object_id,points=np.asarray(approach).tolist()))
  checks.append(dict(object=path.object_id,collision=False,segments=[path_collision(work,ObjectPath(path.object_id,(x,y))) for x,y in zip(path.poses,path.poses[1:])]))
  work['objects'][path.object_id]['pose']=list(path.goal)
  work['start']=[*robot_after(path,work['world_size'],radius),0.]
 goal_route=geometry.analyze(work,body).goal_route;assert goal_route is not None
 routes.append(dict(kind='goal',points=np.asarray(goal_route).tolist()))
 for route in routes:assert np.isfinite(route['points']).all()
 assert episode['task_success'] and episode['status']=='goal_reached'
 result=dict(schema=2,scene=scene,checkpointSHA256=sha,seed=seed,candidate=chosen,recordedCandidate=recorded_candidate,steps=steps,
  selection=h['selection'][chosen].sigmoid().tolist(),rank=out['rank'][chosen].tolist(),
  selectionDraw=draw[chosen].tolist(),priority=score[chosen].tolist(),mu=h['mu'][chosen].tolist(),sigma=h['sigma'][chosen].tolist(),
  representation=dict(keys=keys,attention=attention.tolist(),tokens=h['tokens'][chosen].tolist(),structure=rows),
  states=states,checks=checks,referencePaths=[dict(object=p.object_id,poses=p.poses) for p in final.paths],routes=routes,
  execution=dict(duration=episode['elapsed_sim_s'],status=episode['status'],
   attempts=[dict(object=e['object_id'],approachEnd=e['approach_end_time_s'],end=e['end_time_s'],push=e['info']['push_window_s'],success=e['success']) for e in episode['attempt_log']]),
  provenance=dict(observation='Recorded G1 two-passage scene',decoding='raw',referenceDecoding='Recorded chord decoder and 0.15 m push margin',selection='model sampled',generation='Fresh CPU draw on the recorded observation. The archived executed reference is shown separately.',
   validation='Object collision, approach routes and post-interaction goal route under the recorded geometric navigation contract.'))
 (ROOT/'assets/code-native-data.js').write_text('window.CLEAR_CODE_NATIVE='+json.dumps(result,separators=(',',':'),allow_nan=False)+';\n')
 print('PASS CPU flow draw',chosen,'and recorded reference',recorded_candidate,'attention normalized, blocked route opens after two interactions, recorded goal reached',flush=True)
if __name__=='__main__':main()
