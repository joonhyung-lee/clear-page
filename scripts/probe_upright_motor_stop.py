"""Open-floor step response of the native walker with the requested palm pose.

This isolates locomotion from object contact and MPC. It is a diagnostic, not
a task rollout or a substitute for the main scene's initial conditions.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import numpy as np

p = argparse.ArgumentParser()
p.add_argument('--project', type=Path, required=True)
p.add_argument('--plan', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--arm-observation', choices=['relative', 'native'], required=True)
p.add_argument('--gravity-support', action='store_true')
p.add_argument('--motor', type=Path, help='Explicit compatible walker artifact for this diagnostic only')
a = p.parse_args()
a.out.mkdir(parents=True, exist_ok=False)
sys.path.insert(0, str(a.project))
os.chdir(a.project)
os.environ.setdefault('MJLAB_PUSH_LOWLEVEL_ONNX', str(a.project/'assets/pretrained/g1/locomotion/g1_sumo_flat.onnx'))
os.environ.setdefault('XDG_CACHE_HOME', '/tmp/clear-replanning-cache')
import torch
torch.set_num_threads(2)
from experiments.exp3.trajectory_v3.native_sumo import NativeG1World
if a.motor:
    from clear.maze import mjlab_runtime
    mjlab_runtime.FLAT_G1 = a.motor.resolve()

scene = json.loads(a.plan.read_text())['row']['scene']
obj = scene['objects'][0]
obj.update(pose=[6., 6., 0.])
scene.update(world_size=[10., 10.], start=[2., 2., 0.], goal=[7., 2., 0.], walls=[], terrain=[], objects=[obj])
world = NativeG1World(scene, 'cpu', seed=0, g1_contact_palms=True, g1_contact_palm_gain=1.)
rt = world.rt
rt.contact_palm.observation_reference_enabled = a.arm_observation == 'relative'
if a.gravity_support:
    from replanning_upright_support import install_arm_gravity_support
    install_arm_gravity_support(rt)
rt.set_mode('push')
samples = []
try:
    for phase, command in [('raise_and_settle', 0.), ('forward', .15), ('stop', 0.), ('reverse', -.15), ('settle', 0.)]:
        for _ in range(round(3./rt.dt)):
            rt.step([command, 0., 0.])
            state = dict(phase=phase, time_s=rt.steps*rt.dt, requested_forward_m_s=command,
                         pose=world.base()[0].tolist(), root_z=float(world.robot.data.root_link_pos_w[0, 2]),
                         velocity_world=world.robot.data.root_link_lin_vel_w[0].cpu().tolist())
            samples.append(state)
        (a.out/'samples.json').write_text(json.dumps(samples, indent=2)+'\n')
        recent = samples[-10:]
        print(phase, 'requested', command, 'measured mean X velocity', float(np.mean([x['velocity_world'][0] for x in recent])), flush=True)
    from clear.maze.fixed_palm import PALM_JOINTS
    (a.out/'result.json').write_text(json.dumps(dict(arm_observation=a.arm_observation, gravity_support=a.gravity_support,
        arm_reference_sha256=hashlib.sha256(json.dumps(PALM_JOINTS, sort_keys=True).encode()).hexdigest(),
        crouch_offsets=False,
        motor=None if a.motor is None else str(a.motor.resolve()), checkpoints=rt.checkpoints, samples=samples), indent=2)+'\n')
finally:
    rt.close()
