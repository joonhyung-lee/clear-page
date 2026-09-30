"""Train a traceable Spot curriculum from random initialization, privately.

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


def train(args):
    # Set before task registration evaluates environment-dependent curricula.
    os.environ.update(WANDB_MODE='disabled', MJLAB_SPOT_ARM_FOLLOW='1',
                      MJLAB_SPOT_ARM_JITTER='0', MJLAB_SPOT_ARM_BLEND='0',
                      MJLAB_SPOT_TORSO_STANCE='1',
                      MJLAB_SPOT_ARM_CURRICULUM=str(int(args.stage == 'arm')),
                      MJLAB_SPOT_ARM_SPAN=str(int(args.stage == 'arm')))
    from dataclasses import asdict
    import numpy as np
    import random
    import torch
    from mjlab.envs import ManagerBasedRlEnv
    from mjlab.rl import MjlabOnPolicyRunner, RslRlVecEnvWrapper
    from mjlab.tasks.registry import load_env_cfg, load_rl_cfg
    from mjlab.utils.os import dump_yaml
    from mjlab.utils.torch import configure_torch_backends

    torch.set_num_threads(4)
    configure_torch_backends()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    out = args.output / args.stage
    out.mkdir(parents=True, exist_ok=True)
    task = 'Mjlab-Velocity-Mixed-Spot'
    cfg = load_env_cfg(task)
    if args.body == 'spot':
        from bare_spot import configure
        cfg = configure(cfg)
    cfg.seed = args.seed
    cfg.scene.num_envs = args.num_envs
    cfg.sim.nconmax = 96
    if args.stage == 'locomotion':
        cfg.scene.terrain.terrain_type = 'plane'
        cfg.scene.terrain.terrain_generator = None
        cfg.curriculum.pop('terrain_levels', None)
    else:
        cfg.scene.terrain.terrain_generator.num_rows = 8
        cfg.scene.terrain.terrain_generator.num_cols = 10
        cfg.scene.terrain.max_init_terrain_level = 0
    rl = load_rl_cfg(task)
    rl.seed = args.seed
    rl.logger = 'tensorboard'
    rl.upload_model = False
    # A common critic input preserves optimizer/critic compatibility across
    # plane and terrain environments (48 inputs for Spot, 84 for Spot + arm).
    rl.obs_groups['critic'] = ('actor',)
    rl.save_interval = 100
    dump_yaml(out / 'environment.yaml', asdict(cfg))
    dump_yaml(out / 'agent.yaml', asdict(rl))
    env = ManagerBasedRlEnv(cfg=cfg, device='cuda:0')
    if args.body == 'spot':
        from bare_spot import verify_model
        write_json(out / 'body.json', verify_model(env.sim.mj_model))
    wrapped = RslRlVecEnvWrapper(env, clip_actions=rl.clip_actions)
    started = time.time()
    durations = []
    parent_hash = digest(args.parent) if args.parent else None

    class RecordedRunner(MjlabOnPolicyRunner):
        def save(self, path, infos=None):
            completed = self.current_learning_iteration + 1
            target = out / f'update_{completed:06d}.pt'
            metadata = dict(body=args.body, stage=args.stage, completed_updates=completed,
                            cumulative_updates=args.offset + completed,
                            parent_sha256=parent_hash, seed=args.seed,
                            origin='random_initialization', num_envs=args.num_envs)
            super().save(str(target), {**(infos or {}), 'curriculum': metadata})
            write_json(out / 'latest.json', {**metadata, 'checkpoint': str(target),
                                           'sha256': digest(target)})

    runner = RecordedRunner(wrapped, asdict(rl), str(out), device='cuda:0')
    if args.parent:
        runner.load(str(args.parent), map_location='cuda:0')
        # Loop counter is local to this stage; cumulative updates are explicit.
        runner.current_learning_iteration = 0
    elif args.stage != 'locomotion':
        raise ValueError('Later stages require the preceding stage checkpoint')
    initial = out / 'update_000000.pt'
    MjlabOnPolicyRunner.save(runner, str(initial), {'curriculum': {
        'body': args.body, 'stage': args.stage, 'completed_updates': 0,
        'cumulative_updates': args.offset, 'parent_sha256': parent_hash,
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
    p.add_argument('--body', choices=['spot', 'spot_arm'], required=True,
                   help='Explicit physical body; Spot is arm-free and uses its own policy')
    p.add_argument('--num-envs', type=int, default=512)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--budgets', type=int, nargs=3, default=[3000, 6000, 4000])
    p.add_argument('--stage', choices=['locomotion', 'terrain', 'arm'])
    p.add_argument('--updates', type=int)
    p.add_argument('--offset', type=int, default=0)
    p.add_argument('--parent', type=Path)
    args = p.parse_args()
    args.output = args.output.resolve()
    public_root = Path(__file__).resolve().parents[1]
    if args.output.is_relative_to(public_root):
        p.error('Training outputs must be outside the published website')
    if args.stage:
        if args.body == 'spot' and args.stage == 'arm':
            p.error('Bare Spot has no arm adaptation stage')
        train(args)
        return
    args.output.mkdir(parents=True, exist_ok=True)
    if (args.output / 'plan.json').exists():
        p.error('Output already contains a run; choose a new directory, do not overwrite it')
    stages = list(zip(['locomotion', 'terrain', 'arm'], args.budgets))
    if args.body == 'spot':
        stages = stages[:2]
    write_json(args.output / 'plan.json', {
        'stages': [{'name': name, 'updates': n} for name, n in stages],
        'body': args.body, 'seed': args.seed, 'num_envs': args.num_envs, 'initialization': 'random',
        'purpose': 'New stagewise controller training reproduction',
        'script_sha256': digest(__file__), 'started_at': time.time(),
    })
    parent, offset = None, 0
    for stage, updates in stages:
        command = [sys.executable, str(Path(__file__).resolve()), '--output', str(args.output),
                   '--body', args.body, '--stage', stage, '--updates', str(updates), '--offset', str(offset),
                   '--num-envs', str(args.num_envs), '--seed', str(args.seed)]
        if parent:
            command += ['--parent', str(parent)]
        with (args.output / f'{stage}.log').open('w') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
        latest = json.loads((args.output / stage / 'latest.json').read_text())
        assert latest['completed_updates'] == updates
        parent = Path(latest['checkpoint'])
        offset += updates
    write_json(args.output / 'complete.json', {'checkpoint': str(parent), 'updates': offset,
                                             'completed_at': time.time()})


if __name__ == '__main__':
    main()
