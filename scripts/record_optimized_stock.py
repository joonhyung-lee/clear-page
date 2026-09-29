"""Run CLEAR's existing contact controller on the SUMO box geometry.

The metric scene is translated into positive coordinates for the CLEAR adapter.
Controller and simulation code are imported from a private CLI source root.
This is a scene transfer across runtimes, not a selector-only ablation.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time

import numpy as np

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('source_root',type=Path);p.add_argument('contract',type=Path)
p.add_argument('contact_checkpoint',type=Path);p.add_argument('output',type=Path)
a=p.parse_args();sys.path.insert(0,str(a.source_root.resolve()))
import torch
from experiments.exp3.trajectory_v3 import native_sumo_task as task
from experiments.exp3.trajectory_v3.contracts import ObjectPath
from experiments.exp3.trajectory_v3.training_state import file_hash
import clear.maze.mjlab_runtime as runtime

torch.set_num_threads(2);a.output.mkdir(parents=True,exist_ok=False)
c=json.loads(a.contract.read_text());shift=np.array([4.,4.]);start=np.array(c['qpos'][:2])+shift
obj=np.array(c['qpos'][36:38])+shift;goal=np.array(c['goal'][:2])+shift
scene=dict(base_scene_id='sumo-box-geometry-transfer',world_size=[8.,8.],terrain=[],walls=[],
    floor_friction=c['floor_friction'][0],start=[*start,0.],goal=[*goal,0.],
    objects=[dict(object_id=0,pose=[*obj,0.],size=c['object_size'],mass_kg=c['object_mass'],friction=.5)],
    replay_scope='SUMO box geometry in the CLEAR runtime, translated by (4, 4) metres. Native controller comparison, not a selector ablation.')
# Match the source box's explicit inertia, contact priority and resting height.
# The source inertia is not the uniform-box inertia inferred by the adapter.
original_box_spec=runtime.box_spec
def stock_box_spec(*args,**kwargs):
    spec=original_box_spec(*args,**kwargs);body=spec.body('box')
    body.mass=c['object_mass'];body.inertia=c['object_inertia'];body.ipos=[0.,0.,0.];body.iquat=[1.,0.,0.,0.];body.explicitinertial=True
    body.pos[2]=c['qpos'][38]
    for geom in spec.geoms:geom.priority=1
    return spec
runtime.box_spec=stock_box_spec
import experiments.exp3.trajectory_v3.native_sumo as native_module
original_metric_inputs=native_module.metric_runtime_inputs
def stock_metric_inputs(scene):
    grid,kwargs=original_metric_inputs(scene)
    kwargs['initial_object_poses'][0][2]=c['qpos'][38]
    return grid,kwargs
native_module.metric_runtime_inputs=stock_metric_inputs
row=dict(scene=scene,body_id='g1',split='development')
backend=task.SumoTaskBackend(row,'cuda:0',a.output,24,seed=0,
    contact_checkpoint=str(a.contact_checkpoint),horizon_s=.6,apply_steps=1,
    contact_weight=4.,residual_space='normalized',residual_scale=.05,yaw_weight=2.,
    contact_height=.8,hand_reference='wrist_yaw',navigation_mode='holonomic',
    g1_contact_palms=True,g1_contact_palm_gain=.25,record_rollouts=True,mpc_selector='laqdpp')
# Keep the original controller and stopping conditions. Record every real step.
record=backend._record
last=-1

def report():
    global last
    record();now=backend.times[-1]
    if int(now)>last:
        last=int(now);print('time',now,'object',backend.real.poses(0)[0].tolist(),flush=True)
backend._record=report
path=ObjectPath(0,tuple((*point,0.) for point in np.linspace(obj,goal,8)))
config=dict(scope=scene['replay_scope'],seed=0,scene=scene,contact_height=.8,
    contact_checkpoint_sha256=file_hash(a.contact_checkpoint),translation=shift.tolist(),
    controller='Existing CLEAR contact tracking and LA-QDPP MPC',horizon_s=.6,step_s=backend.real.dt,
    note='The stock scene has a 1 m box. Contact prior height is 0.8 m. Runtime-specific robot reset and contact dynamics are retained.')
(a.output/'config.json').write_text(json.dumps(config,indent=2))
result=dict(success=False,status='not_started');began=time.monotonic()
try:
    result=asdict(backend.interact_trajectory(path))
finally:
    config['wall_time_s']=time.monotonic()-began
    config['contact_palm_controller']=backend.real.rt.contact_palm.metadata()
    (a.output/'config.json').write_text(json.dumps(config,indent=2))
    backend.save(result,config);backend.close()
    print(json.dumps(result),flush=True)
