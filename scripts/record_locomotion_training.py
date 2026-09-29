"""Record 32 independent environments with an existing frozen locomotion policy.

This records new policy playback in its task, not an archived training session.
Checkpoint paths and hashes are kept in the private output directory.
Run with the source project's Python environment and patched mjlab on PYTHONPATH.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--body', choices=['g1', 'spot', 'spot_arm'], required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--steps', type=int, default=600)
parser.add_argument('--width', type=int, default=960)
parser.add_argument('--height', type=int, default=600)
a = parser.parse_args()
os.environ.setdefault('MUJOCO_GL', 'egl')
os.environ['WANDB_MODE'] = 'disabled'
if a.body.startswith('spot'):
    os.environ['MJLAB_SPOT_ARM_FOLLOW'] = '1'
    os.environ['MJLAB_SPOT_ARM_JITTER'] = '0'
    os.environ['MJLAB_SPOT_TORSO_STANCE'] = '1'
    os.environ['MJLAB_SPOT_ARM_BLEND'] = '1' if a.body == 'spot_arm' else '0'
import numpy as np
import torch
from dataclasses import asdict
from mjlab.envs import ManagerBasedRlEnv
from mjlab.rl import MjlabOnPolicyRunner, RslRlVecEnvWrapper
from mjlab.tasks.registry import load_env_cfg, load_rl_cfg, load_runner_cls
from mjlab.viewer.offscreen_renderer import OffscreenRenderer
from mjlab.viewer.viewer_config import ViewerConfig
from PIL import Image
import imageio_ffmpeg

paths = {'g1':'g1/locomotion/g1_blind_stairs_ARCLIP2_model_22800.pt', 'spot':'spot/locomotion/spot_stance_model_13200.pt', 'spot_arm':'spot/locomotion_armstow/spot_stowspan_model_28000.pt'}
checkpoint = a.source / 'assets/pretrained' / paths[a.body]
task = 'Mjlab-Velocity-BlindStairs-Unitree-G1' if a.body == 'g1' else 'Mjlab-Velocity-Mixed-Spot'
cfg = load_env_cfg(task, play=True)
cfg.seed = 42
cfg.scene.num_envs = 32
cfg.curriculum = {}
# Display independent command tracking rollouts on a compact flat practice floor.
# This presentation override is recorded below and is not a claim about training footage.
cfg.scene.terrain.terrain_type = 'plane'
cfg.scene.terrain.terrain_generator = None
cfg.scene.env_spacing = 2.8
cfg.terminations.pop('out_of_terrain_bounds', None)
cfg.episode_length_s = 12.
cfg.sim.nconmax = 256
if a.body == 'spot':
    from clear.maze.mjlab_actions import configure_armless_spot
    configure_armless_spot(cfg)
    cfg.rewards.pop('track_arm', None)
    for key in ['std_standing', 'std_walking', 'std_running']:
        cfg.rewards['pose'].params[key] = {k:v for k,v in cfg.rewards['pose'].params[key].items() if not k.startswith('arm_')}
twist = cfg.commands['twist']
twist.heading_command = False
twist.ranges.heading = None
twist.rel_heading_envs = 0.
twist.rel_standing_envs = 0.
twist.resampling_time_range = (2., 4.)
cfg.viewer.width = a.width
cfg.viewer.height = a.height
env = ManagerBasedRlEnv(cfg=cfg, device='cuda:0')
rl = load_rl_cfg(task)
if a.body.startswith('spot'):
    rl.obs_groups['critic'] = ('actor',)
wrapped = RslRlVecEnvWrapper(env, clip_actions=rl.clip_actions)
runner = (load_runner_cls(task) or MjlabOnPolicyRunner)(wrapped, asdict(rl), device='cuda:0')
runner.load(str(checkpoint), load_cfg={'actor':True}, strict=True, map_location='cuda:0')
policy = runner.get_inference_policy(device='cuda:0')
env.reset()
obs = env.observation_manager.compute()
origins = env.scene.env_origins.cpu().numpy()
center = (origins.min(axis=0) + origins.max(axis=0)) * .5
vcfg = ViewerConfig(width=a.width, height=a.height, max_extra_envs=31, origin_type=ViewerConfig.OriginType.WORLD,
                    lookat=tuple(center), distance=25., elevation=-48., azimuth=110., enable_shadows=True,
                    geom_group=(1,1,1,0,0,0), site_group=(0,0,0,0,0,0))
renderer = OffscreenRenderer(env.sim.mj_model, vcfg, env.scene)
# Neutral render-only floor preserves the policy's simulated dynamics.
import mujoco
for geom in np.flatnonzero(renderer._model.geom_type == mujoco.mjtGeom.mjGEOM_PLANE):
    material = renderer._model.geom_matid[geom]
    if material >= 0:
        renderer._model.mat_texid[material] = -1
        renderer._model.mat_rgba[material] = [.84, .86, .82, 1.]
renderer.initialize()
a.output.mkdir(parents=True, exist_ok=True)
fps = round(1 / env.step_dt)
writer = imageio_ffmpeg.write_frames(str(a.output / f'{a.body}.mp4'), (a.width,a.height), fps=fps, codec='libx264', macro_block_size=1,
    output_params=['-crf','22','-map_metadata','-1','-fflags','+bitexact','-flags:v','+bitexact','-movflags','+faststart'])
writer.send(None)
positions = []
try:
    for i in range(a.steps):
        with torch.inference_mode():
            obs, *_ = env.step(policy(obs))
        renderer.update(env.sim.data)
        frame = renderer.render()
        if i == 0:
            Image.fromarray(frame).save(a.output / f'{a.body}.png')
        writer.send(frame)
        positions.append(env.scene['robot'].data.root_link_pos_w.cpu().numpy().copy())
        if i % 50 == 0:
            print(a.body, i, '/', a.steps, flush=True)
finally:
    writer.close()
    renderer.close()
np.savez_compressed(a.output / f'{a.body}-positions.npz', positions=np.asarray(positions), origins=origins)
(a.output / f'{a.body}-provenance.json').write_text(json.dumps(dict(checkpoint=str(checkpoint.resolve()), sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(), task=task, environments=32, frames=a.steps, fps=fps, seed=42, terrain='Flat presentation floor, 2.8 m environment spacing', provenance='Fresh frozen-policy replay, not archived training footage'), indent=2))
env.close()
