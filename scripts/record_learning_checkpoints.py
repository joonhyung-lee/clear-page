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
p.add_argument('--initial-frame', action='store_true', help='Record reset at t=0, before any action')
p.add_argument('--deterministic', action='store_true', help='Evaluate the policy mean without exploration noise')
p.add_argument('--arm-motion', action='store_true', help='Evaluate commanded arm posture changes during locomotion')
p.add_argument('--bare-spot', action='store_true', help='Use the distinct arm-free physical model and policy')
p.add_argument('--device', default='cuda:0')
p.add_argument('--consistent-commands', action='store_true', help='Use the corrected per-episode Spot torso commands')
a = p.parse_args()
os.environ['WANDB_MODE'] = 'disabled'
os.environ.setdefault('MUJOCO_GL', 'egl')
if a.body.startswith('spot'):
    os.environ.update(MJLAB_SPOT_ARM_FOLLOW='1', MJLAB_SPOT_ARM_JITTER='0',
                      MJLAB_SPOT_TORSO_STANCE='1', MJLAB_SPOT_ARM_BLEND='0')
import numpy as np
import torch
import warp as wp
from dataclasses import asdict, replace
from mjlab.envs import ManagerBasedRlEnv
from mjlab.rl import MjlabOnPolicyRunner, RslRlVecEnvWrapper
from mjlab.tasks.registry import load_env_cfg, load_rl_cfg, load_runner_cls

stages = json.loads(a.manifest.read_text())[a.body]
task = 'Mjlab-Velocity-BlindStairs-Unitree-G1' if a.body == 'g1' else 'Mjlab-Velocity-Mixed-Spot'
cfg = load_env_cfg(task, play=True)
torch.set_num_threads(4)
wp.config.kernel_cache_dir = str(a.output / 'warp-cache')
if a.consistent_commands and a.body == 'spot_arm':
    from progressive_policy_mdp import configure_command_consistency
    cfg = configure_command_consistency(cfg)
if a.bare_spot:
    assert a.body == 'spot' and not a.arm_motion
    from bare_spot import configure
    cfg = configure(cfg)
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
cfg.sim.nan_guard = replace(cfg.sim.nan_guard, output_dir=str(a.output / 'nan-dumps'))
cfg.events.pop('randomize_terrain', None)
twist = cfg.commands['twist']
twist.heading_command = False
twist.ranges.heading = None
twist.rel_heading_envs = 0.
twist.rel_standing_envs = 0.
twist.resampling_time_range = (2., 4.)
env = ManagerBasedRlEnv(cfg=cfg, device=a.device)
# One independent simulated environment per terrain tile avoids visual overlap.
t = env.scene.terrain
t.terrain_levels[:] = torch.arange(32, device=env.device) // columns
t.terrain_types[:] = torch.arange(32, device=env.device) % columns
t.env_origins[:] = t.terrain_origins[t.terrain_levels, t.terrain_types]
rl = load_rl_cfg(task)
normalization_modes = []
for stage in stages:
    saved = torch.load(stage['checkpoint'], map_location='cpu', weights_only=False)
    mode = (saved.get('infos') or {}).get('curriculum', {}).get(
        'actor_normalization', rl.actor.obs_normalization)
    if not isinstance(mode, bool):
        raise ValueError('Invalid actor normalization metadata')
    normalization_modes.append(mode)
if len(set(normalization_modes)) != 1:
    raise ValueError('A checkpoint replay must use one consistent actor normalization contract')
rl.actor = replace(rl.actor, obs_normalization=normalization_modes[0])
if a.body.startswith('spot'):
    rl.obs_groups['critic'] = ('actor',)
wrapped = RslRlVecEnvWrapper(env, clip_actions=rl.clip_actions)
runner = (load_runner_cls(task) or MjlabOnPolicyRunner)(wrapped, asdict(rl), device=env.device)
model = env.sim.mj_model
if a.bare_spot:
    from bare_spot import verify_model
    verify_model(model)
a.output.mkdir(parents=True, exist_ok=True)
fields = ['geom_type', 'geom_size', 'geom_pos', 'geom_quat', 'geom_bodyid',
          'geom_dataid', 'geom_rgba', 'geom_matid', 'geom_group', 'mat_rgba',
          'mesh_vert', 'mesh_face', 'mesh_vertadr', 'mesh_vertnum',
          'mesh_faceadr', 'mesh_facenum', 'hfield_data', 'hfield_adr',
          'hfield_nrow', 'hfield_ncol', 'hfield_size']
np.savez_compressed(a.output / (a.body + '-geometry.npz'),
                    body_names=np.asarray([model.body(i).name for i in range(model.nbody)]),
                    **{k: np.asarray(getattr(model, k)) for k in fields})
frames = []
audit = []
for stage in stages:
    checkpoint = Path(stage['checkpoint'])
    infos = runner.load(str(checkpoint), load_cfg={'actor': True}, strict=True, map_location=env.device)
    from policy_action_contract import checkpoint_action_limit
    wrapped.clip_actions = checkpoint_action_limit(infos, rl.clip_actions)
    actor = runner.alg.get_policy()
    actor.eval()
    # The same seed, commands and terrain bank make stages directly comparable.
    torch.manual_seed(42)
    with torch.inference_mode():
        env.reset()
        obs = env.observation_manager.compute()
    poses = []
    for i in range(a.steps):
        if a.arm_motion:
            from mjlab.tasks.velocity.config.spot import spot_mdp
            blend = .5 - .5 * np.cos(2 * np.pi * i / a.steps)
            spot_mdp._arm_blend(env).fill_(float(blend))
            with torch.inference_mode():
                obs = env.observation_manager.compute()
        if not a.initial_frame:
            with torch.inference_mode():
                obs, *_ = wrapped.step(actor(obs, stochastic_output=not a.deterministic))
        if i % 2 == 0:
            pos = env.sim.data.xpos.cpu().numpy().copy()
            quat = env.sim.data.xquat.cpu().numpy().copy()
            assert np.isfinite(pos).all() and np.isfinite(quat).all()
            poses.append((pos, quat))
        if a.initial_frame:
            with torch.inference_mode():
                obs, *_ = wrapped.step(actor(obs, stochastic_output=not a.deterministic))
        if i % 100 == 0:
            print(a.body, stage['iteration'], i, flush=True)
    frames.append(poses)
    audit.append({**stage, 'sha256': hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                  'actionLimit': wrapped.clip_actions})
np.savez_compressed(a.output / (a.body + '-states.npz'),
    positions=np.asarray([[f[0] for f in stage] for stage in frames], dtype=np.float32),
    quaternions=np.asarray([[f[1] for f in stage] for stage in frames], dtype=np.float32),
    origins=t.env_origins.cpu().numpy(), dt=env.step_dt * 2)
(a.output / (a.body + '-audit.json')).write_text(json.dumps({
    'stages': audit, 'environments': 32, 'task': task, 'seed': 42,
    'terrains': list(generator.sub_terrains), 'terrainGrid': [generator.num_rows, columns],
    'framesPerStage': len(frames[0]), 'dt': env.step_dt * 2,
    'evaluation': ('Deterministic' if a.deterministic else 'Stochastic') + ' checkpoint reconstruction on a common task terrain bank. Not archived training footage.',
    'initialFrameBeforeAction': a.initial_frame,
    'device': a.device, 'consistentTorsoCommands': a.consistent_commands,
    'actorNormalization': rl.actor.obs_normalization,
    'physicalBody': 'spot' if a.bare_spot else ('spot_arm' if a.body.startswith('spot') else 'g1'),
    'arm': None if a.bare_spot else (('Commanded nominal-to-stowed-to-nominal cycle over the replay' if a.arm_motion else 'Training body with nominal arm pose') if a.body.startswith('spot') else None),
}, indent=2))
env.close()
