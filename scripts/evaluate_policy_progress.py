"""Evaluate saved policies on a fixed terrain bank, without modifying training.

Manifest paths, policy hashes and individual episodes remain private. A separate
exporter publishes only aggregate evaluation values and protocol metadata.
"""
import argparse
import hashlib
import json
import math
import os
import time
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--body', choices=['g1', 'spot', 'spot_arm'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seeds', type=int, nargs='+', default=[101, 202, 303])
    parser.add_argument('--duration', type=float, default=20.)
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    os.environ.update(WANDB_MODE='disabled', MUJOCO_GL='egl',
                      MJLAB_SPOT_ARM_FOLLOW='1', MJLAB_SPOT_ARM_JITTER='0',
                      MJLAB_SPOT_TORSO_STANCE='1', MJLAB_SPOT_ARM_BLEND='0',
                      MJLAB_SPOT_ARM_CURRICULUM='0', MJLAB_SPOT_ARM_SPAN='0')
    from dataclasses import asdict
    import numpy as np
    import torch
    from mjlab.envs import ManagerBasedRlEnv
    from mjlab.rl import MjlabOnPolicyRunner, RslRlVecEnvWrapper
    from mjlab.tasks.registry import load_env_cfg, load_rl_cfg
    from mjlab.tasks.velocity.config.spot.spot_stairs_env_cfg import spot_mixed_terrain_cfg

    torch.set_num_threads(4)
    checkpoints = json.loads(args.manifest.read_text())[args.body]
    if args.limit:
        checkpoints = checkpoints[:args.limit]
    task = 'Mjlab-Velocity-BlindStairs-Unitree-G1' if args.body == 'g1' else 'Mjlab-Velocity-Mixed-Spot'
    cfg = load_env_cfg(task, play=True)
    if args.body == 'spot':
        from bare_spot import configure, verify_model
        cfg = configure(cfg)
    cfg.seed = 42
    cfg.scene.num_envs = 20
    cfg.auto_reset = False
    cfg.curriculum = {}
    cfg.episode_length_s = args.duration + 1.
    cfg.sim.nconmax = 256
    # Keep only reset events, eliminating pushes and startup randomization.
    cfg.events = {k: v for k, v in cfg.events.items() if v.mode == 'reset'}
    cfg.events.pop('randomize_terrain', None)
    cfg.events['reset_base'].params['pose_range'] = {
        'x': (-.1, .1), 'y': (-.1, .1), 'z': (.02, .02), 'yaw': (0., 0.)}
    cfg.events['reset_base'].params['velocity_range'] = {}
    for group in cfg.observations.values():
        group.enable_corruption = False
    # Use exactly the same terrain geometry for every body and checkpoint.
    generator = spot_mixed_terrain_cfg(curriculum=True)
    generator.seed = 42
    generator.num_rows = 4
    generator.num_cols = 5
    generator.difficulty_range = (0., .6)
    generator.border_width = 2.
    for tile in generator.sub_terrains.values():
        tile.proportion = .2
    cfg.scene.terrain.terrain_generator = generator
    cfg.scene.terrain.max_init_terrain_level = 0
    command = cfg.commands['twist']
    command.heading_command = False
    command.ranges.heading = None
    command.rel_heading_envs = command.rel_standing_envs = command.rel_forward_envs = 0.
    command.rel_world_envs = 1.
    command.init_velocity_prob = 0.
    command.ranges.lin_vel_x = (.5, .5)
    command.ranges.lin_vel_y = (0., 0.)
    command.ranges.ang_vel_z = (0., 0.)
    command.resampling_time_range = (1000., 1000.)
    cfg.terminations = {'fell_over': cfg.terminations['fell_over']}
    cfg.terminations['fell_over'].params['limit_angle'] = math.radians(70)
    env = ManagerBasedRlEnv(cfg=cfg, device='cuda:0')
    if args.body == 'spot':
        physics = verify_model(env.sim.mj_model)
    else:
        physics = {'body': args.body, 'actuators': env.sim.mj_model.nu,
                   'nq': env.sim.mj_model.nq, 'nv': env.sim.mj_model.nv}
    terrain = env.scene.terrain
    terrain.terrain_levels[:] = torch.arange(20, device=env.device) // 5
    terrain.terrain_types[:] = torch.arange(20, device=env.device) % 5
    terrain.env_origins[:] = terrain.terrain_origins[terrain.terrain_levels, terrain.terrain_types]
    rl = load_rl_cfg(task)
    if args.body != 'g1':
        rl.obs_groups['critic'] = ('actor',)
    runner = MjlabOnPolicyRunner(RslRlVecEnvWrapper(env, clip_actions=rl.clip_actions), asdict(rl), device=env.device)
    robot = env.scene['robot']
    args.output.mkdir(parents=True, exist_ok=True)
    protocol = {'version': 1, 'terrainSeed': 42, 'episodeSeeds': args.seeds,
                'terrains': list(generator.sub_terrains), 'difficulties': [0., .2, .4, .6],
                'numEnvironments': 20, 'durationSeconds': args.duration,
                'goalDistanceM': 3., 'lateralToleranceM': .75,
                'commandWorldVelocity': [.5, 0.], 'fallAngleDegrees': 70,
                'armProtocol': 'fixed nominal pose', 'deterministicPolicy': True,
                'initialPoseXYJitterM': .1, 'terrainOriginHash': hashlib.sha256(
                    terrain.terrain_origins.cpu().numpy().tobytes()).hexdigest(),
                'tracking': 'Mean episode planar velocity RMSE, until goal, fall, or time limit',
                'success': f'3 m world +X progress with absolute lateral error <= 0.75 m, before a fall or {args.duration:g} s',
                'fall': 'Tilt > 70 degrees before goal or time limit',
                'terrainDirection': 'Start at tile center and travel toward the +X edge; names identify terrain templates'}
    identity = {'body': args.body, 'manifest': digest(args.manifest),
                'evaluator': digest(__file__), 'protocol': protocol}
    target = args.output / f'{args.body}.json'
    result = {'identity': identity, 'physics': physics, 'checkpoints': []}
    if target.exists():
        previous = json.loads(target.read_text())
        assert previous['identity'] == identity, 'Evaluation identity changed; use a fresh output directory'
        result = previous
    finished = {c['update'] for c in result['checkpoints']}
    started = time.monotonic()
    for checkpoint in checkpoints:
        update = checkpoint['update']
        if update in finished:
            continue
        tick = time.monotonic()
        runner.load(checkpoint['path'], load_cfg={'actor': True}, strict=True, map_location=env.device)
        actor = runner.alg.get_policy()
        actor.eval()
        episodes = []
        for seed in args.seeds:
            with torch.inference_mode():
                obs, _ = env.reset(seed=seed)
                actor.reset(torch.ones(20, dtype=torch.bool, device=env.device))
                initial = robot.data.root_link_pos_w.clone()
                initial_states = np.concatenate((env.sim.data.qpos.cpu().numpy(), env.sim.data.qvel.cpu().numpy()), axis=1)
                active = torch.ones(20, dtype=torch.bool, device=env.device)
                error_sum = torch.zeros(20, device=env.device)
                count = torch.zeros(20, dtype=torch.long, device=env.device)
                end_progress = torch.zeros(20, device=env.device)
                succeeded = torch.zeros_like(active)
                fallen = torch.zeros_like(active)
                steps = int(round(args.duration / env.step_dt))
                for step in range(steps):
                    actions = actor(obs, stochastic_output=False)
                    if rl.clip_actions is not None:
                        actions = actions.clamp(-rl.clip_actions, rl.clip_actions)
                    obs, _, terminated, _, _ = env.step(actions)
                    terminated = terminated.clone()
                    velocity = robot.data.root_link_lin_vel_w[:, :2]
                    squared_error = ((velocity - velocity.new_tensor([.5, 0.])) ** 2).sum(dim=1)
                    displacement = robot.data.root_link_pos_w - initial
                    assert torch.isfinite(squared_error).all() and torch.isfinite(displacement).all()
                    error_sum += squared_error * active
                    count += active.long()
                    end_progress[active] = displacement[active, 0]
                    fell = active & terminated
                    goal = active & ~fell & (displacement[:, 0] >= 3.) & (displacement[:, 1].abs() <= .75)
                    fallen |= fell
                    succeeded |= goal
                    active &= ~(fell | goal)
                    # Read terminal state before resetting. Completed envs never
                    # contribute a second episode or a reset discontinuity.
                    reset_ids = terminated.nonzero(as_tuple=False).flatten()
                    if reset_ids.numel():
                        obs, _ = env.reset(env_ids=reset_ids)
                        actor.reset(terminated)
                    if not active.any():
                        break
                rmse = (error_sum / count.clamp_min(1)).sqrt().cpu().tolist()
                for i in range(20):
                    episodes.append({'seed': seed, 'environment': i,
                                     'terrain': protocol['terrains'][i % 5], 'difficulty': protocol['difficulties'][i // 5],
                                     'initialStateHash': hashlib.sha256(initial_states[i].tobytes()).hexdigest(),
                                     'rmse': rmse[i], 'success': bool(succeeded[i]), 'fall': bool(fallen[i]),
                                     'duration': int(count[i]) * env.step_dt,
                                     'progress': float(end_progress[i])})
            print(f'PROGRESS {args.body} update {update} seed {seed}: {sum(e["success"] for e in episodes[-20:])}/20 goals, {sum(e["fall"] for e in episodes[-20:])}/20 falls', flush=True)
        result['checkpoints'].append({'update': update, 'phase': checkpoint['phase'],
                                      'checkpointHash': digest(checkpoint['path']), 'episodes': episodes,
                                      'wallSeconds': round(time.monotonic() - tick, 3)})
        write_json(target, result)
        print(f'SAVED {args.body} update {update}: {time.monotonic() - tick:.1f}s, total {time.monotonic() - started:.1f}s', flush=True)
    env.close()


if __name__ == '__main__':
    main()
