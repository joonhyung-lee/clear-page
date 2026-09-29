"""Export recorded MPC populations, scores, elites, and executed commands."""
import argparse,json
from pathlib import Path
import numpy as np
import mujoco
p=argparse.ArgumentParser();p.add_argument('baseline',type=Path);p.add_argument('optimized',type=Path);args=p.parse_args()
result={}
for key,folder in [('baseline',args.baseline),('optimized',args.optimized)]:
 roll=dict(np.load(folder/'task.rollouts.npz',allow_pickle=False));states=dict(np.load(folder/'task.npz',allow_pickle=False));meta=json.loads(str(roll['metadata']))
 assert np.isfinite(roll['eef_world']).all()
 future_times=meta.get('future_times',np.arange(roll['eef_world'].shape[2])*meta['step_s'])
 assert len(future_times)==roll['eef_world'].shape[2]
 oid=int(roll['object_id'][0]);ids=np.flatnonzero(roll['object_id']==oid);source_count=len(ids)
 if len(ids)>240:ids=ids[np.unique(np.linspace(0,len(ids)-1,240).round().astype(int))]
 if 'object_qposadr' in meta:
  object_address=int(meta['object_qposadr']);size=meta['object_size']
 else:
  model=mujoco.MjModel.from_binary_path(str(folder/'task.mjb'))
  body=mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_BODY,'object/box' if oid==0 else f'object_{oid}/box')
  object_address=int(model.jnt_qposadr[model.body_jntadr[body]])
  size=(model.geom_size[np.flatnonzero(model.geom_bodyid==body)[0]]*2).tolist()
 ref=next(p['poses'] for p in json.loads(str(states['reference_paths'])) if p['object_id']==oid)
 updates=[]
 for i in ids:
  k=int(np.argmin(abs(states['time']-roll['time_s'][i])))
  updates.append(dict(sourceIndex=int(i)+1,time=float(roll['time_s'][i]),until=float(roll['valid_until_s'][i]),
   paths=roll['eef_world'][i].round(5).tolist(),costs=[round(float(c),5) if np.isfinite(c) else None for c in roll['costs'][i]],
   elites=roll['elite_indices'][i].tolist(),applied=int(roll['applied_candidate'][i]),
   object=states['qpos'][k,object_address:object_address+3].round(5).tolist(),robot=states['qpos'][k,:3].round(5).tolist()))
 result[key]=dict(updates=updates,sourceUpdates=source_count,objectSize=size,reference=ref,horizon=meta['horizon_s'],step=meta['step_s'],population=24,
  executionPreview=0 if key=='optimized' else 1,selector=meta['selector'],futureTimes=list(future_times))
def rounded(value):
 if isinstance(value,float):return round(value,5)
 if isinstance(value,list):return [rounded(x) for x in value]
 if isinstance(value,dict):return {k:rounded(v) for k,v in value.items()}
 return value
Path(__file__).resolve().parents[1].joinpath('assets/mpc-process-data.js').write_text('window.CLEAR_MPC_PROCESS='+json.dumps(rounded(result),allow_nan=False,separators=(',',':'))+';\n')
print({key:len(value['updates']) for key,value in result.items()})
