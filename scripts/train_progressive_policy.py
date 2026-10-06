"""Train independent progressive G1 or Spot curricula from random initialization.

Run with the CLEAR simulation environment and its mjlab source on PYTHONPATH.
No pretrained policy is loaded. Every stage inherits its predecessor's actor,
critic and optimizer. Checkpoints are numbered by completed PPO updates, not
the upstream loop's zero-based iteration index. Outputs must stay outside the
published website. This is a new reproduction, not historical paper evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def write_json(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    temp.replace(path)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_random_initial_state(path, body):
    """Allow controlled comparisons to share weights, never a trained policy."""
    import torch
    checkpoint = torch.load(path, map_location='cpu', weights_only=False)
    info = checkpoint.get('infos', {})
    meta = info.get('curriculum', {})
    if not (meta.get('body') == body and meta.get('origin') == 'random_initialization'
            and meta.get('before_first_optimizer_update') is True
            and meta.get('completed_updates') == 0 and meta.get('cumulative_updates') == 0
            and meta.get('parent_sha256') is None and checkpoint.get('iter') == 0
            and info.get('env_state', {}).get('common_step_counter') == 0
            and checkpoint.get('optimizer_state_dict', {}).get('state') == {}):
        raise ValueError('Initial state must be a matching, untrained update-zero checkpoint')
    return digest(path)


def training_runner(task):
    from mjlab.rl import MjlabOnPolicyRunner
    from mjlab.tasks.registry import load_runner_cls
    # Task runners can install essential model behavior. In particular, G1's
    # BlindStairsRunner bounds normalized critic observations before the MLP.
    return load_runner_cls(task) or MjlabOnPolicyRunner


def configure_observation_groups(rl, critic_observations):
    # Native G1 keeps the same 298-dimensional privileged critic on both plane
    # and terrain. Reducing it to 99 actor inputs is not required for transfer.
    if critic_observations == 'actor':
        rl.obs_groups['critic'] = ('actor',)
    elif critic_observations != 'native':
        raise ValueError(f'Unknown critic observation mode: {critic_observations}')
    return rl


def resolve_critic_observations(mode, parent, body):
    """Defaults for new runs must never alter a resumed critic architecture."""
    if not parent:
        return mode or 'native'
    import torch
    saved = torch.load(parent, map_location='cpu', weights_only=False)
    width = saved['critic_state_dict']['mlp.0.weight'].shape[1]
    actor_width = saved['actor_state_dict']['mlp.0.weight'].shape[1]
    native_width = 298 if body == 'g1' else 271
    inferred = 'actor' if width == actor_width else 'native' if width == native_width else None
    if inferred is None or (mode is not None and mode != inferred):
        raise ValueError(f'Parent critic has {width} inputs; requested mode {mode!r} cannot resume it')
    return inferred


def train(args):
    # Set before task registration evaluates environment-dependent curricula.
    os.environ.update(WANDB_MODE='disabled', MJLAB_SPOT_ARM_FOLLOW='1',
                      MJLAB_SPOT_ARM_JITTER='0', MJLAB_SPOT_ARM_BLEND='0',
                      MJLAB_SPOT_TORSO_STANCE='1',
                      MJLAB_SPOT_ARM_CURRICULUM=str(int(args.stage == 'arm')),
                      MJLAB_SPOT_ARM_SPAN=str(int(args.stage == 'arm')))
    from dataclasses import asdict, replace
    import numpy as np
    import random
    import torch
    import warp as wp
    from mjlab.envs import ManagerBasedRlEnv
    from mjlab.rl import MjlabOnPolicyRunner, RslRlVecEnvWrapper
    from mjlab.tasks.registry import load_env_cfg, load_rl_cfg
    from mjlab.utils.os import dump_yaml
    from mjlab.utils.torch import configure_torch_backends

    torch.set_num_threads(4)
    wp.config.kernel_cache_dir = str(args.output / 'warp-cache')
    if args.device.startswith('cuda') and not torch.cuda.is_available():
        raise RuntimeError('CUDA is unavailable; no training was started. CPU is supported only as an explicit device choice.')
    configure_torch_backends()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    out = args.output / args.stage
    out.mkdir(parents=True, exist_ok=True)
    task = 'Mjlab-Velocity-BlindStairs-Unitree-G1' if args.body == 'g1' else 'Mjlab-Velocity-Mixed-Spot'
    cfg = load_env_cfg(task)
    if args.body == 'spot_arm':
        from progressive_policy_mdp import configure_command_consistency
        cfg = configure_command_consistency(cfg)
    if args.body == 'spot':
        from bare_spot import configure
        cfg = configure(cfg)
    cfg.seed = args.seed
    cfg.scene.num_envs = args.num_envs
    cfg.sim.nconmax = 256 if args.body == 'g1' else 96
    cfg.sim.nan_guard = replace(cfg.sim.nan_guard, enabled=True, output_dir=str(out / 'nan-dumps'))
    if args.stage == 'locomotion':
        cfg.scene.terrain.terrain_type = 'plane'
        cfg.scene.terrain.terrain_generator = None
        cfg.curriculum.pop('terrain_levels', None)
        if args.forward_locomotion:
            from progressive_policy_mdp import configure_forward_locomotion
            cfg = configure_forward_locomotion(cfg)
    else:
        cfg.scene.terrain.terrain_generator.num_rows = 8
        cfg.scene.terrain.terrain_generator.num_cols = 10
        cfg.scene.terrain.max_init_terrain_level = 0
    rl = load_rl_cfg(task)
    rl.seed = args.seed
    rl.logger = 'tensorboard'
    rl.upload_model = False
    rl = configure_observation_groups(rl, args.critic_observations)
    if args.actor_normalization:
        rl.actor = replace(rl.actor, obs_normalization=True)
    from policy_action_contract import configure_action_limit
    rl = configure_action_limit(rl, args.action_limit)
    if args.action_rate_warmup and args.stage == 'locomotion':
        from progressive_policy_rewards import configure as configure_regularization
        cfg = configure_regularization(cfg, args.updates * rl.num_steps_per_env)
    if args.failure_cost is not None:
        from progressive_policy_rewards import configure_failure_cost
        cfg = configure_failure_cost(cfg, args.failure_cost)
    rl.save_interval = 100
    dump_yaml(out / 'environment.yaml', asdict(cfg))
    dump_yaml(out / 'agent.yaml', asdict(rl))
    env = ManagerBasedRlEnv(cfg=cfg, device=args.device)
    if args.body == 'spot':
        from bare_spot import verify_model
        write_json(out / 'body.json', verify_model(env.sim.mj_model))
    wrapped = RslRlVecEnvWrapper(env, clip_actions=rl.clip_actions)
    from policy_training_health import attach_transition_guard
    attach_transition_guard(wrapped, out / 'health')
    started = time.time()
    durations = []
    parent_hash = digest(args.parent) if args.parent else None
    initial_hash = digest(args.initial_state) if args.initial_state else None

    class RecordedRunner(training_runner(task)):
        def save(self, path, infos=None):
            completed = self.current_learning_iteration + 1
            target = out / f'update_{completed:06d}.pt'
            metadata = dict(body=args.body, stage=args.stage, completed_updates=completed,
                            cumulative_updates=args.offset + completed,
                            action_limit=rl.clip_actions,
                            failure_cost=args.failure_cost,
                            actor_normalization=rl.actor.obs_normalization,
                            forward_locomotion=args.forward_locomotion,
                            parent_sha256=parent_hash, seed=args.seed,
                            initial_state_sha256=initial_hash,
                            origin='random_initialization', num_envs=args.num_envs)
            super().save(str(target), {**(infos or {}), 'curriculum': metadata})
            write_json(out / 'latest.json', {**metadata, 'checkpoint': str(target),
                                           'sha256': digest(target)})

    runner = RecordedRunner(wrapped, asdict(rl), str(out), device=args.device)
    # The default logger snapshots the whole enclosing repository, including
    # unrelated LFS media. Record the actual Python sources read-only instead.
    import inspect
    sources = {Path(__file__).resolve(), Path(__file__).with_name('policy_training_health.py').resolve(),
               Path(__file__).with_name('progressive_policy_mdp.py').resolve(),
               Path(__file__).with_name('policy_action_contract.py').resolve()}
    if args.action_rate_warmup or args.failure_cost is not None:
        sources.add(Path(__file__).with_name('progressive_policy_rewards.py').resolve())
    for cls in type(runner).__mro__:
        try:
            sources.add(Path(inspect.getfile(cls)).resolve())
        except TypeError:
            pass
    for obj in [type(env), type(runner.alg), type(runner.alg.actor), type(runner.alg.critic)]:
        sources.add(Path(inspect.getfile(obj)).resolve())
    source_dir = out / 'sources'
    source_dir.mkdir(exist_ok=True)
    fingerprints = []
    for source in sorted(sources):
        fingerprint = digest(source)
        copied = source_dir / (fingerprint[:12] + '-' + source.name)
        copied.write_bytes(source.read_bytes())
        fingerprints.append({'path': str(source), 'sha256': fingerprint, 'copy': copied.name})
    write_json(out / 'source-digests.json', fingerprints)
    runner.logger.git_status_repos = []
    if args.parent:
        runner.load(str(args.parent), map_location=args.device)
        # Loop counter is local to this stage; cumulative updates are explicit.
        runner.current_learning_iteration = 0
    elif args.initial_state:
        runner.load(str(args.initial_state), map_location=args.device)
        runner.current_learning_iteration = 0
    elif args.stage != 'locomotion':
        raise ValueError('Later stages require the preceding stage checkpoint')
    initial = out / 'update_000000.pt'
    MjlabOnPolicyRunner.save(runner, str(initial), {'curriculum': {
        'body': args.body, 'stage': args.stage, 'completed_updates': 0,
        'action_limit': rl.clip_actions,
        'failure_cost': args.failure_cost,
        'actor_normalization': rl.actor.obs_normalization,
        'forward_locomotion': args.forward_locomotion,
        'cumulative_updates': args.offset, 'parent_sha256': parent_hash,
        'initial_state_sha256': initial_hash,
        'origin': 'random_initialization', 'seed': args.seed,
        'before_first_optimizer_update': args.parent is None,
    }})
    write_json(out / 'initial.json', {'checkpoint': str(initial),
                                    'sha256': digest(initial), 'parent_sha256': parent_hash})
    original_log = runner.logger.log

    def log(**values):
        original_log(**values)
        completed = values['it'] + 1
        seconds = values['collect_time'] + values['learn_time']
        durations.append(seconds)
        recent = durations[-50:]
        write_json(out / 'status.json', {
            'pid': os.getpid(), 'stage': args.stage, 'state': 'training',
            'updated_at': time.time(), 'completed_updates': completed,
            'cumulative_updates': args.offset + completed,
            'target_updates': args.updates, 'num_envs': args.num_envs,
            'environment_steps': (args.offset + completed) * args.num_envs * rl.num_steps_per_env,
            'seconds_per_update': sum(recent) / len(recent),
            'elapsed_seconds': time.time() - started,
            'losses': {k: float(v) for k, v in values['loss_dict'].items()},
        })
        if completed in (1, 5, 10, 25, 50):
            runner.save('')

    runner.logger.log = log
    runner.learn(num_learning_iterations=args.updates, init_at_random_ep_len=True)
    status = json.loads((out / 'status.json').read_text())
    write_json(out / 'status.json', {**status, 'state': 'complete', 'updated_at': time.time()})
    env.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--body', choices=['g1', 'spot', 'spot_arm'], required=True,
                   help='Explicit physical body; Spot is arm-free and uses its own policy')
    p.add_argument('--num-envs', type=int, default=512)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--device', default='cuda:0', help='Explicit simulation and PPO device; use cpu for small diagnostic runs')
    p.add_argument('--critic-observations', choices=['actor', 'native'],
                   help='Native task critic inputs by default; actor mode is retained for explicit historical comparisons')
    p.add_argument('--action-limit', type=float,
                   help='Applied command bound saved for replay; defaults to 5 for G1 and native task setting for Spot')
    p.add_argument('--action-rate-warmup', action='store_true',
                   help='Diagnostic profile: ramp action-change penalty from10percent to native weight during locomotion')
    p.add_argument('--failure-cost', type=float,
                   help='Optional one-time cost for non-timeout episode termination')
    p.add_argument('--budgets', type=int, nargs=3, default=[3000, 6000, 4000])
    p.add_argument('--stage', choices=['locomotion', 'terrain', 'arm'])
    p.add_argument('--updates', type=int)
    p.add_argument('--offset', type=int, default=0)
    p.add_argument('--parent', type=Path)
    p.add_argument('--initial-state', type=Path,
                   help='Reuse only verified random update-zero weights for a controlled comparison')
    p.add_argument('--actor-normalization', action='store_true',
                   help='Use native PPO actor normalization for a fresh-policy comparison')
    p.add_argument('--forward-locomotion', action='store_true',
                   help='Private comparison: straight 0.3–0.6 m/s walking in phase I, native commands thereafter')
    args = p.parse_args()
    args.critic_observations = resolve_critic_observations(
        args.critic_observations, args.parent, args.body)
    if args.body == 'g1' and args.action_limit is None:
        # The upstream task documents this bound but leaves clip_actions unset.
        # Apply it to new training without relying on a caller to opt in.
        args.action_limit = 5.
    args.output = args.output.resolve()
    public_root = Path(__file__).resolve().parents[1]
    if args.output.is_relative_to(public_root):
        p.error('Training outputs must be outside the published website')
    if args.initial_state:
        if args.parent or args.offset or (args.stage and args.stage != 'locomotion'):
            p.error('A shared random initial state is only valid at the start of locomotion')
        args.initial_state = args.initial_state.resolve()
        validate_random_initial_state(args.initial_state, args.body)
    if args.stage:
        if args.body != 'spot_arm' and args.stage == 'arm':
            p.error('Only Spot + arm has an arm adaptation stage')
        train(args)
        return
    args.output.mkdir(parents=True, exist_ok=True)
    if (args.output / 'plan.json').exists():
        p.error('Output already contains a run; choose a new directory, do not overwrite it')
    stages = list(zip(['locomotion', 'terrain', 'arm'], args.budgets))
    if args.body != 'spot_arm':
        stages = stages[:2]
    write_json(args.output / 'plan.json', {
        'stages': [{'name': name, 'updates': n} for name, n in stages],
        'body': args.body, 'seed': args.seed, 'num_envs': args.num_envs, 'initialization': 'random',
        'critic_observations': args.critic_observations,
        'action_limit': args.action_limit,
        'action_rate_warmup': args.action_rate_warmup,
        'failure_cost': args.failure_cost,
        'actor_normalization': args.actor_normalization,
        'forward_locomotion': args.forward_locomotion,
        'initial_state_sha256': digest(args.initial_state) if args.initial_state else None,
        'purpose': 'New progressive controller reproduction from random initialization',
        'script_sha256': digest(__file__), 'started_at': time.time(),
    })
    parent, offset = None, 0
    for stage, updates in stages:
        command = [sys.executable, str(Path(__file__).resolve()), '--output', str(args.output),
                   '--body', args.body, '--stage', stage, '--updates', str(updates), '--offset', str(offset),
                   '--num-envs', str(args.num_envs), '--seed', str(args.seed), '--device', args.device,
                   '--critic-observations', args.critic_observations]
        if parent:
            command += ['--parent', str(parent)]
        elif args.initial_state:
            command += ['--initial-state', str(args.initial_state)]
        if args.action_limit is not None:
            command += ['--action-limit', str(args.action_limit)]
        if args.action_rate_warmup:
            command += ['--action-rate-warmup']
        if args.failure_cost is not None:
            command += ['--failure-cost', str(args.failure_cost)]
        if args.actor_normalization:
            command += ['--actor-normalization']
        if args.forward_locomotion:
            command += ['--forward-locomotion']
        try:
            with (args.output / f'{stage}.log').open('w') as log:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
        except subprocess.CalledProcessError as error:
            stage_dir = args.output / stage
            stage_dir.mkdir(exist_ok=True)
            status_path = stage_dir / 'status.json'
            status = json.loads(status_path.read_text()) if status_path.exists() else {}
            write_json(status_path, {**status, 'state': 'failed', 'updated_at': time.time(),
                                    'exit_code': error.returncode, 'target_updates': updates})
            raise
        latest = json.loads((args.output / stage / 'latest.json').read_text())
        assert latest['completed_updates'] == updates
        parent = Path(latest['checkpoint'])
        offset += updates
    write_json(args.output / 'complete.json', {'checkpoint': str(parent), 'updates': offset,
                                             'completed_at': time.time()})


if __name__ == '__main__':
    main()
