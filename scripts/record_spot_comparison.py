"""Record the source Spot arm MPC controllers on one shared pushing scene.

Raw results stay outside published assets. This is a qualitative whole-controller
comparison, not a benchmark result or an optimization-off ablation.
"""
import argparse
import json
from pathlib import Path
import sys
import torch
from clear_cpu_arrays import empty_cpu_arrays

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('project',type=Path);p.add_argument('output',type=Path)
p.add_argument('--controller',choices=['optimized','baseline'],required=True)
a=p.parse_args();sys.path.insert(0,str(a.project));torch.set_num_threads(2)
from experiments.exp3.development.spot_metric_path import run

row=dict(body_id='spot_arm',scene=dict(base_scene_id='qualitative-shared-box-push',world_size=[12.,12.],
    start=[3.5,6.,0.],goal=[9.5,6.],
    walls=[[0.,0.,.2,12.],[11.8,0.,12.,12.],[.2,0.,11.8,.2],[.2,11.8,11.8,12.]],
    terrain=[],objects=[dict(object_id=0,pose=[6.,6.,0.],size=[.8,.8,.6],mass_kg=4.,friction=.4)]),
    plan=dict(schema='clear-object-path-v3',units='metres-radians',parameter='path_progress',
        paths=[dict(object_id=0,poses=[[6.+2.*i/7,6.,0.] for i in range(8)],body_part=None)]))
ours=a.controller=='optimized'
config=dict(device='cpu',seed=10,worlds=16,guide_only=False,radius=.55,
    body='spot_arm',selector='laqdpp' if ours else 'topk',eef_cross_track=True,
    execute_best=True,arm_standoff=.8,interaction_budget=60.,
    eef_yaw_gain=1. if ours else .2,horizon_s=1.,replan_every=5,
    transition_speed=1. if ours else .6,arm_trust_region=1. if ours else .35,
    transition_roll_gain=1.5 if ours else 0.,push_roll_gain=.5 if ours else 0.)
a.output.mkdir(parents=True,exist_ok=False)
(a.output/'comparison-input.json').write_text(json.dumps(dict(row=row,config=config),indent=2))
with empty_cpu_arrays():
    result=run(row,a.output,**config)
print(json.dumps(dict(status=result['status'],task_success=result['task_success'])),flush=True)
