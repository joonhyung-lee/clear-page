"""Reconstruct historical policy checkpoints on a shared bank of task terrains.

Input manifest and numeric archives remain private. These are checkpoint
evaluations, not a recording of the original optimization session.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--manifest', type=Path, required=True)
p.add_argument('--body', choices=['g1', 'spot', 'spot_arm'], required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--steps', type=int, default=400)
a = p.parse_args()
os.environ['WANDB_MODE'] = 'disabled'
os.environ.setdefault('MUJOCO_GL', 'egl')
if a.body.startswith('spot'):
    os.environ.update(MJLAB_SPOT_ARM_FOLLOW='1', MJLAB_SPOT_ARM_JITTER='0',
                      MJLAB_SPOT_TORSO_STANCE='1', MJLAB_SPOT_ARM_BLEND='0')
import numpy as np
import torch
from dataclasses import asdict
from mjlab.envs import ManagerBasedRlEnv
from mjlab.rl import MjlabOnPolicyRunner, RslRlVecEnvWrapper
from mjlab.tasks.registry import load_env_cfg, load_rl_cfg, load_runner_cls

stages = json.loads(a.manifest.read_text())[a.body]
task = 'Mjlab-Velocity-BlindStairs-Unitree-G1' if a.body == 'g1' else 'Mjlab-Velocity-Mixed-Spot'
cfg = load_env_cfg(task, play=True)
cfg.seed = 42
cfg.scene.num_envs = 32
cfg.curriculum = {}
terrain = cfg.scene.terrain
generator = terrain.terrain_generator
generator.seed = 42
columns = len(generator.sub_terrains)
generator.num_rows = (32 + columns - 1) // columns
generator.num_cols = columns
generator.curriculum = True
generator.border_width = 2.
terrain.max_init_terrain_level = 3
cfg.episode_length_s = a.steps * .02
cfg.sim.nconmax = 256
cfg.events.pop('randomize_terrain', None)
twist = cfg.commands['twist']
twist.heading_command = False
twist.ranges.heading = None
twist.rel_heading_envs = 0.
twist.rel_standing_envs = 0.
twist.resampling_time_range = (2., 4.)
env = ManagerBasedRlEnv(cfg=cfg, device='cuda:0')
# One independent simulated environment per terrain tile avoids visual overlap.
t = env.scene.terrain
t.terrain_levels[:] = torch.arange(32, device=env.device) // columns
t.terrain_types[:] = torch.arange(32, device=env.device) % columns
t.env_origins[:] = t.terrain_origins[t.terrain_levels, t.terrain_types]
rl = load_rl_cfg(task)
if a.body.startswith('spot'):
    rl.obs_groups['critic'] = ('actor',)
wrapped = RslRlVecEnvWrapper(env, clip_actions=rl.clip_actions)
runner = (load_runner_cls(task) or MjlabOnPolicyRunner)(wrapped, asdict(rl), device=env.device)
model = env.sim.mj_model
a.output.mkdir(parents=True, exist_ok=True)
fields = ['geom_type', 'geom_size', 'geom_pos', 'geom_quat', 'geom_bodyid',
          'geom_dataid', 'geom_rgba', 'geom_matid', 'geom_group', 'mat_rgba',
          'mesh_vert', 'mesh_face', 'mesh_vertadr', 'mesh_vertnum',
          'mesh_faceadr', 'mesh_facenum', 'hfield_data', 'hfield_adr',
          'hfield_nrow', 'hfield_ncol', 'hfield_size']
np.savez_compressed(a.output / (a.body + '-geometry.npz'),
                    **{k: np.asarray(getattr(model, k)) for k in fields})
frames = []
audit = []
for stage in stages:
    checkpoint = Path(stage['checkpoint'])
    runner.load(str(checkpoint), load_cfg={'actor': True}, strict=True, map_location=env.device)
    actor = runner.alg.get_policy()
    actor.eval()
    # The same seed, commands and terrain bank make stages directly comparable.
    torch.manual_seed(42)
    with torch.inference_mode():
        env.reset()
        obs = env.observation_manager.compute()
    poses = []
    for i in range(a.steps):
        with torch.inference_mode():
            obs, *_ = env.step(actor(obs, stochastic_output=True))
        if i % 2 == 0:
            pos = env.sim.data.xpos.cpu().numpy().copy()
            quat = env.sim.data.xquat.cpu().numpy().copy()
            assert np.isfinite(pos).all() and np.isfinite(quat).all()
            poses.append((pos, quat))
        if i % 100 == 0:
            print(a.body, stage['iteration'], i, flush=True)
    frames.append(poses)
    audit.append({**stage, 'sha256': hashlib.sha256(checkpoint.read_bytes()).hexdigest()})
np.savez_compressed(a.output / (a.body + '-states.npz'),
    positions=np.asarray([[f[0] for f in stage] for stage in frames], dtype=np.float32),
    quaternions=np.asarray([[f[1] for f in stage] for stage in frames], dtype=np.float32),
    origins=t.env_origins.cpu().numpy(), dt=env.step_dt * 2)
(a.output / (a.body + '-audit.json')).write_text(json.dumps({
    'stages': audit, 'environments': 32, 'task': task, 'seed': 42,
    'terrains': list(generator.sub_terrains), 'terrainGrid': [generator.num_rows, columns],
    'framesPerStage': len(frames[0]), 'dt': env.step_dt * 2,
    'evaluation': 'Stochastic checkpoint reconstruction on a common task terrain bank. Not archived training footage.',
    'arm': 'Training body with nominal arm pose' if a.body.startswith('spot') else None,
}, indent=2))
env.close()
