"""Exercise the training runner's real PPO critic on CPU, without a simulator."""
from dataclasses import asdict
from types import SimpleNamespace
import torch
from tensordict import TensorDict
import mjlab.tasks
from mjlab.tasks.registry import load_rl_cfg
from train_progressive_policy import training_runner, configure_observation_groups

torch.set_num_threads(2)
task = 'Mjlab-Velocity-BlindStairs-Unitree-G1'
for mode, width, group in [('actor', 99, 'actor'), ('native', 298, 'critic')]:
    cfg = configure_observation_groups(load_rl_cfg(task), mode)
    assert cfg.obs_groups['critic'] == (group,), 'Requested critic inputs were discarded'
    env = SimpleNamespace(num_envs=2, num_actions=29, cfg={}, device='cpu')
    env.get_observations = lambda: TensorDict({'actor': torch.zeros(2, 99),
                                              'critic': torch.zeros(2, 298)}, batch_size=[2])
    runner = training_runner(task)(env, asdict(cfg), device='cpu')
    assert runner.alg.critic.mlp[0].in_features == width
    normalizer = runner.alg.critic.obs_normalizer
    normalizer.eval()
    actual = normalizer(torch.full((2, width), 1000.0))
    assert torch.isfinite(actual).all()
    assert actual.abs().max() <= 10, f'Registered critic protection missing: normalized input {actual.abs().max().item()}'
    assert isinstance(runner.alg.actor.obs_normalizer, torch.nn.Identity), 'Keep the deployed raw-observation actor contract'
    print(f'PASS actual G1 runner: {mode} critic has {width} inputs and registered normalization protection')

# The Spot + arm task also supplies privileged terrain observations. Preserve
# those inputs while keeping the deployed policy's 84-input, 12-action contract.
task = 'Mjlab-Velocity-Mixed-Spot'
for mode, width, group in [('actor', 84, 'actor'), ('native', 271, 'critic')]:
    cfg = configure_observation_groups(load_rl_cfg(task), mode)
    assert cfg.obs_groups['critic'] == (group,)
    env = SimpleNamespace(num_envs=2, num_actions=12, cfg={}, device='cpu')
    env.get_observations = lambda: TensorDict({'actor': torch.zeros(2, 84),
                                              'critic': torch.zeros(2, 271)}, batch_size=[2])
    runner = training_runner(task)(env, asdict(cfg), device='cpu')
    assert runner.alg.critic.mlp[0].in_features == width
    assert runner.alg.actor.mlp[0].in_features == 84
    assert runner.alg.actor.mlp[-1].out_features == 12
    assert isinstance(runner.alg.actor.obs_normalizer, torch.nn.Identity)
    assert not isinstance(runner.alg.critic.obs_normalizer, torch.nn.Identity)
    print(f'PASS actual Spot + arm runner: {mode} critic {width}, raw actor 84, actions 12')
