"""Record unmodified native SUMO task attempts and numeric replay geometry.

Run with the pinned SUMO environment after building its native extensions.
Keep raw outputs private. Failed attempts remain failed attempts.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import time

import mujoco
import numpy as np
import sumo.tasks
import sumo.controller
from sumo.run_mpc.run_mpc import _create_sim
from sumo.controller import Controller, ControllerConfig
from sumo.utils.mujoco import G1RolloutBackend
from judo.app.structs import MujocoState
from judo.optimizers.cem import CrossEntropyMethod, CrossEntropyMethodConfig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', choices=['g1_table_push', 'g1_chair_push', 'g1_door'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=30.)
    parser.add_argument('--seed', type=int, default=0)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    np.random.seed(args.seed)
    simulation = _create_sim(args.task)
    task = simulation.task
    optimizer = CrossEntropyMethod(CrossEntropyMethodConfig(num_rollouts=24, num_nodes=4, num_elites=2), task.nu)
    controller = Controller(ControllerConfig(horizon=2.5, spline_order='cubic', control_freq=20.), task, optimizer,
                            rollout_backend='mujoco_g1', rollout_backend_registry={'mujoco_g1': G1RolloutBackend},
                            rollout_backend_kwargs={'cutoff_time': 60.})
    model, data = task.model, task.data
    fields = ['geom_type', 'geom_size', 'geom_pos', 'geom_quat', 'geom_bodyid', 'geom_dataid',
              'geom_rgba', 'geom_matid', 'geom_group', 'mat_rgba', 'mesh_vert', 'mesh_face',
              'mesh_vertadr', 'mesh_vertnum', 'mesh_faceadr', 'mesh_facenum']
    np.savez_compressed(args.output / 'geometry.npz', **{key: np.asarray(getattr(model, key)) for key in fields})
    dt = float(task.dt)
    record_every, control_every = round(.02/dt), round(.05/dt)
    times, qpos, qvel, positions, quaternions, contacts = [], [], [], [], [], []
    began = time.monotonic()
    failed = reached = False
    for step in range(round(args.seconds/dt)+1):
        now = step*dt
        if step % control_every == 0:
            controller.update_states(MujocoState(time=now, qpos=data.qpos.copy(), qvel=data.qvel.copy(),
                mocap_pos=data.mocap_pos.copy(), mocap_quat=data.mocap_quat.copy(), sim_metadata={}))
            controller.update_action()
        if step % record_every == 0:
            times.append(now)
            qpos.append(data.qpos.copy())
            qvel.append(data.qvel.copy())
            positions.append(data.xpos.copy())
            quaternions.append(data.xquat.copy())
        if step % round(1/dt) == 0:
            print(args.task, f't={now:.2f}', f'height={data.qpos[2]:.3f}', f'wall={time.monotonic()-began:.1f}s', flush=True)
        if step:
            failed = bool(task.failure(task.sim_model, data))
            reached = bool(task.success(task.sim_model, data))
            if failed or reached:
                break
        if step == round(args.seconds/dt):
            break
        simulation.step(controller.action(now))
        for contact in data.contact:
            contacts.append([float(data.time), int(contact.geom[0]), int(contact.geom[1]), float(contact.dist)])
    if times[-1] < now-1e-8:
        times.append(now)
        qpos.append(data.qpos.copy())
        qvel.append(data.qvel.copy())
        positions.append(data.xpos.copy())
        quaternions.append(data.xquat.copy())
    np.savez_compressed(args.output / 'states.npz', time=times, qpos=qpos, qvel=qvel,
                        positions=positions, quaternions=quaternions, contacts=contacts)
    mujoco.mj_saveModel(model, str(args.output/'task.mjb'))
    metadata = {'task': args.task, 'seed': args.seed, 'duration': now, 'fell': failed, 'goalReached': reached,
                'population': 24, 'elites': 2, 'horizon': 2.5, 'controlInterval': .05,
                'mujoco': mujoco.__version__, 'taskConfig': asdict(task.config),
                'geometrySHA256': hashlib.sha256((args.output/'geometry.npz').read_bytes()).hexdigest(),
                'scope': 'Native SUMO task geometry, reset, policy, reward and terminal conditions. One recorded attempt.'}
    target_name = {'g1_table_push': 'table', 'g1_chair_push': 'yellow_chair', 'g1_door': 'door'}[args.task]
    target = model.body(target_name).id
    metadata['targetBody'] = target
    metadata['robotBody'] = model.body('pelvis').id
    metadata['objectDisplacement'] = float(np.linalg.norm(positions[-1][target, :2]-positions[0][target, :2]))
    final_xy = qpos[-1][:2] if args.task == 'g1_door' else positions[-1][target, :2]
    metadata['goalError'] = float(np.linalg.norm(final_xy-np.asarray(task.config.goal_position)[:2]))
    if args.task == 'g1_door':
        metadata['doorAngleDegrees'] = float(np.rad2deg(qpos[-1][model.joint('door_hinge').qposadr[0]]))
    policy_dir = os.environ.get('G1_EXTENSIONS_POLICY_DIR')
    if policy_dir:
        metadata['policySHA256'] = hashlib.sha256((Path(policy_dir)/'g1_velocity_policy.onnx').read_bytes()).hexdigest()
    (args.output/'result.json').write_text(json.dumps(metadata, indent=2, default=lambda x:x.tolist())+'\n')
    print('COMPLETE', args.task, f'duration={now:.3f}', f'fell={failed}', f'goalReached={reached}', flush=True)


if __name__ == '__main__':
    main()
