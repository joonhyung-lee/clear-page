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
p.add_argument('--arm-command-shaping',choices=['bounded','none'],default='bounded',
               help='Disable only the shared joint command rate shaping in an explicitly labelled diagnostic.')
p.add_argument('--arm-trust-region',type=float,help='Explicit diagnostic override, in (0, 1] rad; never treated as the original baseline')
p.add_argument('--arm-command-hz',type=float,help='Explicit sample-and-hold arm command diagnostic; physical simulation keeps its native time step')
a=p.parse_args();sys.path.insert(0,str(a.project));torch.set_num_threads(2)
if a.arm_trust_region is not None and not 0<a.arm_trust_region<=1:
    p.error('arm trust region must be in (0, 1] radians')
if a.arm_command_hz is not None and not 1<=a.arm_command_hz<=50:
    p.error('arm command frequency must be in [1, 50] Hz')
from experiments.exp3.development.spot_metric_path import run
if a.arm_command_shaping == 'none':
    import clear.maze.spot_contact as contact
    original_step = contact.shaped_joint_step
    def unshaped_step(*args, **kwargs):
        return original_step(*args, **{**kwargs, 'enabled': False})
    contact.shaped_joint_step = unshaped_step
if a.arm_command_hz is not None:
    from clear.maze.spot_contact import SpotContactTracker
    from arm_command_diagnostic import install_sample_hold
    install_sample_hold(SpotContactTracker,a.arm_command_hz)

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
if a.arm_trust_region is not None:
    config['arm_trust_region']=a.arm_trust_region
a.output.mkdir(parents=True,exist_ok=False)
(a.output/'comparison-input.json').write_text(json.dumps(dict(row=row,config=config,
    armCommandShaping=a.arm_command_shaping,armCommandHz=a.arm_command_hz),indent=2))
with empty_cpu_arrays():
    result=run(row,a.output,**config)
if a.arm_command_shaping == 'none' or a.arm_command_hz is not None or a.arm_trust_region is not None:
    result['scope'] = 'Qualitative controller command-setting diagnostic.'
    if a.arm_command_shaping == 'none':
        result['scope']+=' Arm command velocity, acceleration and jerk shaping are disabled.'
    if a.arm_command_hz is not None:
        result['scope']+=f' Arm actuator targets use sample-and-hold updates at {a.arm_command_hz:g} Hz in both actual and forecast worlds. Physics and base control retain their native rate.'
    if a.arm_trust_region is not None:
        result['scope']+=f' Arm target trust region is {a.arm_trust_region:g} rad instead of the baseline 0.35 rad. This is a command-setting diagnostic, not the original baseline.'
    elif a.arm_command_hz is None:
        result['scope']+=' All other baseline settings are unchanged.'
    result['armCommandShaping'] = a.arm_command_shaping
    result['armCommandHz'] = a.arm_command_hz
    (a.output/'result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(dict(status=result['status'],task_success=result['task_success'])),flush=True)
