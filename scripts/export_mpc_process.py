"""Export recorded MPC populations, scores, elites, and executed commands."""
import argparse,json
from pathlib import Path
import numpy as np
import mujoco
p=argparse.ArgumentParser();p.add_argument('baseline',type=Path);p.add_argument('optimized',type=Path);args=p.parse_args()
result={}
for key,folder in [('baseline',args.baseline),('optimized',args.optimized)]:
 roll=np.load(folder/'task.rollouts.npz',allow_pickle=False);states=np.load(folder/'task.npz',allow_pickle=False);meta=json.loads(str(roll['metadata']))
 assert np.isfinite(roll['eef_world']).all()
 assert roll['eef_world'].shape[2]==round(meta['horizon_s']/meta['step_s'])+1
 oid=int(roll['object_id'][0]);ids=np.flatnonzero(roll['object_id']==oid)
 model=mujoco.MjModel.from_binary_path(str(folder/'task.mjb'));data=mujoco.MjData(model)
 body=mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_BODY,'object/box' if oid==0 else f'object_{oid}/box')
 ref=next(p['poses'] for p in json.loads(str(states['reference_paths'])) if p['object_id']==oid)
 updates=[]
 for i in ids:
  k=int(np.argmin(abs(states['time']-roll['time_s'][i])));data.qpos[:]=states['qpos'][k];mujoco.mj_forward(model,data)
  updates.append(dict(time=float(roll['time_s'][i]),until=float(roll['valid_until_s'][i]),
   paths=roll['eef_world'][i].round(5).tolist(),costs=[round(float(c),5) if np.isfinite(c) else None for c in roll['costs'][i]],
   elites=roll['elite_indices'][i].tolist(),applied=int(roll['applied_candidate'][i]),
   object=data.xpos[body].round(5).tolist(),robot=data.qpos[:3].round(5).tolist()))
 size=(model.geom_size[np.flatnonzero(model.geom_bodyid==body)[0]]*2).tolist()
 result[key]=dict(updates=updates,objectSize=size,reference=ref,horizon=meta['horizon_s'],step=meta['step_s'],population=24,
  executionPreview=0 if key=='optimized' else 1,selector=meta['selector'])
def rounded(value):
 if isinstance(value,float):return round(value,5)
 if isinstance(value,list):return [rounded(x) for x in value]
 if isinstance(value,dict):return {k:rounded(v) for k,v in value.items()}
 return value
Path(__file__).resolve().parents[1].joinpath('assets/mpc-process-data.js').write_text('window.CLEAR_MPC_PROCESS='+json.dumps(rounded(result),allow_nan=False,separators=(',',':'))+';\n')
print({key:len(value['updates']) for key,value in result.items()})
