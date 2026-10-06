"""Add a flat lower corridor and record wheel-actuated Husky navigation on it."""
import argparse,copy,importlib.util,json,math
from pathlib import Path
import mujoco,numpy as np
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
source=a.project/'visualization/replays/exp3/e03_parallel_terrain_g1_clear/scene.json';original=json.loads(source.read_text());scene=copy.deepcopy(original)
shift=2.4
scene['world_size'][1]+=shift
# Translate the complete original interior north; extend the side walls down to the original floor boundary.
for i,wall in enumerate(scene['walls']):
    wall[1]+=shift;wall[3]+=shift
    if i in [0,1]:wall[1]=0
    if i==2:wall[1]=0;wall[3]=.2
for tile in scene['terrain']:tile['bounds'][1]+=shift;tile['bounds'][3]+=shift
for obj in scene['objects']:obj['pose'][1]+=shift
scene['start'][1]+=shift;scene['goal'][1]+=shift;scene['start'][2]=-math.pi/2
scene['base_scene_id']='mixed-terrain-flat-lower-bypass';scene.pop('layout_group_id',None)
route=[scene['start'][:2],[1.2,1.4],[10.8,1.4],scene['goal'][:2]]
scene['route_source']='Designed obstacle-free comparison route, not a learned CLEAR plan.'
(scene_path:=a.output/'scene.json').write_text(json.dumps(scene,indent=2)+'\n')
# Validate a conservative circular footprint continuously, including all terrain patches.
radius=.7
for x,y in np.concatenate([np.linspace(s,e,500) for s,e in zip(route[:-1],route[1:])]):
    for l,b,r,t in scene['walls']+[tile['bounds'] for tile in scene['terrain']]:
        assert np.hypot(max(l-x,x-r,0),max(b-y,y-t,0))>radius
    for obj in scene['objects']:
        ox,oy,_=obj['pose'];sx,sy,_=obj['size'];assert np.hypot(max(abs(x-ox)-sx/2,0),max(abs(y-oy)-sy/2,0))>radius
spec=importlib.util.spec_from_file_location('native_husky',a.project/'experiments/exp3/trajectory_v3/husky_dynamic_execution.py');native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
native.ASSET=a.project/'assets/husky/husky_wo_plate.xml'
real_step=mujoco.mj_step;times=[];states=[];velocities=[];last=-1;captured_model=None

def record(model,data):
    global last,captured_model
    tick=int(round(data.time/.02))
    if captured_model is None:captured_model=model;mujoco.mj_saveModel(model,str(a.output/'task.mjb'))
    if tick!=last:
        last=tick;times.append(float(data.time));states.append(data.qpos.copy());velocities.append(data.qvel.copy())

def step(model,data,*args,**kwargs):
    record(model,data);return real_step(model,data,*args,**kwargs)

mujoco.mj_step=step
try:result=native.execute(scene,route,seed=0,save=a.output)
finally:mujoco.mj_step=real_step
np.savez_compressed(a.output/'task.npz',time=np.asarray(times),qpos=np.asarray(states),qvel=np.asarray(velocities))
(a.output/'route.json').write_text(json.dumps(dict(route=route,source=scene['route_source'],lower_corridor_width_m=shift,terrain_translation_y_m=shift))+'\n')
print(json.dumps({k:result[k] for k in ['status','simulated_seconds','wall_seconds','final_goal_distance','maximum_wall_penetration','maximum_object_displacement','forbidden_object_contact']}),flush=True)
